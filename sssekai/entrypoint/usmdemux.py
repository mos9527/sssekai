from sssekai.unity.AssetBundle import load_assetbundle
from UnityPy.enums import ClassIDType
from os import path, remove, makedirs
from logging import getLogger

logger = getLogger(__name__)


def main_usmdemux(args):
    with open(args.infile, "rb") as f:
        env = load_assetbundle(f)
        datas = dict()
        for obj in env.objects:
            if obj.type in {ClassIDType.MonoBehaviour, ClassIDType.TextAsset}:
                data = obj.read()
                datas[data.m_Name] = data
        movieInfo = datas.get("MovieBundleBuildData", None)
        assert movieInfo, "Invalid AssetBundle. No MovieBundleBuildData found!"
        # movieInfo = movieInfo.read_typetree()
        usm_name = movieInfo.movieBundleDatas[0].usmFileName[: -len(".bytes")]
        logger.info("USM: %s" % usm_name)        
        usm_out = path.abspath(args.outfile)
        makedirs(path.dirname(usm_out), exist_ok=True)        
        with open(usm_out, "wb") as usmstream:
            for data in movieInfo.movieBundleDatas:
                usm = data.usmFileName[: -len(".bytes")]
                usm = datas[usm]
                usmstream.write(usm.m_Script.encode("utf-8", "surrogateescape"))
        logger.info("Saved raw USM file to %s" % usm_out)
