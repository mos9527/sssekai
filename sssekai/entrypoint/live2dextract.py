from sssekai.unity.AssetBundle import load_assetbundle
from sssekai.unity.AnimationClip import read_animation
from UnityPy.classes import AnimationClip
from os import path,remove,makedirs
from logging import getLogger
import json
logger = getLogger(__name__)

# Thanks! https://github.com/Perfare/UnityLive2DExtractor/blob/master/UnityLive2DExtractor/CubismMotion3Converter.cs
def animation_clip_to_live2d_motion3(animationClip: AnimationClip, pathTable : dict) -> dict:
    '''Convert Unity AnimationClip to Live2D Motion3 format

    Args:
        animationClip (AnimationClip): animationClip
        pathTable (dict): CRC32 to Live2D path table

    Returns:
        dict: Live2D Motion3 data
    '''
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
    animation = read_animation(animationClip)
    floatCurves = animation.FloatTracks
    motion['Meta']['CurveCount'] = len(floatCurves)
    for track in [track for path in floatCurves.values() for track in path.values()]:
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
        path = track.Path
        if path in pathTable:
            target, id = pathTable[path].split('/')
            if target == 'Parameters': target = 'Parameter'
            if target == 'Parts': target = 'PartOpacity'
        else:
            logger.warning('Failed to bind path CRC %s to any Live2D path' % path)
            target,id = 'PartOpacity', str(path)
        motion['Curves'].append(
            {
                'Target' : target,
                'Id': id,
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

def main_live2dextract(args):
    with open(args.infile,'rb') as f:
        from UnityPy.enums import ClassIDType
        makedirs(args.outdir,exist_ok=True)
        env = load_assetbundle(f)
        monobehaviors = dict()
        textures = dict()
        animations = dict()
        for obj in env.objects:
            data = obj.read()
            if obj.type in {ClassIDType.MonoBehaviour}:
                monobehaviors[data.name] = data
            if obj.type in {ClassIDType.Texture2D}:
                textures[data.name] = data
            if obj.type in {ClassIDType.AnimationClip}:
                animations[data.name] = data
        modelData = monobehaviors.get('BuildModelData',None)
        if not modelData:
            logger.warning('BuildModelData absent. Not extracting Live2D models!')
        else:
            modelData = modelData.read_typetree()
            # TextAssets are directly extracted
            # Usually there are *.moc3, *.model3, *.physics3; the last two should be renamed to *.*.json
            for obj in env.objects:
                if obj.type == ClassIDType.TextAsset:
                    data = obj.read()
                    out_name : str = data.name
                    if out_name.endswith('.moc3') or out_name.endswith('.model3') or out_name.endswith('.physics3'):
                        if out_name.endswith('.model3') or out_name.endswith('.physics3'):
                            out_name += '.json'
                        with open(path.join(args.outdir, out_name),'wb') as fout:
                            logger.info('Extracting Live2D Asset %s' % out_name)
                            fout.write(data.script)
            # Textures always needs conversion and is placed under specific folders
            for texture in modelData['TextureNames']:
                name = path.basename(texture)
                folder = path.dirname(texture)
                out_folder = path.join(args.outdir, folder)
                makedirs(out_folder,exist_ok=True)
                out_name = path.join(out_folder, name)
                logger.info('Extracting Texture %s' % out_name)
                name_wo_ext = '.'.join(name.split('.')[:-1])
                textures[name_wo_ext].image.save(out_name)
        # Animations are serialized into AnimationClip
        if not args.no_anim:
            from sssekai.unity.constant.SekaiLive2DPathNames import NAMES_CRC_TBL
            for clipName, clip in animations.items():
                logger.info('Extracting Animation %s' % clipName)
                data = animation_clip_to_live2d_motion3(clip, NAMES_CRC_TBL)  
                # https://til.simonwillison.net/python/json-floating-point
                def round_floats(o):
                    if isinstance(o, float):
                        return round(o, 3)
                    if isinstance(o, dict):
                        return {k: round_floats(v) for k, v in o.items()}
                    if isinstance(o, (list, tuple)):
                        return [round_floats(x) for x in o]
                    return o                       
                json.dump(round_floats(data), open(path.join(args.outdir, clipName+'.motion3.json'),'w'), indent=4, ensure_ascii=False)
        pass