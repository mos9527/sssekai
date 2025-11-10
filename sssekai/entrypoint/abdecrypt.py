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
            file = os.path.join(root, fname)
            if os.path.isfile(file):
                logger.info("Decrypting %s", file)
                with open(file, "rb") as src:
                    next_bytes = lambda nbytes: src.read(nbytes)
                    with open(os.path.join(args.outdir, fname), "wb") as dest:
                        for block in decrypt_iter(next_bytes):
                            dest.write(block)
