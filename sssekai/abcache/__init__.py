from os import path, remove, makedirs, stat
from typing import List, Mapping
from dataclasses import dataclass, asdict
from requests import Session
from logging import getLogger
from json import dump, load
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
logger = getLogger('sssekai.abcache')

from sssekai.crypto.APIManager import decrypt
from sssekai.crypto.AssetBundle import decrypt_headaer_inplace, SEKAI_AB_MAGIC
from msgpack import unpackb
from tqdm import tqdm
DEFAULT_CACHE_DIR = '~/.sssekai/abcache'
DEFAULT_SEKAI_VERSION = '3.3.1'
DEFAULT_SEKAI_PLATFORM = 'android'

DOWNLOADER_WORKER_COUNT = 8
class ThreadpoolDownloader(ThreadPoolExecutor):
    session : Session
    progress : tqdm

    def download(self, url, fname, length):
        RETRIES = 1
        for _ in range(0,RETRIES):
            try:
                resp = self.session.get(url,stream=True)
                resp.raise_for_status()
                makedirs(path.dirname(fname),exist_ok=True)
                with open(fname, 'wb') as f:
                    magic = next(resp.iter_content(4))
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
    def add_link(self, url, fname, length):
        self.progress.total += length
        return self.submit(self.download, url, fname, length)
    def __init__(self, session = None) -> None:
        self.session = session or Session()
        self.progress = tqdm(bar_format="{desc}: {percentage:.1f}%|{bar}| {n_fmt}/{total_fmt} {rate_fmt} {elapsed}<{remaining}", total=0,unit='B', unit_scale=True, unit_divisor=1024,desc="Downloading")
        super().__init__(max_workers=DOWNLOADER_WORKER_COUNT)

class AbCacheConfig:
    app_version : str
    app_platform : str

    cache_dir : str # absolute path to cache directory
    downloader : ThreadpoolDownloader
    def __init__(self, downloader : ThreadpoolDownloader, cache_dir: str = DEFAULT_CACHE_DIR, version: str = DEFAULT_SEKAI_VERSION, platform : str = DEFAULT_SEKAI_PLATFORM) -> None:
        self.cache_dir = path.expanduser(cache_dir)
        self.cache_dir = path.abspath(self.cache_dir)
        self.downloader = downloader
        self.app_version = version
        self.app_platform = platform
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
        return self.hash == other.hash and self.get_file_exists(config)
        # HACK: we don't have proper hash checking yet. so we just check if the file exists.
        # The file size isn't a useful predicate, also. Some files will have incorrect file size (compared to the ab cache report)

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
    dataVersion : str
    assetVersion : str
    appHash : str
    assetHash : str
    appVersionStatus : str
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
    
    def list_app_versions(self) -> List[str]:
        return [av.appVersion for av in self.appVersions]
@dataclass
class SekaiGameVersionData:
    profile : str
    assetbundleHostHash : str
    domain : str
