from Crypto.Cipher import AES
def PKCS7_pad(data : bytes,bs) -> bytes:
    size = (bs - len(data) % bs)
    return data + bytes([size] * size)

def PKCS7_unpad(data : bytes,bs) -> bytes:
    pad = data[-1]
    return data[:-pad]

def decrypt_aes_cbc(data : bytes, key, iv, unpad=PKCS7_unpad) -> bytes:
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(data), cipher.block_size)

def encrypt_aes_cbc(data : bytes, key, iv, pad=PKCS7_pad) -> bytes:
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(data, cipher.block_size))

SEKAI_APIMANAGER_KEY = b"g2fcC0ZczN9MTJ61"
SEKAI_APIMANAGER_IV = b"msx3IV0i9XE5uYZ1"
def encrypt(data : bytes) -> bytes:
    return encrypt_aes_cbc(data,SEKAI_APIMANAGER_KEY,SEKAI_APIMANAGER_IV, PKCS7_pad)

def decrypt(data : bytes) -> bytes:
    return decrypt_aes_cbc(data,SEKAI_APIMANAGER_KEY,SEKAI_APIMANAGER_IV, PKCS7_unpad)
