from sssekai.abcache import AbCache, AbCacheConfig, AbCacheEntry, AbCacheIndex, Aria2Downloader
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

downloader = Aria2Downloader()
cache = AbCache(AbCacheConfig(downloader))
cache.update_cahce_index()
downloader.wait_for_downloads()
cache.save()