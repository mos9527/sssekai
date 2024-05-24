import os
from sssekai.abcache import AbCache, AbCacheConfig,logger
def main_abcache(args):
    cache_dir = args.cache_dir
    cache_dir = os.path.expanduser(cache_dir)
    cache_dir = os.path.abspath(cache_dir)
    config = AbCacheConfig(cache_dir, args.version, args.platform, args.appHash)
    if args.open:
        from os import startfile
        startfile(config.cache_dir)
        return
    cache = AbCache(config)
    if not args.skip_update:
        cache.update_metadata()
        cache.queue_update_cache_entry_full()
        cache.wait_for_downloads()
    cache.save()
    logger.info('AssetBundle cache is now ready. Visit: %s' % cache_dir)
