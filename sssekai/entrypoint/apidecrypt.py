import os
def main_apidecrypt(args):
    from sssekai.crypto.APIManager import decrypt
    import json, msgpack
    data = open(args.infile,'rb').read()
    with open(args.outfile,'w',encoding='utf-8') as fout:
        plain = decrypt(data)
        msg = msgpack.unpackb(plain)
        json.dump(msg, fout, indent=4, ensure_ascii=False)