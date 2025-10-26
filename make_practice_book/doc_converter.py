import os
import shutil
import subprocess
import tempfile
from typing import Optional

from rich.console import Console

console = Console()


SUPPORTED_DOC_EXTS = {".doc", ".docx"}
SUPPORTED_PDF_EXTS = {".pdf"}


def _is_soffice_available() -> bool:
    return shutil.which("soffice") is not None


def _convert_with_docx2pdf(input_path: str, output_pdf: str) -> bool:
    try:
        from docx2pdf import convert  # type: ignore
    except Exception as e:
        console.print(f"[yellow]docx2pdf not available: {e}[/yellow]")
        return False
    try:
        # docx2pdf chooses MS Word on Windows, else uses LibreOffice
        convert(input_path, output_pdf)
        return os.path.isfile(output_pdf)
    except Exception as e:
        console.print(f"[yellow]docx2pdf failed: {e}[/yellow]")
        return False


def _convert_with_libreoffice(input_path: str, output_pdf: str) -> bool:
    if not _is_soffice_available():
        console.print("[yellow]LibreOffice (soffice) not found in PATH[/yellow]")
        return False
    outdir = os.path.dirname(os.path.abspath(output_pdf)) or os.getcwd()
    os.makedirs(outdir, exist_ok=True)
    try:
        cmd = [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            outdir,
            input_path,
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # LibreOffice outputs with same basename + .pdf in outdir
        produced = os.path.join(outdir, os.path.splitext(os.path.basename(input_path))[0] + ".pdf")
        if produced != output_pdf and os.path.isfile(produced):
            try:
                if os.path.isfile(output_pdf):
                    os.remove(output_pdf)
                os.replace(produced, output_pdf)
            except Exception:
                shutil.copy2(produced, output_pdf)
        return os.path.isfile(output_pdf)
    except Exception as e:
        console.print(f"[red]LibreOffice conversion failed:[/red] {e}")
        return False


def convert_to_pdf(input_path: str, output_pdf: Optional[str] = None) -> str:
    """Convert a DOC/DOCX/PDF to a normalized PDF path and return it.

    - DOC/DOCX: try docx2pdf (MS Word if available), fallback to LibreOffice headless.
    - PDF: passthrough.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(input_path)

    base, ext = os.path.splitext(input_path)
    ext = ext.lower()

    if ext in SUPPORTED_PDF_EXTS:
        return input_path

    if output_pdf is None:
        output_pdf = base + ".pdf"

    if ext in SUPPORTED_DOC_EXTS:
        # Try docx2pdf first
        if _convert_with_docx2pdf(input_path, output_pdf):
            return output_pdf
        # Fallback to LibreOffice
        if _convert_with_libreoffice(input_path, output_pdf):
            return output_pdf
        raise RuntimeError("Failed to convert document to PDF using both docx2pdf and LibreOffice")

    raise ValueError(f"Unsupported input format: {ext}")
