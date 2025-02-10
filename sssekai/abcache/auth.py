from . import AbCache, SekaiUserData, fromdict
from logging import getLogger

logger = getLogger(__name__)


def sega_register_anonymous_user(cache: AbCache) -> SekaiUserData:
    """Registers an anonymous account on SEGA servers, and writes relavant data to the AbCacheobject.

    Args:
        cache: The AbCache object to write the user data to.

    Returns:
        SekaiUserData: The user data object.
    """
    logger.info("Registering user data")
    cache._update_signatures()
    payload = {
        "platform": cache.headers["X-Platform"],
        "deviceModel": cache.headers["X-DeviceModel"],
        "operatingSystem": cache.headers["X-OperatingSystem"],
    }
    resp = cache.request_packed("POST", cache.SEKAI_API_USER, data=payload)
    data = cache.response_to_dict(resp)
    cache.config.auth_credential = data["credential"]
    logger.info("Success. User ID=%s" % cache.config.auth_userID)
    cache.database.sekai_user_data = data
    return fromdict(SekaiUserData, data)
