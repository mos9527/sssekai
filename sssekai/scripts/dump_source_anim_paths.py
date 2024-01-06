import sys
paths = set()
with open(sys.argv[1],'r',encoding='utf-8') as f:
    while line := f.readline():
        line = line.strip()
        if 'path:' in line or 'attribute:' in line:
            path = line.split(':')[-1]
            paths.add(path)

from zlib import crc32
print('NAMES_CRC_TBL = {')
for path in sorted(list(paths)):
    print('    %d:"%s",' % (crc32(path.encode('utf-8')), path))
print('}')