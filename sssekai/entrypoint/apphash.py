import zipfile
import UnityPy
import logging
import re
import sys

from io import BytesIO

from UnityPy.enums import ClassIDType
from UnityPy.helpers.Tpk import get_typetree_node
from sssekai.unity.AssetBundle import load_assetbundle
from tqdm import tqdm

REGION_MAP = {
    # NOTE: Order is used to determine the region
    "com.hermes.mk": "cn",
    "com.hermes.mk.asia": "tw",
    "com.sega.ColorfulStage.en": "en",
    "com.sega.pjsekai": "jp",
    "com.pjsekai.kr": "kr",
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


def dump_axml_stringpool(f: BytesIO):
    read_int = lambda nbytes: int.from_bytes(f.read(nbytes), "little")
    f.seek(8)
    hdr_type, hdr_size, size = read_int(2), read_int(2), read_int(4)
    n_strings = read_int(4)
    unk = read_int(4)
    flags = read_int(4)
    is_utf8 = flags & (1 << 8)
    string_offset = read_int(4) + 8
    unk = read_int(4)
    offsets = [read_int(4) for _ in range(n_strings)]
    for offset in offsets:
        f.seek(string_offset + offset)
        string_len = read_int(2)
        if is_utf8:
            string = f.read(string_len).decode("utf-8")
        else:
            string = f.read(string_len * 2).decode("utf-16-le")
        yield string


def main_apphash(args):
    env = UnityPy.Environment()
    app_package = None
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
            manifests = [
                manifest
                for package in enum_package(zip_ref)
                for manifest in enum_candidates(
                    package, lambda fn: fn == "AndroidManifest.xml"
                )
            ]
            manifest = manifests[0][1]
            manifest_strings = set(dump_axml_stringpool(manifest))
            # Heur: Reverse lookup the package name from the manifest strings
            for ky in REGION_MAP:
                if ky in manifest_strings:
                    app_package = ky
                    break
            candidates = [
                candidate
                for package in enum_package(zip_ref)
                for candidate in enum_candidates(
                    package,
                    lambda fn: fn.split("/")[-1]
                    in {
                        "6350e2ec327334c8a9b7f494f344a761",  # PJSK Android
                        "c726e51b6fe37463685916a1687158dd",  # PJSK iOS
                        "data.unity3d",  # TW,KR,CN (ByteDance)
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

    ans = None
    for pobj in env.objects:
        if pobj.type == UnityPy.enums.ClassIDType.MonoBehaviour:
            pname = pobj.peek_name()
            # Can't use UTTCGen_Reread because we may have no access to the Script PPtr asset
            # Object name seems to be a good enough heuristic
            for name in {"production_android", "production_ios"}:
                if pname == name:
                    # Works with post 3.4 (JP 3rd Anniversary) builds and downstream regional builds
                    tt = pobj.read_typetree(
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
                    # XXX: CN build has the same package name as the JP build??
                    # We need another heuristic to determine the package name
                    # This is previously done by setting app_package
                    package_heur = app_package or config.bundleIdentifier
                    region = region = REGION_MAP.get(package_heur, "unknown")
                    print(
                        f"Found {config.productName} at {config.m_Name}",
                        f"  Memo: {config.memo}",
                        f"  Package: {config.bundleIdentifier} (actually assumed as {package_heur})",
                        f"  AppHash (app_hash):     {config.clientAppHash}",
                        f"  Region  (app_region):   {region} (determined by {package_heur})",
                        f"  Version (app_version):  {app_version}",
                        f"  Version (ab_version):   {ab_version}",
                        f"  Bundle Version: {config.bundleVersion}",
                        f"  Data Version:   {data_version}",
                        f"  Version Suffix: {config.clientVersionSuffix}" "",
                        sep="\n",
                        file=sys.stderr,
                    )
                    # Only keep the Android one
                    if name == "production_android":
                        ans = f"""
{app_package or 'Unknown Pacakge'} ({app_version}, {region})
---

|{'app_hash'.rjust(48)}|   app_region|  app_version|   ab_version|
|{   '-'.rjust(48,'-')}|-------------|-------------|-------------|
|{  app_hash.rjust(48)}|{region.rjust(13)}|{app_version.rjust(13)}|{ab_version.rjust(13)}|

- CLI Usage:

        sssekai abcache --app-platform android --app-region {region} --app-version {app_version} --app-appHash {app_hash} --app-abVersion {ab_version}

- Python Usage:

        from sssekai.abcache import AbCacheConfig

        AbCacheConfig(
            app_region="{region}",
            app_version="{app_version}",
            ab_version="{ab_version}",
            app_hash="{app_hash}",
            app_platform="android"
        )"""

    print(ans)
