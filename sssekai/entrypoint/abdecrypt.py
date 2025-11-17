import os
from pathlib import Path
from logging import getLogger

logger = getLogger('abdecrypt')

def main_abdecrypt(args):
    from sssekai.crypto.AssetBundle import decrypt_iter

    args.outdir = Path(os.path.abspath(args.outdir))
    args.indir = Path(os.path.abspath(args.indir))
    args.outdir.mkdir(parents=True, exist_ok=True)
    tree = os.walk(args.indir)
    assert args.indir != args.outdir, "Input and output directories must be different"
    for root, dirs, files in tree:
        for fname in files:
            file = Path(root) / fname
            if file.is_file():                
                with open(file, "rb") as src:
                    next_bytes = lambda nbytes: src.read(nbytes)
                    out_path = args.outdir / file.relative_to(args.indir)
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    logger.info("Decrypting %s -> %s", file.as_posix(), out_path.as_posix())
                    with open(out_path, "wb") as dest:
                        for block in decrypt_iter(next_bytes):
                            dest.write(block)
