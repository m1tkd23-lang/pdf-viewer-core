# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

# PyInstaller が spec を exec() で評価する際、環境によって __file__ が定義されないことがある。
# そのため、実行時カレントディレクトリをリポジトリルートとして扱う。
ROOT = Path(os.getcwd()).resolve()
SRC = ROOT / "src"

block_cipher = None

a = Analysis(
    ["apps/main.py"],
    pathex=[str(ROOT), str(SRC)],
    binaries=[],
    datas=[
        # 必要になったら同梱する
        # (str(ROOT / "README.md"), "."),
    ],
    hiddenimports=[],
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

# ---- onefile ----
# COLLECT を使わず EXE だけで完結させる（dist に pdf-viewer-core.exe が出る）
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="pdf-viewer-core",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # rev1.0 GUI配布（デバッグしたい場合は True）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
