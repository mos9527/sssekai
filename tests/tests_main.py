import os
from coloredlogs import install
from logging import getLogger, DEBUG

install(level=DEBUG)
logger = getLogger("tests")

import UnityPy, sssekai

logger.info("UnityPy Version: %s" % UnityPy.__version__)
logger.info("SSSekai Version: %s" % sssekai.__version__)


class NamedDict(dict):
    def __getattribute__(self, name: str):
        try:
            return super().__getattribute__(name)
        except AttributeError:
            return self.get(name, None)


SAMPLE_DIR = os.path.dirname(__file__)
sample_file_path = lambda *args: os.path.join(SAMPLE_DIR, *args)
TEMP_DIR = sample_file_path(".temp")


def test_live2d_motion():
    from sssekai.entrypoint.live2dextract import main_live2dextract

    result = main_live2dextract(
        NamedDict(
            {
                "infile": sample_file_path("live2d", "21miku_motion_base"),
                "outdir": TEMP_DIR,
            }
        )
    )


test_live2d_motion()
