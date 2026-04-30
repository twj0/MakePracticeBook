"""
将 doc/docx/pdf/md/txt 输入转换为做题本 PDF 的命令行工具。
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Optional

import typer
from dotenv import find_dotenv, load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .ai_processor import process_with_ai_exbook
from .chunking import SourceChunk, chunk_source_text, write_chunk_report
from .exbook_writer import write_exbook_output
from .file_converter import FileConverter
from .latex_compiler import compile_latex
from .version import __version__


load_dotenv(find_dotenv(), override=False)

APP_EPILOG = """
示例：
  mpb build examples\\中国科学技术大学.docx
  mpb build D:\\考研资料\\数学一真题.pdf --ocr-backend paddle
  mpb build 英语阅读笔记.md --output-stem 英语阅读做题本
  mpb extract examples\\中国科学技术大学.docx

贴心提示：
  1. 默认输出到你当前工作目录下的 out\\
  2. 默认沿用输入文件名；只有传 --output-stem 才会改名
  3. 扫描版 PDF 或照片转文档时，优先使用 --ocr-backend paddle
"""

BUILD_EPILOG = """
示例：
  mpb build 2024政治真题.docx
  mpb build D:\\考研\\数学一.pdf --ocr-backend paddle --provider openai
  mpb build 专业课整理.md --output-stem 专业课冲刺做题本
  mpb build 英语一阅读.txt --output-dir D:\\我的做题本

适合考研同学的常见场景：
  1. 真题文档转做题本：直接传 .docx/.pdf
  2. 扫描版试卷转做题本：加 --ocr-backend paddle
  3. 已整理好的 Markdown 笔记转做题本：直接传 .md
"""

EXTRACT_EPILOG = """
示例：
  mpb extract 2024数学一.pdf
  mpb extract 专业课真题.docx --output-file out\\专业课真题.source.md

适用场景：
  1. 先检查 OCR / 文本提取效果
  2. 先拿到 source.md，再决定是否继续生成做题本
"""

COMPILE_EPILOG = """
示例：
  mpb compile out\\中国科学技术大学.tex
  mpb compile out\\英语阅读做题本.tex --engine xelatex
