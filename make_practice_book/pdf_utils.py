from typing import Optional
import os

import fitz  # PyMuPDF
from rich.console import Console

from .utils import ensure_parent_dir

console = Console()


def preview_widths_cm(pdf_path: str, pages: int = 5) -> list[float]:
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(pdf_path)
    with fitz.open(pdf_path) as doc:
        out: list[float] = []
        for i in range(min(pages, doc.page_count)):
            page = doc[i]
            w_pt = page.rect.width
            out.append(round(w_pt / 28.35, 2))
        return out


def rescale_pdf_width_cm(input_pdf: str, new_width_cm: float, output_pdf: Optional[str] = None) -> str:
    if not os.path.isfile(input_pdf):
        raise FileNotFoundError(input_pdf)
    if output_pdf is None:
        root, _ = os.path.splitext(input_pdf)
        output_pdf = f"{root}_{new_width_cm}cm.pdf"

    console.print(f"Rescaling PDF width to {new_width_cm} cm -> {output_pdf}")
    ensure_parent_dir(output_pdf)

    src = fitz.open(input_pdf)
    dst = fitz.open()

    for page in src:
        old_w, old_h = page.rect.width, page.rect.height
        new_h = old_h * new_width_cm / old_w
        new_page = dst.new_page(width=new_width_cm * 28.35, height=new_h * 28.35)
        new_page.show_pdf_page(new_page.rect, src, page.number)

    dst.save(output_pdf)
    src.close()
    dst.close()
    return output_pdf
