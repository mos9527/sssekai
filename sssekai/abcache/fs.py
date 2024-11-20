from functools import cached_property
from collections import defaultdict
from fsspec.spec import AbstractBufferedFile
from fsspec.archive import AbstractArchiveFileSystem
from requests import Response
from . import AbCache, AbCacheEntry
from sssekai.crypto.AssetBundle import SEKAI_AB_MAGIC, decrypt_header_inplace


# Reference: https://github.com/fsspec/filesystem_spec/blob/master/fsspec/implementations/http.py#L526
class AbCacheFilesystemStreamingFile(AbstractBufferedFile):
    @property
    def session(self) -> AbCache:
        return self.fs.cache

    @property
    def entry(self) -> AbCacheEntry:
        return self.fs.cache.get_entry_by_bundle_name(self.path)

    def __init__(
        self,
        fs,
        path,
        mode="rb",
        block_size="default",
        autocommit=True,
        cache_type="readahead",
        cache_options=None,
        size=None,
        **kwargs
    ):
        super().__init__(
            fs,
            path,
            mode,
            block_size,
            autocommit,
            cache_type,
            cache_options,
            size,
            **kwargs
        )
        self.size = self.entry.fileSize

    def seek(self, loc, whence=0):
        raise NotImplementedError  # `shutils.copyfileobj` is your friend!

    @cached_property
    def __resp(self) -> Response:
        url = self.session.get_entry_download_url(self.entry)
        resp = self.session.get(url, stream=True)
        return resp

    @cached_property
    def __header(self) -> bytearray:
        header = next(self.__resp.iter_content(4))
        if header == SEKAI_AB_MAGIC:
            header = bytearray(next(self.__resp.iter_content(128)))
            header = decrypt_header_inplace(header)
        return header

    def read(self, length=-1):
        assert self.__header
        if length < 0:
            length = self.size
        buffer = bytearray()
        header_res = max(0, len(self.__header) - self.loc)
        if header_res:
            buffer += self.__header[self.loc : self.loc + header_res]
            self.loc += len(buffer)
            length -= len(buffer)
        if length:
            try:
                buffer += next(self.__resp.iter_content(length))
                self.loc += len(buffer)
            except StopIteration:
                pass
        return buffer


# Reference: https://github.com/fsspec/filesystem_spec/blob/master/fsspec/implementations/libarchive.py
class AbCacheFilesystem(AbstractArchiveFileSystem):
    cache: AbCache

    def __init__(self, cache: AbCache):
        self.cache = cache

    @cached_property
    def dir_cache(self):
        cache = defaultdict(dict)
        for path, bundle in self.cache.abcache_index.bundles.items():
            cache[path] = {"name": bundle.bundleName, "size": bundle.fileSize}
            path = path.split("/")
            dirs = path[:-1]
            for i in range(0, len(dirs)):
                path = "/".join(dirs[0:i])
                cache[path] = {"name": path, "size": 0, "type": "directory"}
        return cache

    def _get_dirs(self):
        return self.dir_cache

    def open(self, path):
        entry = self.cache.get_entry_by_bundle_name(path)
        assert entry is not None, "entry not found"
        return AbCacheFilesystemStreamingFile(
            self, path, size=entry.fileSize, entry=entry
        )
