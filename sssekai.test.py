from sssekai.unity.AnimationClip import read_animation
from sssekai.unity.AssetBundle import load_assetbundle
import sys
sys.path.insert(0,r'C:\Users\Huang')
from sssekai_blender_io.blender.asset import search_env_animations, search_env_meshes
from sssekai_blender_io.blender import BonePhysicsType, BonePhysics, BoneAngularLimit, Bone
with open(r"F:\Sekai\live_pv\timeline\0002\stage",'rb') as f:
    env = load_assetbundle(f)
    anims = search_env_animations(env)
    CRC_DOF = 3138646591
    for anim in anims:
        data = read_animation(anim)
        pass
    pass
pass