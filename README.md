# sssekai
这里是 https://mos9527.github.io/tags/project-sekai/ 的仓库
```
usage: __main__.py [-h] {apidecrypt,abdecrypt,mitm} ...

SSSekai 世界计划缤纷舞台！ feat. 初音未来 （台服） MOD 工具

options:
  -h, --help            show this help message and exit

subcommands:
  valid subcommands

  {apidecrypt,abdecrypt,mitm}
                        additional help
    apidecrypt          API crypto dumper
                        This crypto applies to:
                            - API request/response body dumped by packet sniffer (mitmproxy, wireshark, etc.)
                            - AssetBundleInfo (can be found at /sdcard/Android/data/com.hermes.mk.asia/files/data/AssetBundleInfo)
    abdecrypt           Decrypt Sekai AssetBundle
                        These can be found at /sdcard/Android/data/com.hermes.mk.asia/files/data/
    mitm                Run Sekai API MITM proxy (WIP)
```
