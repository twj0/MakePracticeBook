from __future__ import annotations

import os
from typing import List, Tuple

import numpy as np
import cv2  # type: ignore
from PIL import Image
from rich.console import Console
from rich.progress import Progress

from .ocr_processor import OcrEngine, OcrBox, preprocess_for_layout, block_starts_with_number

console = Console()

# A segment is a vertical slice [y1, y2) across the full width
Segment = Tuple[int, int]


def detect_horizontal_cuts(bin_img: np.ndarray, min_gap_height: int = 30) -> List[int]:
    """Find horizontal cut lines in a binary inverted image (text=white, background=black).

    Returns Y positions including 0 and height as boundaries.
    """
    h, w = bin_img.shape[:2]
    proj = (bin_img > 0).sum(axis=1)  # number of white pixels per row

    cuts: List[int] = [0]
    in_gap = False
    gap_start = 0

    for y in range(h):
        if proj[y] == 0:
            if not in_gap:
                in_gap = True
                gap_start = y
        else:
            if in_gap:
                gap_h = y - gap_start
                if gap_h >= min_gap_height:
                    # Use center of the gap as cut line
                    cuts.append((gap_start + y) // 2)
                in_gap = False
    # Close trailing gap
    if in_gap and (h - gap_start) >= min_gap_height:
        cuts.append((gap_start + h) // 2)

    if cuts[-1] != h:
        cuts.append(h)

    # Deduplicate and ensure increasing order
    out = []
    last = -1
    for c in cuts:
        if c > last:
            out.append(c)
            last = c
    return out


def segments_from_cuts(cuts: List[int], min_height: int = 60) -> List[Segment]:
    segs: List[Segment] = []
    for i in range(len(cuts) - 1):
        y1, y2 = cuts[i], cuts[i + 1]
        if y2 - y1 >= min_height:
            segs.append((y1, y2))
    return segs


def refine_segments_with_ocr(img_bgr: np.ndarray, segs: List[Segment], engine: OcrEngine) -> List[Segment]:
    if not segs:
        return []
    # OCR once per segment, then merge segments that do not start with a numbering pattern
    refined: List[Segment] = []
    h, w = img_bgr.shape[:2]
    # Cache OCR boxes for entire page to speed up lookups
    boxes = engine.ocr_image(img_bgr)

    for seg in segs:
        if not refined:
            refined.append(seg)
            continue
        y1, y2 = seg
        block = (0, y1, w, y2 - y1)
        if block_starts_with_number(boxes, block):
            refined.append(seg)
        else:
            # Merge with previous segment
            py1, py2 = refined[-1]
            refined[-1] = (py1, y2)
    return refined


def save_segments(pil_page: Image.Image, segs: List[Segment], out_dir: str, page_num: int, prefix: str = "page") -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    w, h = pil_page.size
    paths: List[str] = []
    for idx, (y1, y2) in enumerate(segs, start=1):
        crop = pil_page.crop((0, y1, w, y2))
        out_name = f"{prefix}_{page_num:03d}_q_{idx:03d}.jpg"
        out_path = os.path.join(out_dir, out_name)
        crop.save(out_path, format="JPEG", quality=90)
        paths.append(out_path)
    return paths


def segment_pdf_to_questions(pdf_path: str, engine: OcrEngine, out_dir: str, dpi: int = 300, page_from: int | None = None, page_to: int | None = None) -> List[str]:
    from .ocr_processor import render_pdf_pages, pil_to_cv

    saved: List[str] = []
    pages = render_pdf_pages(pdf_path, dpi=dpi, page_from=page_from, page_to=page_to)
    with Progress() as progress:
        task = progress.add_task("Segmenting questions", total=len(pages))
        for page_num, pil_img in pages:
            cv_img = pil_to_cv(pil_img)
            bin_img = preprocess_for_layout(cv_img)
            cuts = detect_horizontal_cuts(bin_img)
            segs = segments_from_cuts(cuts)
            segs = refine_segments_with_ocr(cv_img, segs, engine)
            saved += save_segments(pil_img, segs, out_dir, page_num)
            progress.update(task, advance=1)
    return saved
