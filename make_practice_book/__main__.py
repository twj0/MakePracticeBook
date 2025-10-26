import os
import sys
from rich.console import Console

from . import imaging

console = Console()


def _auto_process(path: str) -> int:
    # Default parameters for Phase 1
    size = "A4"
    dpi = 300
    output_pdf = "做题本.pdf"
    bg_file = "background.png"
    offset_y = 100

    # Ensure background
    if not os.path.isfile(bg_file):
        console.print(f"[yellow]{bg_file} not found. Generating...[/yellow]")
        if size.upper() == "A4":
            w_mm, h_mm = 210, 297
        else:
            w_mm, h_mm = 148, 210
        imaging.generate_background(w_mm, h_mm, dpi, output=bg_file)

    # Set DPI, composite, export PDF
    imaging.set_dpi(input_path=path, dpi=dpi)
    imaging.add_background(
        input_path=path,
        background=bg_file,
        offset_x=0,
        offset_y=offset_y,
        gravity="north",
        in_place=True,
        output_dir=None,
    )
    imaging.jpgs_to_pdf(input_dir=path, output_pdf=output_pdf, quality=80)
    console.print(f"[green]Done -> {output_pdf}[/green]")
    return 0


def main() -> int:
    # Drag-and-drop support: if single existing path passed, run auto pipeline
    argv = sys.argv[1:]
    if len(argv) == 1 and os.path.exists(argv[0]):
        return _auto_process(argv[0])

    # Otherwise, show CLI help via `mpb` entry point
    from .cli import app
    app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
