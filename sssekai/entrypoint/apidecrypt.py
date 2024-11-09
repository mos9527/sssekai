import os


def main_apidecrypt(args):
    from sssekai.crypto.APIManager import decrypt, SEKAI_APIMANAGER_KEYSETS
    import json, msgpack

    data = open(args.infile, "rb").read()
    with open(args.outfile, "w", encoding="utf-8") as fout:
        plain = decrypt(data, SEKAI_APIMANAGER_KEYSETS[args.region])
        try:
            msg = msgpack.unpackb(plain)
            json.dump(msg, fout, indent=4, ensure_ascii=False)
        except Exception:
            print("Malformed decrypted data")
            print(
                "Please consider switching to another region with `--region` flag (i.e. `--region en`)"
            )
