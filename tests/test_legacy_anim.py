from . import *


def test():
    import UnityPy
    from UnityPy.enums import ClassIDType
    from sssekai.unity.AnimationClip import AnimationHelper

    file = sample_file_path("animation", "legacy")
    env = UnityPy.load(file)
    anim = next(
        filter(lambda x: x.type == ClassIDType.AnimationClip, env.objects)
    ).read()
    helper = AnimationHelper.from_clip(anim)
    pass


if __name__ == "__main__":
    test()
