from . import AbCache, AbCacheConfig
from logging import getLogger
import json

logger = getLogger(__name__)


def set_anoymous_acc_sega(config: AbCacheConfig):
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
    return config


AUTH_CONFIG_BYTEDANCE_TW = {
    "aid": 5245,
    "app_name": "pjsk_oversea",
    "app_package": "com.hermes.mk.asia",
    "sdk_app_id": 1782,
    "game_id": 5245,
}


def _generate_device_id():
    import uuid

    uid = uuid.uuid1().bytes[8:]
    uid = int.from_bytes(uid, "little")
    uid = str(uid).ljust(19, "0")
    return uid[:19]


__device_id = _generate_device_id()


def __gen_bytedance_headers(config: AbCacheConfig):
    auth_config = dict()
    match config.app_region:
        case "tw":
            auth_config = AUTH_CONFIG_BYTEDANCE_TW
        case _:
            raise NotImplementedError("Region not supported")
    return {
        "device_id": __device_id,
        "channel": "GooglePlay",
        "os": config.app_platform.lower(),
        **auth_config,
    }


def acc_logout_bytedance(config: AbCacheConfig, token: str):
    logger.info("Logging out from ByteDance servers")

    with AbCache(config) as session:
        params = __gen_bytedance_headers(config)
        params |= {
            "login_type": "home",
            "user_type": 1,
            "iid": __device_id,
        }
        resp = session.request(
            "POST",
            "https://gsdk-sg.bytegsdk.com/gsdk/account/logout",
            params=params,
            data={
                "device_id": __device_id,
                "token": token,
                "channel_id": "bsdkintl",
            },
            headers={
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8"
            },
        )
        resp.raise_for_status()
        logger.info("Success. Token was=%s" % token)


def set_acc_bytedance(config: AbCacheConfig, user_id: str, token: str):
    logger.info("Logging into ByteDance servers")

    with AbCache(config) as session:
        params = __gen_bytedance_headers(config)
        params |= {
            "login_type": "home",
            "user_type": 1,
            "iid": __device_id,
        }
        resp = session.request(
            "POST",
            "https://gsdk-sg.bytegsdk.com/gsdk/account/login",
            params=params,
            data={
                "device_id": __device_id,
                "data": json.dumps({"user_id": str(user_id), "token": token}),
                "channel_id": "bsdkintl",
            },
            headers={
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8"
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if "data" in data:
            data = data["data"]
            logger.info("Success. AccessToken=%s" % data["access_token"])
            config.auth_userID = user_id
            config.auth_credential = data["access_token"]
            return config
        else:
            raise Exception("Failed to register user data: %s" % resp.text)


def set_anoymous_acc_bytedance(config: AbCacheConfig):
    logger.info("Registering user data")

    with AbCache(config) as session:
        params = __gen_bytedance_headers(config)
        params |= {
            "login_type": "home",
            "user_type": 1,
            "ui_flag": 1,
            "is_create": 0,
        }
        resp = session.request(
            "POST",
            "https://gsdk-sg.bytegsdk.com/sdk/account/visitor_login",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        if "data" in data:
            data = data["data"]
            logger.info(
                "Success. User =ID=%s, Token=%s" % (data["user_id"], data["token"])
            )
            acc_logout_bytedance(config, data["token"])
            return set_acc_bytedance(config, data["user_id"], data["token"])
        else:
            raise Exception("Failed to register user data: %s" % resp.text)
