# -*- mode: python ; coding: utf-8 -*-

# https://github.com/K0lb3/UnityPy/issues/184
import UnityPy,archspec,GooeyEx, os

module_path_func = lambda module: lambda path: os.path.join(
    os.path.dirname(module.__file__), path
)

unitypy_path = module_path_func(UnityPy)
archspec_path = module_path_func(archspec)
gooeyex_path = module_path_func(GooeyEx)
block_cipher = None

a = Analysis(
    ["sssekai\\__gui__.py"],
    pathex=[],
    binaries=[],
    datas=[
        (unitypy_path("resources/*"), "UnityPy/resources"),        
        (archspec_path('json'), 'archspec/json'),
        (gooeyex_path('images'), 'GooeyEx/images'),
        (gooeyex_path('languages'), 'GooeyEx/languages'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="sssekai-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
