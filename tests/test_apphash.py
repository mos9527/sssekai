from . import *


def test_apphash():
    from sssekai.entrypoint.apphash import main_apphash

    result = main_apphash(NamedDict())
