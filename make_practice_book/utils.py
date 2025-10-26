import os
import shutil
import sys
import subprocess
from typing import Iterable, List

from rich.console import Console

console = Console()

SUPPORTED_IMG_EXTS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}


def is_windows() -> bool:
    return os.name == "nt"


def cpu_count_default() -> int:
    try:
        return max(1, os.cpu_count() or 1)
    except Exception:
        return 1


def get_magick_executable() -> str:
    """Return path to magick executable. Prefer bundled copy in the app dir if present.
    Fallback to system 'magick' on PATH.
    """
    # If running from PyInstaller one-folder, the executable dir contains bundled files
    base_dirs: List[str] = []
    if getattr(sys, "frozen", False):
        base_dirs.append(os.path.dirname(sys.executable))
    # Development: repository root
    base_dirs.append(os.getcwd())

    env_path = os.environ.get("MAGICK_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    for d in base_dirs:
        candidate = os.path.join(d, "magick.exe") if is_windows() else os.path.join(d, "magick")
        if os.path.isfile(candidate):
            return candidate

    # Fallback to PATH
    exe = "magick.exe" if is_windows() else "magick"
    return exe if shutil.which(exe) else exe


def run_cmd(args: List[str]) -> int:
    """Run a command and stream output. Return process returncode."""
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert proc.stdout is not None
        for line in proc.stdout:
            console.print(line.rstrip())
        return proc.wait()
    except FileNotFoundError:
        console.print("[red]Executable not found:[/red] " + (args[0] if args else "<unknown>"))
        return 127


def iter_image_files(path: str) -> Iterable[str]:
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in sorted(files, key=lambda s: s.lower()):
                _, ext = os.path.splitext(f)
                if ext in SUPPORTED_IMG_EXTS:
                    yield os.path.join(root, f)
    elif os.path.isfile(path):
        _, ext = os.path.splitext(path)
        if ext in SUPPORTED_IMG_EXTS:
            yield path


def mm_to_px(value_mm: float, dpi: int) -> int:
    return int(round(value_mm * dpi / 25.4))


def ensure_parent_dir(p: str) -> None:
    d = os.path.dirname(os.path.abspath(p))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
