# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

import imageio_ffmpeg
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


project_root = Path(SPECPATH)
assets_dir = project_root / "assets"
build_assets_dir = project_root / ".build_assets"

datas = [
    (str(project_root / "README.md"), "."),
    (str(project_root / "ui.css"), "."),
    (str(project_root / "ui.js"), "."),
]

for relative_path in ("vendor", "assets"):
    source = project_root / relative_path
    if source.exists():
        datas.append((str(source), relative_path))

bundled_model = build_assets_dir / "models" / "small"
if bundled_model.exists():
    datas.append((str(bundled_model), "models/small"))

for package_name in (
    "gradio",
    "gradio_client",
    "groovy",
    "transformers",
    "huggingface_hub",
    "imageio_ffmpeg",
    "safehttpx",
    "webview",
):
    datas += collect_data_files(package_name, include_py_files=package_name == "gradio")

for distribution_name in (
    "gradio",
    "gradio_client",
    "groovy",
    "transformers",
    "huggingface-hub",
    "imageio-ffmpeg",
    "pywebview",
    "safehttpx",
):
    try:
        datas += copy_metadata(distribution_name)
    except Exception:
        pass

binaries = [
    (imageio_ffmpeg.get_ffmpeg_exe(), "imageio_ffmpeg/binaries"),
]

hiddenimports = []
hiddenimports += collect_submodules("transformers.models.depth_anything_v2")
if sys.platform == "win32":
    hiddenimports += [
        "webview.platforms.edgechromium",
        "webview.platforms.mshtml",
        "webview.platforms.win32",
        "webview.platforms.winforms",
    ]
elif sys.platform == "darwin":
    hiddenimports += ["webview.platforms.cocoa"]
else:
    hiddenimports += ["webview.platforms.gtk", "webview.platforms.qt"]
hiddenimports += [
    "PIL._tkinter_finder",
    "gradio.routes",
    "gradio_client.utils",
    "transformers.models.auto.image_processing_auto",
]

excludes = [
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
    "cefpython3",
    "gi",
    "gtk",
    "matplotlib",
    "notebook",
    "scipy",
    "tensorflow",
    "tkinter",
]

icon_path = assets_dir / ("icon.icns" if sys.platform == "darwin" else "icon.ico")

a = Analysis(
    [str(project_root / "desktop.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DepthVideo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DepthVideo",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Depth Video.app",
        icon=str(icon_path) if icon_path.exists() else None,
        bundle_identifier="com.longway.depthvideo",
        info_plist={
            "CFBundleDisplayName": "Depth Video",
            "CFBundleName": "Depth Video",
            "NSHighResolutionCapable": True,
        },
    )
