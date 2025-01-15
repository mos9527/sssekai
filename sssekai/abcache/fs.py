import math, fsspec
from typing import Callable
from functools import cached_property, cache
from collections import defaultdict
from fsspec.spec import AbstractBufferedFile
from fsspec.caching import BaseCache, register_cache
from fsspec.archive import AbstractArchiveFileSystem
from requests import Response
from logging import getLogger
from sssekai.crypto.AssetBundle import decrypt_iter, SEKAI_AB_MAGIC
from . import AbCache, AbCacheEntry

logger = getLogger("abcache.fs")


# Reference: https://github.com/fsspec/filesystem_spec/blame/master/fsspec/caching.py
class UnidirectionalBlockCache(BaseCache):
    """Block-based cache that only fetches data in one direction with a fixed block size"""

    name: str = "unidirectional_blockcache"

    def __init__(
        self,
        blocksize: int,
        fetcher: Callable[[int, int], bytes],
        size: int,
        ignore_size: bool = False,
    ) -> None:
        """Create a unidirectional block cache.

        Args:
            blocksize (int): Block size in bytes.
            fetcher (Callable[[int, int], bytes]): Fetcher function that takes start and end byte positions and returns the data.
            size (int): Size of the file.
            ignore_size (bool, optional): Don't truncate reads with `size` provided. Defaults to False.
        """
        super().__init__(blocksize, fetcher, size)
        self.ignore_size = ignore_size
        if not ignore_size:
            self.nblocks = math.ceil(size / self.blocksize)
        else:
            self.nblocks = float("inf")
        self.blocks = list()
        self.eof = False

    def __fetch_block(self, block_number):
        assert block_number < self.nblocks, "block out of range"
        while not self.eof and len(self.blocks) - 1 < block_number:
            start = self.blocksize * len(self.blocks)
            end = start + self.blocksize
            block = self.fetcher(start, end)
            if block:
                self.blocks.append(block)
            else:
                self.eof = True
        if block_number < len(self.blocks):
            return self.blocks[block_number]
        return b""  # EOF behavior when ignore_size is True

    def _fetch(self, start: int | None, stop: int | None) -> bytes:
        if start is None:
            start = 0
        if stop is None:
            stop = self.size
        if not self.ignore_size:
            stop = min(stop, self.size)  # XXX: why didn't fsspec handle this?
        if (not self.ignore_size and start >= self.size) or start >= stop:
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
        - File sizes reported are *inaccurate* due to wrong values sent by the server.
          Read until EOF otherwise you will miss data.
    """

    DEFAULT_BLOCK_SIZE = 65536  # 64KB
    entry: AbCacheEntry

    @property
    def session(self) -> AbCache:
        return self.fs.cache

    @property
    def entry(self) -> AbCacheEntry:
        entry = self.session.get_entry_by_bundle_name(self.path.strip("/"))
        assert entry is not None, "entry not found"
        return entry

    def read(self, length=-1):
        if length < 0:
            length = float("inf")
        out = self.cache._fetch(self.loc, self.loc + length)
        self.loc += len(out)
        return out

    def __init__(self, fs, bundle: str, block_size=None):
        self.fs, self.path = fs, bundle
        self.fetch_loc = 0
        super().__init__(
            fs,
            bundle,
            block_size=block_size or self.DEFAULT_BLOCK_SIZE,
            mode="rb",
            cache_type="unidirectional_blockcache",
            size=self.entry.fileSize,
            cache_options={"ignore_size": True},
            # Sadly entry size could be *extremely* inaccurate.
            # We have to ignore it and fetch until EOF.
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
                lambda nbytes: next(self.__resp.iter_content(nbytes), b""),
                self.blocksize,
            ):
                yield bytes(block)

        return __innner()

    def _fetch_range(self, start, end):
        assert start - self.fetch_loc == 0, "can only fetch sequentially"
        self.fetch_loc = end
        return next(self.__fetch, b"")


# Reference: https://github.com/fsspec/filesystem_spec/blob/master/fsspec/implementations/libarchive.py
class AbCacheFilesystem(AbstractArchiveFileSystem):
    """Filesystem for reading from an AbCache on demand."""

    root_marker = "/"
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
        # Reference implementation did O(n) per *every* ls() call
        # We can make it O(1) with DP on tree preprocessing of O(nlogn)
        bundles = self.cache.abcache_index.bundles
        # Only the leaf nodes are given.
        keys = set((self.root_marker + key for key in bundles.keys()))
        keys |= self._all_dirnames(bundles.keys())
        # Sorting implies DFS order.
        keys = [self.root_marker] + [key for key in sorted(keys)]
        _trim = lambda key: key[len(self.root_marker) :]
        nodes = [
            {
                "name": key,
                "type": "directory" if not _trim(key) in bundles else "file",
                "size": (
                    0 if not _trim(key) in bundles else bundles[_trim(key)].fileSize
                ),
                "item_count": 0,
                "file_count": 0,
                "total_size": 0,
            }
            for key in keys
        ]
        # Already in DFS order.
        # Get start index for each directory and their item count.
        stack = [0]
        graph = defaultdict(list)
        table = {node["name"]: index for index, node in enumerate(nodes)}

        def is_file(name):
            return _trim(name) in bundles

        def is_parent_path(a, b):
            # a is parent of b
            if a == self.root_marker:
                return True
            return b.startswith(a + self.root_marker)

        def maintain():
            # Always starts from root. Safe to assume stack size >= 2
            u, v = stack[-2], stack[-1]
            nodes[u]["item_count"] += nodes[v]["item_count"]
            nodes[u]["file_count"] += nodes[v]["file_count"]
            nodes[u]["total_size"] += nodes[v]["total_size"]
            stack.pop()

        for index, name in enumerate(keys):
            # Skip root
            if index == 0:
                continue
            while not is_parent_path(keys[stack[-1]], name):
                maintain()
            pa = stack[-1]
            nodes[pa]["item_count"] += 1
            graph[pa].append(index)
            if not is_file(name):
                stack.append(index)
            else:
                nodes[pa]["file_count"] += 1
                nodes[pa]["total_size"] += nodes[index]["size"]
                nodes[index]["total_size"] = nodes[index]["size"]
        while len(stack) >= 2:
            maintain()
        assert nodes[0]["file_count"] == len(bundles), "file count mismatch"
        return nodes, graph, table

    def _get_dirs(self):
        return self.dir_cache

    def info(self, path, **kwargs):
        nodes, graph, table = self._get_dirs()
        path = path or self.root_marker
        if path in table:
            return nodes[table[path]]
        else:
            raise FileNotFoundError(path)

    @cache
    def ls(self, path, detail=True, **kwargs):
        nodes, graph, table = self._get_dirs()
        path = path or self.root_marker
        if path in table:
            u = table[path]
            return [nodes[v] if detail else nodes[v]["name"] for v in graph[u]]
        return []

    def open(self, path, mode="rb"):
        assert mode == "rb", "only binary read-only mode is supported"
        return AbCacheFile(self, path)


fsspec.register_implementation("abcache", AbCacheFilesystem)
