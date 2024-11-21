from io import BytesIO
from typing import BinaryIO, Iterator

SEKAI_AB_MAGIC = b"\x10\x00\x00\x00"


def decrypt_header_inplace(header: bytearray):
    assert len(header) == 128
    for i in range(0, 128, 8):
        for j in range(5):
            header[i + j] = ~header[i + j] & 0xFF
    return header


def decrypt_iter(next_bytes: callable, block_size=65536):
    header = next_bytes(4)
    if header == SEKAI_AB_MAGIC:
        header = bytearray(next_bytes(128))
        header = decrypt_header_inplace(header)
    assert len(header) <= block_size, "impossible to satisfiy bs=%d" % block_size
    header_res = block_size - len(header)
    if header_res:
        header += next_bytes(header_res)
    yield header
    while block := next_bytes(block_size):
        yield block
