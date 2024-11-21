from typing import BinaryIO
from sssekai.crypto.AssetBundle import decrypt_iter

from . import UnityPy, sssekai_get_unity_version
from UnityPy import Environment


def load_assetbundle(file: BinaryIO) -> Environment:
    UnityPy.config.FALLBACK_VERSION_WARNED = True
    UnityPy.config.FALLBACK_UNITY_VERSION = sssekai_get_unity_version()
    stream = BinaryIO()
    for block in decrypt_iter(lambda nbytes: file.read(nbytes)):
        stream.write(block)
    return UnityPy.load(stream)
