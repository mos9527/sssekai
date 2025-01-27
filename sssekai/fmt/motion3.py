from sssekai.unity.AnimationClip import read_animation
from UnityPy.classes import AnimationClip
from logging import getLogger

logger = getLogger(__name__)


# Thanks! https://github.com/Perfare/UnityLive2DExtractor/blob/master/UnityLive2DExtractor/CubismMotion3Converter.cs
def unity_animation_clip_to_motion3(
    animationClip: AnimationClip, pathTable: dict
) -> dict:
    """Convert Unity AnimationClip to Live2D Motion3 format

    Args:
        animationClip (AnimationClip): animationClip
        pathTable (dict): CRC32 to Live2D path table

    Returns:
        dict: Live2D Motion3 data
    """
    motion = {
        "Version": 3,
        "Meta": {
            "Name": animationClip.m_Name,
            "Duration": animationClip.m_MuscleClip.m_StopTime,
            "Fps": animationClip.m_SampleRate,
            "Loop": True,
            "AreBeziersRestricted": True,
            "CurveCount": 0,
            "UserDataCount": 0,
            "TotalPointCount": 0,
            "TotalSegmentCount": 0,
            "TotalUserDataSize": 0,
        },
        "Curves": [],
        "UserData": [],
    }
    animation = read_animation(animationClip)
    floatCurves = list(animation.FloatCurves)
    motion["Meta"]["CurveCount"] = len(floatCurves)
    for curve in floatCurves:
        segments = list()
        segments.append(0)
        segments.append(curve.Curve[0].value)
        curveIndex = 1
        while curveIndex < len(curve.Data):
            key = curve.Data[curveIndex]
            preKey = curve.Data[curveIndex - 1]
            if abs(key.time - preKey.time - 0.01) < 0.0001:
                nextCurve = curve.Data[curveIndex + 1]
                if nextCurve.value == key.value:
                    segments.append(3)  # InverseSteppedSegment
                    segments.append(nextCurve.time)
                    segments.append(nextCurve.value)
                    motion["Meta"]["TotalPointCount"] += 1
                    motion["Meta"]["TotalSegmentCount"] += 1
                    curveIndex += 1
                    continue
            if key.inSlope == float("+inf"):
                segments.append(2)  # SteppedSegment
                segments.append(key.time)
                segments.append(key.value)
                motion["Meta"]["TotalPointCount"] += 1
            elif preKey.outSlope == 0 and abs(key.inSlope) < 0.0001:
                segments.append(0)  # LinearSegment
                segments.append(key.time)
                segments.append(key.value)
                motion["Meta"]["TotalPointCount"] += 1
            else:
                tangentLength = (key.time - preKey.time) / 3
                segments.append(1)  # BezierSegment
                segments.append(preKey.time + tangentLength)
                segments.append(preKey.outSlope * tangentLength + preKey.value)
                segments.append(key.time - tangentLength)
                segments.append(key.value - key.inSlope * tangentLength)
                segments.append(key.time)
                segments.append(key.value)
                motion["Meta"]["TotalPointCount"] += 3
            motion["Meta"]["TotalSegmentCount"] += 1
            curveIndex += 1
        path = curve.Path
        if path in pathTable:
            target, id = pathTable[path].split("/")
            if target == "Parameters":
                target = "Parameter"
            if target == "Parts":
                target = "PartOpacity"
        else:
            logger.warning("Failed to bind path CRC %s to any Live2D path" % path)
            target, id = "PartOpacity", str(path)
        motion["Curves"].append({"Target": target, "Id": id, "Segments": segments})
    for event in animationClip.m_Events:
        motion["UserData"].append({"time": event.time, "value": event.data})
        motion["Meta"]["UserDataCount"] += 1
        motion["Meta"]["TotalUserDataSize"] += len(event.data)
    return motion
