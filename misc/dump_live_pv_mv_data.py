import sys, os, json
from sssekai.unity.AssetBundle import load_assetbundle

if len(sys.argv) != 3:
    print('usage: python dump_live_pv_mv_data.py <assetbundle directory> <dest json>')
else:
    contents = dict()
    for file in os.listdir(sys.argv[1]):        
        with open(os.path.join(sys.argv[1], file), 'rb') as f:
            try:
                ab = load_assetbundle(f)
            except:
                continue
            for obj in ab.objects:
                data = obj.read()
                if data.name == 'data':
                    contents[file] = data.read_typetree()
    with open(sys.argv[2], 'w', encoding='utf-8') as f:
        json.dump(contents, f, ensure_ascii=False, indent=4)