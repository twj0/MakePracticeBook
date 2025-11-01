"""
Exercise Book Generator CLI Interface
"""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.panel import Panel
import os
import subprocess
import shutil
from dotenv import load_dotenv, find_dotenv

from .file_converter import FileConverter
from .ai_processor import AIProcessor, GroqProcessor, ZhipuAIProcessor
from .version import __version__

app = typer.Typer(
    name="mpb",
    help="Exercise Book Generator - Convert docx/doc/pdf files to handwritten exercise book format",
    add_completion=False
)
console = Console()

# Load environment variables from .env if present (searching upwards)
load_dotenv(find_dotenv(), override=False)


@app.command()
def convert(
    input_file: Path = typer.Argument(..., help="Input file path (.docx, .pdf)", exists=True),
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o", help="Output file path"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API key override (uses GROQ_API_KEY or ZHIPUAI_API_KEY from env if omitted)"),
    model: str = typer.Option("glm-4", "--model", "-m", help="AI model to use (e.g., glm-4, llama3-70b-8192)"),
    skip_ai: bool = typer.Option(False, "--skip-ai", help="Skip AI processing, only convert to Markdown"),
    use_segments: bool = typer.Option(False, "--use-segments", help="Process long content in segments"),
    tesseract_cmd: Optional[str] = typer.Option(None, "--tesseract-cmd", help="Path to tesseract executable"),
    provider: Optional[str] = typer.Option("zhipu", "--provider", "-p", help="AI provider: groq, zhipu"),
    exbook: bool = typer.Option(False, "--exbook", help="Output ExBook LaTeX to out/main.tex instead of Markdown"),
    compile_pdf: bool = typer.Option(False, "--compile", help="Compile out/main.tex to PDF (requires xelatex/pdflatex)")
):
    """
    Convert document file to exercise book format
    
    Examples:
        mpb convert input.docx
        mpb convert input.pdf --output-file my_book.md
        mpb convert input.docx --skip-ai
        mpb convert input.pdf --provider groq
    """
    # Check file format
    suffix = input_file.suffix.lower()
    if suffix == '.doc':
        console.print("[red]Error: .doc (legacy) is not supported. Please convert to .docx first.[/red]")
        raise typer.Exit(1)
    supported_formats = ['.docx', '.pdf']
    if suffix not in supported_formats:
        console.print(f"[red]Error: Unsupported file format. Supported formats: {', '.join(supported_formats)}[/red]")
        raise typer.Exit(1)
    
    # Set default output file name (Markdown mode)
    if output_file is None and not exbook:
        output_file = input_file.with_name(f"{input_file.stem}_exercise_book.md")
    
    # Compose an initial status panel (for ExBook we will show target .tex later)
    panel_lines = [f"[bold cyan]Processing file:[/bold cyan] {input_file}"]
    if not exbook:
        panel_lines.append(f"[bold cyan]Output file:[/bold cyan] {output_file}")
    console.print(Panel.fit(
        "\n".join(panel_lines),
        title="Exercise Book Generator",
        border_style="cyan"
    ))
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        # Step 1: File conversion
        task1 = progress.add_task("[cyan]Converting file to Markdown...", total=None)
        converter = FileConverter(tesseract_cmd=tesseract_cmd)
        try:
            markdown_content = converter.convert_to_markdown(str(input_file))
            markdown_content = FileConverter.clean_text(markdown_content)
            progress.update(task1, completed=True)
            console.print("[green]✓[/green] File conversion completed")
        except Exception as e:
            progress.stop()
            console.print(f"[red]✗ File conversion failed: {str(e)}[/red]")
            raise typer.Exit(1)
        
        # If skip AI processing
        if skip_ai:
            if exbook:
                # Write ExBook template with empty snippet
                base_name = input_file.stem
                tex_path = _write_exbook_output("", base_name=base_name)
                console.print(f"[green]✓[/green] ExBook LaTeX generated: {tex_path}")
                if compile_pdf:
                    _compile_pdf(console, tex_filename=f"{base_name}.tex")
                return
            else:
                task_save = progress.add_task("[cyan]Saving file...", total=None)
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    progress.update(task_save, completed=True)
                    console.print("[green]✓[/green] File saved successfully")
                    console.print(f"[green]Original Markdown file generated:[/green] {output_file}")
                    return
                except Exception as e:
                    progress.stop()
                    console.print(f"[red]✗ File save failed: {str(e)}[/red]")
                    raise typer.Exit(1)
        
        # Step 2: AI processing
        task2 = progress.add_task("[cyan]AI processing...", total=None)
        
        try:
            # Select AI processor based on provider
            if provider == "groq":
                processor = GroqProcessor(api_key=api_key)
            elif provider == "zhipu":
                processor = ZhipuAIProcessor(api_key=api_key)
            else:
                console.print("[red]Error: Unknown provider. Use 'groq' or 'zhipu'.[/red]")
                raise typer.Exit(1)
            
            if exbook:
                exercise_book_content = processor.process_to_exbook_latex(markdown_content)
            else:
                if use_segments:
                    exercise_book_content = processor.process_with_segments(markdown_content)
                else:
                    exercise_book_content = processor.process_exercise_book(markdown_content)
            
            progress.update(task2, completed=True)
            console.print("[green]✓[/green] AI processing completed")
        except Exception as e:
            progress.stop()
            console.print(f"[red]✗ AI processing failed: {str(e)}[/red]")
            console.print("[yellow]Tip: You can use --skip-ai to generate Markdown without AI processing[/yellow]")
            raise typer.Exit(1)
        
        # Step 3: Save file
        if exbook:
            # Write ExBook LaTeX to out/{input_stem}.tex
            try:
                base_name = input_file.stem
                tex_path = _write_exbook_output(exercise_book_content, base_name=base_name)
                console.print(f"[green]✓[/green] ExBook LaTeX generated: {tex_path}")
                if compile_pdf:
                    _compile_pdf(console, tex_filename=f"{base_name}.tex")
            except Exception as e:
                progress.stop()
                console.print(f"[red]✗ ExBook save failed: {str(e)}[/red]")
                raise typer.Exit(1)
        else:
            task3 = progress.add_task("[cyan]Saving file...", total=None)
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(exercise_book_content)
                progress.update(task3, completed=True)
                console.print("[green]✓[/green] File saved successfully")
            except Exception as e:
                progress.stop()
                console.print(f"[red]✗ File save failed: {str(e)}[/red]")
                raise typer.Exit(1)
    
    console.print(Panel.fit(
        f"[bold green]Exercise book generated successfully![/bold green]\n"
        f"[cyan]Output:[/cyan] {output_file}",
        border_style="green"
    ))


