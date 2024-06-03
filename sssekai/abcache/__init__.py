from os import path, remove, makedirs, stat
from typing import List, Mapping
from dataclasses import dataclass, asdict
from requests import Session
from logging import getLogger
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from sssekai import __version__
from sssekai.unity import sssekai_get_unity_version
logger = getLogger('sssekai.abcache')

from sssekai.crypto.APIManager import decrypt, encrypt
from sssekai.crypto.AssetBundle import decrypt_headaer_inplace, SEKAI_AB_MAGIC
from msgpack import unpackb, dump, load, packb
from tqdm import tqdm
DEFAULT_CACHE_DIR = '~/.sssekai/abcache'
DOWNLOADER_WORKER_COUNT = 8
DEFAULT_FILESIZE_MATCH_RATIO = 1.5

DEFAULT_SEKAI_APP_VERSION = '3.6.0'
DEFAULT_SEKAI_APP_HASH = '7558547e-4753-6ebd-03ff-168494c32769'
DEFAULT_SEKAI_APP_PLATFORM = 'android'

class AbCacheDownloader(ThreadPoolExecutor):
    session : Session
    progress : tqdm = None
    def _ensure_progress(self):
        if not self.progress:
            self.progress = tqdm(bar_format="{desc}: {percentage:.1f}%|{bar}| {n_fmt}/{total_fmt} {rate_fmt} {elapsed}<{remaining}", total=0,unit='B', unit_scale=True, unit_divisor=1024,desc="Downloading")
    def _download(self, url, fname, length):
        self._ensure_progress()
        RETRIES = 1
        for _ in range(0,RETRIES):
            try:
                resp = self.session.get(url,stream=True)
                resp.raise_for_status()
                makedirs(path.dirname(fname),exist_ok=True)
                with open(fname, 'wb') as f:
                    magic = next(resp.iter_content(4))
                    self.progress.update(4)
                    if magic == SEKAI_AB_MAGIC:
                        header = next(resp.iter_content(128))            
                        self.progress.update(128)
                        f.write(decrypt_headaer_inplace(bytearray(header)))
                    else:
                        f.write(magic)                
                    for chunk in resp.iter_content(65536):
                        self.progress.update(len(chunk))
                        f.write(chunk)
                    return
            except Exception as e:
                logger.error('While downloading %s : %s. Retrying' % (url,e))
        if _ == RETRIES - 1:
            logger.critical('Did not download %s' % url)
        self._ensure_progress()
    def __init__(self, session) -> None:
        self.session = session        
        super().__init__(max_workers=DOWNLOADER_WORKER_COUNT)
    def add_link(self, url, fname, length):
        self._ensure_progress()
        self.progress.total += length
        return self.submit(self._download, url, fname, length)

@dataclass
class AbCacheConfig:
    cache_dir : str # absolute path to cache directory
    app_version : str = None
    app_platform : str = None
    app_hash : str  = None

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

    def up_to_date(self, config: AbCacheConfig, other) -> bool:
        return (
            self.hash == other.hash and 
            self.get_file_exists(config) and 
            (other.fileSize / max(1,self.get_file_size(config)) < DEFAULT_FILESIZE_MATCH_RATIO)
        )
        # HACK: we don't have proper hash checking yet. so we just check if the file exists and
        # the file size roughly matches

    def get_file_size(self, config: AbCacheConfig):
        if self.get_file_exists(config):
            return stat(self.get_file_path(config)).st_size
        else:
            return 0

    def get_file_exists(self, config: AbCacheConfig) -> bool:
        return path.exists(self.get_file_path(config))
    
    def get_file_path(self, config: AbCacheConfig) -> str:
        return path.join(config.cache_dir, self.bundleName)
