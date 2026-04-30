# MakePracticeBook

一个面向 Windows 的 CLI 工具，把 `doc` / `docx` / `pdf` / `md` / `txt` 输入整理成 ExBook LaTeX，再编译为适合手写做题的 PDF。

## 当前定位

这个仓库已经从早期的 GUI 半成品，收束为纯命令行工作流：

`输入文档 -> 文本/版面提取 -> Groq/Zhipu 生成 ExBook 片段 -> 输出 .tex -> 编译 .pdf`

最终核心产物：

- `out/<name>.source.md`
- `out/<name>.tex`
- `out/<name>.pdf`

## 支持输入

- `.txt`
- `.md`
- `.docx`
- `.doc`
- `.pdf`

处理策略：

- `txt/md`：直接读取
- `docx`：使用 `python-docx` 提取段落和表格
- `doc`：优先用本地 Microsoft Word 2021 COM 自动转成 `docx`，失败后尝试 LibreOffice
- `pdf`：优先尝试 Paddle `PPStructureV3` 版面解析，其次回退到 PaddleOCR 按页 OCR，最后退回 PyMuPDF / Tesseract

## 环境要求

- Windows
- Python `>= 3.11, < 3.14`
- 本地 TeX 发行版，推荐 `latexmk + xelatex`
- Microsoft Office 或 LibreOffice
- 如果要处理扫描版 PDF，建议安装 PaddleOCR 与 PaddlePaddle

说明：

- 这个仓库已经支持代理环境变量，适合中国大陆网络环境
- Groq 支持多 API Key 轮换

## 安装

### 开发态

```powershell
pip install -e .
```

然后直接使用：

```powershell
mpb --help
```

### 打包为 EXE

```powershell
pyinstaller mpb.spec
```

生成目录：

```text
dist/mpb/mpb.exe
```

把目录加入用户 PATH：

```powershell
.\mpb.ps1
```

之后重新打开终端：

```powershell
mpb --help
```

## 配置

参考 [.env.example](/d:/py_work/2025/MakePracticeBook/.env.example:1)。

常用变量：

```env
ZHIPUAI_API_KEY=your_zhipu_key
GROQ_API_KEYS=key1;key2;key3
HTTP_PROXY=http://127.0.0.1:10808
HTTPS_PROXY=http://127.0.0.1:10808
ALL_PROXY=socks5://127.0.0.1:10808
```

说明：

- `GROQ_API_KEYS` 使用分号分隔，程序会在可恢复错误时自动切换
- 若同时设置 `--api-key`，命令行参数优先

## 命令

### 1. 生成做题本

```powershell
mpb build examples\中国科学技术大学.docx --provider openai --compile
```

常见参数：

- `--output-dir out`
- `--output-stem custom_name`
- `--provider openai`
- `--api-key xxx`
- `--api-keys key1;key2;key3`
- `--model llama-3.1-70b-versatile`
- `--use-segments`
- `--ocr-backend paddle`
- `--doc-strategy auto`
- `--engine latexmk`

### 2. 只提取源文本

```powershell
mpb extract examples\中国科学技术大学.docx
```

### 3. 单独编译 TeX

```powershell
mpb compile out\中国科学技术大学.tex
```

### 4. 查看环境信息

```powershell
mpb info
```

## 模块结构

```text
make_practice_book/
├── __main__.py
├── ai_processor.py
├── cli.py
├── doc_converter.py
├── exbook_writer.py
├── file_converter.py
├── latex_compiler.py
└── version.py
```

## 已知边界

- 当前 `docx` 提取仍以文字和表格为主，不是完整版式还原
- PaddleOCR 首次运行会下载官方模型，第一次明显更慢
- `.doc` 转换依赖本机 Office 或 LibreOffice
- AI 只负责生成 ExBook 内容片段，完整文档壳由程序写入

## 设计原则

- GUI 不再是主路径
- ExBook 是最终排版目标
- 程序写文档骨架，AI 只写题目内容片段
- 先保证 CLI 闭环稳定，再逐步增强 OCR 和复杂版式恢复
