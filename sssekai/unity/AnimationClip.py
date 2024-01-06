from collections import OrderedDict
from typing import Dict, List
from UnityPy.classes import AnimationClip
from UnityPy.math import Matrix4x4, Quaternion, Vector3
from dataclasses import dataclass
from logging import getLogger
logger = getLogger(__name__)

@dataclass
class KeyFrame:
    time : float
    value : float | Vector3 | Quaternion
    inSlope : float = 0
    outSlope : float = 0
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

def read_animation_clip(animationClip: AnimationClip) -> List[Track]:
    '''Reads AnimationClip data and converts it to a list of Tracks

    Args:
        animationClip (AnimationClip): animationClip

    Returns:
        List[Track]: List of Tracks
    '''
    m_Clip = animationClip.m_MuscleClip.m_Clip
    streamedFrames = m_Clip.m_StreamedClip.ReadData()
    m_ClipBindingConstant = animationClip.m_ClipBindingConstant
    animationTracks = dict()

    def get_track(key : int | str) -> Track:
        if not key in animationTracks:
            animationTracks[key] = Track()
        return animationTracks[key]

    for frame in streamedFrames:
        for curveKey in frame.keyList:
            binding = m_ClipBindingConstant.FindBinding(curveKey.index)
            get_track(id(binding)).Attribute = binding.attribute
            get_track(id(binding)).Path = binding.path
            get_track(id(binding)).add_keyframe(KeyFrame(frame.time, curveKey.value,getattr(curveKey,'inSlope',0),curveKey.outSlope,curveKey.coeff))      
  
    def read_curve_data(index, time, data, curveIndex):
        binding = m_ClipBindingConstant.FindBinding(index)
        get_track(id(binding)).Attribute = binding.attribute
        get_track(id(binding)).Path = binding.path
        get_track(id(binding)).add_keyframe(KeyFrame(time, data[curveIndex], 0,0,None))

    m_DenseClip = m_Clip.m_DenseClip
    streamCount = m_Clip.m_StreamedClip.curveCount
    for frameIndex in range(0,m_DenseClip.m_FrameCount):
        time = m_DenseClip.m_BeginTime + frameIndex / m_DenseClip.m_SampleRate
        # frameOffset = frameIndex * m_DenseClip.m_CurveCount
        for curveIndex in range(0,m_DenseClip.m_CurveCount):
            index = streamCount + curveIndex
            read_curve_data(index, time, m_DenseClip.m_SampleArray, curveIndex)   

    m_ConstantClip = m_Clip.m_ConstantClip
    denseCount = m_Clip.m_DenseClip.m_CurveCount
    time2 = 0
    for _ in range(0,2):
        for curveIndex in range(0, len(m_ConstantClip.data)):
            index = streamCount + denseCount + curveIndex
            read_curve_data(index, time2, m_ConstantClip.data, curveIndex)
        time2 = animationClip.m_MuscleClip.m_StopTime
    return list(animationTracks.values())
