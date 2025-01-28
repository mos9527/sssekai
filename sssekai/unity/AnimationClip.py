from collections import defaultdict
from typing import Dict, List, Generator
from bisect import bisect_right
from dataclasses import dataclass, field
from UnityPy.enums import ClassIDType
from UnityPy.classes import (
    AnimationClip,
    StreamedClip,
    GenericBinding,
)
from UnityPy.classes.math import Vector3f as Vector3, Quaternionf as Quaternion
from UnityPy.streams.EndianBinaryReader import EndianBinaryReader
from logging import getLogger
from enum import IntEnum

logger = getLogger(__name__)


def vec3_quat_as_floats(value):
    if type(value) == Vector3:
        return [value.x, value.y, value.z]
    elif type(value) == Quaternion:
        return [value.x, value.y, value.z, value.w]
    else:
        return [value]


def vec3_quat_from_floats(*values):
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


class _StreamedClipKey:
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
    coeff: List[int]

    time: float
    prev: "_StreamedClipKey" = None

    def __init__(self, reader: EndianBinaryReader, time: float):
        self.index = reader.read_int()
        self.coeff = reader.read_float_array(4)
        self.time = time

    inSlope: float = float("inf")

    @property
    def outSlope(self):
        return self.coeff[2]

    @property
    def value(self):
        return self.coeff[3]

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


class _StreamedClipFrame:
    time: float
    keys: List[_StreamedClipKey]

    def __init__(self, reader: EndianBinaryReader):
        self.time = reader.read_float()
        self.keys = [
            _StreamedClipKey(reader, self.time) for _ in range(reader.read_int())
        ]


def _read_streamed_clip_frames(clip: StreamedClip) -> List[_StreamedClipFrame]:
    frames: List[_StreamedClipFrame] = []
    buffer = b"".join(val.to_bytes(4, "big") for val in clip.data)
    reader = EndianBinaryReader(buffer)
    while reader.Position < reader.Length:
        frames.append(_StreamedClipFrame(reader))
    for frameNum in range(2, len(frames) - 1):
        frame = frames[frameNum]
        for curveKey in frame.keys:
            for i in range(frameNum - 1, 0, -1):
                preFrame = frames[i]
                preCurveKey = next(
                    filter(lambda x: x.index == curveKey.index, preFrame.keys), None
                )
                if preCurveKey:
                    curveKey.inSlope = preCurveKey.calc_next_in_slope(
                        frame.time - preFrame.time, curveKey
                    )
                    break
    return frames


