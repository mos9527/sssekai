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
    import sys

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
    from gooey.gui.containers.application import ConfigPage
    from gooey.gui.lang.i18n import _

    __original = ConfigPage.layoutComponent

    def __patch(self):
        self.rawWidgets["contents"][0]["description"] = self.rawWidgets["help"]
        __original(self)

    ConfigPage.layoutComponent = __patch


from sssekai.unity import sssekai_set_unity_version


class GooeyParser(GooeyParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # It's guaranteed that with file input/outputs
    # that we have
    # infile, outfile, indir, outdir as names
    # Map them to File Widgets
    def add_argument(self, name, *args, **kwargs):
        WIDGET_MAP = {
            "infile": "FileChooser",
            "outfile": "FileSaver",
            "indir": "DirChooser",
            "outdir": "DirChooser",
            # Special cases
            # AppHash
            "--apk_src": "FileChooser",
            "--ab_src": "FileChooser",
            # AbCache
            "--db": "FileChooser",
            "--download_dir": "DirChooser",
            "--dump_master_data": "DirChooser",
            "--dump_user_data": "DirChooser",
        }
        kwargs |= {"widget": WIDGET_MAP.get(name, None)}
        return super().add_argument(name, *args, **kwargs)


@Gooey(
    show_preview_warning=False,
    program_name="sssekai",
    tabbed_groups=False,
    advanced=True,
)
def __main__():
    __Gooey_120_patch_TaskBar()
    __Gooey_120_patch_wxTimer()
    __Gooey_120_patch_tqdm()
    __Gooey_120_patch_Applications()
    # ooh ooh aah aah monkey patching
    parser = create_parser(GooeyParser)
    args = parser.parse_args()
    basicConfig(
        level="DEBUG",
        format="[%(levelname).4s] %(name)s %(message)s",
    )
    getLogger("pyaxmlparser.axmlprinter").setLevel("ERROR")
    # override unity version
    sssekai_set_unity_version(args.unity_version)
    if "func" in args:
        args.func(args)
    pass


if __name__ in {"__main__", "__gui__"}:
    __main__()
