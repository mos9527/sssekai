from sssekai.unity.AssetBundle import load_assetbundle
from sssekai.unity.AnimationClip import read_animation
from UnityPy.enums import ClassIDType
from matplotlib import pyplot as plt
from numpy import arange

fp = open(
    r"/Volumes/mos9527弄丢的盘/Reverse/unity_ik/HumanoidIK/Build.app/Contents/Resources/Data/sharedassets0.assets",
    "rb",
)
env = load_assetbundle(fp)

for anim in filter(lambda obj: obj.type == ClassIDType.AnimationClip, env.objects):
    anim = anim.read()
    if not anim.m_Name == "CameraCut":
        continue
    anim = read_animation(anim)
    fp.close()
    print("Time", "Value", "InSlope", "OutSlope", "Interpolation", sep="\t")
    t = arange(0, anim.Duration, 0.001)
    for curve in anim.TransformCurves:
        c = [curve.evaluate(t) for t in arange(0, anim.Duration, 0.001)]
        plt.plot(c)
        plt.show()
    pass
