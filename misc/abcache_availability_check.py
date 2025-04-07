import coloredlogs, logging, time
from sssekai.abcache import AbCache, AbCacheConfig
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from threading import Lock

UPDATE = True

coloredlogs.install(level=logging.INFO)
logger = logging.getLogger("abcache-test")

if UPDATE:
    cache = AbCache(
        AbCacheConfig(
            app_region="cn",
            app_version="3.4.1",
            ab_version="3.4.0",
            app_hash="a3015fe8-785f-27e1-fb8b-546a23c82c1f",
            app_platform="android",
        )
    )
    cache.update()
    cache.save(open("tmp.abcache.db", "wb"))
else:
    cache = AbCache.from_file(open("tmp.abcache.db", "rb"))


PENDING = 0
stats = defaultdict(int)  # stats[response code] = count
stat_lock = Lock()


def hit_and_run(cache: AbCache, name: str):
    global stats, stat_lock

    bundle = cache.get_entry_by_bundle_name(name)
    url = cache.get_entry_download_url(bundle)
    resp = cache.get(url, stream=True)
    with stat_lock:
        stats[resp.status_code] += 1
        stats[PENDING] -= 1
    resp.close()


with ThreadPoolExecutor(16) as queue:
    stats[PENDING] = len(cache.abcache_index.bundles.items())
    for name, bundle in cache.abcache_index.bundles.items():
        queue.submit(hit_and_run, cache, name)
    while True:
        with stat_lock:
            for code, count in stats.items():
                print(f"code={code or '<pending>'}, count={count}", end="\t")
            print(end="\r")
            if stats[PENDING] == 0:
                break
        time.sleep(0.1)