@dataclass
class KeyFrame:
    time: float
    typeID: int
    value: float | Vector3 | Quaternion = 0

    isDense: bool = False
    isConstant: bool = False
    # Used for Hermite curves
    inSlope: float | Vector3 | Quaternion = 0
    outSlope: float | Vector3 | Quaternion = 0

    prev: "KeyFrame" = None
    next: "KeyFrame" = None

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
    def interpolation_segment(lhs: "KeyFrame", rhs: "KeyFrame") -> List[Interpolation]:
        """Interpolation of the segment between lhs and rhs"""
        EPS = 1e-5
        rhs = lhs.next
        if not rhs:
            return [Interpolation.Constant] * len(vec3_quat_as_floats(lhs.value))
        lhsInSlopes = vec3_quat_as_floats(lhs.inSlope)
        lhsOutSlopes = vec3_quat_as_floats(lhs.outSlope)
        rhsInSlopes = vec3_quat_as_floats(rhs.inSlope)
        rhsOutSlopes = vec3_quat_as_floats(rhs.outSlope)
        ipo = [Interpolation.Hermite] * len(lhsOutSlopes)
        if lhs.isConstant or not rhs:
            ipo = [Interpolation.Constant] * len(lhsOutSlopes)
        elif lhs.isDense:
            ipo = [Interpolation.Linear] * len(lhsOutSlopes)
        else:
            for i, (lhsInSlope, lhsOutSlope, rhsInSlope, rhsOutSlope) in enumerate(
                zip(lhsInSlopes, lhsOutSlopes, rhsInSlopes, rhsOutSlopes)
            ):
                if any((x == float("inf") for x in (lhsOutSlope, rhsInSlope))):
                    ipo[i] = Interpolation.Stepped
                elif abs(rhsInSlope - lhsOutSlope) < EPS:
                    ipo[i] = Interpolation.Linear
                else:
                    ipo[i] = Interpolation.Hermite
        return ipo

    @staticmethod
    def interpolate(
        t, lhs: "KeyFrame", rhs: "KeyFrame", unit_t: bool = False
    ) -> float | Vector3 | Quaternion:
        if not rhs:
            return lhs.value
        dx = rhs.time - lhs.time
        if not unit_t:
            t -= lhs.time
            t /= dx  # Normalized to [0,1]
        lhsValues = vec3_quat_as_floats(lhs.value)
        rhsValues = vec3_quat_as_floats(rhs.value)
        lhsInSlopes = vec3_quat_as_floats(lhs.inSlope)
        lhsOutSlopes = vec3_quat_as_floats(lhs.outSlope)
        rhsInSlopes = vec3_quat_as_floats(rhs.inSlope)
        rhsOutSlopes = vec3_quat_as_floats(rhs.outSlope)
        interpolations = KeyFrame.interpolation_segment(lhs, rhs)
        result = [0] * len(lhsValues)
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
                lhsValues,
                rhsValues,
                lhsInSlopes,
                lhsOutSlopes,
                rhsInSlopes,
                rhsOutSlopes,
                interpolations,
            )
        ):
            match interpolation:
                case Interpolation.Hermite:
                    result[i] = KeyFrame.interpolate_cubic_hermite_unit(
                        t, lhsValue, lhsOutSlope * dx, rhsInSlope * dx, rhsValue
                    )
                case Interpolation.Linear:
                    # Lerp doesn't seem to be explicitly used as a cubic hermite curve when correctly
                    # setup can produce results of a linear interpolation
                    # However this is necessary for Dense curves. So we'll keep it here.
                    result[i] = KeyFrame.interpolate_linear_unit(t, lhsValue, rhsValue)
                    # result[i] = KeyFrame.interpolate_cubic_hermite_unit(
                    #     t, lhsValue, lhsOutSlope * dx, rhsInSlope * dx, rhsValue
                    # )
                case Interpolation.Stepped:
                    result[i] = KeyFrame.interpolate_stepped(t, lhsValue, rhsValue)
                case Interpolation.Constant:
                    result[i] = lhsValue
        return result[0] if len(result) == 1 else vec3_quat_from_floats(*result)


