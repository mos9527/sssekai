from sssekai.abcache import AbCache, AbCacheConfig,ThreadpoolDownloader, logger, DEFAULT_CACHE_DIR
def main_abcache(args):
    downloader = ThreadpoolDownloader()
    cache_dir = args.cache_dir or DEFAULT_CACHE_DIR
    config = AbCacheConfig(downloader, cache_dir, args.version, args.platform)
    if args.open:
        from os import startfile
        startfile(config.cache_dir)
        return
    cache = AbCache(config)
    downloader.session = cache
    if not args.skip_update:
        cache.update_cahce_index()
    downloader.shutdown()
    cache.save()
    logger.info('AssetBundle cache is now ready. Visit: %s' % cache_dir)
