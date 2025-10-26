from __future__ import annotations

import os
import io
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import cv2  # type: ignore
from PIL import Image
from rich.console import Console
from rich.progress import Progress

console = Console()


# ---------- OCR engine selection ----------

def is_tesseract_available() -> bool:
    try:
        import pytesseract  # noqa: F401
        from pytesseract import get_tesseract_version
        _ = get_tesseract_version()
        return True
    except Exception:
        return False


def is_paddle_available() -> bool:
    try:
        from paddleocr import PaddleOCR  # noqa: F401
        return True
    except Exception:
        return False


@dataclass
class OcrBox:
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    text: str
    conf: float


class OcrEngine:
    def __init__(self, engine: str = "tesseract", lang: str = "chi_sim") -> None:
        engine = engine.lower()
        self.engine = engine
        self.lang = lang
        self._paddle = None
        if engine == "paddle":
            if not is_paddle_available():
                raise RuntimeError("PaddleOCR not installed. Please install paddleocr to use this engine.")
            self._init_paddle()
        elif engine == "tesseract":
            if not is_tesseract_available():
                console.print("[yellow]Tesseract not detected. OCR will likely fail. Install Tesseract and ensure it is on PATH.[/yellow]")
        else:
            raise ValueError("engine must be 'tesseract' or 'paddle'")

    def _init_paddle(self) -> None:
        from paddleocr import PaddleOCR  # type: ignore
        # lang 'ch' covers Chinese; set use_angle_cls for better rotated text handling
        paddle_lang = "ch" if self.lang.startswith("chi") else "en"
        self._paddle = PaddleOCR(lang=paddle_lang, use_angle_cls=True, show_log=False)

    def ocr_image(self, img: np.ndarray) -> List[OcrBox]:
        if self.engine == "tesseract":
            return self._ocr_tesseract(img)
        else:
            return self._ocr_paddle(img)

    def _ocr_tesseract(self, img: np.ndarray) -> List[OcrBox]:
        import pytesseract
        # Convert to RGB PIL Image
        if len(img.shape) == 2:
            pil = Image.fromarray(img)
        else:
            pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        data = pytesseract.image_to_data(pil, lang=self.lang, output_type=pytesseract.Output.DICT)
        n = len(data.get("level", []))
        boxes: List[OcrBox] = []
        for i in range(n):
            text = (data["text"][i] or "").strip()
            if not text:
                continue
            conf_str = data.get("conf", ["0"]) [i]
            try:
                conf = float(conf_str)
            except Exception:
                conf = 0.0
            x, y, w, h = int(data["left"][i]), int(data["top"][i]), int(data["width"][i]), int(data["height"][i])
            boxes.append(OcrBox((x, y, w, h), text, conf))
        return boxes

    def _ocr_paddle(self, img: np.ndarray) -> List[OcrBox]:
        assert self._paddle is not None
        # Paddle expects RGB ndarray
        if len(img.shape) == 2:
            rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        else:
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        result = self._paddle.ocr(rgb, cls=True)
        boxes: List[OcrBox] = []
        for line in result:
            for (quad, (text, conf)) in line:
                xs = [int(pt[0]) for pt in quad]
                ys = [int(pt[1]) for pt in quad]
                x, y, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
                boxes.append(OcrBox((x, y, w, h), text.strip(), float(conf)))
        return boxes


# ---------- PDF rendering ----------

def render_pdf_pages(pdf_path: str, dpi: int = 300, page_from: Optional[int] = None, page_to: Optional[int] = None) -> List[Tuple[int, Image.Image]]:
    import fitz  # PyMuPDF
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(pdf_path)
    doc = fitz.open(pdf_path)
    pages: List[Tuple[int, Image.Image]] = []
    start = page_from or 1
    end = page_to or doc.page_count
    start = max(1, start)
    end = min(doc.page_count, end)
    scale = dpi / 72.0
    mat = fitz.Matrix(scale, scale)
    with Progress() as progress:
        task = progress.add_task("Rendering PDF", total=end - start + 1)
        for i in range(start - 1, end):
            page = doc[i]
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            pages.append((i + 1, img))
            progress.update(task, advance=1)
    doc.close()
    return pages


# ---------- Preprocessing & layout ----------

def preprocess_for_layout(img: np.ndarray) -> np.ndarray:
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    # Adaptive threshold for variable backgrounds
    bin_img = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 15)
    # Morph close to join text lines within a question block
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(bin_img, cv2.MORPH_CLOSE, kernel, iterations=1)
    return closed


def find_text_blocks(bin_img: np.ndarray, min_block_height: int = 40) -> List[Tuple[int, int, int, int]]:
    # Find contours; filter by size; return bounding rectangles sorted top-to-bottom
    contours, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects: List[Tuple[int, int, int, int]] = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if h >= min_block_height and w >= 40:
            rects.append((x, y, w, h))
    rects.sort(key=lambda r: r[1])
    return rects


# ---------- Numbering pattern detection ----------
QUESTION_HEAD_PATTERNS = [
    r"^\(?\d{1,3}\)?[\.、)]",   # 1.  1)  (1)  1、
    r"^[（(]\d+[）)]",           # (1) style
    r"^[一二三四五六七八九十百千]+[、.]",  # Chinese numerals like 一、
]
QUESTION_HEAD_REGEX = re.compile("|".join(QUESTION_HEAD_PATTERNS))


def block_starts_with_number(ocr_boxes: List[OcrBox], block: Tuple[int, int, int, int]) -> bool:
    x, y, w, h = block
    if not ocr_boxes:
        return False
    # Focus on top region of the block
    top_h = max(10, int(h * 0.25))
    roi_y2 = y + top_h
    texts: List[str] = []
    for box in ocr_boxes:
        bx, by, bw, bh = box.bbox
        if by >= y and by + bh <= roi_y2 and bx >= x and bx + bw <= x + w:
            if box.conf >= 40:  # basic confidence gate
                texts.append(box.text)
    head_line = " ".join(texts)[:50]
    return bool(QUESTION_HEAD_REGEX.search(head_line))


# ---------- Public API ----------

def pil_to_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def cv_to_pil(img: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
