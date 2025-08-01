import os, re, json, time
from sssekai.abcache import AbCache, AbCacheEntry, logger, REGION_JP_EN, REGION_ROW
from sssekai.abcache.fs import AbCacheFilesystem, AbCacheFile
from concurrent.futures import ThreadPoolExecutor
from requests import Session
from tqdm import tqdm

class AbCacheDownloader(ThreadPoolExecutor):
    session: Session
    progress: tqdm = None

    def _ensure_progress(self):
        if not self.progress:
            self.progress = tqdm(
                total=0,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
            )

    def _download(self, args):
        if self._shutdown:
            return
        self._ensure_progress()
        RETRIES = 1
        src, dest = args
        src: AbCacheFile
        dest: str
        for _ in range(0, RETRIES):
            n_written = 0
            try:
                if os.path.dirname(dest):
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    while block := src.read(65536):
                        n_block = f.write(block)
                        self.progress.update(n_block)
                        n_written += n_block
                        if self._shutdown:
                            self.progress.update(-n_written)
                            return
                    return
            except Exception as e:
                logger.error("While downloading %s : %s. Retrying" % (src.path, e))
                self.progress.update(-n_written)
                time.sleep(1)

        if _ == RETRIES - 1:
            logger.critical("Did not download %s" % src.path)
        self._ensure_progress()

    queue: list

    def __init__(self, session, **kw) -> None:
        self.session = session
        self.queue = []
        super().__init__(**kw)

    def __enter__(self):
        return super().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return super().__exit__(exc_type, exc_val, exc_tb)

    def add_link(self, file: AbCacheFile, dest: str):
        self._ensure_progress()
        self.progress.total += file.size
        return self.queue.append((file, dest))

    def run_until_complete(self):
        for _ in self.map(self._download, self.queue):
            pass


def dump_dict_by_keys(d: dict, dir: str, keep_compact: bool):
    for k, v in tqdm(d.items(), unit="file"):
        if not keep_compact and k.startswith("compact"):
            # NOTE: These are emprical and have yet been backed by decompilation
            # Assumptions:
            #   - List[Mapping[K,V]] are compacted into Mapping[K,List[V]]
            #   - Mapping[K,V] does not contain recusive mappings
            #   - Enums can only be Values and they would be stored as strings. Once compacted
            #     To 0-indexed array keyed by their parent's key in a special __ENUM__ LUT
            logger.debug("Decompacting %s", k)
            enums = v.get("__ENUM__", {})
            struct = [kk for kk in v if isinstance(v[kk], list)]
            count = len(v[struct[-1]])
            getkey = lambda kk, i: enums[kk][v[kk][i] or 0] if kk in enums else v[kk][i]
            v = [{kk: getkey(kk, i) for kk in struct} for i in range(count)]
            k = k[len("compact") :]
            k = k[0].lower() + k[1:]  # Save in the style of JP server's keys
        save_as = k + ".json"
        with open(os.path.join(dir, save_as), "w", encoding="utf-8") as f:
            json.dump(v, f, indent=4, ensure_ascii=False)
            logger.info("Saved %s", save_as)


