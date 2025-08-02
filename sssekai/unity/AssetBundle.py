from io import BytesIO
from sssekai.crypto.AssetBundle import decrypt_iter

from . import sssekai_get_unity_version
import UnityPy


def load_assetbundle(file: BytesIO) -> UnityPy.Environment:
    UnityPy.config.FALLBACK_UNITY_VERSION = sssekai_get_unity_version()
    stream = BytesIO()
    for block in decrypt_iter(lambda nbytes: file.read(nbytes)):
        stream.write(block)
    return UnityPy.load(stream)
