import argparse
import sys

from sssekai.entrypoint.apidecrypt import main_apidecrypt
from sssekai.entrypoint.abdecrypt import main_abdecrypt
from sssekai.entrypoint.rla2json import main_rla2json
from sssekai.entrypoint.usmdemux import main_usmdemux
from sssekai.entrypoint.abcache import main_abcache, DEFAULT_CACHE_DB_FILE
from sssekai.entrypoint.abserve import main_abserve
from sssekai.entrypoint.live2dextract import main_live2dextract
from sssekai.entrypoint.spineextract import main_spineextract
from sssekai.entrypoint.apphash import main_apphash
from sssekai.entrypoint.mvdata import main_mvdata
from sssekai.entrypoint.moc3paths import main_moc3paths
from sssekai.unity import sssekai_get_unity_version, sssekai_set_unity_version


def create_parser(clazz=argparse.ArgumentParser):
    """
    Create the command line parser for the application.

    Args:
        clazz (type): The parser class to use. Defaults to argparse.ArgumentParser.
        In GUI mode this should be set to GooeyParser otherwise.
    """

    def gooey_only(**kwargs):
        # Silent non-argparse kwargs
        if clazz == argparse.ArgumentParser:
            return {}
        return kwargs

    parser = clazz(
        description="""Project SEKAI Asset Utility / PJSK 资源工具""",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--log-level",
        type=str,
        help="logging level (default: %(default)s)",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    parser.add_argument(
        "--unity-version",
        type=str,
        help="""Unity version to use (default: %(default)s)
Prior to game version 3.6.0 (JP), this has always been 2020.3.21f1
This has been changed to 2022.3.21f1 since, which would apply to all the assets from 3.6.0 onwards.
If you encounter any issues, try switching to the old version, or vice versa.""",
        default=sssekai_get_unity_version(),
    )
    subparsers = parser.add_subparsers(
        title="subcommands", description="valid subcommands", help="additional help"
    )
    # apidecrypt
    apidecrypt_parser = subparsers.add_parser(
        "apidecrypt",
        usage="""API crypto dumper
This crypto applies to:
    - API request/response body dumped by packet sniffer (mitmproxy, wireshark, etc.)
    - AssetBundleInfo (see sssekai.abcache)""",
    )
    apidecrypt_parser.add_argument(
        "infile", type=str, help="input dump file", **gooey_only(widget="FileChooser")
    )
    apidecrypt_parser.add_argument(
        "outfile", type=str, help="output json file", **gooey_only(widget="FileSaver")
    )
    apidecrypt_parser.add_argument(
        "--region",
        type=str,
        help="app region",
        default="jp",
        choices=["jp", "tw", "en", "kr", "cn"],
    )
    apidecrypt_parser.set_defaults(func=main_apidecrypt)
    # abdecrypt
    abdecrypt_parser = subparsers.add_parser(
        "abdecrypt", usage="""Decrypt Sekai AssetBundle"""
    )
    abdecrypt_parser.add_argument(
        "indir", type=str, help="input directory", **gooey_only(widget="DirChooser")
    )
    abdecrypt_parser.add_argument(
        "outdir", type=str, help="output directory", **gooey_only(widget="DirChooser")
    )
    abdecrypt_parser.set_defaults(func=main_abdecrypt)
    # usmdemux
    usmdemux_parser = subparsers.add_parser(
        "usmdemux", usage="""Demux Sekai USM Video in a AssetBundle"""
    )
    usmdemux_parser.add_argument(
        "infile", type=str, help="input file", **gooey_only(widget="FileChooser")
    )
    usmdemux_parser.add_argument(
        "outdir", type=str, help="output directory", **gooey_only(widget="DirChooser")
    )
    usmdemux_parser.set_defaults(func=main_usmdemux)
    # abcache
    abcache_parser = subparsers.add_parser(
        "abcache", usage="""Sekai AssetBundle Metadata Cache / Game API Helper"""
    )
    abcache_parser.add_argument(
        "--proxy",
        type=str,
        help="HTTP Proxy to use. This overrides the system proxy (environ HTTP_PROXY, HTTPS_PROXY) settings.",
        default=None,
    )
    group = abcache_parser.add_argument_group("save/load options")
    group.add_argument(
        "--db",
        type=str,
        help="""cache database file path (default: %(default)s)""",
        default=DEFAULT_CACHE_DB_FILE,
        **gooey_only(widget="FileChooser"),
    )
    group.add_argument(
        "--no-update",
        action="store_true",
        help="skip all metadata updates and use cached ones as is. this supercedes 'game version options' and 'authentication options'",
    )
    group = abcache_parser.add_argument_group(
        "game version options",
        "NOTE: these options are used to *update* the cache database. Use --no-update to skip updating. Also, you may want to read the Wiki to know how to get these values.",
    )
    group.add_argument(
        "--app-region",
        type=str,
        help="PJSK app region (default: %(default)s)",
        choices=["jp", "tw", "en", "kr", "cn"],
        default="jp",
    )
    group.add_argument(
        "--app-platform",
        type=str,
        help="PJSK app platform (default: %(default)s",
        choices=["ios", "android"],
        default="android",
    )  # Let's hope this doesn't age well...
    group.add_argument(
        "--app-version",
        type=str,
        help="PJSK app version. This is required unless --no-update is specified",
        default="",
    )
    group.add_argument(
        "--app-appHash",
        type=str,
        help="PJSK app hash. This is required unless --no-update is specified",
        default="",
    )
    group.add_argument(
        "--app-abVersion",
        type=str,
        help="PJSK AssetBundle URL version. This is used for ROW servers since it may differ.",
        default=None,
    )
    group = abcache_parser.add_argument_group("download options")
    group.add_argument(
        "--download-filter",
        type=str,
        help="filter AssetBundles (by bundle names) with this regex pattern",
        default=None,
    )
    group.add_argument(
        "--download-filter-cache-diff",
        type=str,
        help="filter AssetBundles (by hashes) by *ONLY* downloading ones with a *different* hash from the current hash with this one.",
        default=None,
        **gooey_only(widget="FileChooser"),
    )
    group.add_argument(
        "--download-dir",
        type=str,
        help="asset bundle download directory. leave empty if you don't want to download anything",
        default="",
        **gooey_only(widget="DirChooser"),
    )
    group.add_argument(
        "--download-ensure-deps",
        action="store_true",
        help="ensure dependencies (of the downloaded ones) are downloaded as well",
    )
    group.add_argument(
        "--download-workers",
        type=int,
        help="number of download workers (default: %(default)s)",
        default=4,
    )
    group = abcache_parser.add_argument_group(
        "extra options",
        "NOTE: when *any* of these options are specified, the cache database *won't* be updated, and no download will be performed either.",
    )
    group.add_argument(
        "--dump-master-data",
        type=str,
        help="directory to store the dumped master data in JSON.",
        default=None,
        **gooey_only(widget="DirChooser"),
    )
    group.add_argument(
        "--dump-user-data",
        type=str,
        help="directory to store the dumped master data of the authencicated user in JSON. NOTE: --auth-credential required",
        default=None,
        **gooey_only(widget="DirChooser"),
    )
    group.add_argument(
        "--keep-compact",
        help="keep compacted datasets as is without expanding them to key-value pairs",
        action="store_true",
    )
    group = abcache_parser.add_argument_group(
        "authentication arguments",
        "Only needed for some functionailties (i.e. --dump-user-data)",
    )
    group.add_argument(
        "--auth-credential",
        type=str,
        help="Credential for API authentication. Can be omitted on JP/EN servers, in which case a guest account would be automatically registered and used.",
        default=None,
    )
    abcache_parser.set_defaults(func=main_abcache)
    abserve_parser = subparsers.add_parser(
        "abserve", usage="""AbCache Filesystem Server / Backend"""
    )
    abserve_parser.add_argument(
        "--db",
        type=str,
        help="""cache database file path (default: %(default)s)""",
        default=DEFAULT_CACHE_DB_FILE,
        **gooey_only(widget="FileChooser"),
    )
    abserve_parser.add_argument(
        "--fuse",
        type=str,
        help="""local mount point for AbCache. Required FUSE on host OS and fusepy (default: %(default)s)""",
        default="",
        **gooey_only(widget="DirChooser"),
    )
    abserve_parser.add_argument(
        "--host",
        type=str,
        help="""address of the interface to listen on (default: %(default)s)""",
        default="0.0.0.0",
    )
    abserve_parser.add_argument(
        "--port",
        type=int,
        help="""port to listen on (default: %(default)s)""",
        default="3939",
    )
    abserve_parser.set_defaults(func=main_abserve)
    # live2dextract
    live2dextract_parser = subparsers.add_parser(
        "live2dextract", usage="""Extract Sekai Live2D Models in a AssetBundle"""
    )
    live2dextract_parser.add_argument(
        "infile", type=str, help="input file", **gooey_only(widget="FileChooser")
    )
    live2dextract_parser.add_argument(
        "outdir", type=str, help="output directory", **gooey_only(widget="DirChooser")
    )
    live2dextract_parser.add_argument(
        "--no-anim", action="store_true", help="don't extract animation clips"
    )
    live2dextract_parser.set_defaults(func=main_live2dextract)
    # spineextract
    spineextract_parser = subparsers.add_parser(
        "spineextract",
        usage="""Extract Sekai Spine (Esoteric Spine2D) Models in a AssetBundle""",
    )
    spineextract_parser.add_argument(
        "infile", type=str, help="input file", **gooey_only(widget="FileChooser")
    )
    spineextract_parser.add_argument(
        "outdir", type=str, help="output directory", **gooey_only(widget="DirChooser")
    )
    spineextract_parser.set_defaults(func=main_spineextract)
    # rla2json
    rla2json_parser = subparsers.add_parser(
        "rla2json",
        usage="""Read streaming_live/archive files and dump their information to JSON or HCA packets""",
    )
    rla2json_parser.add_argument(
        "input",
        type=str,
        help="input archive file or directory containing loose packets",
        **gooey_only(widget="FileChooser"),
    )
    rla2json_parser.add_argument(
        "outdir", type=str, help="output directory", **gooey_only(widget="DirChooser")
    )
    rla2json_parser.add_argument(
        "--version",
        type=str,
        help="RLA version. Only used for loose packets",
        default="1.6",
        choices=["1.%1s" % x for x in range(0, 6 + 1)],
    )
    rla2json_parser.add_argument(
        "--strict",
        action="store_true",
        help="strict mode. raise exception on unknown frame type or corrupt frames",
    )
    rla2json_parser.set_defaults(func=main_rla2json)
    # apphash
    apphash_parser = subparsers.add_parser(
        "apphash",
        usage="""Download/extract game AppHash values
*NOTE*: Only [app version] [app region] [app hash] are written to stdout if successful. Fields are separated by space. Unavailable fields are left as 'unknown'.""",
    )
    apphash_parser.add_argument(
        "--apk-src",
        type=str,
        help="APK source file (default: fetch from APKPure)",
        default=None,
        **gooey_only(widget="FileChooser"),
    )
    apphash_parser.add_argument(
        "--ab-src",
        type=str,
        help="AssetBundle (namely, 6350e2ec327334c8a9b7f494f344a761 or c726e51b6fe37463685916a1687158dd) source file (default: fetch from APK)",
        default=None,
        **gooey_only(widget="FileChooser"),
    )
    apphash_parser.add_argument(
        "--fetch", action="store_true", help="force fetching the latest APK"
    )
    apphash_parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        help="output format",
        default="markdown",
    )
    apphash_parser.add_argument(
        "--proxy",
        type=str,
        help="HTTP Proxy to use. This overrides the system proxy (environ HTTP_PROXY, HTTPS_PROXY) settings.",
        default=None,
    )
    apphash_parser.set_defaults(func=main_apphash)
    # mvdata
    mvdata_parser = subparsers.add_parser(
        "mvdata", usage="""Extract MV Data from AssetBundle"""
    )
    mvdata_parser.add_argument(
        "infile",
        type=str,
        help="cache directory (live_pv/mv_data)",
        **gooey_only(widget="DirChooser"),
    )
    mvdata_parser.add_argument(
        "outdir",
        type=str,
        help="output JSON file to dump into",
        **gooey_only(widget="FileSaver"),
    )
    mvdata_parser.set_defaults(func=main_mvdata)
    # moc3paths
    moc3paths_parser = subparsers.add_parser(
        "moc3paths", usage="""Extract animation path CRCs from raw .moc3 binaries"""
    )
    moc3paths_parser.add_argument(
        "indir", type=str, help="input directory", **gooey_only(widget="DirChooser")
    )
    moc3paths_parser.set_defaults(func=main_moc3paths)
    return parser


def __main__():
    from tqdm.std import tqdm as tqdm_c

    class TqdmMutexStream:
        @staticmethod
        def write(__s):
            with tqdm_c.external_write_mode(file=sys.stderr, nolock=False):
                return sys.stderr.write(__s)

    # parse args
    parser = create_parser(argparse.ArgumentParser)
    args = parser.parse_args()
    # set logging level
    import coloredlogs
    from logging import basicConfig

    coloredlogs.install(
        level=args.log_level,
        format="%(asctime)s | %(levelname).1s | %(name)s %(message)s",
        datefmt="%H:%M:%S",
        isatty=True,
        stream=TqdmMutexStream,
    )
    basicConfig(
        level=args.log_level,
        format="%(asctime)s | %(levelname).1s | %(name)s %(message)s",
        datefmt="%H:%M:%S",
        stream=TqdmMutexStream,
    )
    # override unity version
    sssekai_set_unity_version(args.unity_version)
    if "func" in args:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    __main__()
    sys.exit(0)
