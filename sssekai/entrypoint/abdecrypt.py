import os
def main_abdecrypt(args):
    from sssekai.crypto.AssetBundle import decrypt
    for root, dirs, files in os.walk(args.indir):
        for fname in files:
            file = os.path.join(root,fname)
            if (os.path.isfile(file)):
                decrypt(open(file,'rb'), open(os.path.join(args.outdir, fname),'wb'))
