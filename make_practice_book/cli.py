from typing import Optional
import os
import sys

import typer
from rich.console import Console

from .version import __version__
from . import imaging
from . import pdf_utils
from . import doc_converter
from . import ocr_processor
from . import question_splitter

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"make-practice-book {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(None, "--version", callback=version_callback, is_eager=True, help="Show version and exit"),
):
    """Make Practice Book CLI"""


@app.command()
def generate_background(
    size: str = typer.Option("A4", help="Paper size preset: A4 or A5"),
    dpi: int = typer.Option(300, help="Background DPI"),
    output: str = typer.Option("background.png", help="Output background file"),
    color: str = typer.Option("#FFFFFF", help="Background color"),
):
    """Generate a blank background image using ImageMagick."""
    size = size.upper()
    if size == "A4":
        w_mm, h_mm = 210, 297
    elif size == "A5":
        w_mm, h_mm = 148, 210
    else:
        raise typer.BadParameter("Unsupported size. Use A4 or A5.")
    imaging.generate_background(w_mm, h_mm, dpi, output=output, color=color)


@app.command()
def add_background(
    input_path: str = typer.Argument(..., help="File or directory of images"),
    background: str = typer.Option("background.png", help="Background image file"),
    offset_x: int = typer.Option(0, help="Horizontal offset in pixels"),
    offset_y: int = typer.Option(100, help="Vertical offset in pixels"),
    gravity: str = typer.Option("north", help="Composite gravity"),
    in_place: bool = typer.Option(True, help="Modify images in place"),
    output_dir: Optional[str] = typer.Option(None, help="Output directory when not in-place"),
):
    """Composite each input image onto a background image."""
    imaging.add_background(
        input_path=input_path,
        background=background,
        offset_x=offset_x,
        offset_y=offset_y,
        gravity=gravity,
        in_place=in_place,
        output_dir=output_dir,
    )


@app.command()
def pairwise_concat(
    input_path: str = typer.Argument(..., help="File or directory of images"),
    extend_last: bool = typer.Option(True, help="Extend bottom of last single image"),
):
    """Append images vertically in pairs, deleting the second of each pair."""
    imaging.pairwise_concat(input_path=input_path, extend_last=extend_last)


@app.command()
def set_dpi(
    input_path: str = typer.Argument(..., help="File or directory of JPG images"),
    dpi: int = typer.Option(300, help="Target DPI"),
):
    """Set image DPI using mogrify for directories."""
    imaging.set_dpi(input_path=input_path, dpi=dpi)


@app.command("jpgs-to-pdf")
def jpgs_to_pdf(
    input_dir: str = typer.Argument(..., help="Directory containing JPG images"),
    output_pdf: str = typer.Option("做题本.pdf", help="Output PDF file name"),
    quality: int = typer.Option(80, help="JPEG compression quality (0-100)"),
):
    """Convert JPG images to a single PDF."""
    imaging.jpgs_to_pdf(input_dir=input_dir, output_pdf=output_pdf, quality=quality)


@app.command("pdf-rescale")
def pdf_rescale(
    input_pdf: str = typer.Argument(..., help="Input PDF path"),
    width_cm: float = typer.Option(..., help="New PDF page width in cm"),
    output_pdf: Optional[str] = typer.Option(None, help="Output PDF path; default appends width suffix"),
):
    """Rescale PDF physical width to a given size in cm (keeps aspect)."""
    pdf_utils.rescale_pdf_width_cm(input_pdf=input_pdf, new_width_cm=width_cm, output_pdf=output_pdf)


@app.command()
def process(
    input_path: str = typer.Argument(".", help="Directory of prepared JPG slices"),
    size: str = typer.Option("A4", help="Background paper size preset: A4 or A5"),
    dpi: int = typer.Option(300, help="DPI for background and final PDF"),
    output_pdf: str = typer.Option("做题本.pdf", help="Output PDF file"),
    bg_file: str = typer.Option("background.png", help="Background file to use or create"),
    offset_y: int = typer.Option(100, help="Vertical offset for pasted images"),
    set_dpi_first: bool = typer.Option(True, help="Set JPG DPI before composing"),
):
    """One-stop pipeline: ensure background, optionally set DPI, composite, then export PDF.

    Note: This Phase 1 pipeline expects already-sliced images. OCR-based auto-splitting arrives in Phase 2.
    """
    # Ensure background exists
    if not os.path.isfile(bg_file):
        console.print(f"[yellow]{bg_file} not found. Generating...[/yellow]")
        size_up = size.upper()
        if size_up == "A4":
            w_mm, h_mm = 210, 297
        elif size_up == "A5":
            w_mm, h_mm = 148, 210
        else:
            raise typer.BadParameter("Unsupported size. Use A4 or A5.")
        imaging.generate_background(w_mm, h_mm, dpi, output=bg_file)

    # Optionally set DPI for JPGs
    if set_dpi_first:
        imaging.set_dpi(input_path=input_path, dpi=dpi)

    # Composite onto background
    imaging.add_background(
        input_path=input_path,
        background=bg_file,
        offset_x=0,
        offset_y=offset_y,
        gravity="north",
        in_place=True,
        output_dir=None,
    )

    # Export to PDF
    imaging.jpgs_to_pdf(input_dir=input_path, output_pdf=output_pdf, quality=80)


