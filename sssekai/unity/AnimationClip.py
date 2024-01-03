from typing import List
from UnityPy.classes import AnimationClip
from dataclasses import dataclass
from logging import getLogger
logger = getLogger(__name__)
@dataclass
class KeyFrame:
    time : float
    value : float
    inSlope : float = 0
    outSlope : float = 0
    coeff : float = 0

@dataclass
class Track:
    Name : str
    Target : str
    Curve : List[KeyFrame]
    def __init__(self) -> None:
        self.Curve = list()
    def add(self, keyframe : KeyFrame):
        self.Curve.append(keyframe)

# Thanks! https://github.com/Perfare/UnityLive2DExtractor/blob/master/UnityLive2DExtractor/CubismMotion3Converter.cs
def animation_clip_to_live2d_motion3(animationClip: AnimationClip, pathTable : dict) -> dict:
    motion = {
            'Version': 3,
            'Meta': {
                "Name":animationClip.m_Name,
                "Duration":animationClip.m_MuscleClip.m_StopTime,
                "Fps":animationClip.m_SampleRate,
                "Loop":True,
                "AreBeziersRestricted":True,
                "CurveCount":0,
                "UserDataCount":0,
                "TotalPointCount":0,
                "TotalSegmentCount":0,
                "TotalUserDataSize":0
            },
            'Curves': [],
            'UserData': []
        }
    m_Clip = animationClip.m_MuscleClip.m_Clip
    streamedFrames = m_Clip.m_StreamedClip.ReadData()
    m_ClipBindingConstant = animationClip.m_ClipBindingConstant

    animationTracks = list()
    def FindTrack(key : str):
        for track in animationTracks:
            if track.Name == key: return track
        track = Track()
        track.Name = key
        animationTracks.append(track)
        return track

    def GetLive2DPath(path: int):
        if path in pathTable:
            target, track = pathTable[path].split('/')
            if target == 'Parameters': target = 'Parameter'
            if target == 'Parts': target = 'PartOpacity'
        else:
            logger.warning('Faield to bind %s to any Live2D path' % path)
            return 'PartOpacity', str(path)
        return target, track
    
    for frame in streamedFrames:
        for curveKey in frame.keyList:
            binding = m_ClipBindingConstant.FindBinding(curveKey.index)
            target, track = GetLive2DPath(binding.path)
            FindTrack(track).Target = target
            FindTrack(track).add(KeyFrame(frame.time, curveKey.value,getattr(curveKey,'inSlope',0),curveKey.outSlope,curveKey.coeff))      

    def ReadCurveData(index, time, data, curveIndex):
        binding = m_ClipBindingConstant.FindBinding(index)
        target, track = GetLive2DPath(binding.path)
        FindTrack(track).Target = target
        FindTrack(track).add(KeyFrame(time, data[curveIndex], 0,0,None))

    m_DenseClip = m_Clip.m_DenseClip
    streamCount = m_Clip.m_StreamedClip.curveCount
    for frameIndex in range(0,m_DenseClip.m_FrameCount):
        time = m_DenseClip.m_BeginTime + frameIndex / m_DenseClip.m_SampleRate
        # frameOffset = frameIndex * m_DenseClip.m_CurveCount
        for curveIndex in range(0,m_DenseClip.m_CurveCount):
            index = streamCount + curveIndex
            ReadCurveData(index, time, m_DenseClip.m_SampleArray, curveIndex)
        
    m_ConstantClip = m_Clip.m_ConstantClip
    denseCount = m_Clip.m_DenseClip.m_CurveCount
    time2 = 0
    for i in range(0,2):
        for curveIndex in range(0, len(m_ConstantClip.data)):
            index = streamCount + denseCount + curveIndex
            ReadCurveData(index, time2, m_ConstantClip.data, curveIndex)
        time2 = animationClip.m_MuscleClip.m_StopTime
    motion['Meta']['CurveCount'] = len(animationTracks)
    for track in animationTracks:        
        segments = list()
        segments.append(0)
        segments.append(track.Curve[0].value)
        curveIndex = 1
        while curveIndex < len(track.Curve):
            curve = track.Curve[curveIndex]
            preCurve = track.Curve[curveIndex - 1]
            if (abs(curve.time - preCurve.time - 0.01) < 0.0001): 
                nextCurve = track.Curve[curveIndex + 1]
                if (nextCurve.value == curve.value):
                    segments.append(3) # InverseSteppedSegment
                    segments.append(nextCurve.time)
                    segments.append(nextCurve.value)
                    motion['Meta']['TotalPointCount'] += 1
                    motion['Meta']['TotalSegmentCount'] += 1
                    curveIndex += 1
                    continue
            if (curve.inSlope == float('+inf')):
                segments.append(2) # SteppedSegment
                segments.append(curve.time)
                segments.append(curve.value)
                motion['Meta']['TotalPointCount'] += 1
            elif (preCurve.outSlope == 0 and abs(curve.inSlope) < 0.0001):
                segments.append(0) # LinearSegment
                segments.append(curve.time)
                segments.append(curve.value)
                motion['Meta']['TotalPointCount'] += 1
            else:
                tangentLength = (curve.time - preCurve.time) / 3
                segments.append(1) # BezierSegment
                segments.append(preCurve.time + tangentLength)
                segments.append(preCurve.outSlope * tangentLength + preCurve.value)
                segments.append(curve.time - tangentLength)
                segments.append(curve.value - curve.inSlope * tangentLength)
                segments.append(curve.time)
                segments.append(curve.value)
                motion['Meta']['TotalPointCount'] += 3
            motion['Meta']['TotalSegmentCount'] += 1
            curveIndex+=1

        motion['Curves'].append(
            {
                'Target' : track.Target,
                'Id': track.Name,
                'Segments': segments
            }
        )    
    for event in animationClip.m_Events:
        motion['UserData'].append(
            {
                'time' : event.time,
                'value': event.data
            }
        )
        motion['Meta']['UserDataCount'] += 1
        motion['Meta']['TotalUserDataSize'] += len(event.data)
    return motion