"""
CLI for building practice-book PDFs from doc/docx/pdf/md/txt inputs.
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

app = typer.Typer(
    name="mpb",
    help="Build ExBook practice books from doc/docx/pdf/md/txt inputs.",
    add_completion=False,
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


@app.command()
def build(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        help="Input file path (.doc, .docx, .pdf, .md, .txt)",
    ),
    output_dir: Path = typer.Option(
        _default_output_dir(),
        "--output-dir",
        "-o",
        help="Directory for generated .md/.tex/.pdf files.",
    ),
    output_stem: Optional[str] = typer.Option(
        None,
        "--output-stem",
        help="Override the output file stem.",
    ),
    provider: str = typer.Option(
        "openai",
        "--provider",
        "-p",
        help="AI provider: openai, groq or zhipu.",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="Single API key override.",
    ),
    api_keys: Optional[str] = typer.Option(
        None,
        "--api-keys",
        help="Semicolon-separated API key pool, mainly for Groq.",
    ),
    api_base: Optional[str] = typer.Option(
        None,
        "--api-base",
        help="Override the OpenAI-compatible API base URL.",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Model name override.",
    ),
    use_segments: bool = typer.Option(
        False,
        "--use-segments",
        help="Split long source text into multiple AI calls.",
    ),
    segment_size: int = typer.Option(
        2400,
        "--segment-size",
        help="Maximum characters per inner AI segment when --use-segments is enabled.",
    ),
    chunk_size: int = typer.Option(
        6000,
        "--chunk-size",
        help="Maximum characters per locally chunked section before LLM formatting.",
    ),
    max_output_tokens: int = typer.Option(
        5000,
        "--max-output-tokens",
        help="Maximum output tokens requested from the AI provider for each chunk.",
    ),
    min_coverage_ratio: float = typer.Option(
        0.6,
        "--min-coverage-ratio",
        help="Retry with smaller chunks when output qitem coverage falls below this ratio.",
    ),
    max_chunk_recursion: int = typer.Option(
        2,
        "--max-chunk-recursion",
        help="Maximum retry depth for automatically subdividing low-coverage chunks.",
    ),
    include_answers: bool = typer.Option(
        False,
        "--include-answers",
        help="Include answer sections when the source contains both questions and answers.",
    ),
    compile_pdf_flag: bool = typer.Option(
        True,
        "--compile/--no-compile",
        help="Compile the generated .tex into PDF.",
    ),
    engine: str = typer.Option(
        "auto",
        "--engine",
        help="LaTeX engine: auto, latexmk, xelatex, pdflatex.",
    ),
    ocr_backend: str = typer.Option(
        "paddle",
        "--ocr-backend",
        help="OCR backend: paddle, tesseract, auto, none.",
    ),
    tesseract_cmd: Optional[str] = typer.Option(
        None,
        "--tesseract-cmd",
        help="Path to the Tesseract executable when using Tesseract OCR.",
    ),
    doc_strategy: str = typer.Option(
        "auto",
        "--doc-strategy",
        help="Legacy .doc conversion strategy: auto, office, libreoffice.",
    ),
):
    """
    Convert an input file into ExBook TeX and optionally compile it into PDF.
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


@app.command()
def extract(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        help="Input file path (.doc, .docx, .pdf, .md, .txt)",
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output-file",
        "-o",
        help="Where to save the extracted Markdown-like text.",
    ),
    ocr_backend: str = typer.Option(
        "paddle",
        "--ocr-backend",
        help="OCR backend: paddle, tesseract, auto, none.",
    ),
    tesseract_cmd: Optional[str] = typer.Option(
        None,
        "--tesseract-cmd",
        help="Path to the Tesseract executable when using Tesseract OCR.",
    ),
    doc_strategy: str = typer.Option(
        "auto",
        "--doc-strategy",
        help="Legacy .doc conversion strategy: auto, office, libreoffice.",
    ),
):
    """
    Only extract normalized text/Markdown from the input file.
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


@app.command("compile")
def compile_cmd(
    tex_file: Path = typer.Argument(..., exists=True, help="Path to a .tex file."),
    engine: str = typer.Option(
        "auto",
        "--engine",
        help="LaTeX engine: auto, latexmk, xelatex, pdflatex.",
    ),
):
    """
    Compile an existing TeX file into PDF.
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
    Show environment and dependency information.
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
    Show version information.
    """
    console.print(f"[bold cyan]MakePracticeBook[/bold cyan] [bold green]{__version__}[/bold green]")


@app.callback()
def main():
    """
    MakePracticeBook CLI.
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
