# sssekai
Command-line tool (w/Python API support) for downloading/deobfuscating the game's assets, along with some other tools.

    usage: sssekai [-h]
                  {apidecrypt,abdecrypt,usmdemux,abcache,live2dextract,mitm} ...

    SSSekai Proejct SEKAI feat. Hatsune Miku (Android) Modding Tools
    Installation:
        pip install sssekai

    options:
      -h, --help            show this help message and exit
      --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                            logging level (default: INFO)
      --unity-version UNITY_VERSION
                            Unity version to use (default: 2022.3.21f1)
                            Prior to game version 3.6.0, this has always been 2020.3.21f1
                            This has been changed to 2022.3.21f1 since, which would apply to all the assets from 3.6.0 onwards.
                            If you encounter any issues, try switching to the old version, or vice versa.

    subcommands:
      valid subcommands

      {apidecrypt,abdecrypt,usmdemux,abcache,live2dextract,spineextract,mvdata,mitm}
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
                                  that supports stripped Unity version (should be 2022.3.21f1. the version is ripped).
        live2dextract       Extract Sekai Live2D Models in a AssetBundle
        spineextract        Extract Sekai Spine (Esoteric Spine2D) Models in a AssetBundle
        mvdata              Query Sekai MV data from AssetBundle
        mitm                Run Sekai API MITM proxy (WIP)

# Documentations
See the [wiki page!](https://github.com/mos9527/sssekai/wiki)
# See Also
https://github.com/mos9527/sssekai_blender_io