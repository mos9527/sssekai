import zipfile
import UnityPy
import logging
import re

from io import BytesIO

import UnityPy.classes
import UnityPy.enums
import UnityPy.enums.ClassIDType
from sssekai.unity.AssetBundle import load_assetbundle

HASHREGEX = re.compile(b"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
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
            for chunck in resp.iter_content(chunk_size=2**20):
                src.write(chunck)
                logger.debug("Downloading %d/%s" % (src.tell(), size))
            src.seek(0)
        else:
            src = open(args.apk_src, "rb")
        with zipfile.ZipFile(src, "r") as zip_ref:
            manifests = [
                manifest
                for package in enum_package(zip_ref)
                for manifest in enum_candidates(
                    package, lambda fn: fn == "AndroidManifest.xml"
                )
            ]
            manifest = manifests[0][1]
            from pyaxmlparser.axmlprinter import AXMLPrinter

            manifest = AXMLPrinter(manifest.read()).get_xml_obj()
            find_key = lambda ky: next((k for k in manifest.keys() if ky in k), None)
            app_version = manifest.get(find_key("versionName"), None)
            app_package = manifest.get(find_key("package"), None)
            logger.info("Package: %s" % app_package)
            logger.info("Version: %s" % app_version)
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
    for pobj in env.objects:
        # TODO: Dump actual typetree data from the game itself?
        if pobj.type == UnityPy.enums.ClassIDType.MonoBehaviour:
            obj = pobj.read(check_read=False)
            for name in {"production_android", "production_ios"}:
                if obj.m_Name == name:
                    hashStr = HASHREGEX.finditer(pobj.get_raw_data())
                    for m in hashStr:
                        ans = m.group().decode()
                        logger.debug("%s: %s" % (name, ans))
                        app_hash = ans
    region = REGION_MAP.get(app_package, app_package)
    print(app_version, region, app_hash)
