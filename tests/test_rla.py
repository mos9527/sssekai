from . import *


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
