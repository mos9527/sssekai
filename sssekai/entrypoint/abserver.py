import os

from sssekai.abcache import AbCache
from sssekai.abcache.fs import AbCacheFilesystem
from http.server import SimpleHTTPRequestHandler


def main_abserver(args):
    db_path = os.path.expanduser(args.db)
    cache = AbCache()
    cache.load(open(db_path, "rb"))
    cache.update_download_headers()
    fs = AbCacheFilesystem(cache)
    # IDEA: Divert SimpleHTTPRequestHandler `os` filesystem calls to our FS and...
    # Maybe not. I'll sit on this for now before I'd get better ideas.
    pass
