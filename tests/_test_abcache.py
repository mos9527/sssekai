# Test with:
# pytest -v -s .\tests\_test_abcache.py
from . import *
import traceback

CONFIG = "https://raw.githubusercontent.com/mos9527/sekai-apphash/refs/heads/master/%(region)s/apphash.json"
REGIONS = ["en", "cn", "jp", "tw", "kr"]

from requests import get


def test_abcache():
    from sssekai.entrypoint.abcache import main_abcache

    for region in REGIONS:
        flag = False
        for _ in range(5):
            try:
                config = get(CONFIG % {"region": region}).json()
                main_abcache(
                    NamedDict(
                        {
                            "app_platform": "android",
                            "app_region": region,
                            "app_version": config["app_version"],
                            "app_appHash": config["app_hash"],
                            "app_abVersion": config["ab_version"],
                            "db": os.path.join(TEMP_DIR, "abcache.db"),
                        }
                    )
                )
                flag = True
                break
            except Exception as e:
                logger.error(f"Error occurred for region {region}: {e}")
                logger.error(traceback.format_exc())
                logger.error("Retrying. n=%d" % _)
        assert flag, f"All attemptes failed for region {region}"


if __name__ == "__main__":
    test_abcache()
