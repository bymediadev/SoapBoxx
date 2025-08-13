# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['frontend\\main_window.py'],
    pathex=[],
    binaries=[],
    datas=[('backend', 'backend'), ('frontend', 'frontend')],
    hiddenimports=['backend', 'frontend', 'PyQt6', 'pyaudio', 'openai', 'whisper', 'gtts'],
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
    name='SoapBoxx',
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
