import sys, os
import argparse
from sssekai.entrypoint.apidecrypt import main_apidecrypt
from sssekai.entrypoint.abdecrypt import main_abdecrypt
from sssekai.entrypoint.mitm import main_mitm
from sssekai.entrypoint.usmdemux import main_usmdemux
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
    
    parser = argparse.ArgumentParser(description='SSSekai 世界计划缤纷舞台！ feat. 初音未来 （台服） MOD 工具', formatter_class=argparse.RawTextHelpFormatter)
    subparsers = parser.add_subparsers(title='subcommands', description='valid subcommands', help='additional help')
    # apidecrypt
    apidecrypt_parser = subparsers.add_parser('apidecrypt', help='''API crypto dumper
This crypto applies to:
    - API request/response body dumped by packet sniffer (mitmproxy, wireshark, etc.)
    - AssetBundleInfo (can be found at /sdcard/Android/data/com.hermes.mk.asia/files/data/AssetBundleInfo)''')
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
    usmdemux_parser = subparsers.add_parser('usmdemux', help='''Demux Sekai USM Video in a AssetBundle
NOTE: The AssetBundle MUST NOT be obfuscated. If so, debofuscate it with [abdecrypt] first
''')
    usmdemux_parser.add_argument('infile', type=str, help='input file')
    usmdemux_parser.add_argument('outdir', type=str, help='output directory')
    usmdemux_parser.set_defaults(func=main_usmdemux)
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
