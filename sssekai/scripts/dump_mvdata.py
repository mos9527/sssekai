from sssekai.unity.AssetBundle import load_assetbundle
from sssekai.abcache import AbCache, AbCacheConfig
import os, json
def main_mvdata(args):
    from UnityPy.enums import ClassIDType
    cache_dir = args.cache_dir
    cache_dir = os.path.expanduser(cache_dir)
    cache_dir = os.path.abspath(cache_dir)
    os.chdir(cache_dir)
    mvdata_keys = os.listdir(cache_dir)
    mvdata_items = list()
    mvdata_lut = dict()
    for key in mvdata_keys:
        with open(key,'rb') as f:
            env = load_assetbundle(f)
            for obj in env.objects:
                if obj.type == ClassIDType.MonoBehaviour:
                    data = obj.read()
                    if data.name == 'data':               
                        index = len(mvdata_items)
                        mvdata_items.append(data.read_typetree())
                        mvdata_lut[str(data.name)] = index
                        mvdata_lut[str(data.id)] = index
                        break
    mvdata = mvdata_items[mvdata_lut[args.query]]
    print(json.dumps(mvdata, indent=4,ensure_ascii=False))

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Dump MVData')
    parser.add_argument('cache_dir', help='live_pv\mv_data directory. Downloaded by sssekai abcache.')
    parser.add_argument('query', help='Query')
    args = parser.parse_args()
    main_mvdata(args)