import math, fsspec
from typing import Callable
from functools import cached_property
from collections import defaultdict
from fsspec.spec import AbstractBufferedFile
from fsspec.caching import BaseCache, register_cache
from fsspec.archive import AbstractArchiveFileSystem
from requests import Response
from logging import getLogger
from sssekai.crypto.AssetBundle import decrypt_iter
from . import AbCache, AbCacheEntry

logger = getLogger("abcache.fs")


# Reference: https://github.com/fsspec/filesystem_spec/blame/master/fsspec/caching.py
class UnidirectionalBlockCache(BaseCache):
    """Block-based cache that only fetches data in one direction with a fixed block size"""

    name: str = "unidirectional_blockcache"

    def __init__(
        self, blocksize: int, fetcher: Callable[[int, int], bytes], size: int
    ) -> None:
        super().__init__(blocksize, fetcher, size)
        self.nblocks = math.ceil(size / self.blocksize)
        self.blocks = list()

    def __fetch_block(self, block_number):
        assert block_number < self.nblocks, "block out of range"
        while len(self.blocks) - 1 < block_number:
            logger.debug("Fetching block %d" % (len(self.blocks)))
            start = self.blocksize * len(self.blocks)
            end = start + self.blocksize
            block = self.fetcher(start, end)
            self.blocks.append(block)
        return self.blocks[block_number]

    def _fetch(self, start: int | None, stop: int | None) -> bytes:
        if start is None:
            start = 0
        if stop is None:
            stop = self.size
        if start >= self.size or start >= stop:
            return b""
        start_blk, start_pos = start // self.blocksize, start % self.blocksize
        end_blk, end_pos = stop // self.blocksize, stop % self.blocksize

        if start_blk == end_blk:
            out = self.__fetch_block(start_blk)[start_pos:end_pos]
            return out
        else:
            out = [self.__fetch_block(start_blk)[start_pos:]]
            out += [self.__fetch_block(blk) for blk in range(start_blk + 1, end_blk)]
            out += [self.__fetch_block(end_blk)[:end_pos]]
            return b"".join(out)


register_cache(UnidirectionalBlockCache)


# Reference: https://github.com/fsspec/filesystem_spec/blob/master/fsspec/implementations/http.py#L526
class AbCacheFile(AbstractBufferedFile):
    """Cached, file-like object for reading from an AbCache on demand.

    Note:
        - The fetched content is decrypted on the fly.
        - Seeks are simulated by read-aheads (by UnidirectionalBlockCache). Meaning seek operations
          will incur additional download (in-betweens will be cached as well).
    """

    entry: AbCacheEntry

    @property
    def session(self) -> AbCache:
        return self.fs.cache

    @property
    def entry(self) -> AbCacheEntry:
        entry = self.session.get_entry_by_bundle_name(self.path.strip('/'))
        assert entry is not None, "entry not found"
        return entry

    def __init__(self, fs, bundle: str):
        self.fs, self.path = fs, bundle
        self.fetch_loc = 0
        super().__init__(
            fs,
            bundle,
            mode="rb",
            cache_type="unidirectional_blockcache",
            size=self.entry.fileSize,
        )

    @cached_property
    def __resp(self) -> Response:
        url = self.session.get_entry_download_url(self.entry)
        resp = self.session.get(url, stream=True)
        return resp

    @cached_property
    def __fetch(self):
        def __innner():
            for block in decrypt_iter(
                lambda nbytes: next(self.__resp.iter_content(nbytes)), self.blocksize
            ):
                yield block

        return __innner()

    def _fetch_range(self, start, end):
        assert start - self.fetch_loc == 0, "can only fetch sequentially"
        self.fetch_loc = end
        return next(self.__fetch)


# Reference: https://github.com/fsspec/filesystem_spec/blob/master/fsspec/implementations/libarchive.py
class AbCacheFilesystem(AbstractArchiveFileSystem):
    """Filesystem for reading from an AbCache on demand."""

    protocol = "abcache"
    cache: AbCache

    def __init__(self, fo: str = "", cache_obj: AbCache = None, *args, **kwargs):
        """Initialize the filesystem with a cache object
        or a file-like object that contains the cache database file.

        Args:
            fo (str, optional): the cahce database file object . Defaults to "".
            cache_obj (AbCache, optional): the cache database. Defaults to None.
        """
        if cache_obj:
            self.cache = cache_obj
        else:
            self.cache = AbCache()
            if isinstance(fo, str):
                with fsspec.open(fo, "rb") as f:
                    self.cache.load(f)
            else:
                self.cache.load(fo)
            self.cache.update_download_headers()

    @cached_property
    def dir_cache(self):
        cache = defaultdict(dict)
        for path, bundle in self.cache.abcache_index.bundles.items():
            path = "/" + path
            cache.update(
                {
                    dirname: {"name": dirname, "size": 0, "type": "directory"}
                    for dirname in self._all_dirnames([path])
                }
            )
            cache[path] = {
                "name": path,
                "size": bundle.fileSize,
                "type": "file",
            }
        return cache

    def _get_dirs(self):
        return self.dir_cache

    def open(self, path, mode="rb"):
        assert mode == "rb", "only binary read-only mode is supported"
        return AbCacheFile(self, path)


fsspec.register_implementation("abcache", AbCacheFilesystem)
