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

logger = getLogger(__name__)

# GenericBinding Attributes
kBindTransformPosition = 1
kBindTransformRotation = 2
kBindTransformScale = 3
kBindTransformEuler = 4
# -- Reserved since Unity may uses those
kBindFloat = 10001
kBindInt = 10002
kBindPPtr = 1003
# ---
kAttributeSizeof = lambda x: {
    kBindTransformPosition: 3,
    kBindTransformRotation: 4,  # Quaternion
    kBindTransformScale: 3,
    kBindTransformEuler: 3,
}.get(x, 1)

# Interpolation Types
kInterpolateHermite = 1
kInterpolateLinear = 2
kInterpolateStepped = 3
kInterpolateConstant = 4


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
    prev: "_StreamedClipKey"

    def __init__(self, reader: EndianBinaryReader, time: float):
        self.index = reader.read_int()
        self.coeff = reader.read_float_array(4)
        self.time = time

    @property
    def outSlope(self):
        return self.coeff[2]

    @property
    def value(self):
        return self.coeff[3]

    @property
    def inSlope(self):
        if not self.prev:
            return 0
        if self.coeff[0] == 0 and self.coeff[1] == 0 and self.coeff[2] == 0:  # Stepped
            return float("inf")
        lhs, rhs = self.prev, self
        dx = max(rhs.time - lhs.time, 0.0001)
        dy = rhs.value - lhs.value
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
        for i in range(1, len(self.keys)):
            # Used to calculate inSlope
            self.keys[i].prev = self.keys[i - 1]


def _read_streamed_clip_frames(clip: StreamedClip) -> List[_StreamedClipFrame]:
    frames: List[_StreamedClipFrame] = []
    buffer = b"".join(val.to_bytes(4, "big") for val in clip.data)
    reader = EndianBinaryReader(buffer)
    while reader.Position < reader.Length:
        frames.append(_StreamedClipFrame(reader))
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

    @property
    def interpolation(self):
        if self.isConstant:
            return kInterpolateConstant
        if self.isDense:
            return kInterpolateLinear
        if self.inSlope == float("inf") or self.outSlope == float("inf"):
            return kInterpolateStepped
        return kInterpolateHermite


@dataclass
class Curve:
    Binding: GenericBinding
    Data: List[KeyFrame] = field(list)


@dataclass
class Animation:
    Name: str
    # Dict[internal hash, Curve]
    RawCurves: Dict[int, Curve] = field(default_factory=dict)
    # Curves[Attribute][Path Hash] = Curve
    Curves: Dict[int, Dict[float, Curve]] = field(lambda: defaultdict(dict))
    # CurvesT[Path Hash][Attribute] = Curve
    CurvesT: Dict[int, Dict[float, Curve]] = field(lambda: defaultdict(dict))

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
        else:
            return self.RawCurves[hs]


def _read_clip_keyframe(
    time: float,
    binding: GenericBinding,
    keys: Generator[_StreamedClipKey | KeyFrame, None, None],
) -> KeyFrame:
    XYZW = "xyzw"
    result = KeyFrame(time, binding.typeID)
    if binding.typeID == ClassIDType.Transform:
        dimension = kAttributeSizeof(binding.attribute)
        for i in range(dimension):
            key = next(keys)
            setattr(result.value, XYZW[i], key.value)
            setattr(result.outSlope, XYZW[i], key.outSlope)
            setattr(result.inSlope, XYZW[i], key.inSlope)
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
    return key


def read_animation(src: AnimationClip) -> Animation:
    """Reads AnimationClip data and converts it to a list of Tracks

    Args:
        src (AnimationClip): animationClip

    Returns:
        Animation
    """
    result = Animation(src.m_Name)
    mClip = src.m_MuscleClip.m_Clip.data
    mClipBinding = src.m_ClipBindingConstant
    mClipBindingCurveSizesPfx = [
        kAttributeSizeof(b.attribute) for b in mClipBinding.genericBindings
    ]
    for i in range(1, len(mClipBindingCurveSizesPfx)):
        mClipBindingCurveSizesPfx[i] += mClipBindingCurveSizesPfx[i - 1]

    def mClipFindBinding(cur) -> GenericBinding:
        index = bisect_right(mClipBindingCurveSizesPfx, cur) - 1
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
    mStreamClipFrames = _read_streamed_clip_frames(mClip)
    for frame in mStreamClipFrames:
        curveIndex = 0
        while curveIndex < len(frame.keys):

            def __keygen():
                nonlocal curveIndex
                while True:
                    yield frame.keys[curveIndex]
                    curveIndex = mClipGetNextCurve(curveIndex, frame.keys)

            binding = mClipFindBinding(curveIndex)
            curve = result.get_curve(binding)
            key = _read_clip_keyframe(frame.time, binding, __keygen())
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
        while curveIndex < m_DenseClip.m_CurveCount:

            def __keygen():
                nonlocal curveIndex
                while True:
                    yield KeyFrame(
                        time,
                        binding.typeID,
                        m_DenseClip.m_SampleArray[frameOffset + curveIndex],
                    )
                    curveIndex += 1

            binding = mClipFindBinding(curveOffset + curveIndex)
            curve = result.get_curve(binding)
            key = _read_clip_keyframe(time, binding, __keygen())
            key.isDense = True
            curve.Data.append(key)

    # ConstantClip
    # Unchanging values.
    m_ConstantClip = mClip.m_ConstantClip
    curveOffset = mClip.m_StreamedClip.curveCount + mClip.m_DenseClip.m_CurveCount
    time = 0
    for _ in range(0, 2):  # first and last frame
        curveIndex = 0
        while curveIndex < len(m_ConstantClip.data):

            def __keygen():
                nonlocal curveIndex
                while True:
                    yield KeyFrame(
                        time,
                        binding.typeID,
                        m_ConstantClip.data[curveIndex],
                    )
                    curveIndex += 1

            binding = mClipFindBinding(curveOffset + curveIndex)
            curve = result.get_curve(binding)
            key = _read_clip_keyframe(time, binding, __keygen())
            key.isConstant = True
            curve.Data.append(key)
            binding = mClipFindBinding(curveOffset + curveIndex)
        time = src.m_MuscleClip.m_StopTime

    return result
