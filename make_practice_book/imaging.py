import os
import shlex
from typing import Iterable, List, Optional

from rich.progress import Progress

from .utils import (
    console,
    cpu_count_default,
    ensure_parent_dir,
    get_magick_executable,
    iter_image_files,
    mm_to_px,
    run_cmd,
)


def generate_background(
    width_mm: float,
    height_mm: float,
    dpi: int,
    output: str = "background.png",
    color: str = "#FFFFFF",
) -> None:
    magick = get_magick_executable()
    wpx = mm_to_px(width_mm, dpi)
    hpx = mm_to_px(height_mm, dpi)
    ensure_parent_dir(output)
    args = [
        magick,
        "-size",
        f"{wpx}x{hpx}",
        f"xc:{color}",
        "-density",
        str(dpi),
        "-units",
        "PixelsPerInch",
        output,
    ]
    rc = run_cmd(args)
    if rc != 0:
        raise SystemExit(rc)


def add_background(
    input_path: str,
    background: str,
    offset_x: int = 0,
    offset_y: int = 100,
    gravity: str = "north",
    in_place: bool = True,
    output_dir: Optional[str] = None,
) -> None:
    magick = get_magick_executable()
    files = list(iter_image_files(input_path))
    if not files:
        console.print("[yellow]No images found.[/yellow]")
        return

    if not in_place:
        assert output_dir, "output_dir is required when in_place is False"
        os.makedirs(output_dir, exist_ok=True)

    composite_opts = ["-geometry", f"+{offset_x}+{offset_y}", "-gravity", gravity]

    with Progress() as progress:
        task = progress.add_task("Adding background", total=len(files))
        for src in files:
            dst = src if in_place else os.path.join(output_dir, os.path.basename(src))
            if not in_place and os.path.abspath(dst) != os.path.abspath(src):
                # copy src to dst as base, then composite in place
                args_copy = [magick, src, dst]
                rc_copy = run_cmd(args_copy)
                if rc_copy != 0:
                    raise SystemExit(rc_copy)
            args = [
                magick,
                "composite",
                *composite_opts,
                src if in_place else dst,
                background,
                "-colorspace",
                "RGB",
                dst,
            ]
            rc = run_cmd(args)
            if rc != 0:
                raise SystemExit(rc)
            progress.update(task, advance=1)


def pairwise_concat(
    input_path: str,
    extend_last: bool = True,
) -> None:
    magick = get_magick_executable()
    files = list(iter_image_files(input_path))
    if not files:
        console.print("[yellow]No images found.[/yellow]")
        return

    with Progress() as progress:
        task = progress.add_task("Pairwise concat", total=len(files) // 2)
        idx = 0
        while idx + 1 < len(files):
            img1 = files[idx]
            img2 = files[idx + 1]
            console.print(f"[cyan]Appending[/cyan]\n  {img1}\n  {img2}")
            args = [magick, "convert", img1, img2, "-append", img1]
            rc = run_cmd(args)
            if rc != 0:
                raise SystemExit(rc)
            try:
                os.remove(img2)
            except OSError:
                pass
            idx += 2
            progress.update(task, advance=1)

    if extend_last and idx < len(files):
        last = files[idx]
        console.print(f"[cyan]Extending bottom[/cyan]\n  {last}")
        args = [magick, last, "-gravity", "north", "-extent", "%wx%[fx:h*2]", last]
        rc = run_cmd(args)
        if rc != 0:
            raise SystemExit(rc)


def set_dpi(
    input_path: str,
    dpi: int = 300,
) -> None:
    magick = get_magick_executable()
    if os.path.isdir(input_path):
        # mogrify in place for performance
        pattern = os.path.join(os.path.abspath(input_path), "*.jpg")
        args = [magick, "mogrify", "-density", str(dpi), "-units", "PixelsPerInch", pattern]
        rc = run_cmd(args)
        if rc != 0:
            raise SystemExit(rc)
    else:
        # single file
        args = [magick, input_path, "-density", str(dpi), "-units", "PixelsPerInch", input_path]
        rc = run_cmd(args)
        if rc != 0:
            raise SystemExit(rc)


def jpgs_to_pdf(
    input_dir: str,
    output_pdf: str,
    quality: int = 80,
) -> None:
    magick = get_magick_executable()
    ensure_parent_dir(output_pdf)
    pattern = os.path.join(os.path.abspath(input_dir), "*.jpg")
    args = [magick, "convert", pattern, "-compress", "jpeg", "-quality", str(quality), output_pdf]
    rc = run_cmd(args)
    if rc != 0:
        raise SystemExit(rc)
