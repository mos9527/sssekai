import os

from coloredlogs import install
from logging import getLogger, DEBUG

install(level=DEBUG)
logger = getLogger("tests")

import UnityPy, sssekai

logger.info("UnityPy Version: %s" % UnityPy.__version__)
logger.info("SSSekai Version: %s" % sssekai.__version__)

SOURCE_DIR = os.path.dirname(__file__)
sample_file_path = lambda *args: os.path.join(SOURCE_DIR, *args)
TEMP_DIR = sample_file_path(".temp")


class NamedDict(dict):
    def __getattribute__(self, name: str):
        try:
            return super().__getattribute__(name)
        except AttributeError:
            return self.get(name, None)
