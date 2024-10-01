from test_base import *


class NamedDict(dict):
    def __getattribute__(self, name: str):
        try:
            return super().__getattribute__(name)
        except AttributeError:
            return self.get(name, None)


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


def test_live2d_model():
    from sssekai.entrypoint.live2dextract import main_live2dextract

    result = main_live2dextract(
        NamedDict(
            {
                "infile": sample_file_path("live2d", "21miku_night"),
                "outdir": TEMP_DIR,
            }
        )
    )
