import sys
import zipfile
import UnityPy
import re

HASHREGEX = re.compile(b'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
env = UnityPy.Environment()

with zipfile.ZipFile(sys.argv[1], 'r') as zip_ref:    
    candidates = (
        (f,zip_ref.open(f)) for f in zip_ref.filelist if 
        f.filename.split('/')[-1] in {
            '6350e2ec327334c8a9b7f494f344a761', # PJSK Android
            'c726e51b6fe37463685916a1687158dd'  # PJSK iOS
        }
    )
    for candidate,stream in candidates:
        env.load_file(stream)
    for obj in env.objects:
        obj = obj.read()
        hashStr = HASHREGEX.finditer(obj.raw_data)
        for m in hashStr:
            print(m.group().decode(), obj.name)