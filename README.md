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
                                  that supports stripped Unity version (should be 2020.3.21f1. the version is ripped).
        live2dextract       Extract Sekai Live2D Models in a AssetBundle
        spineextract        Extract Sekai Spine (Esoteric Spine2D) Models in a AssetBundle
        mvdata              Query Sekai MV data from AssetBundle
        mitm                Run Sekai API MITM proxy (WIP)
# Documentations (WIP)
Supplementary instrutions for some of the scripts *(Yes I'm actually writing these now lol)*

*NOTE: You can always view the script's help output by invoking the script with `-h` switch. i.e.*
```
sssekai live2dextract -h
```
Have fun and good luck :)
## Acquiring Game Files
`abcache` was created for it, which allows one to cache *all* of the game's assets locally without pulling them out from the game's runtime or its own cache folder.
### Examples
- Caches the game data into `D:\Sekai`
  ```powershell
  sssekai abcache --cache-dir D:\Sekai
  ```
- Download game data for a *very specific* version into `D:\Sekai`
  ```powershell
  sssekai abcache --cache-dir D:\Sekai --platform android --version "3.5.0" --appHash "5e9fea31-2613-bd13-1723-9fe15156bd66"
  ```

### Known Game Versions And Their Respective Hashes
*NOTE: This table will probably remain not up-to-date and/or incomplete. PRs are welcome for additions.*

|platform|version|appHash|
|-|-|-|
|android|3.6.0|7558547e-4753-6ebd-03ff-168494c32769|
|ios|3.6.0|7558547e-4753-6ebd-03ff-168494c32769|
|android|3.5.0|5e9fea31-2613-bd13-1723-9fe15156bd66|
|ios|3.5.0|5e9fea31-2613-bd13-1723-9fe15156bd66|
#### Bonus: How to extract appHash from Android releases
- Acquire the game's APK file.
- Run [dump_android_pjsk_appHash.py](https://github.com/mos9527/sssekai/blob/main/sssekai/scripts/dump_android_pjsk_appHash.py) on it. For example:
```bash
python dump_android_pjsk_appHash.py pjsk_360.apk
```
- Which prints
```
7558547e-4753-6ebd-03ff-168494c32769 production_android
7558547e-4753-6ebd-03ff-168494c32769 production_android
7558547e-4753-6ebd-03ff-168494c32769 production_ios
```

## What Do These Files Do? (WIP)
There's a *ton* of them. Like ~45GB with version 3.5.0.(!) I'll try to document my limited findings here whenever possible 
### Spine2D Related Files
NOTE: You'll need Spine2D SDK 4.x to load these.
|Path|Purpose (Assumed)|
|-|-|
|area_sd|[Spine2D](https://esotericsoftware.com/) model files (it's those silly creatures you see in the menu screens). Can be extracted with `spineextract`|
### CriWare Related Files
NOTE: USM/HCA files, mainly. For the videos `usmdemux` can handle it by itself. For audio tracks try [vgmstream](https://github.com/vgmstream/vgmstream)!
|Path|Purpose (Assumed)|
|-|-|
|live/2dmode/original_mv|Video, Original PV/MVs for selected tracks. Can be extracted with `usmdemux`. Filenames are the MV IDs which can be queried by `mvdata`.|
|live/2dmode/sekai_mv|Video, PV/MVs tailor made for proseka, for selected tracks. Can be extracted with `usmdemux` Filenames are the MV IDs which can be queried by `mvdata`.|
|music/short|Audio, Preview track for the songs.|
|music/long|Audio, The (*ahem* still cut though) songs that plays in rhythm game or PV viewer.|
|music/jacket|Images! The cover art for the songs.|
### The Charts
You can find them in `music/music_score` in...[SUS Format?](https://gist.github.com/kb10uy/c171c175ba913dc40a73c6ce69da9859)

...Anyways, here are some tools you can use to view them
https://github.com/paralleltree/Ched

https://github.com/crash5band/MikuMikuWorld

*TODO: I'd be really glad to know how to import these back into the game or why is it called SUS for no apparent reasons (jk i love it lmao)*
### Live2D Related Files
NOTE: [Cubism's Live2D edtior comes with a viewer](https://www.live2d.com/en/cubism/download/editor/) which you can use to view these things
|Path|Purpose (Assumed)|
|-|-|
|live2d/model|[Cubism Live2D](https://www.live2d.com/) model files. Can be extracted with `live2dextract`|
|live2d/motion|Animation files for the models. Again, Can be extracted with `live2dextract`|
### 3D Asset Related Files
NOTE: Assets flagged with * can be imported by [sssekai_blender_io](https://github.com/mos9527/sssekai_blender_io) into [Blender](https://www.blender.org/)
|Path|Purpose (Assumed)|
|-|-|
|live_pv/mvdata|Metadata for the PVs. You can query them by name/id with `mvdata`|
|live_pv/model|3D Assets for real-time rendered PVs|
|live_pv/model/character|*Character models|
|live_pv/model/characterv2|**Cooler* character models. (these sport *slightly* more advanced NPR techniques like facial SDF but otherwise the mesh topology/material otherwise stays the same)|
|live_pv/model/stage|*Stage models.|
|live_pv/model/stage_decoration|*Things that makes the stage *cooler*. Per-PV. Can be queried by `mvdata`|
|live_pv/model/music_item|*PV Props. There aren't lots of those.|
And strangly enough there's another folder *outside* live_pv that also contains 3D assets. I'll put it here.
|Path|Purpose (Assumed)|
|-|-|
|model3d/model/stage_object|*PV Props, again. Those this time it's all instruments and it has the same aforementioned weighting issues.|

# See Also
https://github.com/mos9527/sssekai_blender_io