import struct
from collections import defaultdict
from typing import Dict, List, Generator
from bisect import bisect_left
from dataclasses import dataclass, field
from UnityPy.enums import ClassIDType
from UnityPy.classes import (
    AnimationClip,
    StreamedClip,
    GenericBinding,
    # ---
    Vector3Curve,
    QuaternionCurve,
    FloatCurve,
)
from UnityPy.classes.math import Vector3f as Vector3, Quaternionf as Quaternion
from UnityPy.streams.EndianBinaryReader import EndianBinaryReader
from logging import getLogger
from enum import IntEnum
from zlib import crc32

logger = getLogger(__name__)


def num_floats(value):
    if type(value) == Vector3:
        return 3
    elif type(value) == Quaternion:
        return 4
    else:
        return 1


def as_floats(value):
    if type(value) == Vector3:
        return [value.x, value.y, value.z]
    elif type(value) == Quaternion:
        return [value.x, value.y, value.z, value.w]
    else:
        return [value]


def from_floats(*values):
    if len(values) == 1:
        return values[0]
    elif len(values) == 3:
        return Vector3(*values)
    else:
        return Quaternion(*values)


# GenericBinding Attributes
kBindTransformPosition = 1
kBindTransformRotation = 2
kBindTransformScale = 3
kBindTransformEuler = 4
# ---
kAttributeSizeof = lambda x: {
    kBindTransformPosition: 3,
    kBindTransformRotation: 4,  # Quaternion
    kBindTransformScale: 3,
    kBindTransformEuler: 3,
}.get(x, 1)


# Interpolation Types
class Interpolation(IntEnum):
    Hermite = 1
    Linear = 2
    Stepped = 3
    Constant = 4


class StreamedClipKey:
    """
    dx = rhs.time - lhs.time;
    dx = max(dx, 0.0001F);
    dy = rhs.value - lhs.value;
    length = 1.0F / (dx * dx);

    m1 = lhs.outSlope;
    m2 = rhs.inSlope;
    d1 = m1 * dx;
    d2 = m2 * dx;

    cache.coeff[0] = (d1 + d2 - dy - dy) * length / dx;
    cache.coeff[1] = (dy + dy + dy - d1 - d1 - d2) * length;
    cache.coeff[2] = m1;
    cache.coeff[3] = lhs.value;
    """

    index: int

    coeff: List[float]
    int_coeff: List[int]

    raw_coeff: bytes

    time: float
    prev: "StreamedClipKey" = None

    def __init__(self, reader: EndianBinaryReader, time: float):
        self.index = reader.read_int()
        endian = reader.endian

        self.raw_coeff = reader.read_bytes(4 * 4)
        self.coeff = struct.unpack(endian + "4f", self.raw_coeff)
        self.int_coeff = struct.unpack(endian + "4i", self.raw_coeff)

        self.time = time

    inSlope: float = float("inf")

    @property
    def outSlope(self):
        return self.coeff[2]

    @property
    def value(self):
        return self.coeff[3]

    @property
    def int_value(self):
        return self.int_coeff[3]

    def calc_next_in_slope(self, dx: float, rhs):
        # Stepped
        if self.coeff[0] == 0 and self.coeff[1] == 0 and self.coeff[2] == 0:
            return float("inf")

        dx = max(dx, 0.0001)
        dy = rhs.value - self.value
        length = 1.0 / (dx * dx)
        d1 = self.outSlope * dx
        d2 = dy + dy + dy - d1 - d1 - self.coeff[1] / length
        return d2 / dx


class StreamedClipFrame:
    time: float
    keys: List[StreamedClipKey]

    def __init__(self, reader: EndianBinaryReader):
        self.time = reader.read_float()
        self.keys = [
            StreamedClipKey(reader, self.time) for _ in range(reader.read_int())
        ]


def read_streamed_clip_frames(clip: StreamedClip) -> List[StreamedClipFrame]:  # O(n)
    frames: List[StreamedClipFrame] = []
    buffer = b"".join(val.to_bytes(4, "big") for val in clip.data)
    reader = EndianBinaryReader(buffer)
    while reader.Position < reader.Length:
        frames.append(StreamedClipFrame(reader))
    preKeys: Dict[int, StreamedClipKey] = dict()
    for frame in frames:
        for curveKey in frame.keys:
            preKey = preKeys.get(curveKey.index, None)
            if preKey:
                curveKey.inSlope = preKey.calc_next_in_slope(
                    frame.time - preKey.time, curveKey
                )
            preKeys[curveKey.index] = curveKey
    return frames


