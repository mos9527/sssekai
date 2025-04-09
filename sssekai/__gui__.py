from dataclasses import dataclass, field
from sssekai.__main__ import create_parser
from typing import Any, List
from argparse import ArgumentParser
from logging import basicConfig, getLogger

try:
    from GooeyEx import Gooey, GooeyParser
except ImportError as e:
    print("Please install sssekai[gui] to use the GUI")
    raise e


WIDGET_MAP = {
    "infile": "FileChooser",
    "outfile": "FileSaver",
    "indir": "DirChooser",
    "outdir": "DirChooser",
    # Special cases
    # AppHash
    "--apk-src": "FileChooser",
    "--ab-src": "FileChooser",
    # AbCache
    "--db": "FileChooser",
    "--download-dir": "DirChooser",
    "--dump-master-data": "DirChooser",
    "--dump-user-data": "DirChooser",
    "--download-filter-cache-diff": "FileChooser",
}


def __Gooey_120_patch_ArgumentGroup():
    from GooeyEx.python_bindings.gooey_parser import (
        GooeyArgumentGroup,
        GooeyMutuallyExclusiveGroup,
    )

    for clazz in [GooeyArgumentGroup, GooeyMutuallyExclusiveGroup, GooeyParser]:
        __original = clazz.add_argument

        def __patch(self, name, *args, __original=__original, **kwargs):
            # XXX: Capturing the og function is necessary otherwise the reference would be updated
            kwargs |= {"widget": WIDGET_MAP.get(name, None)}
            return __original(self, name, *args, **kwargs)

        clazz.add_argument = __patch


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
    __Gooey_120_patch_ArgumentGroup()
    # ooh ooh aah aah monkey patching
    parser = create_parser(GooeyParser)
    args = parser.parse_args()
    basicConfig(
        level="DEBUG",
        format="%(asctime)s | %(levelname).1s | %(name)s %(message)s",
        datefmt="%H:%M:%S",
    )
    # override unity version
    sssekai_set_unity_version(args.unity_version)
    if "func" in args:
        args.func(args)
    pass


if __name__ in {"__main__", "__gui__"}:
    __main__()
