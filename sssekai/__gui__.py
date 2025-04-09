from dataclasses import dataclass, field
from sssekai.__main__ import create_parser
from typing import Any, List
from argparse import ArgumentParser
from logging import basicConfig, getLogger
import sys

try:
    from GooeyEx import Gooey, GooeyParser
except ImportError as e:
    print("Please install sssekai[gui] to use the GUI")
    raise e


from sssekai.unity import sssekai_set_unity_version


@Gooey(
    show_preview_warning=False,
    program_name="sssekai",
    tabbed_groups=True,
    advanced=True,
    monospace_display=True,
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
    parser = create_parser(GooeyParser)
    args = parser.parse_args()
    basicConfig(
        level="DEBUG",
        format="%(asctime)s | %(levelname).1s | %(name)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    # override unity version
    sssekai_set_unity_version(args.unity_version)
    if "func" in args:
        args.func(args)
    pass


if __name__ in {"__main__", "__gui__"}:
    __main__()
