# -*- mode: python ; coding: utf-8 -*-

import sys

from PyInstaller.utils.hooks import collect_submodules


hiddenimports = (
    collect_submodules("PySide6.QtPdf")
    + collect_submodules("PySide6.QtPdfWidgets")
    + collect_submodules("PySide6.QtSvg")
    + collect_submodules("PySide6.QtSvgWidgets")
    + collect_submodules("PySide6.QtMultimedia")
    + collect_submodules("PySide6.QtMultimediaWidgets")
)


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("assets", "assets")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ZJX LMS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/app_icon.ico" if sys.platform == "win32" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ZJX LMS",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="ZJX LMS.app",
        icon="build/app_icon.icns",
        bundle_identifier="com.zjx.lms",
    )
