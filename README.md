# sssekai
```
usage: __main__.py [-h] {apidecrypt,abdecrypt,usmdemux,mitm} ...

SSSekai 世界计划缤纷舞台！ feat. 初音未来 （台服） MOD 工具

options:
  -h, --help            show this help message and exit

subcommands:
  valid subcommands

  {apidecrypt,abdecrypt,usmdemux,mitm}
                        additional help
    apidecrypt          API crypto dumper
                        This crypto applies to:
                            - API request/response body dumped by packet sniffer (mitmproxy, wireshark, etc.)
                            - AssetBundleInfo (can be found at /sdcard/Android/data/com.hermes.mk.asia/files/data/AssetBundleInfo)
    abdecrypt           Decrypt Sekai AssetBundle
                        These can be found at /sdcard/Android/data/com.hermes.mk.asia/files/data/
    usmdemux            Demux Sekai USM Video in a AssetBundle
                        NOTE: The AssetBundle MUST NOT be obfuscated. If so, debofuscate it with [abdecrypt] first
    mitm                Run Sekai API MITM proxy (WIP)
```
