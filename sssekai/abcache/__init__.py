from collections import defaultdict
from pickle import load, dump
from typing import BinaryIO, List, Mapping, Optional, Union
from logging import getLogger
from dataclasses import dataclass, fields, is_dataclass
from functools import cached_property

logger = getLogger("sssekai.abcache")


def fromdict(klass: type, d: Union[Mapping, List], warn_missing_fields=True):
    """
    Recursively convert a dictionary to a dataclass instance, if applicable.
    https://stackoverflow.com/a/54769644
    https://gist.github.com/gatopeich/1efd3e1e4269e1e98fae9983bb914f22
    """

    while klass.__name__ == "Optional":
        klass = klass.__args__[0]  # Reduce Optional[T] -> T

    def ensure_iterable(d):
        if isinstance(d, Mapping):
            return d
        if hasattr(d, "__dict__"):
            return d.__dict__
        return dict()

    def check_field(key, fields):
        if not key in fields:
            if warn_missing_fields:
                logger.error(f"Field {key} of type {type(d[key])} not found in {klass}")
            return False
        return True

    if is_dataclass(klass):
        fieldtypes = {f.name: f.type for f in fields(klass)}
        d = ensure_iterable(d)
        return klass(
            **(
                {
                    f: fromdict(fieldtypes[f], d[f], warn_missing_fields)
                    for f in d
                    if check_field(f, fieldtypes)
                }
            )
        )
    if isinstance(d, list) and hasattr(klass, "__args__"):
        return [fromdict(klass.__args__[0], di, warn_missing_fields) for di in d]
    if isinstance(d, dict) and hasattr(klass, "__args__"):
        return {
            k: fromdict(klass.__args__[1], v, warn_missing_fields) for k, v in d.items()
        }
    return d


from requests import Session, Response
from msgpack import unpackb, packb

from sssekai import __version__
from sssekai.unity import sssekai_get_unity_version
from sssekai.crypto.APIManager import decrypt, encrypt, SEKAI_APIMANAGER_KEYSETS


@dataclass
class AbCacheConfig:
    app_region: str
    app_version: str
    app_platform: str
    app_hash: str


@dataclass
class AbCacheEntry(dict):
    bundleName: str
    cacheFileName: str
    cacheDirectoryName: str
    hash: str
    category: str
    crc: int
    fileSize: int
    dependencies: List[str]
    paths: List[str]
    isBuiltin: bool
    # TW, KR only
    md5Hash: Optional[str] = None
    downloadPath: Optional[str] = None


@dataclass
class AbCacheIndex(dict):
    version: str
    os: Optional[str] = None  # Undefined in KR, TW
    bundles: Mapping[str, AbCacheEntry] = None


@dataclass
class SekaiAppVersion:
    systemProfile: str
    appVersion: str
    multiPlayVersion: str
    appVersionStatus: str
    assetVersion: str
    # These are sadly removed from 3.5.0 (JP)
    dataVersion: Optional[str] = None
    appHash: Optional[str] = None
    assetHash: Optional[str] = None


@dataclass
class SekaiSystemData:
    serverDate: int
    # Undefined in KR, TW
    timezone: Optional[str] = None
    profile: Optional[str] = None
    maintenanceStatus: Optional[str] = None
    appVersions: Optional[List[SekaiAppVersion]] = None

    @cached_property
    def appVersionDict(self):
        return {av.appVersion: av for av in self.appVersions or []}


@dataclass
class SekaiGameVersionData:
    profile: str
    assetbundleHostHash: str
    domain: str


@dataclass
class SekaiUserRegistrationData:
    userId: int
    signature: str
    platform: str
    deviceModel: str
    operatingSystem: str
    registeredAt: int


@dataclass
class SekaiUserData:
    userRegistration: SekaiUserRegistrationData
    credential: str
    updatedResources: dict


@dataclass
class SekaiUserAuthData:
    sessionToken: str
    appVersion: str
    multiPlayVersion: str
    dataVersion: str
    assetVersion: str
    removeAssetVersion: str
    assetHash: str
    appVersionStatus: str
    isStreamingVirtualLiveForceOpenUser: bool
    deviceId: str
    updatedResources: dict
    suiteMasterSplitPath: list
    obtainedBondsRewardIds: Optional[list] = None  # JP 4.0+


@dataclass
class SSSekaiDatabase:
    config: AbCacheConfig = None
    sekai_user_data: SekaiUserData = None
    sekai_user_auth_data: SekaiUserAuthData = None
    sekai_abcache_index: AbCacheIndex = None
    sekai_system_data: SekaiSystemData = None
    sekai_gameversion_data: SekaiGameVersionData = None


