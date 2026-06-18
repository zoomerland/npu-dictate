# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata


project_root = Path(SPECPATH).parent

block_cipher = None


def metadata_for(packages):
    result = []
    for package in packages:
        try:
            result += copy_metadata(package)
        except Exception:
            pass
    return result


metadata_datas = metadata_for(
    [
        "onnx-asr",
        "onnxruntime",
        "openvino",
        "torch",
        "transformers",
        "numpy",
        "scipy",
        "sounddevice",
        "soundfile",
        "huggingface-hub",
        "tokenizers",
        "safetensors",
        "regex",
        "tqdm",
    ]
)

openvino_binaries = collect_dynamic_libs("openvino")
onnx_asr_datas = collect_data_files("onnx_asr")
openvino_datas = [
    (
        str(project_root / ".venv" / "Lib" / "site-packages" / "openvino" / "libs" / "cache.json"),
        "openvino/libs",
    )
]

a = Analysis(
    [str(project_root / "tools" / "voice_dictation_app.py")],
    pathex=[str(project_root / "tools"), str(project_root)],
    binaries=openvino_binaries,
    datas=[
        (str(project_root / "LICENSE"), "."),
        (str(project_root / "README.md"), "."),
        (str(project_root / "voice_dictation_config.example.json"), "."),
        (str(project_root / "docs" / "model-sources-and-licenses.md"), "docs"),
    ]
    + metadata_datas
    + onnx_asr_datas
    + openvino_datas,
    hiddenimports=[
        "app_paths",
        "comtypes.client",
        "gigaam_openvino_asr",
        "model_setup",
        "openvino",
        "onnx_asr",
        "pystray",
        "sounddevice",
        "soundfile",
        "uiautomation",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "notebook",
        "pytest",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LocalVoiceDictation",
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
    name="LocalVoiceDictation",
)
