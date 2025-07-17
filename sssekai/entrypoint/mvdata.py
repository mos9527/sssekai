from sssekai.unity.AssetBundle import load_assetbundle
import os, json


def main_mvdata(args):
    from UnityPy.enums import ClassIDType

    source = args.indir
    source = os.path.expanduser(source)
    source = os.path.abspath(source)
    outfile = os.path.abspath(args.outfile)
    os.chdir(source)
    mvdata_keys = sorted(os.listdir(source))
    mvdata_items = list()
    for key in mvdata_keys:
        try:
            with open(key, "rb") as f:
                env = load_assetbundle(f)
                for obj in env.objects:
                    if obj.type == ClassIDType.MonoBehaviour:
                        data = obj.read()
                        if data.m_Name == "data":
                            typetree = obj.read_typetree()
                            typetree = {
                                k: v
                                for k, v in typetree.items()
                                if not k.startswith("m_")
                            }
                            mvdata_items.append(typetree)
                            break
        except Exception as e:
            print(f"skipping {key}: {e}")
    outdir = os.path.dirname(outfile)
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(mvdata_items, f, indent=4, ensure_ascii=False)
