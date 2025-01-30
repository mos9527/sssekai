from . import AbCache, AbCacheConfig, SekaiUserData, fromdict
from logging import getLogger

logger = getLogger(__name__)


def set_anonymous_acc_sega(config: AbCacheConfig) -> SekaiUserData:
    logger.info("Registering user data")
    with AbCache(config) as session:
        session._update_signatures()
        payload = {
            "platform": session.headers["X-Platform"],
            "deviceModel": session.headers["X-DeviceModel"],
            "operatingSystem": session.headers["X-OperatingSystem"],
        }
        resp = session.request_packed("POST", session.SEKAI_API_USER, data=payload)
        data = session.response_to_dict(resp)
        config.auth_userID = data["userRegistration"]["userId"]
        config.auth_credential = data["credential"]
        logger.info("Success. User ID=%s" % config.auth_userID)
    return fromdict(SekaiUserData, data)