@app.command()
def info():
    """
    Display project information
    """
    table = Table(title="Exercise Book Generator Information", show_header=True, header_style="bold cyan")
    table.add_column("Item", style="cyan", width=20)
    table.add_column("Details", style="magenta")
    
    table.add_row("Version", __version__)
    table.add_row("Supported Input", "docx, pdf")
    table.add_row("Output Format", "Markdown or ExBook LaTeX (--exbook)")
    table.add_row("AI Support", "Groq/ZhipuAI and compatible OpenAI APIs")
    table.add_row("OCR Support", "Yes (for scanned PDFs)")
    
    console.print(table)
    
    console.print("\n[bold cyan]Environment Variables:[/bold cyan]")
    env_table = Table(show_header=True, header_style="bold yellow")
    env_table.add_column("Variable", style="yellow")
    env_table.add_column("Description", style="white")
    env_table.add_column("Status", style="green")
    
    env_vars = [
        ("GROQ_API_KEY", "Groq API key", os.getenv("GROQ_API_KEY")),
        ("ZHIPUAI_API_KEY", "Zhipu AI API key", os.getenv("ZHIPUAI_API_KEY")),
    ]
    
    for var_name, description, value in env_vars:
        status = "✓ Set" if value else "✗ Not set"
        style = "green" if value else "red"
        env_table.add_row(var_name, description, f"[{style}]{status}[/{style}]")
    
    console.print(env_table)


