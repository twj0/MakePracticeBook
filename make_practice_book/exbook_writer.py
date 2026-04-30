"""
Build full ExBook documents from AI-generated snippets.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def build_exbook_document(snippet: str) -> str:
    lines = [
        r"\newcommand{\EXBOOKDIR}{ExBook}",
        r"\IfFileExists{../ExBook/ExBook.cls}{\renewcommand{\EXBOOKDIR}{../ExBook}}{}",
        r"\IfFileExists{ExBook/ExBook.cls}{\renewcommand{\EXBOOKDIR}{ExBook}}{}",
        r"\documentclass[standard]{\EXBOOKDIR/ExBook}",
        r"\usepackage{graphicx}",
        r"\graphicspath{{\EXBOOKDIR/}{\EXBOOKDIR/img/}}",
        r"\begin{document}",
        r"\input{\EXBOOKDIR/config.tex}",
        r"\maketitle",
        r"\input{\EXBOOKDIR/contents/pre.tex}",
        r"\input{\EXBOOKDIR/contents/print.tex}",
        r"\setcounter{page}{1}",
        r"\tableofcontents",
        "",
        r"% AI generated content starts",
    ]
    if snippet and snippet.strip():
        lines.append(snippet.strip())
    else:
        lines.append(r"% (empty) no AI snippet inserted")
    lines += [
        "",
        r"% AI generated content ends",
        "",
        r"\end{document}",
    ]
    return "\n".join(lines)


def write_exbook_output(snippet: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_exbook_assets(output_path.parent)
    output_path.write_text(build_exbook_document(snippet), encoding="utf-8")
    return output_path


def ensure_exbook_assets(output_dir: Path) -> Path:
    source_dir = _find_exbook_source()
    target_dir = output_dir / "ExBook"
    shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
    return target_dir


def _find_exbook_source() -> Path:
    candidates = []

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "ExBook")
        candidates.append(Path(sys.executable).resolve().parent / "ExBook")

    module_root = Path(__file__).resolve().parent.parent
    candidates.append(module_root / "ExBook")
    candidates.append(Path.cwd() / "ExBook")

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError("ExBook assets not found")
