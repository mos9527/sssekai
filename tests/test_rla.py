from . import *


def __check_paths(paths: list, version: tuple):
    from sssekai.fmt.rla import read_rla_frames

    bingen = ((f, open(sample_file_path("rla", f), "rb").read()) for f in paths)
    for tick, frame in read_rla_frames(bingen, version):
        print("ok", tick, frame["type"])


def test_rla_1_6_split():
    PATHS = [
        "1740309585940-0.bin",
        "1740309585941-0.bin",
    ]
    __check_paths(PATHS, (1, 6))


def test_rla_1_5():
    PATHS = ["1728191806276-0.bin"]
    __check_paths(PATHS, (1, 5))


def test_rla_1_4():
    PATHS = ["1718434788237-0.bin"]
    __check_paths(PATHS, (1, 4))


def test_rla_1_0():
    PATH = ["streaming_live_vbs_1-0_0.bin"]
    __check_paths(PATH, (1, 0))


if __name__ == "__main__":
    test_rla_1_6_split()
    test_rla_1_5()
    test_rla_1_4()
    test_rla_1_0()
