bl_info = {
    "name": "SSSekai Blender IO",
    "author": "SSSekai",
    "version": (0, 0, 1),
    "blender": (4, 0, 0),
    "location": "File > Import-Export",
    "description": "Import-Export SSSekai Assets",
    "warning": "",
    "wiki_url": "https://github.com/mos9527/sssekai",
    "tracker_url": "https://github.com/mos9527/sssekai",
    "category": "Import-Export",
}
try:
    import bpy
    from .blender.addon import register, unregister, SSSekaiBlenderImportPanel
    BLENDER = True
except:
    BLENDER = False

if BLENDER and __name__ == "__main__":
    register()
