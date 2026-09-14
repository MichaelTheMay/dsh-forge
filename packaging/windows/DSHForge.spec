# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path


root = Path(SPECPATH).resolve().parents[1]
metadata = Path(os.environ["DSH_FORGE_BUILD_METADATA"]).resolve()
icon = Path(os.environ["DSH_FORGE_BUILD_ICON"]).resolve()

a = Analysis(
    [str(root / "scripts" / "serve.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "web" / "index.html"), "web"),
        (str(root / "web" / "launcher.js"), "web"),
        (str(root / "web" / "support.js"), "web"),
        (str(root / "web" / "vendor"), "web/vendor"),
        (str(root / "data"), "data"),
        (str(root / "dsh_forge" / "assistant_server.mjs"), "dsh_forge"),
        (str(metadata), "."),
    ],
    hiddenimports=["tkinter", "tkinter.filedialog"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["test", "tests"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DSH Forge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(icon),
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DSH Forge",
)
