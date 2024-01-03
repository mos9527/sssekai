from sssekai.crypto.AssetBundle import SEKAI_AB_MAGIC
from sssekai.unity.AssetBundle import load_assetbundle

from os import path,remove,makedirs
def main_usmdemux(args):
    from UnityPy.enums import ClassIDType
    from wannacri.usm import Usm

    with open(args.infile,'rb') as f:
        env = load_assetbundle(f)    
        datas = dict()
        for obj in env.objects:
            if obj.type in {ClassIDType.MonoBehaviour, ClassIDType.TextAsset}:
                data = obj.read()
                datas[data.name] = data    
        movieInfo = datas.get('MovieBundleBuildData',None)
        assert movieInfo, "Invalid AssetBundle. No MovieBundleBuildData found!"
        movieInfo = movieInfo.read_typetree()
        usm_name = movieInfo['movieBundleDatas'][0]['usmFileName'][:-len('.bytes')]
        print('USM: %s' % usm_name)
        usm_folder = path.join(args.outdir,usm_name)
        makedirs(usm_folder,exist_ok=True)
        usm_temp = path.join(usm_folder,usm_name + '.tmp')
        with open(usm_temp,'wb') as usmstream:
            for data in movieInfo['movieBundleDatas']:
                usm = data['usmFileName'][:-len('.bytes')]
                usm = datas[usm]
                usmstream.write(usm.script)
        usm = Usm.open(usm_temp,encoding='shift-jis')
        usm.demux(path.join(args.outdir,usm_name),usm_name)
        remove(usm_temp)
        print('Saved to %s/' % usm_folder)