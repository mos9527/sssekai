from typing import BinaryIO
from struct import unpack

# https://github.com/OpenL2D/moc3ingbird/blob/master/src/moc3.hexpat
def read_moc3(file: BinaryIO):
    '''Reads a MOC3 file and returns Part names and Parameter names

    Args:
        file (BinaryIO): File pointer

    Returns:
        tuple: (list[str], list[str]), Part names and Parameter names
    '''
    # Header: 64 bytes
    file.seek(0)
    assert file.read(4) == b'MOC3'
    version = unpack('<c',file.read(1))[0]
    isBigEndian = unpack('<b',file.read(1))[0]
    assert not isBigEndian
            
    # TODO: Other fields
    file.seek(0x40)
    pCountInfo = unpack('<I',file.read(4))[0]
    
    file.seek(pCountInfo)
    numParts = unpack('<I',file.read(4))[0]
    file.seek(0x10, 1)
    numParameters = unpack('<I',file.read(4))[0]

    file.seek(0x4C)
    pParts = unpack('<I',file.read(4))[0]

    file.seek(0x108)
    pParameters = unpack('<I',file.read(4))[0]
    
    def read_strings(offset, count):
        for i in range(0,count):
            file.seek(offset + i * 0x40)   
            buffer = bytearray()  
            while b := file.read(1)[0]:
                buffer.append(b)
            yield buffer.decode(encoding='utf-8')
    
    return list(read_strings(pParts,numParts)), list(read_strings(pParameters,numParameters))
