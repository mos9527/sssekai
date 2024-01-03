from typing import BinaryIO
from sssekai.crypto.AssetBundle import has_magic, decrypt

from . import UnityPy, SEKAI_UNITY_VERSION
from UnityPy import Environment

def load_assetbundle(file : BinaryIO) -> Environment:
    UnityPy.config.FALLBACK_VERSION_WARNED = True
    UnityPy.config.FALLBACK_UNITY_VERSION = SEKAI_UNITY_VERSION 
    stream = file
    if has_magic(file):
        stream = decrypt(file)
    return UnityPy.load(stream)
