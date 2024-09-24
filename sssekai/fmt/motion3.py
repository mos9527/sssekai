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
    floatCurves = animation.FloatTracks
    motion["Meta"]["CurveCount"] = len(floatCurves)
    for track in [track for path in floatCurves.values() for track in path.values()]:
        segments = list()
        segments.append(0)
        segments.append(track.Curve[0].value)
        curveIndex = 1
        while curveIndex < len(track.Curve):
            curve = track.Curve[curveIndex]
            preCurve = track.Curve[curveIndex - 1]
            if abs(curve.time - preCurve.time - 0.01) < 0.0001:
                nextCurve = track.Curve[curveIndex + 1]
                if nextCurve.value == curve.value:
                    segments.append(3)  # InverseSteppedSegment
                    segments.append(nextCurve.time)
                    segments.append(nextCurve.value)
                    motion["Meta"]["TotalPointCount"] += 1
                    motion["Meta"]["TotalSegmentCount"] += 1
                    curveIndex += 1
                    continue
            if curve.inSlope == float("+inf"):
                segments.append(2)  # SteppedSegment
                segments.append(curve.time)
                segments.append(curve.value)
                motion["Meta"]["TotalPointCount"] += 1
            elif preCurve.outSlope == 0 and abs(curve.inSlope) < 0.0001:
                segments.append(0)  # LinearSegment
                segments.append(curve.time)
                segments.append(curve.value)
                motion["Meta"]["TotalPointCount"] += 1
            else:
                tangentLength = (curve.time - preCurve.time) / 3
                segments.append(1)  # BezierSegment
                segments.append(preCurve.time + tangentLength)
                segments.append(preCurve.outSlope * tangentLength + preCurve.value)
                segments.append(curve.time - tangentLength)
                segments.append(curve.value - curve.inSlope * tangentLength)
                segments.append(curve.time)
                segments.append(curve.value)
                motion["Meta"]["TotalPointCount"] += 3
            motion["Meta"]["TotalSegmentCount"] += 1
            curveIndex += 1
        path = track.Path
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
