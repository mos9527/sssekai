from dataclasses import dataclass, field
from sssekai.__main__ import create_parser
from typing import Any, List
from argparse import ArgumentParser
from logging import basicConfig, getLogger

try:
    from gooey import Gooey, GooeyParser
except ImportError as e:
    print("Please install sssekai[gui] to use the GUI")
    raise e


# https://github.com/chriskiehl/Gooey/issues/826#issuecomment-1240180894
def __Gooey_120_patch_TaskBar():
    from rewx import widgets
    from rewx.widgets import set_basic_props, dirname
    from rewx.dispatch import update
    import wx

    @update.register(wx.Frame)
    def frame(element, instance: wx.Frame):
        props = element["props"]
        set_basic_props(instance, props)
        if "title" in props:
            instance.SetTitle(props["title"])
        if "show" in props:
            instance.Show(props["show"])
        if "icon_uri" in props:
            pass  # No icons for now
        if "on_close" in props:
            instance.Bind(wx.EVT_CLOSE, props["on_close"])

        return instance

    widgets.frame = frame


def __Gooey_120_patch_wxTimer():
    from gooey.gui.util.time import get_current_time, Timing

    def __patch(self: Timing):
        self.startTime = get_current_time()
        self.estimatedRemaining = None
        self.wxTimer.Start(milliseconds=1)

    Timing.start = __patch


def __Gooey_120_patch_tqdm():
    from subprocess import Popen
    from gooey.gui import events
    from gooey.gui.processor import ProcessController, pub

    def __patch(self, process: Popen):
        """
        Reads the stdout of `process` and forwards lines and progress
        to any interested subscribers
        """
        while True:
            line = []
            while ch := process.stdout.read(1):
                if ch in (b"\r", b"\n"):
                    break
                line.append(ch)
            if not ch:  # EOF
                break
            line = b"".join(line)
            line = line.decode(self.encoding)
            line = line.strip("\r\n")  # Windows CRLF
            if line:
                _progress = line.find("%")
                if _progress in range(0, 4):
                    _progress = int(line[:_progress].strip())
                else:
                    _progress = None
                pub.send_message(events.PROGRESS_UPDATE, progress=_progress)
                if _progress is None or self.hide_progress_msg is False:
                    pub.send_message(events.CONSOLE_UPDATE, msg=line + "\n")
        pub.send_message(events.EXECUTION_COMPLETE)

    ProcessController._forward_stdout = __patch
    pass


def __Gooey_120_patch_Applications():
    from gooey.gui.containers.application import TabbedConfigPage
    from gooey.gui.lang.i18n import _

    __original = TabbedConfigPage.layoutComponent

    def __patch(self):
        self.rawWidgets["contents"][0]["description"] = self.rawWidgets["help"]
        __original(self)

    TabbedConfigPage.layoutComponent = __patch


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
    from gooey.python_bindings.gooey_parser import (
        GooeyArgumentGroup,
        GooeyMutuallyExclusiveGroup,
    )

    for clazz in [GooeyArgumentGroup, GooeyMutuallyExclusiveGroup, GooeyParser]:
        __original = clazz.add_argument

        def __patch(self, name, *args, __original=__original, **kwargs):
            # XXX: Capturing the og function is necessary otherwise the reference would be updated
            kwargs |= {"widget": WIDGET_MAP.get(name, None)}
            kwargs["help"] = kwargs.get("help", "") % kwargs
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
    __Gooey_120_patch_TaskBar()
    __Gooey_120_patch_wxTimer()
    __Gooey_120_patch_tqdm()
    __Gooey_120_patch_Applications()
    __Gooey_120_patch_ArgumentGroup()
    # ooh ooh aah aah monkey patching
    parser = create_parser(GooeyParser)
    args = parser.parse_args()
    basicConfig(
        level="DEBUG",
        format="%(asctime)s | %(levelname).1s | %(name)s %(message)s",
        datefmt="%H:%M:%S",
    )
    getLogger("pyaxmlparser.axmlprinter").setLevel("ERROR")
    # override unity version
    sssekai_set_unity_version(args.unity_version)
    if "func" in args:
        args.func(args)
    pass


if __name__ in {"__main__", "__gui__"}:
    __main__()