@dataclass
class KeyframeHelper:
    """Custom KeyFrame container/lookup type analogus to Unity's Keyframe
    whilst providing dynamic type support (float/int/Euler/Vector/Quaternion) and interpolation
    """

    time: float
    typeID: int
    value: float | Vector3 | Quaternion = 0

    isDense: bool = False
    isConstant: bool = False
    # Used for Hermite curves
    inSlope: float | Vector3 | Quaternion = 0
    outSlope: float | Vector3 | Quaternion = 0

    prev: "KeyframeHelper" = None
    next: "KeyframeHelper" = None

    endian: str = ">"

    @property
    def int_value(self):
        assert type(self.value) == float
        b = struct.pack("<f", self.value)
        return struct.unpack(self.endian + "i", b)[0]

    def __repr__(self):
        return f"KeyFrame({self.time}, {self.value}, inSlope={self.inSlope}, outSlope={self.outSlope})"

    @staticmethod
    def interpolate_cubic_hermite_unit(t, p0, m0, m1, p1):
        # https://en.wikipedia.org/wiki/Cubic_Hermite_spline
        t2 = t * t
        t3 = t2 * t
        a = 2 * t3 - 3 * t2 + 1
        b = t3 - 2 * t2 + t
        c = -2 * t3 + 3 * t2
        d = t3 - t2
        return a * p0 + b * m0 + c * p1 + d * m1

    @staticmethod
    def interpolate_linear_unit(t, p0, p1):
        return p0 + t * (p1 - p0)

    @staticmethod
    def interpolate_stepped(t, p0, p1):
        return p0

    @staticmethod
    def interpolation_segment(
        lhs: "KeyframeHelper", rhs: "KeyframeHelper"
    ) -> List[Interpolation]:
        """Interpolation of the segment between lhs and rhs"""
        if lhs.isDense:
            ipo = [Interpolation.Linear] * num_floats(lhs.value)
        elif lhs.isConstant or not rhs:
            ipo = [Interpolation.Constant] * num_floats(lhs.value)
        else:
            ipo = [Interpolation.Hermite] * num_floats(lhs.value)
            for i, (lhsInSlope, lhsOutSlope, rhsInSlope, rhsOutSlope) in enumerate(
                zip(
                    as_floats(lhs.inSlope),
                    as_floats(lhs.outSlope),
                    as_floats(rhs.inSlope),
                    as_floats(rhs.outSlope),
                )
            ):
                if any((x == float("inf") for x in (lhsOutSlope, rhsInSlope))):
                    ipo[i] = Interpolation.Stepped
                else:
                    ipo[i] = Interpolation.Hermite
        return ipo

    @staticmethod
    def interpolate(
        t, lhs: "KeyframeHelper", rhs: "KeyframeHelper", unit_t: bool = False
    ) -> float | Vector3 | Quaternion:
        EPS = 1e-8
        dx = rhs.time - lhs.time        
        if not rhs or dx <= EPS:
            return lhs.value
        if not unit_t:
            t -= lhs.time
            t /= dx  # Normalized to [0,1]
        result = [0] * num_floats(lhs.value)
        for i, (
            lhsValue,
            rhsValue,
            lhsInSlope,
            lhsOutSlope,
            rhsInSlope,
            rhsOutSlope,
            interpolation,
        ) in enumerate(
            zip(
                as_floats(lhs.value),
                as_floats(rhs.value),
                as_floats(lhs.inSlope),
                as_floats(lhs.outSlope),
                as_floats(rhs.inSlope),
                as_floats(rhs.outSlope),
                KeyframeHelper.interpolation_segment(lhs, rhs),
            )
        ):
            match interpolation:
                case Interpolation.Hermite:
                    result[i] = KeyframeHelper.interpolate_cubic_hermite_unit(
                        t, lhsValue, lhsOutSlope * dx, rhsInSlope * dx, rhsValue
                    )
                case Interpolation.Linear:
                    # Lerp doesn't seem to be explicitly used as a cubic hermite curve when correctly
                    # setup can produce results of a linear interpolation
                    # However this is necessary for Dense curves. So we'll keep it here.
                    result[i] = KeyframeHelper.interpolate_linear_unit(
                        t, lhsValue, rhsValue
                    )
                    # result[i] = KeyFrame.interpolate_cubic_hermite_unit(
                    #     t, lhsValue, lhsOutSlope * dx, rhsInSlope * dx, rhsValue
                    # )
                case Interpolation.Stepped:
                    result[i] = KeyframeHelper.interpolate_stepped(
                        t, lhsValue, rhsValue
                    )
                case Interpolation.Constant:
                    result[i] = lhsValue
        return result[0] if len(result) == 1 else from_floats(*result)


