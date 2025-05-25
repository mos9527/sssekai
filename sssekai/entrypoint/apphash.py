import zipfile
import UnityPy
import logging
import json
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
ROW_REGIONS = {"cn", "tw", "kr"}
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


def dump_metadata_stringpool(f: BytesIO):
    metadata = f.read()
    metadata = metadata[metadata.find(b"\xaf\x1b\xb1\xfa") :]
    f = BytesIO(metadata)
    read_int = lambda nbytes: int.from_bytes(f.read(nbytes), "little")
    assert read_int(4) == 0xFAB11BAF, "bad sanity"
    logger.info("metadata version: %s" % read_int(4))
    stringLiteralOffset = read_int(4)  # string data for managed code
    stringLiteralSize = read_int(4)
    stringLiteralDataOffset = read_int(4)
    stringLiteralDataSize = read_int(4)
    f.seek(stringLiteralOffset)
    stringLiterals = [
        (read_int(4), read_int(4)) for _ in range(stringLiteralSize // 8)
    ]  # length, dataIndex
    for length, dataIndex in stringLiterals:
        f.seek(stringLiteralDataOffset + dataIndex)
        string = f.read(length)
        yield string.decode("utf-8")
    pass


def main_apphash(args):
    env = UnityPy.Environment()
    app_package = None
    app_version = "unknown"
    app_hash = "unknown"
    app_metadata_strings = None
    proxies = None
    if args.proxy:
        logger.info("Overriding proxy: %s", args.proxy)
        proxies = {"http": args.proxy, "https": args.proxy}
    if not args.ab_src:
        if not args.apk_src or args.fetch:
            from requests import get

            src = BytesIO()
            logger.debug("Fetching latest game package (JP) from APKPure")
            resp = get(
                "https://d.apkpure.net/b/XAPK/com.sega.pjsekai?version=latest",
                stream=True,
                proxies=proxies,
            )
            size = resp.headers.get("Content-Length", -1)
            with tqdm(total=int(size), unit="B", unit_scale=True) as progress:
                for chunk in resp.iter_content(chunk_size=2**20):
                    src.write(chunk)
                    progress.update(len(chunk))
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
            # if REGION_MAP[app_package] in ROW_REGIONS:
            #     metadata = [
            #         meta
            #         for package in enum_package(zip_ref)
            #         for meta in enum_candidates(
            #             package,
            #             lambda fn: fn.endswith("global-metadata.dat"),
            #         )
            #     ]
            #     if metadata:
            #         metadata = metadata[0][1]
            #         metadata_strings = list(dump_metadata_stringpool(metadata))
            #     app_metadata_strings = [s for s in metadata_strings if "bytedgame" in s]
            #     pass
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

    from sssekai.generated import UTTCGen_AsInstance
    from sssekai.generated.Sekai import (
        AndroidPlayerSettingConfig,
        IOSPlayerSettingConfig,
    )

    for reader in env.objects:
        if reader.type == UnityPy.enums.ClassIDType.MonoBehaviour:
            pname = reader.peek_name()
            clazz = {
                "production_android": AndroidPlayerSettingConfig,
                "production_ios": IOSPlayerSettingConfig,
            }
            clazz = clazz.get(pname, None)
            if clazz:
                # Works with post 3.4 (JP 3rd Anniversary) builds and downstream regional builds
                config = UTTCGen_AsInstance(clazz, reader)
                config: AndroidPlayerSettingConfig | IOSPlayerSettingConfig
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
                    f"  Version Suffix: {config.clientVersionSuffix}",
                    "",
                    "",
                    sep="\n",
                    file=sys.stderr,
                )
                # Only keep the Android one
                if pname == "production_android":
                    app_package = (
                        app_package or "Unknown Package (Failed APK Heuristic)"
                    )
                    # fmt: off
                    match args.format:
                        case 'json':
                            print(json.dumps({
                                "package": app_package,
                                "reported_package": config.bundleIdentifier,
                                "app_hash": app_hash,
                                "app_region": region,
                                "app_version": app_version,
                                "ab_version": ab_version,
                            }, indent=4))
                        case "markdown":
                            print(f"""{app_package} ({app_version}, {region})
---
Reported Package: {config.bundleIdentifier}

|{'app_hash'.rjust(48)}|   app_region|  app_version|   ab_version|
|{'-'.rjust(48, '-')}|-------------|-------------|-------------|
|{app_hash.rjust(48)}|{region.rjust(13)}|{app_version.rjust(13)}|{ab_version.rjust(13)}|

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
        )
""")
