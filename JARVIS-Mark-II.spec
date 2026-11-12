# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Users/Naman Gaonkar/Desktop/AITD/Projects/VISION/config', 'config'), ('C:/Users/Naman Gaonkar/Desktop/AITD/Projects/VISION/core', 'core'), ('C:/Users/Naman Gaonkar/Desktop/AITD/Projects/VISION/gui', 'gui'), ('C:/Users/Naman Gaonkar/Desktop/AITD/Projects/VISION/actions', 'actions'), ('C:/Users/Naman Gaonkar/Desktop/AITD/Projects/VISION/providers', 'providers'), ('C:/Users/Naman Gaonkar/Desktop/AITD/Projects/VISION/plugins', 'plugins'), ('C:/Users/Naman Gaonkar/Desktop/AITD/Projects/VISION/memory', 'memory'), ('C:/Users/Naman Gaonkar/Desktop/AITD/Projects/VISION/dashboard', 'dashboard')],
    hiddenimports=['PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'psutil', 'PIL', 'winreg'],
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
    name='JARVIS-Mark-II',
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
    name='JARVIS-Mark-II',
)
