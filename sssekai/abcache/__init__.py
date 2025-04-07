from collections import defaultdict
from pickle import load, dump
from typing import BinaryIO, List, Mapping, Optional, Union, Tuple
from logging import getLogger
from dataclasses import dataclass, fields, is_dataclass, field
from functools import cached_property
from base64 import b64encode, b64decode
import json

logger = getLogger("sssekai.abcache")

REGION_JP_EN = {"jp", "en"}
REGION_ROW = {"tw", "kr", "cn"}
REGION_OPTIONS = REGION_JP_EN | REGION_ROW


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


from requests import Session, Response, HTTPError
from msgpack import unpackb, packb

from sssekai import __version__, __version_tuple__
from sssekai.unity import sssekai_get_unity_version
from sssekai.crypto.APIManager import decrypt, encrypt, SEKAI_APIMANAGER_KEYSETS


@dataclass
class AbCacheConfig:
    app_region: str
    app_version: str
    app_platform: str
    app_hash: str

    ab_version: str = None  # Override AB version in url for ROW
    auth_credential: str = None  # JWT token for JP/EN, Base64 encoded JWT token for ROW

    version: Tuple[int, int, int] = (0, 0, 0)  # Internal versioning

    @property
    def auth_jwt(self) -> str:
        if self.app_region in REGION_JP_EN:
            return self.auth_credential
        else:
            return b64decode(self.auth_credential).decode()

    @property
    def auth_jwt_payload(self) -> dict:
        header, payload, signature = self.auth_jwt.split(".")
        return json.loads(b64decode(payload + "=="))

    @property
    def auth_userID(self) -> str:
        return self.auth_jwt_payload.get("userId", None)

    @property
    def auth_available(self):
        return self.auth_credential is not None

    @property
    def cache_version(self):
        return getattr(self, "version", (0, 0, 0))

    @property
    def cache_version_string(self):
        return "%s.%s.%s" % self.cache_version if self.cache_version else "pre-0.5.17"

    @property
    def is_up_to_date(self):
        return self.cache_version == __version_tuple__


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
    # ROW only
    md5Hash: Optional[str] = None
    downloadPath: Optional[str] = None


@dataclass
class AbCacheIndex(dict):
    version: str
    os: Optional[str] = None  # Undefined in ROW
    bundles: Mapping[str, AbCacheEntry] = None


# DS for the game's APIs
# There're *plenty* differences across regions. The implementations here
#   - Contains all the fields, even if they're not used in all regions
#   - Only the fields that are common across regions are non Optional[T]
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
    # These are all undefined in ROW
    timezone: Optional[str] = None
    profile: Optional[str] = None
    maintenanceStatus: Optional[str] = None
    appVersions: Optional[List[SekaiAppVersion]] = None

    @cached_property
    def app_version_dict(self):
        return {av.appVersion: av for av in self.appVersions or []}


@dataclass
class SekaiGameVersionData:
    profile: str
    assetbundleHostHash: str
    domain: str


@dataclass
class SekaiUserRegistrationData:
    userId: int
    # JP/EN only
    signature: Optional[str] = None
    platform: Optional[str] = None
    deviceModel: Optional[str] = None
    operatingSystem: Optional[str] = None
    registeredAt: Optional[int] = None


@dataclass
class SekaiUserData:
    userRegistration: SekaiUserRegistrationData
    # JP/EN Only
    credential: Optional[str] = None
    updatedResources: Optional[dict] = None
    # ROW
    sessionToken: Optional[str] = None

    @property
    def user_credentials(self):
        return self.credential or self.sessionToken


@dataclass
class SekaiUserAuthData:
    sessionToken: str
    appVersion: str
    multiPlayVersion: str
    dataVersion: str
    assetVersion: str

    # JP/EN only
    removeAssetVersion: Optional[str] = None
    assetHash: Optional[str] = None

    appVersionStatus: Optional[str] = None

    # JP/EN only
    isStreamingVirtualLiveForceOpenUser: Optional[bool] = None
    deviceId: Optional[str] = None
    updatedResources: Optional[dict] = None
    suiteMasterSplitPath: Optional[list] = None
    obtainedBondsRewardIds: Optional[list] = None  # JP 4.0+

    # ROW
    configs: Optional[List[dict]] = None


