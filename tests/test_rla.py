from . import *


def test_rla_1_6_split():
    PATHS = [
        sample_file_path("rla", "1740309585940-0.bin"),
        sample_file_path("rla", "1740309585941-0.bin"),
    ]
    from sssekai.fmt.rla import read_rla_frames

    bingen = (open(f, "rb").read() for f in PATHS)
    for frame in read_rla_frames(bingen, (1, 6)):
        print("ok", frame["type"])


def test_rla_1_5():
    PATH = sample_file_path("rla", "1728191806276-0.bin")
    from sssekai.fmt.rla import read_rla_frame

    with open(PATH, "rb") as f:
        frame = read_rla_frame(f.read(), (1, 5), True)


def test_rla_1_4():
    PATH = sample_file_path("rla", "1718434788237-0.bin")
    from sssekai.fmt.rla import read_rla_frame

    with open(PATH, "rb") as f:
        frame = read_rla_frame(f.read(), (1, 4), True)


def test_rla_1_0():
    PATH = sample_file_path("rla", "streaming_live_vbs_1-0_0.bin")
    from sssekai.fmt.rla import read_rla_frame

    with open(PATH, "rb") as f:
        frame = read_rla_frame(f.read(), (1, 0), True)


if __name__ == "__main__":
    test_rla_1_5()
    test_rla_1_4()
    test_rla_1_0()
