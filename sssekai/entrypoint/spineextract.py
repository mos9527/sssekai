import os
from sssekai.unity.AssetBundle import load_assetbundle
from logging import getLogger
logger = getLogger(__name__)

def main_spineextract(args):
    outdir = args.outdir
    with open(args.infile, "rb") as f:
        env = load_assetbundle(f)
        objects = [pobj.read() for pobj in env.objects]
        objects = {obj.name: obj for obj in objects if hasattr(obj,'name')}
        spines = set()
        for name in objects:
            if name.endswith(".atlas") or name.endswith(".skel"):
                spines.add(".".join(name.split(".")[:-1]))
        for spine in spines:
            logger.info('Extracting %s' % spine)
            atlas = objects.get(spine + ".atlas", None)
            skel = objects.get(spine + ".skel", None)
            texture = objects.get(spine, None)
            os.makedirs(os.path.join(outdir, spine), exist_ok=True)
            if atlas:
                with open(os.path.join(outdir, spine, spine + ".atlas.txt"), "wb") as f:
                    f.write(atlas.script)
            else:
                logger.warning("No atlas found for %s" % spine)

            if skel:
                with open(os.path.join(outdir, spine, spine + ".skel.bytes"), "wb") as f:
                    f.write(skel.script)
            else:
                logger.warning("No skel found for %s" % spine)

            if texture:            
                with open(os.path.join(outdir, spine, spine + ".png"), "wb") as f:
                    texture.image.save(f)
            else:
                logger.warning("No texture found for %s" % spine)