def _read_clip_keyframe(
    time: float,
    binding: GenericBinding,
    keys: Generator[StreamedClipKey | KeyframeHelper, None, None],
) -> KeyframeHelper:
    result = KeyframeHelper(time, binding.typeID)
    if binding.typeID == ClassIDType.Transform:
        dimension = kAttributeSizeof(binding.attribute)
        values, outSlopes, inSlopes = [0] * dimension, [0] * dimension, [0] * dimension
        for i in range(dimension):
            key = next(keys)
            values[i] = key.value
            outSlopes[i] = key.outSlope
            inSlopes[i] = key.inSlope
        result.value = from_floats(*values)
        result.outSlope = from_floats(*outSlopes)
        result.inSlope = from_floats(*inSlopes)
    else:
        if binding.isIntCurve:
            key = next(keys)
            result.value = key.int_value
            # Can only be stepped
            result.outSlope = float("inf")
            result.inSlope = float("inf")
        elif binding.isPPtrCurve:
            # !! TODO PPtr curves not yet implemented
            pass
        else:
            # Default to float curves
            key = next(keys)
            result.value = key.value
            result.outSlope = key.outSlope
            result.inSlope = key.inSlope
    return result


@dataclass
class CurveHelper:
    """Custom Curve container/lookup type analogus to Unity's AnimationCurve

    Note:
        - Properties here aren't prefixed with `m_` like in Unity's AnimationClip
        - For more information, read docs on `sssekai.unity.KeyFrame`
    """

    Binding: GenericBinding
    Data: List[KeyframeHelper] = field(default_factory=list)

    def evaluate(self, t: float) -> float | Vector3 | Quaternion:  # O(log n)
        lhs = bisect_left(self.Data, t, key=lambda x: x.time)
        lhs = min(max(lhs, 0), len(self.Data) - 1)
        rhs = min(lhs + 1, len(self.Data) - 1)
        return KeyframeHelper.interpolate(t, self.Data[lhs], self.Data[rhs])

    def resample_dense(self, times: List[float]) -> "CurveHelper": # O(n)
        """Resamples the curve at given times **as a Dense curve**, losing all tangent information.

        This guarantees accuracy when played back at a constant sample rate at the cost of space
        and interpolation information.

        Args:
            times (List[float]): Times to sample the curve at

        Returns:
            CurveHelper: A new CurveHelper with the sampled values
        """
        lhs = 0
        data = [None] * len(times)
        for i, t in enumerate(times):
            while lhs + 1 < len(self.Data) and self.Data[lhs + 1].time < t:
                lhs += 1            
            lhs = min(max(lhs - 1, 0), len(self.Data) - 1)
            rhs = min(lhs + 1, len(self.Data) - 1)
            data[i] = KeyframeHelper.interpolate(t, self.Data[lhs], self.Data[rhs])
        slope = from_floats(*([0] * num_floats(data[0])))
        data = [KeyframeHelper(t, self.Binding.typeID, value, isDense=True, inSlope=slope, outSlope=slope) for t, value in zip(times, data)]
        for i in range(1, len(data)):
            data[i].prev = data[i - 1]
            data[i - 1].next = data[i]
        return CurveHelper(self.Binding, data)

    @property
    def Duration(self):
        return self.Data[-1].time - self.Data[0].time

    @property
    def Path(self):
        return self.Binding.path

    @property
    def Attribute(self):
        return self.Binding.attribute

    @property
    def is_transform_curve(self):
        return self.Binding.typeID == ClassIDType.Transform


