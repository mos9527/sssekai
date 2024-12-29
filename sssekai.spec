# -*- mode: python ; coding: utf-8 -*-

# https://github.com/K0lb3/UnityPy/issues/184
import UnityPy, pyaxmlparser, os
module_path_func = lambda module:lambda path:os.path.join(os.path.dirname(module.__file__), path)

unitypy_path = module_path_func(UnityPy)
pyaxmlparser_path = module_path_func(pyaxmlparser)

a = Analysis(
    ['sssekai\\__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        (unitypy_path('resources/*'), 'UnityPy/resources'),
        (pyaxmlparser_path('resources/*'), 'pyaxmlparser/resources'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='sssekai',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='NONE',
)
