from . import *


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


if __name__ == "__main__":
    test_live2d_motion()
    test_live2d_model()
