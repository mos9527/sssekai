from sssekai.abcache import AbCache, AbCacheConfig, AbCacheEntry, AbCacheIndex, ThreadpoolDownloader
import coloredlogs
from logging import basicConfig
coloredlogs.install(
        level='INFO',
        fmt="%(asctime)s %(name)s [%(levelname).4s] %(message)s",
        isatty=True,
    )
basicConfig(
    level='INFO', format="[%(levelname).4s] %(name)s %(message)s"
)

downloader = ThreadpoolDownloader()
cache = AbCache(AbCacheConfig(downloader))
cache.update_cahce_index()
downloader.shutdown(wait=True)
cache.save()