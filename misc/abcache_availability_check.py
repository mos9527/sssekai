import coloredlogs, logging
from sssekai.abcache import AbCache, AbCacheConfig

coloredlogs.install(level=0)
logger = logging.getLogger("abcache-test")

config = AbCacheConfig(
    app_region="cn",
    app_version="3.4.1",
    app_hash="a3015fe8-785f-27e1-fb8b-546a23c82c1f",
    app_platform="android",
)
cache = AbCache(config)
cache.update()
pass
