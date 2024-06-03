from typing import BinaryIO
from sssekai.crypto.AssetBundle import has_magic, decrypt

from . import UnityPy, sssekai_get_unity_version
from UnityPy import Environment

def load_assetbundle(file : BinaryIO) -> Environment:
    UnityPy.config.FALLBACK_VERSION_WARNED = True
    UnityPy.config.FALLBACK_UNITY_VERSION = sssekai_get_unity_version() 
    stream = file
    if has_magic(file):
        stream = decrypt(file)
    return UnityPy.load(stream)
