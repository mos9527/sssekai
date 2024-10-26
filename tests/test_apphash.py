from . import *


def test_apphash():
    from sssekai.entrypoint.apphash import main_apphash

    result = main_apphash(
        NamedDict(
            {"ab_src": sample_file_path("apphash", "6350e2ec327334c8a9b7f494f344a761")}
        )
    )


if __name__ == "__main__":
    test_apphash()