class AbCache(Session):    
    config : AbCacheConfig
    index : AbCacheIndex
    
    sekai_system_data : SekaiSystemData
    sekai_gameversion_data : SekaiGameVersionData

    @property
    def SEKAI_APP_VERSION(self): 
        version = self.sekai_system_data.get_app_version_by_app(self.config.app_version)
        assert version, "Incorrect app version %s. Please choose from: %s" % (self.config.app_version, ', '.join(self.sekai_system_data.list_app_versions()))
        return version
    @property
    def SEKAI_ASSET_VERSION(self): return self.SEKAI_APP_VERSION.assetVersion
    @property
    def SEKAI_AB_HASH(self): return self.SEKAI_APP_VERSION.assetHash
    @property
    def SEKAI_AB_HOST_HASH(self): return self.sekai_gameversion_data.assetbundleHostHash
    @property
    def SEKAI_API_ENDPOINT(self): return 'https://production-game-api.sekai.colorfulpalette.org'
    @property
    def SEKAI_API_SYSTEM_DATA(self): return self.SEKAI_API_ENDPOINT + '/api/system'
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
        resp = self.get(self.SEKAI_API_GAMEVERSION_ENDPOINT + '/' + self.SEKAI_APP_VERSION.appVersion + '/' + self.SEKAI_APP_VERSION.appHash)
        resp.raise_for_status()
        data = decrypt(resp.content)
        data = unpackb(data)
        self.sekai_gameversion_data = SekaiGameVersionData(**data)
    
    def download_cache_index(self) -> AbCacheIndex:
        logger.info('Downloading Asset Bundle Index')
        resp = self.get(
            url=self.SEKAI_AB_INFO_ENDPOINT + self.SEKAI_AB_INDEX_PATH
        )
        resp.raise_for_status()
        data = decrypt(resp.content)
        data = unpackb(data)
        cache = AbCacheIndex(**data)
        for k,v in cache.bundles.items():
            cache.bundles[k] = AbCacheEntry(**v)
        return cache

    def update_cahce_entry(self, entry : AbCacheEntry, new_entry : AbCacheEntry = None):
        if new_entry:
            entry = new_entry
        return self.config.downloader.add_link(
            self.SEKAI_AB_ENDPOINT + self.SEKAI_AB_BASE_PATH + entry.bundleName,
            entry.get_file_path(self.config),
            entry.fileSize
        )
                
    def update_cahce_index(self):
        logger.info('Updating Asset Bundle Index')
        dl = self.download_cache_index()
        all_keys = sorted(list({k for k in dl.bundles.keys()}.union({k for k in self.index.bundles.keys()})))
        update_count = 0
        for k in all_keys:
            if k in dl.bundles and k in self.index.bundles:
                # update
                if not dl.bundles[k].up_to_date(self.config, self.index.bundles[k]):
                    logger.info('Updating bundle %s. (size on disk=%d, reported=%d)' % (k, self.index.bundles[k].get_file_size(self.config), self.index.bundles[k].fileSize))
                    self.update_cahce_entry(self.index.bundles[k], dl.bundles[k])
                    update_count+=1
                else:
                    logger.debug('Bundle %s is up to date' % k)
                    pass
            elif k in dl.bundles: 
                # append
                logger.debug('Adding bundle %s', k)
                self.index.bundles[k] = dl.bundles[k]
                self.update_cahce_entry(self.index.bundles[k])
                update_count+=1
            else: 
                # removal
                logger.info('Removing bundle %s', k)
                if path.exists(self.index.bundles[k].get_file_path(self.config)):
                    remove(self.index.bundles[k].get_file_path(self.config))
                del self.index.bundles[k]
        logger.info('Saving AssetBundle index')
        self.save()
        logger.info('...Saved. Need %d updates' % update_count)
        self.config.downloader.shutdown(wait=True)
        logger.info('AssetBundles are now up-to-date')
    
    def __init__(self, config : AbCacheConfig) -> None:
        super().__init__()
        self.config = config
        self.headers.update({
            'Accept': 'application/octet-stream',
            'Content-Type': 'application/octet-stream',
            'Accept-Encoding': 'deflate, gzip',
            'User-Agent': 'UnityPlayer/2020.3.32f1 (UnityWebRequest/1.0, libcurl/7.80.0-DEV)',
            'X-Platform': self.config.app_platform,
            'X-Unity-Version': '2020.3.32f1',
            'X-App-Version': self.config.app_version,
            'X-Platform': self.config.app_platform
        })
        logger.info('Cache directory: %s' % self.config.cache_dir)
        logger.info('App version: %s (%s)' % (self.config.app_version,self.config.app_platform))
        self.update_signatures()
        self.update_system_data()
        self.update_gameversion_data()
        logger.info('Sekai AssetBundle version: %s' % self.SEKAI_ASSET_VERSION)
        logger.info('Sekai AssetBundle host hash: %s' % self.SEKAI_AB_HOST_HASH)
        makedirs(self.config.cache_dir,exist_ok=True)
        try:
            self.load()
        except Exception as e:
            logger.warning('Failed to load cache index. Creating new one. (%s)' % e)
            self.index = AbCacheIndex(bundles=dict())
            self.save()
    
    def save(self):
        with open(path.join(self.config.cache_dir, 'abindex.json'),'w',encoding='utf-8') as f:
            dump(asdict(self.index), f, indent=4, ensure_ascii=False)
            logger.info("Saved %d entries to cache index" % len(self.index.bundles))

    def load(self):
        with open(path.join(self.config.cache_dir, 'abindex.json'),'r',encoding='utf-8') as f:
            self.index = AbCacheIndex(**load(f))
            for k,v in self.index.bundles.items():
                self.index.bundles[k] = AbCacheEntry(**v)
            logger.info("Loaded %d entries from cache index" % len(self.index.bundles))