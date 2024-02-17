# sssekai
Command-line tool (w/Python API support) for downloading/deobfuscating the game's assets, along with some other tools.

    usage: sssekai [-h]
                  {apidecrypt,abdecrypt,usmdemux,abcache,live2dextract,mitm} ...

    SSSekai Proejct SEKAI feat. Hatsune Miku (Android) Modding Tools
    Installation:
        pip install git+https://github.com/mos9527/sssekai

    options:
      -h, --help            show this help message and exit

    subcommands:
      valid subcommands

      {apidecrypt,abdecrypt,usmdemux,abcache,live2dextract,mitm}
                            additional help
        apidecrypt          API crypto dumper
                            This crypto applies to:
                                - API request/response body dumped by packet sniffer (mitmproxy, wireshark, etc.)
                                - AssetBundleInfo (can be found at /sdcard/Android/data/com.hermes.mk.asia/files/data/AssetBundleInfo,or see sssekai.abcache)
        abdecrypt           Decrypt Sekai AssetBundle
                            These can be found at /sdcard/Android/data/com.hermes.mk.asia/files/data/
        usmdemux            Demux Sekai USM Video in a AssetBundle
        abcache             Sekai AssetBundle local cache
                            Downloads/Updates *ALL* PJSK JP assets to local devices.
                            NOTE: The assets can take quite a lot of space (est. 42.5GB for app version 3.3.1) so be prepared
                            NOTE: The AssetBundles *cached* are NOT OBFUSCATED. They can be used as is by various Unity ripping tools (and sssekai by extension)
                                  that supports stripped Unity version (should be 2020.3.21f1. the version is ripped).
        live2dextract       Extract Sekai Live2D Models in a AssetBundle
        mitm                Run Sekai API MITM proxy (WIP)

# Usage
Refer to the Wiki!
https://github.com/mos9527/sssekai/wiki （附带简中）

# See Also
https://github.com/mos9527/sssekai_blender_io