@dataclass
class AnimationHelper:
    """Custom Animation container/lookup type analogus to Unity's AnimationClip

    Note:
        - Properties here aren't prefixed with `m_` like in Unity's AnimationClip
        - Mapping of functionality isn't 1:1 with Unity's AnimationClip since
          there's no access to post-build clip data. Everything here is ready for use.
        - For more information, read docs on `sssekai.unity.Curve` and `sssekai.unity.KeyFrame`
    """

    Name: str
    Duration: float
    SampleRate: float
    # Dict[internal hash, Curve]
    RawCurves: Dict[int, CurveHelper] = field(default_factory=dict)
    # Curves[Attribute][Path Hash] = Curve
    Curves: Dict[int, Dict[int, CurveHelper]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    # CurvesT[Path Hash][Attribute] = Curve
    CurvesT: Dict[int, Dict[int, CurveHelper]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    # From path id to the full path
    InvCRC: Dict[int, str] = field(default_factory=dict)

    @staticmethod
    def hash_of(binding: GenericBinding):
        return hash((binding.path, binding.attribute))

    def get_curve(self, binding: GenericBinding):
        hs = self.hash_of(binding)
        if not hs in self.RawCurves:
            curve = CurveHelper(binding)
            # Refcounted
            self.RawCurves[hs] = curve
            self.Curves[binding.attribute][binding.path] = curve
            self.CurvesT[binding.path][binding.attribute] = curve
            return curve
        else:
            return self.RawCurves[hs]

    # Shorthands for Unity-like access
    @property
    def TransformCurves(self):
        return filter(lambda c: c.is_transform_curve, self.RawCurves.values())

    @property
    def FloatCurves(self):
        return filter(lambda c: not c.is_transform_curve, self.RawCurves.values())

    @property
    def PositionCurves(self):
        return self.Curves[kBindTransformPosition].values()

    @property
    def RotationCurves(self):
        return self.Curves[kBindTransformRotation].values()

    @property
    def ScaleCurves(self):
        return self.Curves[kBindTransformScale].values()

    @property
    def EulerCurves(self):
        return self.Curves[kBindTransformEuler].values()

    @property
    def PPtrCurves(self):
        raise NotImplementedError

    def process_legacy(self, src: AnimationClip) -> "AnimationHelper":
        """Reads pre-build AnimationClip data and converts it to an Animation

        NOTE: This only works with Legacy AnimationClips, where the animation data
        is not compacted into a MuscleClip and is instead stored in the AnimationClip itself.

        Note:
            `Animation` in this context is NOT a part of Unity (which coincidentally also has an `Animation` class)
            Read `sssekai.unity.Animation`'s docs for more information

        Args:
            src (AnimationClip): An Unity AnimationClip object

        Returns:
            sssekai.unity.Animation
        """

        def process_curves(
            curves: List[Vector3Curve | QuaternionCurve | FloatCurve], attribute: int
        ):
            for curve in curves:
                binding = GenericBinding(
                    attribute or curve.attribute,
                    None,
                    False,
                    crc32(curve.path.encode("utf-8")),
                    None,
                )
                binding.typeID = ClassIDType.Transform
                self.InvCRC[binding.path] = curve.path
                keyframes = [
                    KeyframeHelper(
                        time=key.time,
                        typeID=binding.typeID,
                        value=key.value,
                        inSlope=key.inSlope,
                        outSlope=key.outSlope,
                    )
                    for key in curve.curve.m_Curve
                ]
                self.get_curve(binding).Data = keyframes
            pass

        process_curves(src.m_PositionCurves, kBindTransformPosition)
        process_curves(src.m_RotationCurves, kBindTransformRotation)
        process_curves(src.m_ScaleCurves, kBindTransformScale)
        process_curves(src.m_EulerCurves, kBindTransformEuler)
        process_curves(src.m_FloatCurves, None)
        # ! TODO: PPtr curves not yet supported
        # process_curves(src.m_PPtrCurves, ClassIDType.PPtr)
        for curve in self.RawCurves.values():
            for i in range(1, len(curve.Data)):
                curve.Data[i].prev = curve.Data[i - 1]
                curve.Data[i - 1].next = curve.Data[i]
        return self

    def process(self, src: AnimationClip) -> "AnimationHelper":
        """Reads post-build AnimationClip data and converts it to an Animation

        Note:
            `Animation` in this context is NOT a part of Unity (which coincidentally also has an `Animation` class)
            Read `sssekai.unity.Animation`'s docs for more information

        Args:
            src (AnimationClip): An Unity AnimationClip object

        Returns:
            sssekai.unity.Animation
        """
        mClip = src.m_MuscleClip.m_Clip.data
        mClipBinding = src.m_ClipBindingConstant
        mClipBindingCurveSizesPfx = [
            kAttributeSizeof(b.attribute) for b in mClipBinding.genericBindings
        ]
        for i in range(1, len(mClipBindingCurveSizesPfx)):
            mClipBindingCurveSizesPfx[i] += mClipBindingCurveSizesPfx[i - 1]

        def mClipFindBinding(cur) -> GenericBinding:  # O(log n)
            index = bisect_right(mClipBindingCurveSizesPfx, cur)
            index = max(index, 0)
            index = min(index, len(mClipBinding.genericBindings) - 1)
            return mClipBinding.genericBindings[index]

        def mClipGetNextCurve(
            cur, keys
        ) -> int:  # O(1) since curve counts are between 1 and 4
            i = cur
            while i < len(keys) and keys[cur].index == keys[i].index:
                i += 1
            return i

        # https://docs.unity3d.com/Manual/class-Animator.html
        # When actually stored post build, the data is *only* stored with Stream, Dense or Constant clips
        # Float, TRS curves will be optimized into these formats and will not be available.

        # StreamClip
        # Animation is stored with Keyframe Reduction
        # Interpolated with Hermite curves
        mStreamClipFrames = read_streamed_clip_frames(mClip.m_StreamedClip)
        for frame in mStreamClipFrames:
            curveIndex = 0

            def __keygen():
                nonlocal curveIndex
                while True:
                    currIndex = curveIndex
                    curveIndex = mClipGetNextCurve(curveIndex, frame.keys)
                    yield frame.keys[currIndex]

            __keygen_g = __keygen()
            while curveIndex < len(frame.keys):
                binding = mClipFindBinding(frame.keys[curveIndex].index)
                curve = self.get_curve(binding)
                key = _read_clip_keyframe(frame.time, binding, __keygen_g)
                curve.Data.append(key)

        # DenseClip
        # Animation is stored as a dense clip
        # Values are to be interpolated linearly
        m_DenseClip = mClip.m_DenseClip
        curveOffset = mClip.m_StreamedClip.curveCount
        for frameIndex in range(0, m_DenseClip.m_FrameCount):
            time = m_DenseClip.m_BeginTime + frameIndex / m_DenseClip.m_SampleRate
            frameOffset = frameIndex * m_DenseClip.m_CurveCount
            curveIndex = 0

            def __keygen():
                nonlocal curveIndex
                while True:
                    currIndex = curveIndex
                    curveIndex += 1
                    yield KeyframeHelper(
                        time,
                        binding.typeID,
                        m_DenseClip.m_SampleArray[frameOffset + currIndex],
                    )

            __keygen_g = __keygen()
            while curveIndex < m_DenseClip.m_CurveCount:
                binding = mClipFindBinding(curveOffset + curveIndex)
                curve = self.get_curve(binding)
                key = _read_clip_keyframe(time, binding, __keygen_g)
                key.isDense = True
                curve.Data.append(key)

        # ConstantClip
        # Unchanging values.
        m_ConstantClip = mClip.m_ConstantClip
        curveOffset = mClip.m_StreamedClip.curveCount + mClip.m_DenseClip.m_CurveCount
        time = 0
        for _ in range(0, 2):  # first and last frame
            curveIndex = 0

            def __keygen():
                nonlocal curveIndex
                while True:
                    currIndex = curveIndex
                    curveIndex += 1
                    yield KeyframeHelper(
                        time,
                        binding.typeID,
                        m_ConstantClip.data[currIndex],
                    )

            __keygen_g = __keygen()
            while curveIndex < len(m_ConstantClip.data):
                binding = mClipFindBinding(curveOffset + curveIndex)
                curve = self.get_curve(binding)
                key = _read_clip_keyframe(time, binding, __keygen_g)
                key.isConstant = True
                curve.Data.append(key)
                binding = mClipFindBinding(curveOffset + curveIndex)
            time = src.m_MuscleClip.m_StopTime

        for curve in self.RawCurves.values():
            for i in range(1, len(curve.Data)):
                curve.Data[i].prev = curve.Data[i - 1]
                curve.Data[i - 1].next = curve.Data[i]
        return self

    @staticmethod
    def from_clip(src: AnimationClip):
        helper = AnimationHelper(
            src.m_Name, src.m_MuscleClip.m_StopTime, src.m_SampleRate
        )
        if src.m_Legacy:
            helper.process_legacy(src)
        else:
            helper.process(src)
        return helper


# Backwards compatibility
Animation = AnimationHelper
KeyFrame = KeyframeHelper
Curve = CurveHelper

vec3_quat_as_floats = as_floats
vec3_quat_from_floats = from_floats
read_animation = AnimationHelper.from_clip
