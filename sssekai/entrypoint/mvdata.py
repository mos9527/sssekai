from sssekai.unity.AssetBundle import load_assetbundle
from sssekai.abcache import AbCache, AbCacheConfig
import os
def main_mvdata(args):
    from UnityPy.enums import ClassIDType
    from pprint import pprint
    cache_dir = args.cache_dir
    cache_dir = os.path.expanduser(cache_dir)
    cache_dir = os.path.abspath(cache_dir)
    config = AbCacheConfig(cache_dir)
    cache = AbCache(config)
    mvdata_keys = filter(lambda x: x.startswith('live_pv/mv_data/'),cache.list_entry_keys())
    mvdata_items = list()
    mvdata_lut = dict()
    for key in mvdata_keys:
        entry = cache.query_entry(key)
        if entry.get_file_exists(config):
            path = entry.get_file_path(config)
            with open(path,'rb') as f:
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
    pprint(mvdata)
    