"""
Compile ExBook LaTeX into PDF.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def compile_latex(tex_path: Path, engine: str = "auto") -> Path:
    if not tex_path.exists():
        raise FileNotFoundError(f"TeX file not found: {tex_path}")

    selected_engine = _resolve_engine(engine)
    workdir = tex_path.parent
    tex_name = tex_path.name

    if os.path.basename(selected_engine).lower().startswith("latexmk"):
        proc = subprocess.run(
            [selected_engine, "-xelatex", "-pdf", tex_name],
            cwd=str(workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stdout)
    else:
        for _ in range(2):
            proc = subprocess.run(
                [selected_engine, "-interaction=nonstopmode", "-halt-on-error", tex_name],
                cwd=str(workdir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
            )
            if proc.returncode != 0:
                raise RuntimeError(proc.stdout)

    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.exists():
        raise RuntimeError(f"Compilation finished but PDF was not produced: {pdf_path}")
    return pdf_path


def _resolve_engine(engine: str) -> str:
    requested = (engine or "auto").strip().lower()
    if requested == "auto":
        for candidate in ("xelatex", "latexmk", "pdflatex"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        raise RuntimeError("latexmk/xelatex/pdflatex not found in PATH")

    resolved = shutil.which(requested)
    if not resolved:
        raise RuntimeError(f"{requested} not found in PATH")
    return resolved
