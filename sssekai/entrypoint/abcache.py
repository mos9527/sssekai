import os, re
from types import TracebackType
from sssekai.abcache import AbCache, AbCacheConfig, logger
from sssekai.crypto.AssetBundle import SEKAI_AB_MAGIC, decrypt_headaer_inplace
from concurrent.futures import ThreadPoolExecutor
from requests import Session
from tqdm import tqdm

DEFAULT_CACHE_DB_FILE = '~/.sssekai/abcache.db'
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
                os.makedirs(os.path.dirname(fname),exist_ok=True)
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
    
    def __init__(self, session, **kw) -> None:
        self.session = session        
        super().__init__(**kw)
    
    def __enter__(self):
        return super().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return super().__exit__(exc_type, exc_val, exc_tb)

    def add_link(self, url, fname, length):
        self._ensure_progress()
        self.progress.total += length
        return self.submit(self._download, url, fname, length)

def main_abcache(args):
    cache = AbCache(AbCacheConfig(args.app_version, args.app_platform, args.app_appHash))
    db_path = os.path.expanduser(args.db)
    if not args.no_update:
        with open(db_path, 'wb') as f:
            cache.update()
            cache.save(f)
    else:
        with open(db_path, 'rb') as f:
            cache.load(f)
    
    if args.download_dir:
        download_dir = os.path.expanduser(args.download_dir)
        bundles = set()
        def _iter_bundles():
            if args.download_filter:
                logger.info('Filtering bundles with regex pattern: %s', args.download_filter)
                pattern = re.compile(args.download_filter)
                for entry in cache.abcache_index.bundles:
                    if pattern.match(entry): yield entry
            else:
                logger.warning('No filter pattern specified. All bundles will be downloaded.')
                for entry in cache.abcache_index.bundles: yield entry
        for bundleName in _iter_bundles(): bundles.add(bundleName)
        basebundles = bundles.copy()
        logger.info('Selected %d bundles to download', len(basebundles))
        if args.download_ensure_deps:
            for bundleName in basebundles:
                cache.get_or_update_dependency_tree_flatten(bundleName, bundles)
            logger.info('Added dependencies:')
            for dep in bundles - basebundles:
                logger.info('   - %s', dep) 
        with AbCacheDownloader(cache, max_workers=args.download_workers) as downloader:
            cache.update_download_headers()
            logger.info('Downloading %d bundles to %s' % (len(bundles), download_dir))
            for bundleName in bundles:
                entry = cache.get_entry_by_bundle_name(bundleName)
                url = cache.get_entry_download_url(entry)
                fname = os.path.join(download_dir, bundleName)
                downloader.add_link(url, fname, entry.fileSize)