def main_abcache(args):
    db_path = os.path.expanduser(args.db)
    cache: AbCache = AbCache()
    try:
        with open(db_path, "rb") as f:
            cache = AbCache.from_file(f)
    except Exception as e:
        logger.error("Failed to load cache from %s: %s", db_path, e)
        logger.warning("Force rebuilding cache from scratch.")
        if args.no_update:
            logger.error(
                "no_update is specified, but no valid cache file is found. AbCache will not exit."
            )
            return

    config = cache.config

    if args.proxy:
        logger.info("Overriding proxy: %s", args.proxy)
        cache.proxies = {"http": args.proxy, "https": args.proxy}

    if args.download_filter_cache_diff:
        diff_path = os.path.abspath(os.path.expanduser(args.download_filter_cache_diff))
        curr_path = os.path.abspath(os.path.expanduser(db_path))
        assert (
            diff_path != curr_path
        ), "Cache diff path must be different from current cache path! Make a copy of the diff cache if this is required."

    def try_auth():
        try:
            if not config.auth_available:
                logger.warning("No *valid* auth info provided.")
                # Register as anonymous user in this case
                if config.app_region in REGION_JP_EN:
                    from sssekai.abcache.auth import register_as_anonymous_user_sega

                    logger.warning("Registering as an anonymous user on SEGA servers.")
                    register_as_anonymous_user_sega(cache)
                else:
                    logger.warning("No *valid* auth info provided for ROW region.")
                    logger.warning(
                        "Anonymous user registration is not supported for those regions. You may encounter errors."
                    )
            else:
                if config.auth_available:
                    logger.info(
                        "Using cached auth credential. UserId=%s" % cache.SEKAI_USERID
                    )
            return config.auth_available
        except Exception as e:
            logger.error("Failed to authenticate: %s", e)
            return False

    if not args.no_update:
        config.app_region = args.app_region
        config.app_version = args.app_version
        config.app_platform = args.app_platform
        config.app_hash = args.app_appHash
        config.row_ab_version = args.app_abVersion
        config.asset_hash = args.app_asset_hash
        config.asset_host = args.app_asset_host
        config.asset_version = args.app_asset_version
        config.auth_credential = args.auth_credential

    if config.app_region in {"jp"}:
        cache.update_signatures()

    if args.dump_master_data:
        if config.app_region in REGION_JP_EN:
            assert (
                try_auth()
            ), "Cannot dump master data without valid auth info in EN/JP servers."
        cache.update_client_headers()
        master_data_path = os.path.expanduser(args.dump_master_data)
        os.makedirs(master_data_path, exist_ok=True)
        logger.info("Dumping master data to %s", master_data_path)
        for url in tqdm(cache.SEKAI_API_MASTER_SUITE_URLS, unit="file"):
            resp = cache.request_packed("GET", url)
            dump_dict_by_keys(
                cache.response_to_dict(resp), master_data_path, args.keep_compact
            )
        return

    if args.dump_user_data:
        assert try_auth(), "Cannot dump user data without valid auth info."
        cache.update_client_headers()
        user_data_path = os.path.expanduser(args.dump_user_data)
        os.makedirs(user_data_path, exist_ok=True)
        logger.info("Dumping user data to %s", user_data_path)
        resp = cache.request_packed("GET", cache.SEKAI_API_USER_SUITE)
        dump_dict_by_keys(
            cache.response_to_dict(resp), user_data_path, args.keep_compact
        )
        return

    if not args.no_update:
        if config.need_client_header_update:
            if config.app_region in REGION_JP_EN:
                assert (
                    try_auth()
                ), "Cannot update client headers without auth info. NOTE: You can fill in the EN/JP override fields (`--app-asset-...`) to bypass auth."
            cache.update_client_headers()
        cache.update_abcache_index()
        if os.path.dirname(db_path):
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with open(db_path, "wb") as f:
            cache.save(f)

    if args.download_dir:
        download_dir = os.path.expanduser(args.download_dir)
        bundles = set()

        def _iter_bundles():
            filter_pred = []
            if args.download_filter:
                logger.info(
                    "Filtering bundles with regex pattern: %s", args.download_filter
                )
                pattern = re.compile(args.download_filter)
                filter_pred.append(lambda bundle: pattern.match(bundle.bundleName))
            if args.download_filter_cache_diff:
                logger.info("Filtering bundles with cache diff")
                diff_path = args.download_filter_cache_diff
                diff_path = os.path.abspath(os.path.expanduser(diff_path))
                logger.info("Loading cache diff from %s", diff_path)
                diff_cache = AbCache.from_file(open(diff_path, "rb"))

                def __diff_pred(bundle: AbCacheEntry):
                    diff = diff_cache.abcache_index.bundles.get(bundle.bundleName, None)
                    if diff is not None:
                        if diff.hash != bundle.hash:
                            return True
                        else:
                            logger.debug(
                                "Skipped %s due to cache diff hit (hash)",
                                bundle.bundleName,
                            )
                            return False
                    else:
                        return True

                filter_pred.append(__diff_pred)
            if filter_pred:
                for name, entry in cache.abcache_index.bundles.items():
                    if all(pred(entry) for pred in filter_pred):
                        yield name
            else:
                logger.warning(
                    "No filter pattern specified. All bundles will be downloaded."
                )
                for name, entry in cache.abcache_index.bundles.items():
                    yield name

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
        fs = AbCacheFilesystem(cache_obj=cache)
        with AbCacheDownloader(fs, max_workers=args.download_workers) as downloader:
            logger.info("Downloading %d bundles to %s" % (len(bundles), download_dir))
            for bundleName in bundles:
                downloader.add_link(
                    fs.open(bundleName), os.path.join(download_dir, bundleName)
                )
            try:
                downloader.run_until_complete()
            except KeyboardInterrupt:
                logger.warning("Download interrupted by user.")
                downloader.shutdown(wait=False, cancel_futures=True)
                return 1
    return 0
