from Crypto.Cipher import AES
from typing import Tuple


def PKCS7_pad(data: bytes, bs) -> bytes:
    size = bs - len(data) % bs
    return data + bytes([size] * size)


def PKCS7_unpad(data: bytes, bs) -> bytes:
    pad = data[-1]
    return data[:-pad]


def decrypt_aes_cbc(data: bytes, key, iv, unpad=PKCS7_unpad) -> bytes:
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(data), cipher.block_size)


def encrypt_aes_cbc(data: bytes, key, iv, pad=PKCS7_pad) -> bytes:
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(data, cipher.block_size))


SEKAI_APIMANAGER_KEYSETS = {
    "en": (
        b"\xdf8B\x14\xb2\x9a:\xdf\xbf\x1b\xd9\xee[\x16\xf8\x84",
        b"~\x85l\x90y\x87\xf8\xae\xc6\xaf\xc0\xc5G8\xfc~",
    ),
    "jp": (b"g2fcC0ZczN9MTJ61", b"msx3IV0i9XE5uYZ1"),
}


def encrypt(data: bytes, keyset: Tuple[bytes, bytes]) -> bytes:
    return encrypt_aes_cbc(data, *keyset, PKCS7_pad)


def decrypt(data: bytes, keyset: Tuple[bytes, bytes]) -> bytes:
    return decrypt_aes_cbc(data, *keyset, PKCS7_unpad)
