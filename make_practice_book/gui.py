#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Exercise Book Generator GUI (Simplified Chinese UI)
"""

import sys
import os
import re
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List, Tuple
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QFileDialog,
    QProgressBar, QCheckBox, QGroupBox, QFormLayout, QMessageBox,
    QComboBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=False)

try:
    # Package-relative imports (preferred)
    from .file_converter import convert_file_to_markdown
    from .ai_processor import process_with_ai, process_with_ai_exbook
except Exception:
    # Fallback for direct execution: python make_practice_book/gui.py
    try:
        from make_practice_book.file_converter import convert_file_to_markdown
        from make_practice_book.ai_processor import process_with_ai, process_with_ai_exbook
    except Exception:
        # As last resort, add project root to sys.path and retry
        project_root = Path(__file__).resolve().parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from make_practice_book.file_converter import convert_file_to_markdown
        from make_practice_book.ai_processor import process_with_ai, process_with_ai_exbook


class ConvertWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, input_path: str, tesseract_cmd: Optional[str] = None):
        super().__init__()
        self.input_path = input_path
        self.tesseract_cmd = tesseract_cmd

    def run(self):
        try:
            self.log.emit("开始将文件转换为 Markdown ...")
            md = convert_file_to_markdown(self.input_path, self.tesseract_cmd)
            self.finished.emit(md)
        except Exception as e:
            self.error.emit(str(e))


class AIWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, markdown: str, provider: str, api_key: Optional[str],
                 api_base: Optional[str], model: str, use_segments: bool, exbook_mode: bool = False):
        super().__init__()
        self.markdown = markdown
        self.provider = provider
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.use_segments = use_segments
        self.exbook_mode = exbook_mode

    def run(self):
        try:
            self.log.emit("开始进行 AI 处理 ...")
            if self.exbook_mode:
                result = process_with_ai_exbook(
                    self.markdown,
                    provider=self.provider,
                    api_key=self.api_key,
                    model=self.model,
                )
            else:
                result = process_with_ai(
                    self.markdown,
                    provider=self.provider,
                    api_key=self.api_key,
                    api_base=self.api_base,
                    model=self.model,
                    use_segments=self.use_segments,
                )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("做题本生成器 (GUI)")
        self.resize(900, 680)
        self._build_ui()
        self._apply_style()

        self._current_markdown: Optional[str] = None
        self._convert_thread: Optional[ConvertWorker] = None
        self._ai_thread: Optional[AIWorker] = None

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # 输入输出
        io_group = QGroupBox("输入与输出")
        io_form = QFormLayout(io_group)
        io_form.setLabelAlignment(Qt.AlignRight)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("选择输入文件（.docx / .doc / .pdf）")
        input_row = QHBoxLayout()
        input_row.addWidget(self.input_edit)
        btn_browse_in = QPushButton("浏览...")
        btn_browse_in.clicked.connect(self._choose_input)
        input_row.addWidget(btn_browse_in)
        io_form.addRow(QLabel("输入文件："), self._wrap_row(input_row))

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("输出 Markdown 文件路径，默认与输入文件同名")
        out_row = QHBoxLayout()
        out_row.addWidget(self.output_edit)
        btn_browse_out = QPushButton("选择...")
        btn_browse_out.clicked.connect(self._choose_output)
        out_row.addWidget(btn_browse_out)
        io_form.addRow(QLabel("输出文件："), self._wrap_row(out_row))

        root.addWidget(io_group)

        # AI 设置
        ai_group = QGroupBox("AI 设置")
        ai_form = QFormLayout(ai_group)
        ai_form.setLabelAlignment(Qt.AlignRight)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["智谱AI", "Groq"])  # default to Zhipu (GLM)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("留空将从环境变量读取（GROQ_API_KEY / ZHIPUAI_API_KEY）")

        self.model_edit = QLineEdit("glm-4")
        self.model_combo = QComboBox()
        self.model_combo.setEditable(False)
        self.model_combo.currentIndexChanged.connect(self._on_model_selected)

        self.skip_ai_chk = QCheckBox("跳过 AI 处理（仅输出原始 Markdown）")
        self.exbook_chk = QCheckBox("输出为 ExBook LaTeX 到 out/main.tex")
        self.exbook_chk.setChecked(True)
        self.segments_chk = QCheckBox("分段处理长文档")

        # 编译引擎
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["latexmk (xelatex)", "xelatex", "pdflatex"])

        ai_form.addRow(QLabel("提供商："), self.provider_combo)
        ai_form.addRow(QLabel("API Key："), self.api_key_edit)
        ai_form.addRow(QLabel("推荐模型："), self.model_combo)
        ai_form.addRow(QLabel("模型："), self.model_edit)
        ai_form.addRow(QLabel("选项："), self._wrap_row(self._row(self.skip_ai_chk, self.segments_chk, self.exbook_chk)))
        ai_form.addRow(QLabel("编译引擎："), self.engine_combo)

        root.addWidget(ai_group)

        # OCR 设置
        ocr_group = QGroupBox("OCR 设置")
        ocr_form = QFormLayout(ocr_group)
        ocr_form.setLabelAlignment(Qt.AlignRight)

        self.tesseract_edit = QLineEdit()
        self.tesseract_edit.setPlaceholderText("Tesseract 可执行文件路径（可选）")
        t_row = QHBoxLayout()
        t_row.addWidget(self.tesseract_edit)
        btn_browse_tes = QPushButton("浏览...")
        btn_browse_tes.clicked.connect(self._choose_tesseract)
        t_row.addWidget(btn_browse_tes)
        ocr_form.addRow(QLabel("Tesseract："), self._wrap_row(t_row))

        root.addWidget(ocr_group)

        # 控制区
        ctrl_row = QHBoxLayout()
        self.btn_start = QPushButton("开始处理")
        self.btn_start.clicked.connect(self._on_start)
        self.btn_clear = QPushButton("清空日志")
        self.btn_clear.clicked.connect(lambda: self.log_view.clear())
        self.btn_compile = QPushButton("编译PDF")
        self.btn_compile.clicked.connect(self._on_compile)
        self.btn_open_dir = QPushButton("打开输出文件夹")
        self.btn_open_dir.clicked.connect(self._open_output_dir)
        ctrl_row.addWidget(self.btn_start)
        ctrl_row.addWidget(self.btn_clear)
        ctrl_row.addWidget(self.btn_compile)
        ctrl_row.addWidget(self.btn_open_dir)
        root.addLayout(ctrl_row)

        # 进度与日志
        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(1)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        # Prefill API key from .env and populate model list according to default provider
        try:
            self._on_provider_changed()
        except Exception:
            pass

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        root.addWidget(self.log_view, 1)

        # 初始化 provider 环境变量提示
        self._on_provider_changed()

    def _apply_style(self):
        self.setStyleSheet(
            """
            QMainWindow { background: #0f141a; }
            QGroupBox { color: #e6edf3; border: 1px solid #2d333b; border-radius: 6px; margin-top: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QLabel { color: #c9d1d9; }
            QLineEdit, QTextEdit, QComboBox { background: #161b22; color: #e6edf3; border: 1px solid #30363d; border-radius: 6px; padding: 6px; }
            QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled { background: #0b0f14; color: #8b949e; }
            QPushButton { background: #238636; color: white; border: none; border-radius: 6px; padding: 8px 12px; }
            QPushButton:hover { background: #2ea043; }
            QPushButton:disabled { background: #2f3338; color: #8b949e; }
            QCheckBox { color: #c9d1d9; }
            QProgressBar { background: #161b22; color: #e6edf3; border: 1px solid #30363d; border-radius: 6px; text-align: center; }
            QProgressBar::chunk { background-color: #2ea043; border-radius: 6px; }
            """
        )

    def _wrap_row(self, layout: QHBoxLayout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _row(self, *widgets) -> QHBoxLayout:
        row = QHBoxLayout()
        for w in widgets:
            row.addWidget(w)
        row.addStretch(1)
        return row

    def _choose_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择输入文件", str(Path.cwd()), "文档文件 (*.docx *.doc *.pdf)"
        )
        if not path:
            return
        self.input_edit.setText(path)
        self._suggest_output_path(Path(path))

    def _choose_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "选择输出文件", str(Path.cwd()), "Markdown 文件 (*.md)"
        )
        if path:
            if not path.lower().endswith('.md'):
                path += '.md'
            self.output_edit.setText(path)

    def _choose_tesseract(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Tesseract 可执行文件", str(Path.cwd()), "可执行文件 (*.*)"
        )
        if path:
            self.tesseract_edit.setText(path)

    def _open_output_dir(self):
        out = self.output_edit.text().strip()
        if out:
            p = Path(out)
            if p.exists():
                os.startfile(p.parent if p.is_file() else p)

    def _suggest_output_path(self, input_path: Path):
        if not self.output_edit.text().strip():
            self.output_edit.setText(str(input_path.with_name(f"{input_path.stem}_做题本.md")))

    def _on_provider_changed(self):
        name = self.provider_combo.currentText()
        if name == "Groq":
            env_key = os.getenv("GROQ_API_KEY", "")
            default_model = "llama3-70b-8192"
        else:
            env_key = os.getenv("ZHIPUAI_API_KEY", "") or os.getenv("ZHIPU_API_KEY", "")
            default_model = "glm-4"
        if not self.api_key_edit.text():
            self.api_key_edit.setText(env_key)
        # populate recommended models
        self._populate_models(name)
        if not self.model_edit.text():
            self.model_edit.setText(default_model)

    def _on_start(self):
        in_path = self.input_edit.text().strip()
        if not in_path:
            QMessageBox.warning(self, "提示", "请先选择输入文件")
            return
        suffix = Path(in_path).suffix.lower()
        if suffix not in (".docx", ".pdf"):
            QMessageBox.warning(self, "提示", "不支持的文件类型，请选择 .docx / .pdf")
            return

        out_path = self.output_edit.text().strip()
        if not out_path:
            self._suggest_output_path(Path(in_path))
            out_path = self.output_edit.text().strip()

        self._set_busy(True)
        self._append_log("开始处理...")

        self._convert_thread = ConvertWorker(
            in_path,
            tesseract_cmd=self.tesseract_edit.text().strip() or None,
        )
        self._convert_thread.finished.connect(self._on_convert_finished)
        self._convert_thread.error.connect(self._on_worker_error)
        self._convert_thread.log.connect(self._append_log)
        self._convert_thread.start()

    def _on_convert_finished(self, markdown: str):
        self._append_log("文件转换完成。")
        self._current_markdown = markdown
        if self.skip_ai_chk.isChecked():
            if self.exbook_chk.isChecked():
                # Generate base ExBook document without AI content
                self._write_exbook_output("")
            else:
                self._write_output(markdown)
            self._set_busy(False)
            QMessageBox.information(self, "完成", "已生成 Markdown 文件。")
            return

        provider = self.provider_combo.currentText().lower()
        if provider == "智谱ai":
            provider = "zhipu"

        self._ai_thread = AIWorker(
            markdown,
            provider=provider,
            api_key=self.api_key_edit.text().strip() or None,
            api_base=None,
            model=self.model_edit.text().strip() or "glm-4",
            use_segments=self.segments_chk.isChecked(),
            exbook_mode=self.exbook_chk.isChecked(),
        )
        self._ai_thread.finished.connect(self._on_ai_finished)
        self._ai_thread.error.connect(self._on_worker_error)
        self._ai_thread.log.connect(self._append_log)
        self._ai_thread.start()

    def _on_ai_finished(self, content: str):
        self._append_log("AI 处理完成。")
        if self.exbook_chk.isChecked():
            self._write_exbook_output(content)
        else:
            self._write_output(content)
        self._set_busy(False)
        QMessageBox.information(self, "完成", "做题本文件生成成功！")

    def _build_exbook_document(self, snippet: str) -> str:
        lines = [
            "% Auto-detect ExBook directory for both root and out/ builds",
            "\\newcommand{\\EXBOOKDIR}{ExBook}",
            "\\IfFileExists{../ExBook/ExBook.cls}{\\renewcommand{\\EXBOOKDIR}{../ExBook}}{}",
            "\\documentclass[standard]{\\EXBOOKDIR/ExBook}",
            "\\usepackage{graphicx}",
            "\\graphicspath{{\\EXBOOKDIR/img/}}",
            "\\begin{document}",
            "\\input{\\EXBOOKDIR/config.tex}",
            "\\maketitle",
            "\\input{\\EXBOOKDIR/contents/pre.tex}",
            "\\input{\\EXBOOKDIR/contents/print.tex}",
            "\\setcounter{page}{1}",
            "\\tableofcontents",
            "\\clearpage",
            "",
            "% AI 生成内容开始",
        ]
        if snippet and snippet.strip():
            lines.append(snippet.strip())
        else:
            lines.append("% (空) 跳过 AI 处理，未插入内容")
        lines += [
            "",
            "% AI 生成内容结束",
            "",
            "\\end{document}",
        ]
        return "\n".join(lines)

    def _write_exbook_output(self, snippet: str):
        out_dir = Path.cwd() / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_tex = out_dir / "main.tex"
        try:
            content = self._build_exbook_document(snippet)
            with open(out_tex, "w", encoding="utf-8") as f:
                f.write(content)
            self._append_log(f"已生成 ExBook LaTeX：{out_tex}")
        except Exception as e:
            self._append_log(f"保存 ExBook LaTeX 失败：{e}")
            QMessageBox.critical(self, "错误", f"保存 ExBook LaTeX 失败：{e}")

    def _on_compile(self):
        out_dir = Path.cwd() / "out"
        out_tex = out_dir / "main.tex"
        if not out_tex.exists():
            QMessageBox.warning(self, "提示", f"未找到 {out_tex}，请先生成 LaTeX 文件。")
            return
        sel = self.engine_combo.currentText()
        use_latexmk = sel.startswith("latexmk")
        engine = shutil.which("latexmk") if use_latexmk else (shutil.which("xelatex") if sel == "xelatex" else shutil.which("pdflatex"))
        if not engine:
            QMessageBox.critical(self, "错误", "未找到 xelatex/pdflatex，请安装 TeX 发行版并加入 PATH。")
            return
        self._set_busy(True)
        self._append_log(f"开始编译：{engine} {out_tex}")
        try:
            if use_latexmk:
                proc = subprocess.run(
                    [engine, "-xelatex", "-pdf", "main.tex"],
                    cwd=str(out_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                )
                self._append_log(proc.stdout)
                if proc.returncode != 0:
                    raise RuntimeError("latexmk 编译失败")
            else:
                # run twice for TOC
                for i in range(2):
                    proc = subprocess.run(
                        [engine, "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
                        cwd=str(out_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                    )
                    self._append_log(proc.stdout)
                    if proc.returncode != 0:
                        raise RuntimeError(f"LaTeX 编译失败（第{i+1}次）。")
            pdf_path = out_dir / "main.pdf"
            if pdf_path.exists():
                self._append_log(f"编译成功：{pdf_path}")
                try:
                    os.startfile(str(pdf_path))
                except Exception:
                    pass
                QMessageBox.information(self, "完成", f"PDF 已生成：{pdf_path}")
            else:
                QMessageBox.warning(self, "提示", "编译完成，但未找到 main.pdf")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"编译失败：{e}")
        finally:
            self._set_busy(False)

    def _write_output(self, content: str):
        out = self.output_edit.text().strip()
        try:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                f.write(content)
            self._append_log(f"已保存：{out}")
        except Exception as e:
            self._append_log(f"保存失败：{e}")
            QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def _on_worker_error(self, msg: str):
        self._append_log(f"错误：{msg}")
        self._set_busy(False)
        QMessageBox.critical(self, "错误", msg)

    def _append_log(self, text: str):
        self.log_view.append(text)

    def _set_busy(self, busy: bool):
        self.btn_start.setDisabled(busy)
        self.btn_clear.setDisabled(busy)
        self.btn_open_dir.setDisabled(busy)
        self.btn_compile.setDisabled(busy)
        self.input_edit.setDisabled(busy)
        self.output_edit.setDisabled(busy)
        self.provider_combo.setDisabled(busy)
        self.api_key_edit.setDisabled(busy)
        self.model_edit.setDisabled(busy)
        self.model_combo.setDisabled(busy)
        self.skip_ai_chk.setDisabled(busy)
        self.segments_chk.setDisabled(busy)
        self.tesseract_edit.setDisabled(busy)
        if busy:
            self.progress.setRange(0, 0)  # busy indicator
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)

    def _on_model_selected(self, idx: int):
        if idx >= 0:
            name = self.model_combo.itemData(idx)
            if not name:
                # fallback to text
                name = self.model_combo.currentText().strip()
            if name:
                self.model_edit.setText(str(name))

    def _populate_models(self, provider_name: str):
        # provider_name: "智谱AI" or "Groq"
        prov = "zhipu" if provider_name == "智谱AI" else "groq"
        models = self._load_recommended_models(prov)
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for display, name in models:
            # Store real model name as data
            self.model_combo.addItem(display, name)
        self.model_combo.blockSignals(False)

    def _load_recommended_models(self, provider: str) -> List[Tuple[str, str]]:
        """Load recommended models from models.yaml if present, else fallback to demo parsing.
        Returns list of tuples (display_text, model_name).
        """
        yaml_file = Path.cwd() / "models.yaml"
        if yaml_file.exists():
            try:
                import yaml  # type: ignore
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
                prov = data.get(provider, {})
                rec = prov.get("recommended", [])
                items: List[Tuple[str, str]] = []
                for it in rec:
                    name = it.get("name")
                    alias = it.get("alias") or name
                    if name:
                        display = f"{alias} ({name})" if alias and alias != name else name
                        items.append((display, name))
                if items:
                    return items
                # fallback to all
                all_list = prov.get("all", []) or []
                return [(m, m) for m in all_list]
            except Exception:
                pass

        # Fallback: parse api_demonstrate
        defaults = [
            ("glm-4-flash-250414", "glm-4-flash-250414"),
            ("glm-4-flash-250414", "glm-4-flash-250414"),
            ("glm-4-flash-250414", "glm-4-flash-250414"),
        ] if provider == "zhipu" else [
            ("llama3-70b-8192", "llama3-70b-8192"),
            ("llama3-8b-8192", "llama3-8b-8192"),
        ]
        try:
            base = Path(__file__).resolve().parent.parent / "api_demonstrate" / ("zhipu" if provider == "zhipu" else "groq")
            if not base.exists():
                return defaults
            found: List[str] = []
            for pyf in sorted(base.glob("*.py")):
                try:
                    text = pyf.read_text(encoding="utf-8", errors="ignore")[:4000]
                    m = re.search(r'model\s*=\s*[\"\']([^\"\']+)[\"\']', text)
                    if m:
                        found.append(m.group(1))
                    else:
                        found.append(pyf.stem)
                except Exception:
                    continue
            seen = set()
            uniq: List[str] = []
            for m in found:
                if m and m not in seen:
                    uniq.append(m)
                    seen.add(m)
            return [(m, m) for m in (uniq or [d for d, _ in defaults])]
        except Exception:
            return defaults


def main():
    os.environ.setdefault("QT_API", "pyqt5")
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
