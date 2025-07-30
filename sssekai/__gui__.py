from dataclasses import dataclass, field
from sssekai.__main__ import create_parser
from typing import Any, List
from argparse import ArgumentParser
from logging import basicConfig, getLogger
import sys

try:
    from GooeyEx import Gooey, GooeyParser
except ImportError as e:
    print(
        "Please install sssekai[gui] through your Python package manager to use the GUI"
    )
    raise e


from sssekai.unity import sssekai_set_unity_version


@Gooey(
    show_preview_warning=False,
    program_name="sssekai",
    tabbed_groups=True,
    advanced=True,
    monospace_display=True,
    default_size=(800, 600),
    menu=[
        {
            "name": "Help",
            "items": [
                {
                    "type": "Link",
                    "menuTitle": "Project Wiki",
                    "url": "https://github.com/mos9527/sssekai/wiki",
                },
                {
                    "type": "Link",
                    "menuTitle": "GitHub",
                    "url": "https://github.com/mos9527/sssekai",
                },
            ],
        }
    ],
)
def __main__():
    from tqdm.std import tqdm as tqdm_c

    parser = create_parser(GooeyParser)
    args = parser.parse_args()

    class TqdmMutexStream:
        @staticmethod
        def write(__s):
            # Gooey[Ex] only reads output from stdout so we'd do that here.
            with tqdm_c.external_write_mode(file=sys.stdout, nolock=False):
                return sys.stdout.write(__s)

    basicConfig(
        level="DEBUG",
        format="%(asctime)s | %(levelname).1s | %(name)s %(message)s",
        datefmt="%H:%M:%S",
        stream=TqdmMutexStream,
    )
    # override unity version
    sssekai_set_unity_version(args.unity_version)
    if "func" in args:
        args.func(args)
    pass


if __name__ in {"__main__", "__gui__"}:
    __main__()
