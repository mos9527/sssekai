import os


def main_abdecrypt(args):
    from sssekai.crypto.AssetBundle import decrypt_iter

    tree = os.walk(args.indir)
    for root, dirs, files in tree:
        for fname in files:
            file = os.path.join(root, fname)
            if os.path.isfile(file):
                with open(file, "rb") as src:
                    next_bytes = lambda nbytes: src.read(nbytes)
                    with open(os.path.join(args.outdir, fname), "wb") as dest:
                        for block in decrypt_iter(next_bytes):
                            dest.write(block)
