# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(".").resolve()


a = Analysis(
    ["make_practice_book/__main__.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "ExBook"), "ExBook"),
        (str(project_root / "models.yaml"), "."),
        (str(project_root / ".env.example"), "."),
    ],
    hiddenimports=[
        "make_practice_book",
        "make_practice_book.cli",
        "make_practice_book.ai_processor",
        "make_practice_book.doc_converter",
        "make_practice_book.exbook_writer",
        "make_practice_book.file_converter",
        "make_practice_book.latex_compiler",
        "fitz",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mpb",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="mpb",
)
