from sssekai.unity.AssetBundle import load_assetbundle
from sssekai.unity.AnimationClip import read_animation, vec3_quat_as_floats
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
    for curve in anim.RawCurves.values():
        for key in curve.Data:
            print(
                key.time,
                key.value,
                key.inSlope,
                key.outSlope,
                key.interpolation_segment(key, key.next),
                sep="\t",
            )
        c = [vec3_quat_as_floats(curve.evaluate(x)) for x in t]
        plt.plot(t, c, label=curve.Path)
    plt.show()
    pass
