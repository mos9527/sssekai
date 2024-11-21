import os, re, json
from sssekai.abcache import AbCache, AbCacheConfig, logger
from sssekai.abcache.fs import AbCacheFilesystem, AbCacheFile
from concurrent.futures import ThreadPoolExecutor
from requests import Session
from tqdm import tqdm

DEFAULT_CACHE_DB_FILE = "~/.sssekai/abcache.db"


class AbCacheDownloader(ThreadPoolExecutor):
    session: Session
    progress: tqdm = None

    def _ensure_progress(self):
        if not self.progress:
            self.progress = tqdm(
                bar_format="{desc}: {percentage:.1f}%|{bar}| {n_fmt}/{total_fmt} {rate_fmt} {elapsed}<{remaining}",
                total=0,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc="Downloading",
            )

    def _download(self, src: AbCacheFile, dest: str):
        self._ensure_progress()
        RETRIES = 1
        for _ in range(0, RETRIES):
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    while block := src.read(65536):
                        self.progress.update(f.write(block))
                    return
            except Exception as e:
                logger.error("While downloading %s : %s. Retrying" % (src.path, e))
        if _ == RETRIES - 1:
            logger.critical("Did not download %s" % src.path)
        self._ensure_progress()

    def __init__(self, session, **kw) -> None:
        self.session = session
        super().__init__(**kw)

    def __enter__(self):
        return super().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return super().__exit__(exc_type, exc_val, exc_tb)

    def add_link(self, file: AbCacheFile, dest: str):
        self._ensure_progress()
        self.progress.total += file.size
        return self.submit(self._download, file, dest)


def main_abcache(args):
    cache = AbCache(
        AbCacheConfig(
            args.app_region, args.app_version, args.app_platform, args.app_appHash
        )
    )
    if args.dump_master_data:
        master_data_path = os.path.expanduser(args.dump_master_data)
        logger.info("Dumping master data to %s", master_data_path)
        cache.update_client_headers()
        progress = tqdm(
            total=len(cache.database.sekai_user_auth_data.suiteMasterSplitPath),
            desc="Pulling",
            unit="file",
            bar_format="{desc}: {percentage:.1f}%|{bar}| {n:.1f}/{total_fmt} {rate_fmt} {elapsed}<{remaining}",
        )
        for split in cache.database.sekai_user_auth_data.suiteMasterSplitPath:
            resp = cache.request_packed(
                "GET", cache.SEKAI_API_ENDPOINT + "/api/" + split
            )
            data = cache.response_to_dict(resp)
            path = master_data_path
            os.makedirs(path, exist_ok=True)
            logger.debug("Saving to %s", path)
            for k, v in data.items():
                logger.debug("Saving %s", k)
                fpath = os.path.join(path, k + ".json")
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(v, f, indent=4, ensure_ascii=False)
                progress.update(1 / len(data))
        return

    db_path = os.path.expanduser(args.db)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if not args.no_update:
        assert (
            args.app_version and args.app_appHash
        ), "You need --app-version and --app-appHash to perform a cache index update!"
        with open(db_path, "wb") as f:
            cache.update()
            cache.save(f)
    else:
        with open(db_path, "rb") as f:
            cache.load(f)

    if args.download_dir:
        download_dir = os.path.expanduser(args.download_dir)
        bundles = set()

        def _iter_bundles():
            if args.download_filter:
                logger.info(
                    "Filtering bundles with regex pattern: %s", args.download_filter
                )
                pattern = re.compile(args.download_filter)
                for entry in cache.abcache_index.bundles:
                    if pattern.match(entry):
                        yield entry
            else:
                logger.warning(
                    "No filter pattern specified. All bundles will be downloaded."
                )
                for entry in cache.abcache_index.bundles:
                    yield entry

        for bundleName in _iter_bundles():
            bundles.add(bundleName)
        basebundles = bundles.copy()
        logger.info("Selected %d bundles to download", len(basebundles))
        if args.download_ensure_deps:
            for bundleName in basebundles:
                cache.get_or_update_dependency_tree_flatten(bundleName, bundles)
            logger.info("Added dependencies:")
            for dep in bundles - basebundles:
                logger.info("   - %s", dep)
        fs = AbCacheFilesystem(cache)
        with AbCacheDownloader(fs, max_workers=args.download_workers) as downloader:
            cache.update_download_headers()
            logger.info("Downloading %d bundles to %s" % (len(bundles), download_dir))
            for bundleName in bundles:
                fname = os.path.join(download_dir, bundleName)
                downloader.add_link(fs.open(bundleName), fname)
