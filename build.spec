# -*- mode: python ; coding: utf-8 -*-
# PyInstaller打包配置

import os

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[
        ('src/native/fast_click.dll', 'native'),
    ] if os.path.exists('src/native/fast_click.dll') else [],
    datas=[
        ('assets', 'assets'),
    ],
    hiddenimports=[
        'uiautomation',
        'PyQt5.QtMultimedia',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='微信自动抢红包工具',
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
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
)