@app.command("convert-document")
def convert_document(
    input_path: str = typer.Argument(..., help="Input DOC/DOCX/PDF path"),
    output_pdf: Optional[str] = typer.Option(None, help="Output PDF file path"),
):
    """Convert DOC/DOCX/PDF into a normalized PDF using Word/docx2pdf if available, else LibreOffice."""
    try:
        pdf_path = doc_converter.convert_to_pdf(input_path, output_pdf)
        console.print(f"[green]Converted:[/green] {pdf_path}")
    except Exception as e:
        console.print(f"[red]Conversion failed:[/red] {e}")
        raise typer.Exit(code=1)


@app.command("ocr-segment")
def ocr_segment(
    input_pdf: str = typer.Argument(..., help="Input PDF path"),
    out_dir: str = typer.Option("segments", help="Output directory for question images"),
    engine: str = typer.Option("tesseract", help="OCR engine: tesseract or paddle"),
    lang: str = typer.Option("chi_sim", help="OCR language (Tesseract)"),
    dpi: int = typer.Option(300, help="Rendering DPI"),
    page_from: Optional[int] = typer.Option(None, help="Start page (1-based)"),
    page_to: Optional[int] = typer.Option(None, help="End page (1-based, inclusive)"),
):
    """OCR a PDF and split into per-question images using whitespace and numbering heuristics."""
    try:
        eng = ocr_processor.OcrEngine(engine=engine, lang=lang)
        paths = question_splitter.segment_pdf_to_questions(
            pdf_path=input_pdf,
            engine=eng,
            out_dir=out_dir,
            dpi=dpi,
            page_from=page_from,
            page_to=page_to,
        )
        console.print(f"[green]Saved {len(paths)} segments -> {out_dir}[/green]")
    except Exception as e:
        console.print(f"[red]OCR segmentation failed:[/red] {e}")
        raise typer.Exit(code=1)


@app.command("auto-process")
def auto_process(
    input_path: str = typer.Argument(..., help="Input DOC/DOCX/PDF path"),
    size: str = typer.Option("A4", help="Background paper size preset: A4 or A5"),
    dpi: int = typer.Option(300, help="DPI for rendering and background"),
    engine: str = typer.Option("tesseract", help="OCR engine: tesseract or paddle"),
    lang: str = typer.Option("chi_sim", help="OCR language (Tesseract)"),
    offset_y: int = typer.Option(100, help="Vertical offset when compositing"),
    output_pdf: str = typer.Option("做题本.pdf", help="Final practice book PDF"),
    segments_dir: Optional[str] = typer.Option(None, help="Where to store per-question images (default alongside input)"),
    page_from: Optional[int] = typer.Option(None, help="Start page (1-based)"),
    page_to: Optional[int] = typer.Option(None, help="End page (1-based, inclusive)"),
):
    """End-to-end: convert document to PDF, OCR segment to question images, compose to practice book PDF."""
    try:
        # 1) Convert to PDF
        pdf_path = doc_converter.convert_to_pdf(input_path)

        # 2) Segment to question images
        base_dir = os.path.dirname(os.path.abspath(pdf_path))
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        out_dir = segments_dir or os.path.join(base_dir, base_name + "_segments")
        eng = ocr_processor.OcrEngine(engine=engine, lang=lang)
        _ = question_splitter.segment_pdf_to_questions(
            pdf_path=pdf_path,
            engine=eng,
            out_dir=out_dir,
            dpi=dpi,
            page_from=page_from,
            page_to=page_to,
        )

        # 3) Ensure background
        size_up = size.upper()
        if size_up == "A4":
            w_mm, h_mm = 210, 297
        elif size_up == "A5":
            w_mm, h_mm = 148, 210
        else:
            raise typer.BadParameter("Unsupported size. Use A4 or A5.")
        bg_file = os.path.join(base_dir, "background.png")
        if not os.path.isfile(bg_file):
            imaging.generate_background(w_mm, h_mm, dpi, output=bg_file)

        # 4) Set DPI, composite, and export
        imaging.set_dpi(input_path=out_dir, dpi=dpi)
        imaging.add_background(
            input_path=out_dir,
            background=bg_file,
            offset_x=0,
            offset_y=offset_y,
            gravity="north",
            in_place=True,
            output_dir=None,
        )
        final_pdf = os.path.join(base_dir, output_pdf)
        imaging.jpgs_to_pdf(input_dir=out_dir, output_pdf=final_pdf, quality=80)
        console.print(f"[green]Done -> {final_pdf}[/green]")
    except Exception as e:
        console.print(f"[red]Auto process failed:[/red] {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
