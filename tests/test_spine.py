from . import *


def test_spineextract():
    from sssekai.entrypoint.spineextract import main_spineextract

    result = main_spineextract(
        NamedDict(
            {
                "infile": sample_file_path("spine", "base_model"),
                "outdir": TEMP_DIR,
            }
        )
    )


if __name__ == "__main__":
    test_spineextract()