"""

app = typer.Typer(
    name="mpb",
    help="把文档转换为 ExBook 做题本的命令行工具。",
    epilog=APP_EPILOG,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


def _default_output_dir() -> Path:
    return Path.cwd() / "out"


def _base_stem(input_file: Path, output_stem: Optional[str]) -> str:
    return output_stem.strip() if output_stem else input_file.stem


def _parse_api_keys(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(";") if item.strip()]


@app.command(epilog=BUILD_EPILOG)
def build(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        help="输入文件路径（支持 .doc/.docx/.pdf/.md/.txt）。",
    ),
    output_dir: Path = typer.Option(
        _default_output_dir(),
        "--output-dir",
        "-o",
        help="输出目录，默认是当前工作目录下的 out/。",
    ),
    output_stem: Optional[str] = typer.Option(
        None,
        "--output-stem",
        help="显式指定输出文件名主干；不指定时默认沿用输入文件名。",
    ),
    provider: str = typer.Option(
        "openai",
        "--provider",
        "-p",
        help="AI 提供方：openai、groq 或 zhipu。",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="单个 API Key，优先于环境变量。",
    ),
    api_keys: Optional[str] = typer.Option(
        None,
        "--api-keys",
        help="多个 API Key，使用分号分隔，主要用于轮换。",
    ),
    api_base: Optional[str] = typer.Option(
        None,
        "--api-base",
        help="覆盖 OpenAI 兼容接口的 API Base URL。",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="覆盖默认模型名。",
    ),
    use_segments: bool = typer.Option(
        False,
        "--use-segments",
        help="把较长文本再切成多个 AI 调用分段处理。",
    ),
    segment_size: int = typer.Option(
        2400,
        "--segment-size",
        help="启用 --use-segments 时，每个内部分段允许的最大字符数。",
    ),
    chunk_size: int = typer.Option(
        6000,
        "--chunk-size",
        help="送入 LLM 前，本地分块的最大字符数。",
    ),
    max_output_tokens: int = typer.Option(
        5000,
        "--max-output-tokens",
        help="每个分块向 AI 请求的最大输出 token 数。",
    ),
    min_coverage_ratio: float = typer.Option(
        0.6,
        "--min-coverage-ratio",
        help="当输出题目覆盖率低于该阈值时，自动缩小分块后重试。",
    ),
    max_chunk_recursion: int = typer.Option(
        2,
        "--max-chunk-recursion",
        help="低覆盖率分块自动细分重试的最大递归深度。",
    ),
    include_answers: bool = typer.Option(
        False,
        "--include-answers",
        help="当源文档同时包含试题和答案时，是否把答案部分也纳入处理。",
    ),
    compile_pdf_flag: bool = typer.Option(
        True,
        "--compile/--no-compile",
        help="是否把生成的 .tex 继续编译为 PDF。",
    ),
    engine: str = typer.Option(
        "auto",
        "--engine",
        help="LaTeX 引擎：auto、latexmk、xelatex、pdflatex。",
    ),
    ocr_backend: str = typer.Option(
        "paddle",
        "--ocr-backend",
        help="OCR 后端：paddle、tesseract、auto、none。",
    ),
    tesseract_cmd: Optional[str] = typer.Option(
        None,
        "--tesseract-cmd",
        help="使用 Tesseract OCR 时，指定其可执行文件路径。",
    ),
    doc_strategy: str = typer.Option(
        "auto",
        "--doc-strategy",
        help="旧版 .doc 转换策略：auto、office、libreoffice。",
    ),
):
    """
    把输入文件转换为 ExBook TeX，并可选继续编译为 PDF。
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = _base_stem(input_file, output_stem)
        source_md_path = output_dir / f"{stem}.source.md"
        chunks_json_path = output_dir / f"{stem}.chunks.json"
        tex_path = output_dir / f"{stem}.tex"

        console.print(
            Panel.fit(
                "\n".join(
                    [
                        f"[bold cyan]Input:[/bold cyan] {input_file}",
                        f"[bold cyan]Output dir:[/bold cyan] {output_dir}",
                        f"[bold cyan]Provider:[/bold cyan] {provider}",
                        f"[bold cyan]OCR:[/bold cyan] {ocr_backend}",
                    ]
                ),
                title="MakePracticeBook",
                border_style="cyan",
            )
        )

        converter = FileConverter(
            ocr_backend=ocr_backend,
            tesseract_cmd=tesseract_cmd,
            doc_strategy=doc_strategy,
        )
        markdown_content = converter.convert_to_markdown(str(input_file))
        markdown_content = FileConverter.clean_text(markdown_content)
        source_md_path.write_text(markdown_content, encoding="utf-8")
        console.print(f"[green]✓[/green] Source Markdown saved: {source_md_path}")
        _print_trace(converter.trace)

        report = chunk_source_text(
            markdown_content,
            max_chars=chunk_size,
            include_answers=include_answers,
        )
        write_chunk_report(report, chunks_json_path)
        console.print(f"[green]✓[/green] Chunk report saved: {chunks_json_path}")
        console.print(
            f"[cyan]Chunking:[/cyan] sections={report.section_count}, "
            f"chunks={report.chunk_count}, estimated_questions={report.estimated_questions}"
        )
        if not include_answers:
            console.print("[cyan]Filter:[/cyan] answer sections are excluded by default")

        snippets: list[str] = []
        for index, chunk in enumerate(report.chunks, start=1):
            console.print(
                f"[cyan]LLM chunk {index}/{report.chunk_count}[/cyan] "
                f"{chunk.chunk_id} year={chunk.year or '-'} chars={chunk.char_count} "
                f"q~={chunk.question_estimate}"
            )
            snippets.extend(
                _render_chunk_with_fallback(
                    chunk,
                    provider=provider,
                    api_key=api_key,
                    api_keys=_parse_api_keys(api_keys),
                    api_base=api_base,
                    model=model,
                    use_segments=use_segments,
                    segment_size=segment_size,
                    max_output_tokens=max_output_tokens,
                    min_coverage_ratio=min_coverage_ratio,
                    max_chunk_recursion=max_chunk_recursion,
                    base_chunk_size=chunk_size,
                )
            )

        latex_snippet = "\n\n".join(part for part in snippets if part)
        write_exbook_output(latex_snippet, tex_path)
        console.print(f"[green]✓[/green] ExBook TeX saved: {tex_path}")
        _print_coverage_stats(report.estimated_questions, tex_path)

        if compile_pdf_flag:
            pdf_path = compile_latex(tex_path, engine=engine)
            console.print(f"[green]✓[/green] PDF generated: {pdf_path}")
    except Exception as exc:
        console.print(f"[red]✗ Build failed:[/red] {exc}")
        raise typer.Exit(1)


