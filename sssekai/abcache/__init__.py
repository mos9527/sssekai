from pickle import load, dump
from typing import BinaryIO, List, Mapping, Union
from logging import getLogger
from dataclasses import dataclass, fields, is_dataclass
def fromdict(klass : type, d : Union[Mapping, List]):
    '''
    Recursively convert a dictionary to a dataclass instance, if applicable.
    https://stackoverflow.com/a/54769644
    https://gist.github.com/gatopeich/1efd3e1e4269e1e98fae9983bb914f22
    '''
    if is_dataclass(klass):       
        fieldtypes = {f.name:f.type for f in fields(klass)}
        return klass(**{f:fromdict(fieldtypes[f],d[f]) for f in d})
    if isinstance(d, list) and hasattr(klass, '__args__'):
        return [fromdict(klass.__args__[0],di) for di in d]
    if isinstance(d, dict) and hasattr(klass, '__args__'):
        return {k:fromdict(klass.__args__[1],v) for k,v in d.items()}
    return d

from requests import Session
from msgpack import unpackb, packb

from sssekai import __version__
from sssekai.unity import sssekai_get_unity_version
from sssekai.crypto.APIManager import decrypt, encrypt

logger = getLogger('sssekai.abcache')
@dataclass
class AbCacheConfig:
    app_version : str
    app_platform : str
    app_hash : str
@dataclass
class AbCacheEntry(dict):
    bundleName: str
    cacheFileName: str
    cacheDirectoryName: str
    hash: str
    category: str
    crc: int
    fileSize:int
    dependencies : List[str]
    paths : List[str]
    isBuiltin : bool
@dataclass
class AbCacheIndex(dict):
    version : str
    os : str
    bundles : Mapping[str, AbCacheEntry] = None
@dataclass
class SekaiAppVersion:
    systemProfile : str
    appVersion : str
    multiPlayVersion : str
    appVersionStatus : str
    assetVersion : str
    # These are sadly removed from 3.5.0
    _dataVersion : str = None 
    _appHash : str = None 
    _assetHash : str = None 
@dataclass
class SekaiSystemData:
    serverDate : int
    timezone : str
    profile : str
    maintenanceStatus : str
    appVersions : List[SekaiAppVersion]   

    _appVersionDict : dict = None
    @property
    def appVersionDict(self):
        if self._appVersionDict is None:
            self._appVersionDict = {av.appVersion:av for av in self.appVersions}
        return self._appVersionDict
@dataclass
class SekaiGameVersionData:
    profile : str
    assetbundleHostHash : str
    domain : str
@dataclass
class SekaiUserRegistrationData:
    userId : int
    signature : str
    platform : str
    deviceModel : str
    operatingSystem : str
    registeredAt : int
@dataclass
class SekaiUserData:
    userRegistration : SekaiUserRegistrationData
    credential : str
    updatedResources : dict
@dataclass
class SekaiUserAuthData:
    sessionToken: str
    appVersion: str
    multiPlayVersion: str
    dataVersion: str
    assetVersion: str
    removeAssetVersion: str
    assetHash: str
    appVersionStatus: str
    isStreamingVirtualLiveForceOpenUser: bool
    deviceId: str
    updatedResources: dict
    suiteMasterSplitPath: list

@dataclass
class SSSekaiDatabase:
    sekai_user_data : SekaiUserData = None
    sekai_user_auth_data : SekaiUserAuthData = None
    sekai_abcache_index  : AbCacheIndex = None
    sekai_system_data : SekaiSystemData  = None
    sekai_gameversion_data : SekaiGameVersionData  = None
class AbCacheBundleNotFoundError(Exception):
    bundleName : str
    def __init__(self, bundleName: str):
        self.bundleName = bundleName
        super().__init__('Bundle not found: %s' % bundleName)
