from sssekai.unity.AnimationClip import read_animation
from sssekai.unity.AssetBundle import load_assetbundle
import sys
sys.path.insert(0,r'C:\Users\Huang')
from sssekai_blender_io.blender.asset import search_env_animations, search_env_meshes

with open(r"F:\Sekai\live_pv\timeline\0008\camera",'rb') as f:
    env = load_assetbundle(f)
    anims = search_env_animations(env)
    for anim in anims:
        if 'depth_' in anim.name:
            data = read_animation(anim)
            pass
        pass
pass