import zipfile
import UnityPy
import logging
import re
import sys

from io import BytesIO

import UnityPy.enums
import UnityPy.enums.ClassIDType
from UnityPy.classes import MonoBehaviour
from sssekai.unity.AssetBundle import load_assetbundle
from tqdm import tqdm

REGION_MAP = {
    "com.sega.pjsekai": "jp",
    "com.sega.ColorfulStage.en": "en",
    "com.hermes.mk.asia": "tw",
    "com.pjsekai.kr": "kr",
    "com.hermes.mk": "cn",
}
logger = logging.getLogger("apphash")


def enum_candidates(zip_file, filter):
    return (
        (f, zip_file.open(f), zip_file) for f in zip_file.filelist if filter(f.filename)
    )


def enum_package(zip_file):
    yield zip_file
    for f in zip_file.filelist:
        if f.filename.lower().endswith(".apk"):
            yield zipfile.ZipFile(zip_file.open(f))


def main_apphash(args):
    env = UnityPy.Environment()
    app_package = "unknown"
    app_version = "unknown"
    app_hash = "unknown"

    if not args.ab_src:
        if not args.apk_src or args.fetch:
            from requests import get

            src = BytesIO()
            logger.debug("Fetching latest game package (JP) from APKPure")
            resp = get(
                "https://d.apkpure.net/b/XAPK/com.sega.pjsekai?version=latest",
                stream=True,
            )
            size = resp.headers.get("Content-Length", -1)
            with tqdm(total=int(size), unit="B", unit_scale=True) as progress:
                progress.sp = print
                for chunck in resp.iter_content(chunk_size=2**20):
                    src.write(chunck)
                    progress.update(len(chunck))
            src.seek(0)
        else:
            src = open(args.apk_src, "rb")
        with zipfile.ZipFile(src, "r") as zip_ref:
            candidates = [
                candidate
                for package in enum_package(zip_ref)
                for candidate in enum_candidates(
                    package,
                    lambda fn: fn.split("/")[-1]
                    in {
                        "6350e2ec327334c8a9b7f494f344a761",  # PJSK Android
                        "c726e51b6fe37463685916a1687158dd",  # PJSK iOS
                        "data.unity3d",  # TW,KR (ByteDance)
                    },
                )
            ]
            for candidate, stream, _ in candidates:
                env.load_file(stream)
    else:
        logger.info("Loading from AssetBundle %s" % args.ab_src)
        with open(args.ab_src, "rb") as f:
            env = load_assetbundle(BytesIO(f.read()))

    from sssekai.generated import TYPETREE_DEFS
    from sssekai.generated.Sekai import PlayerSettingConfig

    for pobj in env.objects:
        if pobj.type == UnityPy.enums.ClassIDType.MonoBehaviour:
            obj = pobj.read(check_read=False)
            obj: MonoBehaviour
            # Can't use UTTCGen_Reread because we may have no access to the Script PPtr asset
            # Object name seems to be a good enough heuristic
            for name in {"production_android", "production_ios"}:
                if obj.m_Name == name:
                    tt = obj.object_reader.read_typetree(
                        TYPETREE_DEFS["Sekai.PlayerSettingConfig"], check_read=False
                    )
                    config = PlayerSettingConfig(**tt)
                    app_version = "%s.%s.%s" % (
                        config.clientMajorVersion,
                        config.clientMinorVersion,
                        config.clientBuildVersion,
                    )
                    data_version = "%s.%s.%s" % (
                        config.clientDataMajorVersion,
                        config.clientDataMinorVersion,
                        config.clientDataBuildVersion,
                    )
                    ab_version = "%s.%s.%s" % (
                        config.clientMajorVersion,
                        config.clientMinorVersion,
                        config.clientDataRevision,
                    )
                    app_hash = config.clientAppHash
                    app_package = config.bundleIdentifier
                    region = region = REGION_MAP.get(app_package, "unknown")
                    print(
                        f"Found {config.productName} at {config.m_Name}",
                        f"  Memo: {config.memo}",
                        f"  Package: {config.bundleIdentifier}",
                        f"  AppHash (app_hash):     {config.clientAppHash}",
                        f"  Region  (app_region):   {region}",
                        f"  Version (app_version):  {app_version}",
                        f"  Version (ab_version):   {ab_version}",
                        f"      (NOTE: Set this ONLY with ROW (TW/KR/CN) versions!)",
                        f"  Bundle Version: {config.bundleVersion}",
                        f"  Data Version:   {data_version}",
                        f"  Version Suffix: {config.clientVersionSuffix}" "",
                        sep="\n",
                        file=sys.stderr,
                    )

    print(app_version, region, app_hash)
