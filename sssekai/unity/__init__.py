import UnityPy, logging
logger = logging.getLogger(__name__)

DEFAULT_SEKAI_UNITY_VERSION = '2022.3.21f1'
_sssekai_unity_version = DEFAULT_SEKAI_UNITY_VERSION

def sssekai_get_unity_version():
    return _sssekai_unity_version

def sssekai_set_unity_version(value):    
    global _sssekai_unity_version
    if _sssekai_unity_version != value:        
        logger.warning(f'Setting Unity Version from {_sssekai_unity_version} to {value}')
        _sssekai_unity_version = value
