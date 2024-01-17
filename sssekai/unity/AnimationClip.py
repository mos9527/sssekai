from collections import OrderedDict
from typing import Dict, List, Tuple
from UnityPy.enums import ClassIDType
from UnityPy.classes import AnimationClip
from UnityPy.math import Matrix4x4, Quaternion, Vector3
from dataclasses import dataclass
from enum import IntEnum
from logging import getLogger
logger = getLogger(__name__)
# taken from https://github.com/AssetRipper/AssetRipper
class TransformType(IntEnum):
    _None = 0
    Translation = 1
    Rotation = 2
    Scaling = 3
    EulerRotation = 4
def DimensionOfTransformType(type : TransformType):
    if type != TransformType.Rotation: # Quaternion
        return 3
    return 4 # XYZ 
@dataclass
class KeyFrame:
    time : float
    value : float | Vector3 | Quaternion
    inSlope : float | Vector3 | Quaternion = 0
    outSlope : float | Vector3 | Quaternion = 0
    coeff : float = 0

@dataclass
class Track:
    Attribute: int | str
    Path : int | str
    Curve : List[KeyFrame]
    def __init__(self) -> None:
        self.Curve = list()
    def add_keyframe(self, keyframe : KeyFrame):
        self.Curve.append(keyframe)

class Animation:
    FloatTracks : Dict[int, Dict[int,Track]] # Path crc hash - Attribute crc hash - Track
    TransformTracks : Dict[TransformType ,Dict[int, Track]] # TransformType - Path crc hash - Track
    Framerate : int
    Duration : int
    def __init__(self) -> None:
        self.Framerate = 60
        self.FloatTracks = dict()
        self.TransformTracks = dict()
        self.TransformTracks[TransformType.EulerRotation] = dict()
        self.TransformTracks[TransformType.Rotation] = dict()
        self.TransformTracks[TransformType.Translation] = dict()
        self.TransformTracks[TransformType.Scaling] = dict()

def read_animation(animationClip: AnimationClip) -> Animation:
    '''Reads AnimationClip data and converts it to a list of Tracks

    Args:
        animationClip (AnimationClip): animationClip

    Returns:
        List[Track]: List of Tracks
    '''
    m_Clip = animationClip.m_MuscleClip.m_Clip
    streamedFrames = m_Clip.m_StreamedClip.ReadData()
    m_ClipBindingConstant = animationClip.m_ClipBindingConstant
    animationTracks = Animation()
    animationTracks.Framerate = animationClip.m_SampleRate
    animationTracks.Duration = animationClip.m_MuscleClip.m_StopTime
    def get_transform_track(path : int, type : TransformType): # TransformType is attribute. transposed since there are only TRS
        if not path in animationTracks.TransformTracks[type]:
            animationTracks.TransformTracks[type][path] = Track()
        return animationTracks.TransformTracks[type][path]

    def get_float_track(path : int, attribute : int = 0) -> Track:
        if not path in animationTracks.FloatTracks:
            animationTracks.FloatTracks[path] = dict()
        if not attribute in animationTracks.FloatTracks[path]:
            animationTracks.FloatTracks[path][attribute] = Track()
        return animationTracks.FloatTracks[path][attribute]

    def add_float_curve_data(binding, time, value, inSlope, outSlope, coeff):
        track = get_float_track(binding.path, binding.attribute)
        track.Attribute = binding.attribute
        track.Path = binding.path
        track.add_keyframe(KeyFrame(time,value, inSlope, outSlope, coeff))
    
    def add_transform_curve_data(binding, time, datas : List[Tuple[float,float,float]]): # value, inSlope, outSlope
        type = TransformType(binding.attribute)
        dimension = DimensionOfTransformType(binding.attribute)
        if dimension == 3:
            frame = KeyFrame(time, 
                Vector3(datas[0][0],datas[1][0],datas[2][0]),
                Vector3(datas[0][1],datas[1][1],datas[2][1]),
                Vector3(datas[0][2],datas[1][2],datas[2][2])
            )
        else:
            frame = KeyFrame(time,
                Quaternion(datas[0][0],datas[1][0],datas[2][0],datas[3][0]),
                Quaternion(datas[0][1],datas[1][1],datas[2][1],datas[3][1]),
                Quaternion(datas[0][2],datas[1][2],datas[2][2],datas[3][2]),
            )    
        track = get_transform_track(binding.path, type)
        track.add_keyframe(frame)                                    

    def get_next_curve_index(current, keyList):
        i = current
        while i < len(keyList) and keyList[current].index == keyList[i].index:
            i += 1
        return i

    for frame in streamedFrames:
        curveIndex = 0
        while curveIndex < len(frame.keyList):
            curveKey = frame.keyList[curveIndex]
            binding = m_ClipBindingConstant.FindBinding(curveKey.index)            
            if binding.typeID == ClassIDType.Transform:
                transformType = TransformType(binding.attribute)
                dimension = DimensionOfTransformType(transformType)
                curveData = []
                for _ in range(dimension):
                    curveKey = frame.keyList[curveIndex]
                    curveData.append((curveKey.value,getattr(curveKey,'inSlope',0),curveKey.outSlope))
                    curveIndex = get_next_curve_index(curveIndex, frame.keyList)
                add_transform_curve_data(binding, frame.time, curveData)
            else:
                add_float_curve_data(binding, frame.time, curveKey.value,getattr(curveKey,'inSlope',0),curveKey.outSlope,curveKey.coeff) 
                curveIndex = get_next_curve_index(curveIndex, frame.keyList)
  
    m_DenseClip = m_Clip.m_DenseClip
    streamCount = m_Clip.m_StreamedClip.curveCount
    for frameIndex in range(0,m_DenseClip.m_FrameCount):
        time = m_DenseClip.m_BeginTime + frameIndex / m_DenseClip.m_SampleRate
        frameOffset = frameIndex * m_DenseClip.m_CurveCount
        curveIndex = 0
        while curveIndex < m_DenseClip.m_CurveCount:
            index = streamCount + curveIndex
            framePosition = frameOffset + curveIndex
            binding = m_ClipBindingConstant.FindBinding(index)
            if binding.typeID == ClassIDType.Transform:
                transformType = TransformType(binding.attribute)
                dimension = DimensionOfTransformType(transformType)
                curveData = []
                for i in range(dimension):
                    curveData.append((m_DenseClip.m_SampleArray[framePosition + i],0,0))
                add_transform_curve_data(binding, time, curveData)
                curveIndex += dimension
            else:
                add_float_curve_data(binding, time, m_DenseClip.m_SampleArray[framePosition], 0, 0, 0)
                curveIndex += 1

    m_ConstantClip = m_Clip.m_ConstantClip
    denseCount = m_Clip.m_DenseClip.m_CurveCount
    time2 = 0
    for _ in range(0,2): # first and last frame
        curveIndex = 0
        while curveIndex < len(m_ConstantClip.data):
            index = streamCount + denseCount + curveIndex
            binding = m_ClipBindingConstant.FindBinding(index)
            if binding.typeID == ClassIDType.Transform:
                transformType = TransformType(binding.attribute)
                dimension = DimensionOfTransformType(transformType)
                curveData = []
                for i in range(dimension):
                    curveData.append((m_ConstantClip.data[curveIndex + i],0,0))
                add_transform_curve_data(binding, time2, curveData)
                curveIndex += dimension
            else:
                add_float_curve_data(binding, time2, m_ConstantClip.data[curveIndex], 0, 0, 0)
                curveIndex += 1
        time2 = animationClip.m_MuscleClip.m_StopTime
    return animationTracks
