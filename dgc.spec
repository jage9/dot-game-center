# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import copy_metadata, collect_all

_miniaudio_datas, _miniaudio_binaries, _miniaudio_hiddenimports = collect_all('miniaudio')

a = Analysis(
    ['src\\dgc\\__main__.py'],
    pathex=['src'],
    binaries=_miniaudio_binaries,
    datas=[('assets/sounds', 'assets/sounds')] + copy_metadata('dgc') + _miniaudio_datas,
    hiddenimports=_miniaudio_hiddenimports + ['miniaudio'],
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
    [],
    exclude_binaries=True,
    name='dgc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='dgc',
)
