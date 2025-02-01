from sssekai.unity.AssetBundle import load_assetbundle
from sssekai.unity.AnimationClip import read_animation, vec3_quat_as_floats
from UnityPy.enums import ClassIDType
import UnityPy
from matplotlib import pyplot as plt
from numpy import arange

# Not going in the auto tests yet
UnityPy.config.FALLBACK_VERSION_WARNED = True
UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.21f1"
env = UnityPy.load(
    r"/Volumes/mos9527弄丢的盘/Reverse/unity_ik/HumanoidIK/Build.app/Contents/Resources"
)
for anim in filter(lambda obj: obj.type == ClassIDType.AnimationClip, env.objects):
    anim = anim.read()
    anim = read_animation(anim)
    # print("Time", "Value", "InSlope", "OutSlope", "Interpolation", sep="\t")
    t = arange(0, anim.Duration, 0.001)
    for curve in anim.RawCurves.values():
        # for key in curve.Data:
        #     print(
        #         key.time,
        #         key.value,
        #         key.inSlope,
        #         key.outSlope,
        #         key.interpolation_segment(key, key.next),
        #         sep="\t",
        #     )
        c = [vec3_quat_as_floats(curve.evaluate(x)) for x in t]
        plt.plot(t, c, label=curve.Path)
plt.show()