@dataclass
class AbCacheIndex(dict):
    version : str = 'unknown'
    os : str = 'android'
    bundles : Mapping[str, AbCacheEntry] = None
    def get_bundle_by_abcache_path(self, config: AbCacheConfig, fpath) -> AbCacheEntry | None:
        # "C:\Users\mos9527\.sssekai\abcache\title_screen\anniversary_2nd_bg"
        fpath = Path(fpath)
        cpath = Path(config.cache_dir)
        assert fpath.is_relative_to(cpath), "File provided is not inside the cache"
        relpath = fpath.relative_to(cpath).as_posix()
        return self.bundles.get(relpath,None)    
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

    def get_app_version_by_app(self, app: str) -> SekaiAppVersion | None:        
        for av in self.appVersions:
            if app in av.appVersion:
                return av
        return None
    
    def get_app_version_latest(self):
        return self.appVersions[-1]
    
    def list_app_versions(self) -> List[str]:
        return [av.appVersion for av in self.appVersions]
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
class AbCache(Session):    
    downloader : AbCacheDownloader

    config : AbCacheConfig
    local_abcache_index : AbCacheIndex  = None

    sekai_user_data : SekaiUserData = None
    sekai_user_auth_data : SekaiUserAuthData = None
    sekai_abcache_index  : AbCacheIndex = None
    sekai_system_data : SekaiSystemData  = None
    sekai_gameversion_data : SekaiGameVersionData  = None

    @property
    def SEKAI_APP_VERSION(self): return self.config.app_version
    @property
    def SEKAI_APP_HASH(self): return self.config.app_hash

    @property
    def SEKAI_ASSET_VERSION(self): return self.sekai_system_data.get_app_version_by_app(self.SEKAI_APP_VERSION).assetVersion
    @property
    def SEKAI_AB_HASH(self): return self.sekai_user_auth_data.assetHash
    @property
    def SEKAI_AB_HOST_HASH(self): return self.sekai_gameversion_data.assetbundleHostHash
    @property
    def SEKAI_API_ENDPOINT(self): return 'https://production-game-api.sekai.colorfulpalette.org'
    @property
    def SEKAI_API_SYSTEM_DATA(self): return self.SEKAI_API_ENDPOINT + '/api/system'
    @property
    def SEKAI_API_USER(self): return self.SEKAI_API_ENDPOINT + '/api/user'
    @property
    def SEKAI_API_USER_AUTH(self): return f'{self.SEKAI_API_USER}/{self.sekai_user_data.userRegistration.userId}/auth?refreshUpdatedResources=False'
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

    def update_signatures(self):
        logger.info('Updating signatures')
        resp = self.post(self.SEKAI_ISSUE_SIGNATURE_ENDPOINT)
        resp.raise_for_status()
        self.headers['Cookie'] = resp.headers['Set-Cookie'] 
        # HACK: Per RFC6265, Cookies should not be visible to subdomains since it's not set with Domain attribute (https://github.com/psf/requests/issues/2576)
        # But the other endpoints uses it nontheless. So we have to set it manually.

    def update_user_data(self):
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
        self.sekai_user_data = SekaiUserData(**data)
        self.sekai_user_data.userRegistration = SekaiUserRegistrationData(**self.sekai_user_data.userRegistration)

    def update_user_auth_data(self):
        logger.info('Updating user auth data')
        payload = {
            "credential": self.sekai_user_data.credential,
            "deviceId" : None
        }
        payload = packb(payload)
        payload = encrypt(payload)        
        resp = self.put(self.SEKAI_API_USER_AUTH, data=payload)
        resp.raise_for_status()
        data = decrypt(resp.content)
        data = unpackb(data)        
        self.sekai_user_auth_data = SekaiUserAuthData(**data)
        
    def update_system_data(self):
        logger.info('Updating system data')
        resp = self.get(self.SEKAI_API_SYSTEM_DATA)
        resp.raise_for_status()
        data = decrypt(resp.content)
        data = unpackb(data)
        self.sekai_system_data = SekaiSystemData(**data)
        for i, appVersion in enumerate(self.sekai_system_data.appVersions):
            self.sekai_system_data.appVersions[i] = SekaiAppVersion(**appVersion)

    def update_gameversion_data(self):
        logger.info('Updating game version data')
        resp = self.get(self.SEKAI_API_GAMEVERSION_ENDPOINT + '/' + self.SEKAI_APP_VERSION + '/' + self.SEKAI_APP_HASH)
        resp.raise_for_status()
        data = decrypt(resp.content)
        data = unpackb(data)
        self.sekai_gameversion_data = SekaiGameVersionData(**data)
    
    def update_abcache_index(self) -> AbCacheIndex:
        logger.info('Updating Assetbundle index')
        resp = self.get(
            url=self.SEKAI_AB_INFO_ENDPOINT + self.SEKAI_AB_INDEX_PATH
        )
        resp.raise_for_status()
        data = decrypt(resp.content)
        data = unpackb(data)
        self.sekai_abcache_index = cache = AbCacheIndex(**data)
        for k,v in cache.bundles.items():
            cache.bundles[k] = AbCacheEntry(**v)         

    def list_entry_keys(self) -> List[str]:
        return self.local_abcache_index.bundles.keys()

    def query_entry(self, bundleName : str) -> AbCacheEntry | None:
        return self.local_abcache_index.bundles.get(bundleName, None)

    def queue_update_cache_entry(self, entry : AbCacheEntry, new_entry : AbCacheEntry = None):
        if new_entry:
            entry = new_entry
        return self.downloader.add_link(
            self.SEKAI_AB_ENDPOINT + self.SEKAI_AB_BASE_PATH + entry.bundleName,
            entry.get_file_path(self.config),
            entry.fileSize
        )

    def queue_update_cache_entry_full(self):        
        all_keys = sorted(list({k for k in self.sekai_abcache_index.bundles.keys()}.union({k for k in self.local_abcache_index.bundles.keys()})))
        update_count = 0
        for k in all_keys:
            if k in self.sekai_abcache_index.bundles and k in self.local_abcache_index.bundles:
                # update
                if not self.sekai_abcache_index.bundles[k].up_to_date(self.config,self.local_abcache_index.bundles[k]):
                    logger.debug('Updating bundle %s. (size on disk=%d, reported=%d)' % (k, self.local_abcache_index.bundles[k].get_file_size(self.config), self.local_abcache_index.bundles[k].fileSize))
                    self.queue_update_cache_entry(self.local_abcache_index.bundles[k], self.sekai_abcache_index.bundles[k])
                    update_count+=1
                else:                    
                    pass
            elif k in self.sekai_abcache_index.bundles: 
                # append
                logger.debug('Adding bundle %s', k)
                self.local_abcache_index.bundles[k] = self.sekai_abcache_index.bundles[k]
                self.queue_update_cache_entry(self.local_abcache_index.bundles[k])
                update_count+=1
            else: 
                # removal
                logger.debug('Removing bundle %s', k)
                if path.exists(self.local_abcache_index.bundles[k].get_file_path(self.config)):
                    remove(self.local_abcache_index.bundles[k].get_file_path(self.config))
                del self.local_abcache_index.bundles[k]
        logger.debug('Saving AssetBundle index')
        self.save()
        logger.debug('Queued %d updates' % update_count)

    def wait_for_downloads(self):       
        self.downloader = AbCacheDownloader(self)

    def cancel_downloads(self):
        self.downloader.shutdown(wait=False, cancel_futures=True)
        self.wait_for_downloads()
    
    def update_metadata(self):
        logger.info('Updating metadata')
        logger.debug('Cache directory: %s' % self.config.cache_dir)
        logger.debug('Set App version: %s (%s), hash=%s' % (self.config.app_version,self.config.app_platform, self.SEKAI_APP_HASH))
        self.update_signatures()
        self.update_gameversion_data()               
        self.update_user_data()
        self.update_user_auth_data()
        self.update_system_data()
        self.update_abcache_index()
        logger.debug('Sekai AssetBundle version: %s' % self.SEKAI_ASSET_VERSION)
        logger.debug('Sekai AssetBundle host hash: %s' % self.SEKAI_AB_HOST_HASH)

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
        self.downloader = AbCacheDownloader(self)
        makedirs(self.config.cache_dir,exist_ok=True)
        try:
            self.load()
        except Exception as e:
            logger.warning('Failed to load cache index. Creating a new one. (%s)' % e)
            self.local_abcache_index = AbCacheIndex(bundles=dict())
            self.save()
    
    def save(self):
        with open(path.join(self.config.cache_dir, 'abindex'),'wb') as f:
            dump(asdict(self.local_abcache_index), f)
            logger.info("Saved %d entries to cache index" % len(self.local_abcache_index.bundles))

    def load(self):
        with open(path.join(self.config.cache_dir, 'abindex'), 'rb') as f:
            self.local_abcache_index = AbCacheIndex(**load(f, raw=False))
            for k,v in self.local_abcache_index.bundles.items():
                self.local_abcache_index.bundles[k] = AbCacheEntry(**v)
            logger.info("Loaded %d entries from cache index" % len(self.local_abcache_index.bundles))
