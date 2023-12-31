import codecs
import sys, os
import argparse
from sssekai.entrypoint.apidecrypt import main_apidecrypt
from sssekai.entrypoint.abdecrypt import main_abdecrypt
from sssekai.entrypoint.mitm import main_mitm
from sssekai.entrypoint.usmdemux import main_usmdemux
from sssekai.entrypoint.abcache import main_abcache, DEFAULT_CACHE_DIR
from sssekai.entrypoint.live2dextract import main_live2dextract
from sssekai.unity import SEKAI_UNITY_VERSION
def __main__():
    import coloredlogs
    from logging import basicConfig
    coloredlogs.install(
            level='INFO',
            fmt="%(asctime)s %(name)s [%(levelname).4s] %(message)s",
            isatty=True,
        )
    basicConfig(
        level='INFO', format="[%(levelname).4s] %(name)s %(message)s"
    )
    
    parser = argparse.ArgumentParser(description='''SSSekai Proejct SEKAI feat. Hatsune Miku (TW Android) Modding Tools
Installation:
    pip install git+https://github.com/mos9527/sssekai                                    
''', formatter_class=argparse.RawTextHelpFormatter)
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
    abcache_parser = subparsers.add_parser('abcache', help='''Sekai AssetBundle local cache
Downloads/Updates *ALL* PJSK TW assets to local devices.
NOTE: The assets can take quite a lot of space (est. 27GB) so be prepared
NOTE: The AssetBundles cached are NOT OBFUSCATED. They can be used as is by various Unity ripping tools (and sssekai by extension)
      that supports stripped Unity version (should be %s).''' % SEKAI_UNITY_VERSION)
    abcache_parser.add_argument('--cache-dir', type=str, help='cache directory',default=DEFAULT_CACHE_DIR)
    abcache_parser.add_argument('--skip-update',action='store_true',help='skip all updates and use cached assets as is.')
    abcache_parser.add_argument('--open', action='store_true',help='open cache directory. this will skip all updates.')
    abcache_parser.set_defaults(func=main_abcache)
    # live2dextract
    live2dextract_parser = subparsers.add_parser('live2dextract', help='''Extract Sekai Live2D Models in a AssetBundle''')
    live2dextract_parser.add_argument('infile', type=str, help='input file')
    live2dextract_parser.add_argument('outdir', type=str, help='output directory')
    live2dextract_parser.add_argument('--no-anim',action='store_true',help='don\'t extract animation clips')
    live2dextract_parser.set_defaults(func=main_live2dextract)
    # mitm
    mitm_parser = subparsers.add_parser('mitm', help='Run Sekai API MITM proxy (WIP)')
    mitm_parser.set_defaults(func=main_mitm)
    # parse args
    args = parser.parse_args()
    if 'func' in args:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    __main__()
    sys.exit(0)