@dataclass
class SSSekaiDatabase:
    config: AbCacheConfig = None
    cached_headers: dict = field(default_factory=dict)

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


class AbCacheUserNotAuthenticatedError(Exception):
    pass


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
                return "https://mkcn-prod-public-60001-1.dailygn.com"
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
                return f"https://lf16-mkovscdn-sg.bytedgame.com/obj/sf-game-alisg/gdl_app_5245/AssetBundle/{self.config.ab_version or self.config.app_version}/Release/online/android71/AssetBundleInfoNew.json"
            case "kr":  # NOTE: Android only
                return f"https://lf16-mkkr.bytedgame.com/obj/sf-game-alisg/gdl_app_292248/AssetBundle/{self.config.ab_version or self.config.app_version}/Release/kr_online/android63/AssetBundleInfoNew.json"
            case "cn":  # NOTE: Android only
                # https://github.com/mos9527/sssekai/issues/28
                return f"https://lf3-mkcncdn-tos.dailygn.com/obj/sf-game-lf/gdl_app_5236/AssetBundle/{self.config.ab_version or self.config.app_version}/Release/cn_online1/android91/AssetBundleInfoNew.json"
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
                return f"https://lf16-mkovscdn-sg.bytedgame.com/obj/sf-game-alisg/gdl_app_5245/AssetBundle/{self.config.ab_version or self.config.app_version}/Release/online/android1/"
            case "kr":  # NOTE: Android only
                return f"https://lf16-mkkr.bytedgame.com/obj/sf-game-alisg/gdl_app_292248/AssetBundle/{self.config.ab_version or self.config.app_version}/Release/kr_online/android1/"
            case "cn":  # NOTE: Android only
                # https://github.com/mos9527/sssekai/issues/28
                return f"https://lf3-j1gamecdn-cn.dailygn.com/obj/sf-game-lf/gdl_app_5236/AssetBundle/{self.config.ab_version or self.config.app_version}/Release/cn_online1/android65/"
            case _:
                raise NotImplementedError

    def _update_request_headers(self):
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
        return self.database.sekai_system_data.app_version_dict[
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
    def SEKAI_USERID(self):
        return self.config.auth_userID or (
            self.database.sekai_user_data.userRegistration.userId
            if self.database.sekai_user_data
            else None
        )

    @property
    def SEKAI_CREDENTIAL(self):
        """Keyed in SEKAI_API_USER responses. `accessToken` in ROW servers, `credential` in JP/EN."""
        return self.config.auth_credential or (
            self.database.sekai_user_data.credential
            if self.database.sekai_user_data
            else None
        )

    @property
    def is_authenticated(self):
        return self.database.sekai_user_auth_data is not None

    def raise_for_auth(self, *args):
        if not self.is_authenticated:
            raise AbCacheUserNotAuthenticatedError(*args)

    @property
    def SEKAI_API_USER_AUTH(self):
        if self.config.app_region in REGION_JP_EN:
            assert self.SEKAI_USERID, "User ID must be available"
            return f"{self.SEKAI_API_USER}/{self.SEKAI_USERID}/auth"
        else:
            # For ROW this is the endpoint that retrives SEKAI_API_USER level data as well
            return f"{self.SEKAI_API_USER}/auth"

    @property
    def SEKAI_API_USER_SUITE(self):
        self.raise_for_auth()
        return f"{self.SEKAI_API_ENDPOINT}/api/suite/user/{self.SEKAI_USERID}"

    @property
    def SEKAI_API_MASTER_SUITE_URLS(self):
        match self.config.app_region:
            case "jp":
                self.raise_for_auth()
                return [
                    f"{self.SEKAI_API_ENDPOINT}/api/{path}"
                    for path in self.database.sekai_user_auth_data.suiteMasterSplitPath
                ]
            case "en":
                self.raise_for_auth()
                return [
                    f"{self.SEKAI_API_ENDPOINT}/api/{path}"
                    for path in self.database.sekai_user_auth_data.suiteMasterSplitPath
                ]
            # NOTE: All ROW servers have hardcoded master data URLs in *one* file as of the time of writing.
            # NOTE: Some of the MessagePack schemas is also *omitted* in these endpoints. Good luck parsing them.
            case "tw":
                return [
                    "https://lf21-mkovscdn-sg.bytedgame.com/obj/sf-game-alisg/gdl_app_5245/MasterData/60001/master-data-138.info"
                ]
            case "kr":
                return [
                    "https://lf19-mkkr.bytedgame.com/obj/sf-game-alisg/gdl_app_292248/MasterData/60001/master-data-158.info"
                ]
            case "cn":
                # Verified by https://github.com/mos9527/sssekai/issues/24
                return [
                    "https://lf3-mkcncdn-tos.dailygn.com/obj/sf-game-lf/gdl_app_5236/MasterData/60001/master-data-13.info"
                ]

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
        self._update_request_headers()
        if data is not None:
            data = packb(data)
            data = encrypt(data, SEKAI_APIMANAGER_KEYSETS[self.config.app_region])
        resp = self.request(method=method, url=url, data=data, **kwargs)
        if 400 <= resp.status_code < 600:
            logger.error(f"{method} {url} {resp.status_code}")
            try:  # log the error message provided by the API.
                content = self.response_to_dict(resp)
                logger.error("response=%s" % content)
            except:
                logger.error("response=%s" % resp.content)
            resp.raise_for_status()
        return resp

    def response_to_dict(self, resp: Response, **kwargs):
        """Decrypt and unpack a response content to a dictionary.

        Args:
            resp (Response): Response object
            **kwargs: Additional arguments for MessagePack unpackb

        Returns:
            dict: Decrypted and unpacked data
        """
        data = decrypt(resp.content, SEKAI_APIMANAGER_KEYSETS[self.config.app_region])
        data = unpackb(data, **kwargs)
        return data

    def _update_user_auth_data(self):
        if self.config.auth_available:
            logger.debug("Updating user auth data")
            if self.config.app_region in REGION_JP_EN:
                resp = self.request_packed(
                    "PUT",
                    self.SEKAI_API_USER_AUTH,
                    data={"credential": self.SEKAI_CREDENTIAL, "deviceId": None},
                )
            else:
                resp = self.request_packed(
                    "POST",
                    self.SEKAI_API_USER_AUTH,
                    data={
                        "accessToken": self.SEKAI_CREDENTIAL,
                        "deviceId": None,
                        "userID": 0,
                    },
                )
            data = self.response_to_dict(resp)
            self.database.sekai_user_auth_data = fromdict(
                SekaiUserAuthData, data, False
            )
            if self.config.app_region in REGION_ROW:
                self.database.sekai_user_data = fromdict(SekaiUserData, data, False)
        else:
            if self.config.app_region in REGION_JP_EN:
                raise AbCacheUserNotAuthenticatedError(
                    "Auth config is required for accessing JP/EN game server content"
                )

    def _update_system_data(self):
        logger.debug("Updating system data")
        resp = self.request_packed("GET", self.SEKAI_API_SYSTEM_DATA)
        data = self.response_to_dict(resp)
        self.database.sekai_system_data = fromdict(SekaiSystemData, data)

    def _update_gameversion_data(self):
        if self.config.app_region in REGION_JP_EN:
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

    def _update_signatures(self):
        """Only required for JP for the initial setup. After which the game would cache the signature/cookies."""
        if self.config.app_region in {"jp"}:
            logger.debug("Updating signatures")
            # XXX: Clear all cookies, it 403s otherwise. Does this trigger a rate limit/expiry check since our session would be tracked?
            self.headers["Cookie"] = ""
            self.cookies.clear()
            resp = self.request_packed("POST", self.SEKAI_ISSUE_SIGNATURE_ENDPOINT)
            self.headers["Cookie"] = resp.headers["Set-Cookie"]
            # HACK: Per RFC6265, Cookies should not be visible to subdomains since it's not set with Domain attribute (https://github.com/psf/requests/issues/2576)
            # But the other endpoints uses it nontheless. So we have to set it manually.

    def __init__(self, config: Optional[AbCacheConfig] = None):
        super().__init__()
        self.database = SSSekaiDatabase()
        self.config = config or AbCacheConfig(
            "unknown", "unknown", "unknown", "unknown"
        )
        self.config.version = __version_tuple__

    def update_client_headers(self):
        """Authenticate the user and update client headers WITHOUT updating the AssetBundle Index.

        NOTE:
            - For JP/EN servers, `auth_credential` NEED to be set or otherwise you won't be able to do anything.
            - For ROW servers, it's OK to leave them empty.
                - To access user-level data, however, you still NEED to be authenticated.
        """
        logger.debug("Updating metadata")
        logger.debug("Set config: %s" % self.config)
        try:
            self._update_signatures()
            self._update_system_data()
        except HTTPError as e:
            logger.warning("Attempting to update signatures: %s" % e)
            self._update_signatures()
            self._update_system_data()
        if self.config.app_region in REGION_JP_EN:
            version_newest = self.database.sekai_system_data.appVersions[-1]
            logger.debug("Newest App version: %s" % version_newest)
            if version_newest.appVersion != self.SEKAI_APP_VERSION:
                logger.warning("App version mismatch. This may cause issues.")
        self._update_gameversion_data()
        self._update_user_auth_data()
        if self.is_authenticated:
            self.headers.update(
                {
                    "X-Data-Version": self.database.sekai_user_auth_data.dataVersion,
                    "X-Asset-Version": self.database.sekai_user_auth_data.assetVersion,
                    "X-Session-Token": self.database.sekai_user_auth_data.sessionToken,
                }
            )
        return self.headers

    def update(self):
        """Update the cache with the latest AssetBundle Index data from the server.

        NOTE:
            AbCache should have been initialized with a valid config before calling this method.
            Please refer to `update_client_headers` for more information.
        """
        self.update_client_headers()
        self._update_abcache_index()
        if self.config.app_region in REGION_JP_EN:
            logger.debug("Sekai AssetBundle version: %s" % self.SEKAI_ASSET_VERSION)
            logger.debug("Sekai AssetBundle host hash: %s" % self.SEKAI_AB_HOST_HASH)

    def save(self, f: BinaryIO):
        self._update_request_headers()
        self.database.cached_headers = self.headers
        logger.debug("Saving cache")
        dump(self.database, f)

    def load(self, f: BinaryIO):
        logger.debug("Loading cache")
        self.database = load(f)
        if not self.database.config.is_up_to_date:
            logger.warning(
                "Cache is outdated (cache: %s, current: %s). It's HIGHLY recommended to update the cache to avoid issues."
                % (self.database.config.cache_version_string, __version__)
            )
        self.headers.update(self.database.cached_headers)
        logger.debug("Cache loaded: %s" % self)

    @staticmethod
    def from_file(f: BinaryIO):
        cache = AbCache()
        cache.load(f)
        return cache

    def __repr__(self) -> str:
        return (
            f"AbCache(config={self.config} bundles={len(self.abcache_index.bundles)})"
        )

    def get_entry_by_bundle_name(self, bundleName: str) -> AbCacheEntry:
        return self.abcache_index.bundles.get(bundleName, None)

    def get_entry_download_url(self, entry: AbCacheEntry):
        if self.config.app_region in REGION_JP_EN:
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