@dataclass
class Curve:
    Binding: GenericBinding
    Data: List[KeyFrame] = field(default_factory=list)

    def evaluate(self, t: float) -> float | Vector3 | Quaternion:
        lhs = bisect_right(self.Data, t, key=lambda x: x.time) - 1
        lhs = max(lhs, 0)
        lhs = self.Data[lhs]
        rhs = lhs.next
        return KeyFrame.interpolate(t, lhs, rhs)

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
class Animation:
    Name: str
    Duration: float
    SampleRate: float
    # Dict[internal hash, Curve]
    RawCurves: Dict[int, Curve] = field(default_factory=dict)
    # Curves[Attribute][Path Hash] = Curve
    Curves: Dict[int, Dict[float, Curve]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    # CurvesT[Path Hash][Attribute] = Curve
    CurvesT: Dict[int, Dict[float, Curve]] = field(
        default_factory=lambda: defaultdict(dict)
    )

    @staticmethod
    def hash_of(binding: GenericBinding):
        return hash((binding.path, binding.attribute))

    def get_curve(self, binding: GenericBinding):
        hs = self.hash_of(binding)
        if not hs in self.RawCurves:
            curve = Curve(binding)
            # i love refcounting
            self.RawCurves[hs] = curve
            self.Curves[binding.attribute][binding.path] = curve
            self.CurvesT[binding.path][binding.attribute] = curve
            return curve
        else:
            return self.RawCurves[hs]

    @property
    def FloatCurves(self):
        return filter(lambda c: not c.is_transform_curve, self.RawCurves.values())

    @property
    def TransformCurves(self):
        return filter(lambda c: c.is_transform_curve, self.RawCurves.values())


def _read_clip_keyframe(
    time: float,
    binding: GenericBinding,
    keys: Generator[_StreamedClipKey | KeyFrame, None, None],
) -> KeyFrame:
    result = KeyFrame(time, binding.typeID)
    if binding.typeID == ClassIDType.Transform:
        dimension = kAttributeSizeof(binding.attribute)
        values, outSlopes, inSlopes = [0] * dimension, [0] * dimension, [0] * dimension
        for i in range(dimension):
            key = next(keys)
            values[i] = key.value
            outSlopes[i] = key.outSlope
            inSlopes[i] = key.inSlope
        result.value = vec3_quat_from_floats(*values)
        result.outSlope = vec3_quat_from_floats(*outSlopes)
        result.inSlope = vec3_quat_from_floats(*inSlopes)
    else:
        if binding.isIntCurve:
            raise NotImplementedError
        elif binding.isPPtrCurve:
            raise NotImplementedError
        else:
            # Default to float curves
            key = next(keys)
            result.value = key.value
            result.outSlope = key.outSlope
            result.inSlope = key.inSlope
    return result


def read_animation(src: AnimationClip) -> Animation:
    """Reads AnimationClip data and converts it to an Animation object

    Args:
        src (AnimationClip): animationClip

    Returns:
        Animation
    """
    result = Animation(src.m_Name, src.m_MuscleClip.m_StopTime, src.m_SampleRate)
    mClip = src.m_MuscleClip.m_Clip.data
    mClipBinding = src.m_ClipBindingConstant
    mClipBindingCurveSizesPfx = [
        kAttributeSizeof(b.attribute) for b in mClipBinding.genericBindings
    ]
    for i in range(1, len(mClipBindingCurveSizesPfx)):
        mClipBindingCurveSizesPfx[i] += mClipBindingCurveSizesPfx[i - 1]

    def mClipFindBinding(cur) -> GenericBinding:
        index = bisect_right(mClipBindingCurveSizesPfx, cur)
        index = max(index, 0)
        index = min(index, len(mClipBinding.genericBindings) - 1)
        return mClipBinding.genericBindings[index]

    def mClipGetNextCurve(cur, keys) -> int:
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
    mStreamClipFrames = _read_streamed_clip_frames(mClip.m_StreamedClip)
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
            curve = result.get_curve(binding)
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
                yield KeyFrame(
                    time,
                    binding.typeID,
                    m_DenseClip.m_SampleArray[frameOffset + currIndex],
                )

        __keygen_g = __keygen()
        while curveIndex < m_DenseClip.m_CurveCount:
            binding = mClipFindBinding(curveOffset + curveIndex)
            curve = result.get_curve(binding)
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
                yield KeyFrame(
                    time,
                    binding.typeID,
                    m_ConstantClip.data[currIndex],
                )

        __keygen_g = __keygen()
        while curveIndex < len(m_ConstantClip.data):
            binding = mClipFindBinding(curveOffset + curveIndex)
            curve = result.get_curve(binding)
            key = _read_clip_keyframe(time, binding, __keygen_g)
            key.isConstant = True
            curve.Data.append(key)
            binding = mClipFindBinding(curveOffset + curveIndex)
        time = src.m_MuscleClip.m_StopTime

    for curve in result.RawCurves.values():
        for i in range(1, len(curve.Data)):
            curve.Data[i].prev = curve.Data[i - 1]
            curve.Data[i - 1].next = curve.Data[i]
    return result