class AbCache(Session):
    config : AbCacheConfig
    database : SSSekaiDatabase

    @property
    def SEKAI_APP_VERSION(self): return self.config.app_version
    @property
    def SEKAI_APP_PLATFORM(self): return self.config.app_platform
    @property
    def SEKAI_APP_HASH(self): return self.config.app_hash

    @property
    def SEKAI_ASSET_VERSION(self): return self.database.sekai_system_data.appVersionDict[self.SEKAI_APP_VERSION].assetVersion
    @property
    def SEKAI_AB_HASH(self): return self.database.sekai_user_auth_data.assetHash
    @property
    def SEKAI_AB_HOST_HASH(self): return self.database.sekai_gameversion_data.assetbundleHostHash
    @property
    def SEKAI_API_ENDPOINT(self): return 'https://production-game-api.sekai.colorfulpalette.org'
    @property
    def SEKAI_API_SYSTEM_DATA(self): return self.SEKAI_API_ENDPOINT + '/api/system'
    @property
    def SEKAI_API_USER(self): return self.SEKAI_API_ENDPOINT + '/api/user'
    @property
    def SEKAI_API_USER_AUTH(self): return f'{self.SEKAI_API_USER}/{self.database.sekai_user_data.userRegistration.userId}/auth?refreshUpdatedResources=False'
    @property
    def SEKAI_API_GAMEVERSION_ENDPOINT(self): return 'https://game-version.sekai.colorfulpalette.org'
    @property
    def SEKAI_AB_INFO_ENDPOINT(self): return f'https://production-{self.SEKAI_AB_HOST_HASH}-assetbundle-info.sekai.colorfulpalette.org/'
    @property
    def SEKAI_AB_ENDPOINT(self): return f'https://production-{self.SEKAI_AB_HOST_HASH}-assetbundle.sekai.colorfulpalette.org/'
    @property
    def SEKAI_AB_BASE_PATH(self): return f'{self.SEKAI_ASSET_VERSION}/{self.SEKAI_AB_HASH}/{self.config.app_platform}/'
    @property
    def SEKAI_AB_INDEX_PATH(self): return f'api/version/{self.SEKAI_ASSET_VERSION}/os/{self.config.app_platform}'
    @property
    def SEKAI_ISSUE_ENDPOINT(self): return 'https://issue.sekai.colorfulpalette.org'
    @property
    def SEKAI_ISSUE_SIGNATURE_ENDPOINT(self): return self.SEKAI_ISSUE_ENDPOINT + '/api/signature'

    @property
    def abcache_index(self): return self.database.sekai_abcache_index
    
    def _update_signatures(self):        
        logger.info('Updating signatures')
        resp = self.post(self.SEKAI_ISSUE_SIGNATURE_ENDPOINT)
        resp.raise_for_status()
        self.headers['Cookie'] = resp.headers['Set-Cookie'] 
        # HACK: Per RFC6265, Cookies should not be visible to subdomains since it's not set with Domain attribute (https://github.com/psf/requests/issues/2576)
        # But the other endpoints uses it nontheless. So we have to set it manually.

    def _update_user_data(self):
        logger.info('Updating user data')
        payload = {
            "platform": self.headers['X-Platform'],
            "deviceModel": self.headers['X-DeviceModel'],
            "operatingSystem": self.headers['X-OperatingSystem'],
        }
        payload = packb(payload)
        payload = encrypt(payload)
        resp = self.post(self.SEKAI_API_USER, data=payload)
        resp.raise_for_status()
        data = decrypt(resp.content)
        data = unpackb(data)
        self.database.sekai_user_data = fromdict(SekaiUserData,data)        

    def _update_user_auth_data(self):
        logger.info('Updating user auth data')
        payload = {
            "credential": self.database.sekai_user_data.credential,
            "deviceId" : None
        }
        payload = packb(payload)
        payload = encrypt(payload)        
        resp = self.put(self.SEKAI_API_USER_AUTH, data=payload)
        resp.raise_for_status()
        data = decrypt(resp.content)
        data = unpackb(data)        
        self.database.sekai_user_auth_data = fromdict(SekaiUserAuthData,data)
        
    def _update_system_data(self):
        logger.info('Updating system data')
        resp = self.get(self.SEKAI_API_SYSTEM_DATA)
        resp.raise_for_status()
        data = decrypt(resp.content)
        data = unpackb(data)
        self.database.sekai_system_data = fromdict(SekaiSystemData,data)

    def _update_gameversion_data(self):
        logger.info('Updating game version data')
        resp = self.get(self.SEKAI_API_GAMEVERSION_ENDPOINT + '/' + self.SEKAI_APP_VERSION + '/' + self.SEKAI_APP_HASH)
        resp.raise_for_status()
        data = decrypt(resp.content)
        data = unpackb(data)
        self.database.sekai_gameversion_data = fromdict(SekaiGameVersionData,data)
    
    def _update_abcache_index(self) -> AbCacheIndex:
        logger.info('Updating Assetbundle index')
        resp = self.get(
            url=self.SEKAI_AB_INFO_ENDPOINT + self.SEKAI_AB_INDEX_PATH
        )
        resp.raise_for_status()
        data = decrypt(resp.content)
        data = unpackb(data)
        self.database.sekai_abcache_index = fromdict(AbCacheIndex,data)   

    def __init__(self, config : AbCacheConfig) -> None:
        super().__init__()
        self.config = config
        self.config.app_platform = self.config.app_platform.lower()
        self.headers.update({
            'Accept': 'application/octet-stream',
            'Content-Type': 'application/octet-stream',
            'Accept-Encoding': 'deflate, gzip',
            'User-Agent': 'UnityPlayer/%s' % sssekai_get_unity_version(),
            'X-Platform': self.config.app_platform.capitalize(),
            'X-DeviceModel': 'sssekai/%s' % __version__,
            'X-OperatingSystem': self.config.app_platform.capitalize(),
            'X-Unity-Version': sssekai_get_unity_version(),
            'X-App-Version': self.SEKAI_APP_VERSION,
            'X-App-Hash': self.SEKAI_APP_HASH
        })
        self.database = SSSekaiDatabase()

    def update(self):
        logger.info('Updating metadata')        
        logger.debug('Set App version: %s (%s), hash=%s' % (self.config.app_version,self.config.app_platform, self.SEKAI_APP_HASH))
        self._update_signatures()
        self._update_gameversion_data()               
        self._update_user_data()
        self._update_user_auth_data()
        self._update_system_data()
        self._update_abcache_index()
        logger.debug('Sekai AssetBundle version: %s' % self.SEKAI_ASSET_VERSION)
        logger.debug('Sekai AssetBundle host hash: %s' % self.SEKAI_AB_HOST_HASH)


    def save(self, f : BinaryIO):
        logger.info('Saving cache')
        dump(self.database,f)

    def load(self, f : BinaryIO):
        logger.info('Loading cache')
        self.database = load(f)

    def __repr__(self) -> str:
        return f'<AbCache config={self.config} appVersion={self.SEKAI_APP_VERSION} bundles={len(self.abcache_index.bundles)}>'
    
    def update_download_headers(self):
        '''Update headers with the latest user auth data. Try to call this before downloading anything.'''
        self._update_signatures()
        return self.headers

    def get_entry_by_bundle_name(self, bundleName : str) -> AbCacheEntry:
        return self.abcache_index.bundles.get(bundleName, None)

    def get_entry_download_url(self, entry : AbCacheEntry):
        return self.SEKAI_AB_ENDPOINT + self.SEKAI_AB_BASE_PATH + entry.bundleName
    
    def get_or_update_dependency_tree_flatten(self, bundleName : str, deps : set = None):
        '''Get a flattened set of asset dependency bundle names (including itself) for a given entry.

        Returned order is topologically sorted.

        if 'deps' is provided, it will be used as the initial set of dependencies.
        '''        
        deps = deps or set()        
        def dfs(bundleName):                
            for dep in self.abcache_index.bundles[bundleName].dependencies:
                if dep not in deps:
                    dfs(dep)
                    deps.add(dep)
        dfs(bundleName)
        deps.add(bundleName)
        return deps
