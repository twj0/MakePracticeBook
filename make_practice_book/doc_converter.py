"""
Helpers for converting legacy .doc files into .docx.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


WORD_FORMAT_DOCX = 12


def convert_doc_to_docx(
    input_path: Path,
    output_dir: Path,
    strategy: str = "auto",
) -> Path:
    strategy_name = (strategy or "auto").strip().lower()
    if strategy_name not in {"auto", "office", "libreoffice"}:
        raise ValueError(f"Unsupported doc conversion strategy: {strategy_name}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{input_path.stem}.converted.docx"

    errors: list[str] = []

    if strategy_name in {"auto", "office"}:
        try:
            return _convert_with_word(input_path, output_path)
        except Exception as exc:
            errors.append(f"Office COM failed: {exc}")
            if strategy_name == "office":
                raise

    if strategy_name in {"auto", "libreoffice"}:
        try:
            return _convert_with_soffice(input_path, output_dir)
        except Exception as exc:
            errors.append(f"LibreOffice failed: {exc}")
            if strategy_name == "libreoffice":
                raise

    raise RuntimeError(
        "Unable to convert .doc to .docx. " + " | ".join(errors)
    )


def _convert_with_word(input_path: Path, output_path: Path) -> Path:
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe") or shutil.which("powershell")
    if not powershell:
        raise RuntimeError("PowerShell is not available")

    script = r"""
$src = $args[0]
$dst = $args[1]
$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($src, $false, $true)
    $doc.SaveAs([ref]$dst, [ref]12)
}
finally {
    if ($doc -ne $null) { $doc.Close() }
    if ($word -ne $null) { $word.Quit() }
}
"""

    proc = subprocess.run(
        [powershell, "-NoProfile", "-Command", script, str(input_path), str(output_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0 or not output_path.exists():
        raise RuntimeError((proc.stdout + "\n" + proc.stderr).strip())
    return output_path


def _convert_with_soffice(input_path: Path, output_dir: Path) -> Path:
    soffice = shutil.which("soffice.exe") or shutil.which("soffice")
    if not soffice:
        raise RuntimeError("LibreOffice soffice is not available")

    proc = subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to",
            "docx",
            "--outdir",
            str(output_dir),
            str(input_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    converted_path = output_dir / f"{input_path.stem}.docx"
    if proc.returncode != 0 or not converted_path.exists():
        raise RuntimeError((proc.stdout + "\n" + proc.stderr).strip())
    return converted_path