class AbCacheBundleNotFoundError(Exception):
    bundleName: str

    def __init__(self, bundleName: str):
        self.bundleName = bundleName
        super().__init__("Bundle not found: %s" % bundleName)


class AbCache(Session):
    database: SSSekaiDatabase

    @property
    def SEKAI_API_ENDPOINT(self):
        match self.config.app_region:
            case "jp":
                return "https://production-game-api.sekai.colorfulpalette.org"
            case "en":
                return "https://n-production-game-api.sekai-en.com"
            case "tw":
                return "https://mk-zian-obt-cdn.bytedgame.com"
            case "kr":
                return "https://mkkorea-obt-prod01-cdn.bytedgame.com"
            case "cn":
                return "https://mkcn-prod-public-30001-1.dailygn.com"
            case _:
                raise NotImplementedError

    @property
    def SEKAI_API_GAMEVERSION_ENDPOINT(self):
        match self.config.app_region:
            case "jp":
                return "https://game-version.sekai.colorfulpalette.org"
            case "en":
                return "https://game-version.sekai-en.com"
            case _:
                raise NotImplementedError

    @property
    def SEKAI_ISSUE_ENDPOINT(self):
        match self.config.app_region:
            case "jp":
                return "https://issue.sekai.colorfulpalette.org"
            case _:
                raise NotImplementedError

    @property
    def SEKAI_AB_INFO_ENDPOINT(self):
        match self.config.app_region:
            case "jp":
                return f"https://production-{self.SEKAI_AB_HOST_HASH}-assetbundle-info.sekai.colorfulpalette.org/api/version/{self.SEKAI_ASSET_VERSION}/os/{self.config.app_platform}"
            case "en":
                return f"https://assetbundle-info.sekai-en.com/api/version/{self.SEKAI_ASSET_VERSION}/os/{self.config.app_platform}"
            case "tw":  # NOTE: Android only
                return f"https://lf16-mkovscdn-sg.bytedgame.com/obj/sf-game-alisg/gdl_app_5245/AssetBundle/{self.config.app_version}/Release/online/android49/AssetBundleInfoNew.json"
            case "kr":  # NOTE: Android only
                return f"https://lf16-mkkr.bytedgame.com/obj/sf-game-alisg/gdl_app_292248/AssetBundle/{self.config.app_version}/Release/kr_online/android21/AssetBundleInfo.json"
            case "cn":  # NOTE: Android only
                return f"https://lf3-mkcncdn-tos.dailygn.com/obj/sf-game-lf/gdl_app_5236/AssetBundle/{self.config.app_version}/Release/cn_online/android50/AssetBundleInfoNew.json"
            case _:
                raise NotImplementedError

    @property
    def SEKAI_AB_ENDPOINT(self):
        match self.config.app_region:
            case "jp":
                return f"https://production-{self.SEKAI_AB_HOST_HASH}-assetbundle.sekai.colorfulpalette.org/"
            case "en":
                return f"https://assetbundle.sekai-en.com/"
            case "tw":  # NOTE: Android only
                return f"https://lf16-mkovscdn-sg.bytedgame.com/obj/sf-game-alisg/gdl_app_5245/AssetBundle/{self.config.app_version}/Release/online/android1/"
            case "kr":  # NOTE: Android only
                return f"https://lf16-mkkr.bytedgame.com/obj/sf-game-alisg/gdl_app_292248/AssetBundle/{self.config.app_version}/Release/kr_online/android4/"
            case "cn":  # NOTE: Android only
                return f"https://lf3-j1gamecdn-cn.dailygn.com/obj/sf-game-lf/gdl_app_5236/AssetBundle/{self.config.app_version}/Release/cn_online/android1/"
            case _:
                raise NotImplementedError

    @property
    def config(self):
        return self.database.config

    @config.setter
    def config(self, v):
        self.database.config = v

    @property
    def SEKAI_APP_VERSION(self):
        return self.config.app_version

    @property
    def SEKAI_APP_PLATFORM(self):
        return self.config.app_platform

    @property
    def SEKAI_APP_HASH(self):
        return self.config.app_hash

    @property
    def SEKAI_ASSET_VERSION(self):
        return self.database.sekai_system_data.appVersionDict[
            self.SEKAI_APP_VERSION
        ].assetVersion

    @property
    def SEKAI_AB_HASH(self):
        return self.database.sekai_user_auth_data.assetHash

    @property
    def SEKAI_AB_HOST_HASH(self):
        return self.database.sekai_gameversion_data.assetbundleHostHash

    @property
    def SEKAI_API_SYSTEM_DATA(self):
        return self.SEKAI_API_ENDPOINT + "/api/system"

    @property
    def SEKAI_API_USER(self):
        return self.SEKAI_API_ENDPOINT + "/api/user"

    @property
    def SEKAI_API_USER_AUTH(self):
        return f"{self.SEKAI_API_USER}/{self.database.sekai_user_data.userRegistration.userId}/auth?refreshUpdatedResources=False"

    @property
    def SEKAI_API_USER_SUITE(self):
        return f"{self.SEKAI_API_ENDPOINT}/api/suite/user/{self.database.sekai_user_data.userRegistration.userId}"

    @property
    def SEKAI_API_MASTER_SUITE(self):
        return f"{self.SEKAI_API_ENDPOINT}/api/suite/master"

    @property
    def SEKAI_API_INFORMATION(self):
        return self.SEKAI_API_ENDPOINT + "/api/information"

    @property
    def SEKAI_AB_BASE_PATH(self):
        return f"{self.SEKAI_ASSET_VERSION}/{self.SEKAI_AB_HASH}/{self.config.app_platform}/"

    @property
    def SEKAI_ISSUE_SIGNATURE_ENDPOINT(self):
        return self.SEKAI_ISSUE_ENDPOINT + "/api/signature"

    @property
    def abcache_index(self):
        return self.database.sekai_abcache_index

    def request_packed(self, method: str, url: str, data: dict = None, **kwargs):
        """Send a request with packed data. Data will be packed and encrypted before sending.

        Args:
            method (str): HTTP method
            url (str): URL
            data (dict, optional): Payload data. Defaults to None.

        Returns:
            Response: Response object
        """
        if data is not None:
            data = packb(data)
            data = encrypt(data, SEKAI_APIMANAGER_KEYSETS[self.config.app_region])
        resp = self.request(method=method, url=url, data=data, **kwargs)
        resp.raise_for_status()
        return resp

    def response_to_dict(self, resp: Response):
        """Decrypt and unpack a response content to a dictionary.

        Args:
            resp (Response): Response object

        Returns:
            dict: Decrypted and unpacked data
        """
        data = decrypt(resp.content, SEKAI_APIMANAGER_KEYSETS[self.config.app_region])
        data = unpackb(data)
        return data

    def _update_signatures(self):
        if self.config.app_region in {"jp"}:
            logger.debug("Updating signatures")
            resp = self.request_packed("POST", self.SEKAI_ISSUE_SIGNATURE_ENDPOINT)
            self.headers["Cookie"] = resp.headers["Set-Cookie"]
            # HACK: Per RFC6265, Cookies should not be visible to subdomains since it's not set with Domain attribute (https://github.com/psf/requests/issues/2576)
            # But the other endpoints uses it nontheless. So we have to set it manually.

    def _update_user_data(self):
        if self.config.app_region in {"jp", "en"}:
            logger.debug("Updating user data")
            payload = {
                "platform": self.headers["X-Platform"],
                "deviceModel": self.headers["X-DeviceModel"],
                "operatingSystem": self.headers["X-OperatingSystem"],
            }
            resp = self.request_packed("POST", self.SEKAI_API_USER, data=payload)
            data = self.response_to_dict(resp)
            self.database.sekai_user_data = fromdict(SekaiUserData, data)

    def _update_user_auth_data(self):
        if self.config.app_region in {"jp", "en"}:
            logger.debug("Updating user auth data")
            payload = {
                "credential": self.database.sekai_user_data.credential,
                "deviceId": None,
            }
            resp = self.request_packed("PUT", self.SEKAI_API_USER_AUTH, data=payload)
            data = self.response_to_dict(resp)
            self.database.sekai_user_auth_data = fromdict(SekaiUserAuthData, data)

    def _update_system_data(self):
        logger.debug("Updating system data")
        resp = self.request_packed("GET", self.SEKAI_API_SYSTEM_DATA)
        data = self.response_to_dict(resp)
        self.database.sekai_system_data = fromdict(SekaiSystemData, data)

    def _update_gameversion_data(self):
        if self.config.app_region in {"jp", "en"}:
            logger.debug("Updating game version data")
            resp = self.request_packed(
                "GET",
                self.SEKAI_API_GAMEVERSION_ENDPOINT
                + "/"
                + self.SEKAI_APP_VERSION
                + "/"
                + self.SEKAI_APP_HASH,
            )
            data = self.response_to_dict(resp)
            self.database.sekai_gameversion_data = fromdict(SekaiGameVersionData, data)

    def _update_abcache_index(self) -> AbCacheIndex:
        logger.debug("Updating Assetbundle index")
        resp = self.request_packed("GET", self.SEKAI_AB_INFO_ENDPOINT)
        data = self.response_to_dict(resp)
        self.database.sekai_abcache_index = fromdict(AbCacheIndex, data)
        return self.database.sekai_abcache_index

    def __init__(self, config: Optional[AbCacheConfig] = None):
        super().__init__()
        self.database = SSSekaiDatabase()
        if config is not None:
            self.config = config
            self.config.app_platform = self.config.app_platform.lower()
            self.headers.update(
                {
                    "Accept": "application/octet-stream",
                    "Content-Type": "application/octet-stream",
                    "Accept-Encoding": "deflate, gzip",
                    "User-Agent": "UnityPlayer/%s" % sssekai_get_unity_version(),
                    "X-Platform": self.config.app_platform.capitalize(),
                    "X-DeviceModel": "sssekai/%s" % __version__,
                    "X-OperatingSystem": self.config.app_platform.capitalize(),
                    "X-Unity-Version": sssekai_get_unity_version(),
                    "X-App-Version": self.SEKAI_APP_VERSION,
                    "X-App-Hash": self.SEKAI_APP_HASH,
                }
            )

    def update_download_headers(self):
        """Update headers for downloading assetbundles *ONLY*. Functionalities related to user-level data (e.g. Master Data, etc) won't
        be available.

        Returns:
            dict: Updated headers
        """
        self._update_signatures()
        return self.headers

    def update_client_headers(self):
        """Update headers for client-level functionalities. This includes user-level data (e.g. Master Data, etc) and assetbundle data.

        Returns:
            _type_: _description_
        """
        logger.debug("Updating metadata")
        logger.debug("Set config: %s" % self.config)
        self._update_signatures()
        self._update_system_data()
        if self.config.app_region in {"jp", "en"}:
            version_newest = self.database.sekai_system_data.appVersions[-1]
            logger.debug("Newest App version: %s" % version_newest)
            if version_newest.appVersion != self.SEKAI_APP_VERSION:
                logger.warning("App version mismatch. This may cause issues.")
        self._update_gameversion_data()
        self._update_user_data()
        self._update_user_auth_data()
        if self.config.app_region in {"jp", "en"}:
            self.headers.update(
                {
                    "X-Data-Version": self.database.sekai_user_auth_data.dataVersion,
                    "X-Asset-Version": self.database.sekai_user_auth_data.assetVersion,
                    "X-Session-Token": self.database.sekai_user_auth_data.sessionToken,
                }
            )
        return self.headers

    def update(self):
        self.update_client_headers()
        self._update_abcache_index()
        if self.config.app_region in {"jp", "en"}:
            logger.debug("Sekai AssetBundle version: %s" % self.SEKAI_ASSET_VERSION)
            logger.debug("Sekai AssetBundle host hash: %s" % self.SEKAI_AB_HOST_HASH)

    def save(self, f: BinaryIO):
        logger.debug("Saving cache")
        dump(self.database, f)

    def load(self, f: BinaryIO):
        logger.debug("Loading cache")
        self.database = load(f)
        logger.debug("Cache loaded: %s" % self)

    def __repr__(self) -> str:
        return (
            f"AbCache(config={self.config} bundles={len(self.abcache_index.bundles)})"
        )

    def get_entry_by_bundle_name(self, bundleName: str) -> AbCacheEntry:
        return self.abcache_index.bundles.get(bundleName, None)

    def get_entry_download_url(self, entry: AbCacheEntry):
        if self.config.app_region in {"jp", "en"}:
            return self.SEKAI_AB_ENDPOINT + self.SEKAI_AB_BASE_PATH + entry.bundleName
        else:
            return self.SEKAI_AB_ENDPOINT + entry.bundleName

    def get_or_update_dependency_tree_flatten(self, bundleName: str, deps: set = None):
        """Get a flattened set of asset dependency bundle names (including itself) for a given entry.

        Returned order is topologically sorted.

        if 'deps' is provided, it will be used as the initial set of dependencies.
        """
        deps = deps or set()

        def dfs(bundleName):
            for dep in self.abcache_index.bundles[bundleName].dependencies:
                if dep not in deps:
                    dfs(dep)
                    deps.add(dep)

        dfs(bundleName)
        deps.add(bundleName)
        return deps
