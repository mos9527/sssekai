import zipfile
import UnityPy
import argparse
import re

from io import BytesIO

HASHREGEX = re.compile(b'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')

def dump_axml_stringpool(f : BytesIO):
    read_int = lambda nbytes: int.from_bytes(f.read(nbytes), 'little')
    f.seek(8)
    hdr_type,hdr_size,size = read_int(2),read_int(2),read_int(4)
    n_strings = read_int(4)
    unk = read_int(4)
    flags = read_int(4)
    is_utf8 = flags & (1 << 8)
    string_offset = read_int(4) + 8
    unk = read_int(4)
    offsets = [read_int(4) for _ in range(n_strings)]
    for offset in offsets:
        f.seek(string_offset + offset)
        string_len = read_int(2)
        if is_utf8:
            string = f.read(string_len).decode('utf-8')
        else:
            string = f.read(string_len*2).decode('utf-16-le')
        yield string

def enum_candidates(zip_file, filter):
    return (
        (f,zip_file.open(f),zip_file) for f in zip_file.filelist if filter(f.filename)
    )

def enum_package(zip_file):
    yield zip_file
    for f in zip_file.filelist:        
        if f.filename.lower().endswith('.apk'):
            yield zipfile.ZipFile(zip_file.open(f)) 

def main_apphash(args):
    env = UnityPy.Environment()
    if not args.apk_src or args.fetch:
        from requests import get
        src = BytesIO()
        print('Fetching latest game package from APKPure')
        resp = get('https://d.apkpure.net/b/XAPK/com.sega.pjsekai?version=latest', stream=True)
        size = resp.headers.get('Content-Length',-1)
        for chunck in resp.iter_content(chunk_size=2**10):
            src.write(chunck)
            print('Downloading %d/%s' % (src.tell(), size), end='\r')
        print()
        src.seek(0)
    else:
        src = open(args.apk_src, 'rb')
    with zipfile.ZipFile(src, 'r') as zip_ref:
        manifests = [manifest for package in enum_package(zip_ref) for manifest in enum_candidates(package, lambda fn: fn == 'AndroidManifest.xml')]
        manifest = manifests[0][1]
        manifest_strings = list(dump_axml_stringpool(manifest))
        for i in range(len(manifest_strings)): 
            if 'STAMP_TYPE_' in manifest_strings[i]:
                print('Package Type:', manifest_strings[i])
                print('Version:', manifest_strings[i - 2])
                break
        candidates = [candidate for package in enum_package(zip_ref) for candidate in enum_candidates(
            package, lambda fn: fn.split('/')[-1] in {
            '6350e2ec327334c8a9b7f494f344a761', # PJSK Android
            'c726e51b6fe37463685916a1687158dd'  # PJSK iOS
        })]
        for candidate,stream,_ in candidates:
            env.load_file(stream)
        for obj in env.objects:
            obj = obj.read()
            hashStr = HASHREGEX.finditer(obj.raw_data)
            for m in hashStr:
                print(m.group().decode(), obj.name)