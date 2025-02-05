# -*- mode: python ; coding: utf-8 -*-

# https://github.com/K0lb3/UnityPy/issues/184
import UnityPy, pyaxmlparser, gooey, os

module_path_func = lambda module: lambda path: os.path.join(
    os.path.dirname(module.__file__), path
)

unitypy_path = module_path_func(UnityPy)
pyaxmlparser_path = module_path_func(pyaxmlparser)
gooey_path = module_path_func(gooey)

block_cipher = None

a = Analysis(
    ["sssekai\\__gui__.py"],
    pathex=[],
    binaries=[],
    datas=[
        (unitypy_path("resources/*"), "UnityPy/resources"),
        (pyaxmlparser_path("resources/*"), "pyaxmlparser/resources"),
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