@app.command(epilog=EXTRACT_EPILOG)
def extract(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        help="输入文件路径（支持 .doc/.docx/.pdf/.md/.txt）。",
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output-file",
        "-o",
        help="提取后的 Markdown 风格文本保存位置。",
    ),
    ocr_backend: str = typer.Option(
        "paddle",
        "--ocr-backend",
        help="OCR 后端：paddle、tesseract、auto、none。",
    ),
    tesseract_cmd: Optional[str] = typer.Option(
        None,
        "--tesseract-cmd",
        help="使用 Tesseract OCR 时，指定其可执行文件路径。",
    ),
    doc_strategy: str = typer.Option(
        "auto",
        "--doc-strategy",
        help="旧版 .doc 转换策略：auto、office、libreoffice。",
    ),
):
    """
    只提取并输出规范化文本/Markdown，不进行 AI 生成。
    """
    try:
        output_path = output_file or input_file.with_suffix(".source.md")
        converter = FileConverter(
            ocr_backend=ocr_backend,
            tesseract_cmd=tesseract_cmd,
            doc_strategy=doc_strategy,
        )
        markdown_content = converter.convert_to_markdown(str(input_file))
        markdown_content = FileConverter.clean_text(markdown_content)
        output_path.write_text(markdown_content, encoding="utf-8")
        console.print(f"[green]✓[/green] Extracted source saved: {output_path}")
        _print_trace(converter.trace)
    except Exception as exc:
        console.print(f"[red]✗ Extract failed:[/red] {exc}")
        raise typer.Exit(1)


@app.command("compile", epilog=COMPILE_EPILOG)
def compile_cmd(
    tex_file: Path = typer.Argument(..., exists=True, help="要编译的 .tex 文件路径。"),
    engine: str = typer.Option(
        "auto",
        "--engine",
        help="LaTeX 引擎：auto、latexmk、xelatex、pdflatex。",
    ),
):
    """
    把已有的 TeX 文件编译为 PDF。
    """
    try:
        pdf_path = compile_latex(tex_file, engine=engine)
        console.print(f"[green]✓[/green] PDF generated: {pdf_path}")
    except Exception as exc:
        console.print(f"[red]✗ Compile failed:[/red] {exc}")
        raise typer.Exit(1)