def _build_exbook_document(snippet: str) -> str:
    lines = [
        r"\newcommand{\EXBOOKDIR}{ExBook}",
        r"\IfFileExists{../ExBook/ExBook.cls}{\renewcommand{\EXBOOKDIR}{../ExBook}}{}",
        r"\IfFileExists{ExBook/ExBook.cls}{\renewcommand{\EXBOOKDIR}{ExBook}}{}",
        r"\documentclass[standard]{\EXBOOKDIR/ExBook}",
        r"\usepackage{graphicx}",
        r"\graphicspath{{\EXBOOKDIR/}{\EXBOOKDIR/img/}}",
        r"\begin{document}",
        r"\input{\EXBOOKDIR/config.tex}",
        r"\maketitle",
        r"\input{\EXBOOKDIR/contents/pre.tex}",
        r"\input{\EXBOOKDIR/contents/print.tex}",
        r"\setcounter{page}{1}",
        r"\tableofcontents",
        "",
        r"% AI 生成内容开始",
    ]
    if snippet and snippet.strip():
        lines.append(snippet.strip())
    else:
        lines.append(r"% (空) 跳过 AI 处理，未插入内容")
    lines += [
        "",
        r"% AI 生成内容结束",
        "",
        r"\end{document}",
    ]
    return "\n".join(lines)


def _write_exbook_output(snippet: str, base_name: str = "main") -> str:
    out_dir = Path.cwd() / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_tex = out_dir / f"{base_name}.tex"
    content = _build_exbook_document(snippet)
    with open(out_tex, "w", encoding="utf-8") as f:
        f.write(content)
    return str(out_tex)


def _compile_pdf(console: Console, tex_filename: str = "main.tex"):
    out_dir = Path.cwd() / "out"
    out_tex = out_dir / tex_filename
    if not out_tex.exists():
        console.print(f"[red]{out_tex} not found. Generate LaTeX first.[/red]")
        raise typer.Exit(1)
    engine = shutil.which("latexmk") or shutil.which("xelatex") or shutil.which("pdflatex")
    if not engine:
        console.print("[red]latexmk/xelatex/pdflatex not found in PATH.[/red]")
        raise typer.Exit(1)
    console.print(f"[cyan]Compiling with {engine}...[/cyan]")
    if engine.lower().endswith("latexmk.exe") or os.path.basename(engine).lower() == "latexmk":
        proc = subprocess.run(
            [engine, "-xelatex", "-pdf", tex_filename],
            cwd=str(out_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )
        console.print(proc.stdout)
        if proc.returncode != 0:
            console.print("[red]latexmk compile failed.[/red]")
            raise typer.Exit(1)
    else:
        for i in range(2):
            proc = subprocess.run(
                [engine, "-interaction=nonstopmode", "-halt-on-error", tex_filename],
                cwd=str(out_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
            )
            console.print(proc.stdout)
            if proc.returncode != 0:
                console.print(f"[red]LaTeX compile failed on pass {i+1}.[/red]")
                raise typer.Exit(1)
    # Determine expected PDF name from tex filename
    pdf_basename = Path(tex_filename).with_suffix("")
    pdf_path = out_dir / f"{pdf_basename}.pdf"
    if pdf_path.exists():
        console.print(f"[green]✓ PDF generated:[/green] {pdf_path}")
    else:
        console.print(f"[yellow]Compile finished, but {pdf_path.name} not found.[/yellow]")


@app.command()
def version():
    """
    Display version information
    """
    console.print(f"[bold cyan]Exercise Book Generator[/bold cyan] version [bold green]{__version__}[/bold green]")


@app.callback()
def main():
    """
    Exercise Book Generator - Convert docx/doc/pdf files to handwritten exercise book format
    """
    pass


if __name__ == "__main__":
    app()
