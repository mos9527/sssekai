from sssekai.crypto.AssetBundle import SEKAI_AB_MAGIC
from os import path,remove,makedirs
def main_usmdemux(args):
    import UnityPy
    from UnityPy.enums import ClassIDType
    UnityPy.config.FALLBACK_UNITY_VERSION = "2020.3.32f1" 
    from wannacri.usm import Usm

    with open(args.infile,'rb') as f:
        assert f.read(4) != SEKAI_AB_MAGIC, "AssetBundle is obfuscated. Debofuscate it with sssekai abdecrypt!"
        f.seek(0)
        env = UnityPy.load(f)        
        datas = dict()
        for obj in env.objects:
            if obj.type in {ClassIDType.MonoBehaviour, ClassIDType.TextAsset}:
                data = obj.read()
                datas[data.name] = data    
        movieInfo = datas.get('MovieBundleBuildData',None)
        assert movieInfo, "Invalid AssetBundle. No MovieBundleBuildData found!"
        tree = movieInfo.read_typetree()
        usm_name = tree['movieBundleDatas'][0]['usmFileName'][:-len('.bytes')]
        print('USM: %s' % usm_name)
        usm_folder = path.join(args.outdir,usm_name)
        makedirs(usm_folder,exist_ok=True)
        usm_temp = path.join(usm_folder,usm_name + '.tmp')
        with open(usm_temp,'wb') as usmstream:
            for data in tree['movieBundleDatas']:
                usm = data['usmFileName'][:-len('.bytes')]
                usm = datas[usm]
                usmstream.write(usm.script)
        usm = Usm.open(usm_temp,encoding='shift-jis')
        usm.demux(args.outdir,usm_name)
        remove(usm_temp)
        print('Saved to %s/' % usm_folder)