@app.command()
def info():
    """
    显示环境变量、可执行文件和依赖包信息。
    """
    table = Table(title="MakePracticeBook CLI", show_header=True, header_style="bold cyan")
    table.add_column("Item", style="cyan", width=24)
    table.add_column("Value", style="magenta")
    table.add_row("Version", __version__)
    table.add_row("Supported Input", "doc, docx, pdf, md, txt")
    table.add_row("OCR Backends", "paddle, tesseract, auto, none")
    table.add_row("AI Providers", "openai, groq, zhipu")
    table.add_row("LaTeX Engine", "latexmk/xelatex/pdflatex")
    console.print(table)

    env_table = Table(title="Environment", show_header=True, header_style="bold yellow")
    env_table.add_column("Variable", style="yellow")
    env_table.add_column("Status")
    env_table.add_row("OPENAI_API_KEY", _mark(os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")))
    env_table.add_row("OPENAI_API_BASE", _mark(os.getenv("OPENAI_API_BASE") or os.getenv("API_BASE")))
    env_table.add_row("GROQ_API_KEY", _mark(os.getenv("GROQ_API_KEY")))
    env_table.add_row("GROQ_API_KEYS", _mark(os.getenv("GROQ_API_KEYS") or os.getenv("GROQ_API_kEYS")))
    env_table.add_row("ZHIPUAI_API_KEY", _mark(os.getenv("ZHIPUAI_API_KEY") or os.getenv("ZHIPU_API_KEY")))
    env_table.add_row("HTTP_PROXY", _mark(os.getenv("HTTP_PROXY")))
    env_table.add_row("HTTPS_PROXY", _mark(os.getenv("HTTPS_PROXY")))
    env_table.add_row("ALL_PROXY", _mark(os.getenv("ALL_PROXY")))
    console.print(env_table)

    binaries = Table(title="Detected Binaries", show_header=True, header_style="bold green")
    binaries.add_column("Binary", style="green")
    binaries.add_column("Path", style="white")
    for binary in ("latexmk", "xelatex", "pdflatex", "soffice", "powershell.exe"):
        binaries.add_row(binary, shutil.which(binary) or "-")
    console.print(binaries)

    packages = Table(title="Python Packages", show_header=True, header_style="bold blue")
    packages.add_column("Package", style="blue")
    packages.add_column("Status")
    for package in ("docx", "fitz", "paddleocr", "paddle", "pytesseract"):
        packages.add_row(package, _mark_import(package))
    console.print(packages)


@app.command()
def version():
    """
    显示版本信息。
    """
    console.print(f"[bold cyan]MakePracticeBook[/bold cyan] [bold green]{__version__}[/bold green]")


@app.callback()
def main():
    """
    做题本命令行入口。
    """
    pass


def _mark(value: Optional[str]) -> str:
    return "[green]set[/green]" if value else "[red]not set[/red]"


def _mark_import(module_name: str) -> str:
    try:
        __import__(module_name)
        return "[green]available[/green]"
    except Exception:
        return "[red]missing[/red]"


def _print_trace(trace: list[str]) -> None:
    if not trace:
        return
    console.print("[bold cyan]Extraction Trace[/bold cyan]")
    for item in trace:
        console.print(f"  - {item}")


def _print_coverage_stats(input_question_estimate: int, tex_path: Path) -> None:
    tex = tex_path.read_text(encoding="utf-8", errors="ignore")
    output_qitems = _count_qitems(tex)
    ratio = (output_qitems / input_question_estimate) if input_question_estimate else 0.0
    console.print(
        "[bold cyan]Coverage[/bold cyan]\n"
        f"  - estimated input questions: {input_question_estimate}\n"
        f"  - output qitems: {output_qitems}\n"
        f"  - output/input ratio: {ratio:.2%}"
    )


def _render_chunk_with_fallback(
    chunk: SourceChunk,
    *,
    provider: str,
    api_key: Optional[str],
    api_keys: list[str],
    api_base: Optional[str],
    model: Optional[str],
    use_segments: bool,
    segment_size: int,
    max_output_tokens: int,
    min_coverage_ratio: float,
    max_chunk_recursion: int,
    base_chunk_size: int,
    depth: int = 0,
) -> list[str]:
    snippet = process_with_ai_exbook(
        chunk.content,
        provider=provider,
        api_key=api_key,
        api_keys=api_keys,
        api_base=api_base,
        model=model,
        use_segments=use_segments,
        segment_size=segment_size,
        max_output_tokens=max_output_tokens,
        section_title=chunk.title,
        expected_question_count=chunk.question_estimate,
    ).strip()

    output_qitems = _count_qitems(snippet)
    coverage_ratio = _coverage_ratio(chunk.question_estimate, output_qitems)
    console.print(
        f"  -> output qitems={output_qitems} coverage={coverage_ratio:.2%}"
    )

    if not _should_refine_chunk(
        chunk=chunk,
        output_qitems=output_qitems,
        coverage_ratio=coverage_ratio,
        min_coverage_ratio=min_coverage_ratio,
        depth=depth,
        max_chunk_recursion=max_chunk_recursion,
    ):
        return [snippet]

    retry_chunk_size = max(800, min(base_chunk_size // 2, max(1200, chunk.char_count // 2)))
    subchunks = _split_chunk_for_retry(chunk, retry_chunk_size)
    if len(subchunks) <= 1:
        return [snippet]

    console.print(
        f"  -> [yellow]coverage low, retrying with {len(subchunks)} smaller chunks[/yellow]"
    )
    snippets: list[str] = []
    for subchunk in subchunks:
        snippets.extend(
            _render_chunk_with_fallback(
                subchunk,
                provider=provider,
                api_key=api_key,
                api_keys=api_keys,
                api_base=api_base,
                model=model,
                use_segments=use_segments,
                segment_size=segment_size,
                max_output_tokens=max_output_tokens,
                min_coverage_ratio=min_coverage_ratio,
                max_chunk_recursion=max_chunk_recursion,
                base_chunk_size=retry_chunk_size,
                depth=depth + 1,
            )
        )
    return snippets


def _split_chunk_for_retry(chunk: SourceChunk, max_chars: int) -> list[SourceChunk]:
    report = chunk_source_text(chunk.content, max_chars=max_chars, include_answers=True)
    subchunks: list[SourceChunk] = []
    for index, subchunk in enumerate(report.chunks, start=1):
        subchunks.append(
            SourceChunk(
                chunk_id=f"{chunk.chunk_id}.{index}",
                title=chunk.title,
                year=chunk.year,
                question_estimate=subchunk.question_estimate,
                char_count=subchunk.char_count,
                content=subchunk.content,
            )
        )
    return subchunks


def _should_refine_chunk(
    *,
    chunk: SourceChunk,
    output_qitems: int,
    coverage_ratio: float,
    min_coverage_ratio: float,
    depth: int,
    max_chunk_recursion: int,
) -> bool:
    if depth >= max_chunk_recursion:
        return False
    if chunk.question_estimate < 2:
        return False
    if output_qitems >= chunk.question_estimate:
        return False
    return coverage_ratio < min_coverage_ratio


def _coverage_ratio(question_estimate: int, output_qitems: int) -> float:
    if question_estimate <= 0:
        return 1.0 if output_qitems > 0 else 0.0
    return output_qitems / question_estimate


def _count_qitems(text: str) -> int:
    return len(re.findall(r"\\qitem", text))


if __name__ == "__main__":
    app()
