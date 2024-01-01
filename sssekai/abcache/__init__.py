from io import BytesIO
from os import path, remove, makedirs, stat
from typing import List, Mapping
from dataclasses import dataclass, asdict
from aria2p.client import Client
from requests import get as http_get
from logging import getLogger
from json import dump, load
from time import sleep
logger = getLogger('sssekai.abcache')

import aria2p
from sssekai.crypto.APIManager import decrypt
from sssekai.crypto.AssetBundle import decrypt as ab_decrypt, decrypt_headaer_inplace
from msgpack import unpackb
import hashlib,mmap
DEFAULT_CACHE_DIR = '~/.sssekai/abcache'
# 2.6.1
SEKAI_CDN = 'https://lf16-mkovscdn-sg.bytedgame.com/obj/sf-game-alisg/gdl_app_5245/'
SEKAI_AB_BASE_PATH = 'AssetBundle/2.6.0/Release/online/'
SEKAI_AB_INDEX_PATH = SEKAI_AB_BASE_PATH + 'android21/AssetBundleInfo.json'

class Aria2Downloader(aria2p.API):
    def __init__(self) -> None:
        super().__init__(aria2p.Client(
            host="http://127.0.0.1",
            port=6800,
            secret=""
        ))

    def add_link_simple(self, uri, save_to):
        options = aria2p.Options(self, {})
        options.dir = path.dirname(save_to)
        options.out = path.basename(save_to)
        options.file_allocation = 'none' 
        # don't prealloc. allowing the file size to be exploited to check whether the download's
        # completed        
        self.add(
            uri,
            options=options
        )

    def wait_for_downloads(self):        
        all_done = False
        logger.info('Waiting for downloads to complete')
        while not all_done:
            all_done = True
            for i in self.get_downloads():
                if i.status == 'active':
                    all_done = False
                    break
            sleep(1)
        
class AbCacheConfig:
    cache_dir : str # absolute path to cache directory
    downloader : Aria2Downloader
    def __init__(self, downloader : Aria2Downloader, cache_dir: str = DEFAULT_CACHE_DIR) -> None:
        self.cache_dir = path.expanduser(cache_dir)
        self.cache_dir = path.abspath(self.cache_dir)
        self.downloader = downloader

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
    md5Hash : str
    downloadPath : str

    def up_to_date(self, config: AbCacheConfig, other) -> bool:
        fsize = self.get_file_size(config)     
        return self.hash == AbCacheEntry(**other).hash and self.fileSize <= fsize # fsize may be fileSize + 4
    
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
    version : str
    bundles : Mapping[str, AbCacheEntry]

class AbCache:
    config : AbCacheConfig
    index : AbCacheIndex
    
    @staticmethod
    def download_cache_index() -> AbCacheIndex:
        resp = http_get(
            url=SEKAI_CDN + SEKAI_AB_INDEX_PATH,
            headers={
                'Accept-Encoding': 'deflate, gzip'
            }
        )
        resp.raise_for_status()
        data = decrypt(resp.content)
        data = unpackb(data)
        cache = AbCacheIndex(**data)
        for k,v in cache.bundles.items():
            cache.bundles[k] = AbCacheEntry(**v)
        return cache

    def update_cahce_entry(self, entry : AbCacheEntry, new_entry : AbCacheEntry = None) -> None:
        if new_entry:
            entry = AbCacheEntry(new_entry)
        self.config.downloader.add_link_simple(
            SEKAI_CDN + SEKAI_AB_BASE_PATH + entry.downloadPath,
            path.join(self.config.cache_dir, entry.bundleName)
        )
                
    def update_cahce_index(self):
        logger.info('Downloading AssetBundleInfo.json')
        dl = AbCache.download_cache_index()
        all_keys = sorted([k for k in dl.bundles.keys()] + [k for k in self.index.bundles.keys()])
        for k in all_keys:
            if k in dl.bundles and k in self.index.bundles:
                # update
                if not dl.bundles[k].up_to_date(self.config, self.index.bundles[k]):
                    logger.info('Updating bundle %s', k)
                    self.update_cahce_entry(self.index.bundles[k], dl.bundles[k])
                else:
                    logger.info('Bundle %s is up to date' % k)
            elif k in dl.bundles: 
                # append
                logger.info('Adding bundle %s', k)
                self.index.bundles[k] = dl.bundles[k]
                self.update_cahce_entry(self.index.bundles[k])
            else: 
                # removal
                logger.info('Removing bundle %s', k)
                if path.exists(self.index.bundles[k].get_file_path(self.config)):
                    remove(self.index.bundles[k].get_file_path(self.config))
                del self.index.bundles[k]
            self.save()
    
    def __init__(self, config : AbCacheConfig) -> None:
        self.config = config
        makedirs(self.config.cache_dir,exist_ok=True)
        try:
            self.load()
        except Exception as e:
            logger.warning('Failed to load cache index. Creating new one. (%s)' % e)
            self.index = AbCacheIndex(None, {})
            self.save()
    
    def save(self):
        with open(path.join(self.config.cache_dir, 'abindex.json'),'w',encoding='utf-8') as f:
            dump(asdict(self.index), f, indent=4, ensure_ascii=False)
            # logger.info("Saved %d entries to cache index" % len(self.index.bundles))

    def load(self):
        with open(path.join(self.config.cache_dir, 'abindex.json'),'r',encoding='utf-8') as f:
            self.index = AbCacheIndex(**load(f))
            logger.info("Loaded %d entries from cache index" % len(self.index.bundles))