from sssekai.unity.AssetBundle import load_assetbundle
from os import path, makedirs
from logging import getLogger
import json

logger = getLogger(__name__)


def main_live2dextract(args):
    with open(args.infile, "rb") as f:
        from UnityPy.enums import ClassIDType

        makedirs(args.outdir, exist_ok=True)
        env = load_assetbundle(f)
        monobehaviors = dict()
        textures = dict()
        animations = dict()
        for obj in env.objects:
            data = obj.read()
            if obj.type in {ClassIDType.MonoBehaviour}:
                monobehaviors[data.m_Name] = data
            if obj.type in {ClassIDType.Texture2D}:
                textures[data.m_Name] = data
            if obj.type in {ClassIDType.AnimationClip}:
                animations[data.m_Name] = data
        modelData = monobehaviors.get("BuildModelData", None)
        if not modelData:
            logger.warning("BuildModelData absent. Not extracting Live2D models!")
        else:
            # modelData = modelData.read_typetree()
            # TextAssets are directly extracted
            # Usually there are *.moc3, *.model3, *.physics3; the last two should be renamed to *.*.json
            for obj in env.objects:
                if obj.type == ClassIDType.TextAsset:
                    data = obj.read()
                    out_name: str = data.m_Name
                    if (
                        out_name.endswith(".moc3")
                        or out_name.endswith(".model3")
                        or out_name.endswith(".physics3")
                    ):
                        if out_name.endswith(".model3") or out_name.endswith(
                            ".physics3"
                        ):
                            out_name += ".json"
                        with open(path.join(args.outdir, out_name), "wb") as fout:
                            logger.info("Extracting Live2D Asset %s" % out_name)
                            fout.write(data.m_Script.encode("utf-8", "surrogateescape"))
            # Textures always needs conversion and is placed under specific folders
            for texture in modelData.TextureNames:
                name = path.basename(texture)
                folder = path.dirname(texture)
                out_folder = path.join(args.outdir, folder)
                makedirs(out_folder, exist_ok=True)
                out_name = path.join(out_folder, name)
                logger.info("Extracting Texture %s" % out_name)
                name_wo_ext = ".".join(name.split(".")[:-1])
                textures[name_wo_ext].image.save(out_name)
        # Animations are serialized into AnimationClip
        if not args.no_anim:
            from sssekai.unity.constant.SekaiLive2DPathNames import NAMES_CRC_TBL
            from sssekai.fmt.motion3 import unity_animation_clip_to_motion3

            for clipName, clip in animations.items():
                logger.info("Extracting Animation %s" % clipName)
                data = unity_animation_clip_to_motion3(clip, NAMES_CRC_TBL)
                json.dump(
                    data,
                    open(path.join(args.outdir, clipName + ".motion3.json"), "w"),
                    indent=4,
                    ensure_ascii=False,
                )
