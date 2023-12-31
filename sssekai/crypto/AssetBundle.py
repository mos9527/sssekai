from typing import BinaryIO
def decrypt(fin : BinaryIO, fout : BinaryIO) -> None:      
    magic = fin.read(4)    
    if magic == b'\x10\x00\x00\x00':
        for _ in range(0,128,8):
            block = bytearray(fin.read(8))
            for i in range(5):
                block[i] = ~block[i] & 0xff
            fout.write(block)
        while (block := fin.read(8)):
            fout.write(block)    
    else:
        fin.seek(0)
        while (block := fin.read(8)):
            fout.write(block)

def encrypt(fin, fout):
    raise NotImplementedError
