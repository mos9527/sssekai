import codecs
import sys, os
import argparse
from sssekai.entrypoint.apidecrypt import main_apidecrypt
from sssekai.entrypoint.abdecrypt import main_abdecrypt
from sssekai.entrypoint.mitm import main_mitm
from sssekai.entrypoint.usmdemux import main_usmdemux
from sssekai.entrypoint.abcache import main_abcache, DEFAULT_CACHE_DB_FILE, DEFAULT_SEKAI_APP_PLATFORM, DEFAULT_SEKAI_APP_VERSION, DEFAULT_SEKAI_APP_HASH
from sssekai.entrypoint.live2dextract import main_live2dextract
from sssekai.entrypoint.spineextract import main_spineextract
from sssekai.unity import sssekai_get_unity_version,sssekai_set_unity_version
def __main__():
    from tqdm.std import tqdm as tqdm_c
    class SemaphoreStdout:
        @staticmethod
        def write(__s):
            # Blocks tqdm's output until write on this stream is done
            # Solves cases where progress bars gets re-rendered when logs
            # spews out too fast
            with tqdm_c.external_write_mode(file=sys.stdout, nolock=False):
                return sys.stdout.write(__s)
    parser = argparse.ArgumentParser(description='''SSSekai Proejct SEKAI feat. Hatsune Miku (Android) Modding Tools
Installation:
    pip install sssekai                                    
''', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--log-level', type=str, help='logging level (default: %(default)s)', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    parser.add_argument('--unity-version', type=str, help='''Unity version to use (default: %(default)s)
Prior to game version 3.6.0, this has always been 2020.3.21f1
This has been changed to 2022.3.21f1 since, which would apply to all the assets from 3.6.0 onwards.
If you encounter any issues, try switching to the old version, or vice versa.''', default=sssekai_get_unity_version())
    subparsers = parser.add_subparsers(title='subcommands', description='valid subcommands', help='additional help')
    # apidecrypt
    apidecrypt_parser = subparsers.add_parser('apidecrypt', help='''API crypto dumper
This crypto applies to:
    - API request/response body dumped by packet sniffer (mitmproxy, wireshark, etc.)
    - AssetBundleInfo (can be found at /sdcard/Android/data/com.hermes.mk.asia/files/data/AssetBundleInfo,or see sssekai.abcache)''')
    apidecrypt_parser.add_argument('infile', type=str, help='input dump file')
    apidecrypt_parser.add_argument('outfile', type=str, help='output json file')
    apidecrypt_parser.set_defaults(func=main_apidecrypt)
    # abdecrypt
    abdecrypt_parser = subparsers.add_parser('abdecrypt', help='''Decrypt Sekai AssetBundle
These can be found at /sdcard/Android/data/com.hermes.mk.asia/files/data/                                             
''')
    abdecrypt_parser.add_argument('indir', type=str, help='input directory')
    abdecrypt_parser.add_argument('outdir', type=str, help='output directory')
    abdecrypt_parser.set_defaults(func=main_abdecrypt)
    # usmdemux
    usmdemux_parser = subparsers.add_parser('usmdemux', help='''Demux Sekai USM Video in a AssetBundle''')
    usmdemux_parser.add_argument('infile', type=str, help='input file')
    usmdemux_parser.add_argument('outdir', type=str, help='output directory')
    usmdemux_parser.set_defaults(func=main_usmdemux)
    # abcache
    abcache_parser = subparsers.add_parser('abcache', help='''Sekai AssetBundle Metadata Cache''')
    group = abcache_parser.add_argument_group('save/load options')
    group.add_argument('--db', type=str, help='''cache database file path (default: %(default)s)''',default=DEFAULT_CACHE_DB_FILE)
    group.add_argument('--no-update',action='store_true',help='skip all metadata updates and use cached ones as is.')
    group = abcache_parser.add_argument_group('game version options', 'NOTE: these options are used to *update* the cache database. Use --no-update to skip updating.')
    group.add_argument('--app-version', type=str, help='PJSK app version (default: %(default)s)', default=DEFAULT_SEKAI_APP_VERSION)
    group.add_argument('--app-platform', type=str, help='PJSK app platform (default: %(default)s)', default=DEFAULT_SEKAI_APP_PLATFORM)
    group.add_argument('--app-appHash', type=str, help='PJSK app hash (default: %(default)s)', default=DEFAULT_SEKAI_APP_HASH)
    group = abcache_parser.add_argument_group('download options')
    group.add_argument('--download-filter', type=str, help='filter AssetBundles (by bundle names) with this regex pattern',default=None)
    group.add_argument('--download-dir', type=str, help='asset bundle download directory. leave empty if you don\'t want to download anything',default='')
    group.add_argument('--download-ensure-deps',action='store_true',help='ensure dependencies (of the downloaded ones) are downloaded as well')
    group.add_argument('--download-workers', type=int, help='number of download workers (default: %(default)s)',default=4)
    abcache_parser.set_defaults(func=main_abcache)
    # live2dextract
    live2dextract_parser = subparsers.add_parser('live2dextract', help='''Extract Sekai Live2D Models in a AssetBundle''')
    live2dextract_parser.add_argument('infile', type=str, help='input file')
    live2dextract_parser.add_argument('outdir', type=str, help='output directory')
    live2dextract_parser.add_argument('--no-anim',action='store_true',help='don\'t extract animation clips')
    live2dextract_parser.set_defaults(func=main_live2dextract)
    # spineextract
    spineextract_parser = subparsers.add_parser('spineextract', help='''Extract Sekai Spine (Esoteric Spine2D) Models in a AssetBundle''')
    spineextract_parser.add_argument('infile', type=str, help='input file')
    spineextract_parser.add_argument('outdir', type=str, help='output directory')    
    spineextract_parser.set_defaults(func=main_spineextract)
    # mitm
    mitm_parser = subparsers.add_parser('mitm', help='Run Sekai API MITM proxy (WIP)')
    mitm_parser.set_defaults(func=main_mitm)
    # parse args
    args = parser.parse_args()
    # set logging level
    import coloredlogs
    from logging import basicConfig
    coloredlogs.install(
            level=args.log_level,
            fmt="%(asctime)s %(name)s [%(levelname).4s] %(message)s",
            isatty=True,
            stream=SemaphoreStdout
        )
    basicConfig(
        level=args.log_level, format="[%(levelname).4s] %(name)s %(message)s", stream=SemaphoreStdout
    )
    # override unity version
    sssekai_set_unity_version(args.unity_version)
    if 'func' in args:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    __main__()
    sys.exit(0)
