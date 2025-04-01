from logging import getLogger
from sssekai.unity.AssetBundle import load_assetbundle
from UnityPy.enums import ClassIDType
from sssekai.fmt.rla import read_archive_rla_frames, read_rla_frames
import os, io, json, base64

logger = getLogger(__name__)


def main_rla2json(args):
    def __dump_from_frame_gen(frame_gen):
        outdir = args.outdir
        os.makedirs(outdir, exist_ok=True)
        ensure_dir = lambda x: (
            (
                os.makedirs(os.path.dirname(x), exist_ok=True)
                if os.path.dirname(x)
                else None
            )
            or x
        )
        for tick, frame in frame_gen:
            print("tick: %16s, type: %32s" % (tick, frame["type"]), end="\r")
            match frame["type"]:
                case "SoundData":
                    if frame["encoding"] == "hca":
                        with open(
                            ensure_dir(
                                os.path.join(outdir, "SoundData", str(tick) + ".hca"),
                            ),
                            "wb",
                        ) as f:
                            raw_data = frame["data"]
                            start = raw_data.find(b"\xff\xff")
                            f.write(raw_data[start:])
                    else:
                        raise ValueError("unsupported encoding: %s" % frame["encoding"])
                case _:
                    with open(
                        ensure_dir(
                            os.path.join(outdir, frame["type"], str(tick) + ".json")
                        ),
                        "w",
                        encoding="utf-8",
                    ) as f:
                        json.dump(frame, f, ensure_ascii=False, indent=4)

    if os.path.isfile(args.input):
        with open(args.input, "rb") as f:
            datas = dict()
            rla_env = load_assetbundle(f)
            for obj in rla_env.objects:
                if obj.type in {ClassIDType.TextAsset}:
                    data = obj.read()
                    datas[data.m_Name] = data.m_Script.encode(
                        "utf-8", "surrogateescape"
                    )
            header = datas.get("sekai.rlh", None)
            assert header, "RLH Header file not found!"
            version = tuple(map(int, header["version"].split(".")))
            logger.info("Version: %d.%d" % version)
            logger.info("Count: %d" % len(header["splitFileIds"]))
            splitSeconds = header["splitSeconds"]
            for sid in header["splitFileIds"]:
                sname = "sekai_%02d_%08d" % (splitSeconds, sid)
                script = datas[sname + ".rla"]
                frame_gen = read_archive_rla_frames(
                    io.BytesIO(script), version, args.strict
                )
                __dump_from_frame_gen(frame_gen)
    else:
        logger.info("Reading from directory")
        packet_gen = (
            (file, open(os.path.join(args.input, file), "rb").read())
            for file in os.listdir(args.input)
        )
        version = tuple(map(int, args.version.split(".")))
        frame_gen = read_rla_frames(packet_gen, version, args.strict)
        __dump_from_frame_gen(frame_gen)
