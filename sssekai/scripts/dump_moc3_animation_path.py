from io import BytesIO
from sssekai.unity.AssetBundle import load_assetbundle
from sssekai.fmt.moc3 import read_moc3
import sys, os
from UnityPy.enums import ClassIDType

ParameterNames = set()
PartNames = set()
tree = os.walk(sys.argv[1])
for root, dirs, files in tree:
    for fname in files:
        file = os.path.join(root,fname)
        with open(file,'rb') as f:
            env = load_assetbundle(f)
            for obj in env.objects:
                if obj.type == ClassIDType.TextAsset:
                    data = obj.read()
                    out_name : str = data.name
                    if out_name.endswith('.moc3'):
                        parts, parameters = read_moc3(BytesIO(data.script.tobytes()))                        
                        ParameterNames.update(parameters)
                        PartNames.update(parts)
from zlib import crc32
print('NAMES_CRC_TBL = {')
for name in sorted(list(PartNames)):
    fullpath = 'Parts/' + name
    print('    %d:"%s",' % (crc32(fullpath.encode('utf-8')), fullpath))
for name in sorted(list(ParameterNames)):
    fullpath = 'Parameters/' + name
    print('    %d:"%s",' % (crc32(fullpath.encode('utf-8')), fullpath))    
print('}')