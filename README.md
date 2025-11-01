## 用途

这个项目下的一系列脚本，用于创建考研习题做题本。

像是「李林660」这样的习题册，题与题之间没有空隙，做题体验、笔记体验非常不好。

![image-20230306172247418](assets/李林880截选.jpg)

有博主就做了「做题本」，大致就是先将习题册扫描，再把每道题截图，放到一个单独的页面中，一页纸就放一道题，然后合并成PDF。

![image-20230306172411701](assets/做题本截选.jpg)

不过，博主在制作的时候好像没有去关注 pdf 的尺寸，页面放得很大，导致将这些习题册PDF导入到 GoodNotes 这样的笔记软件中时，会使得正常的笔画很细。

于是，就自己搞了一下做题本的制作流程，这样，能按照自己的喜好快速制作这样的「做题本」：

![我的习题本示例](assets/我的习题本示例.jpg)

## 运行环境

只适用于 Windows

需要用到 ImageMagick，已内置 `magick.exe` 

## 用法

视频教程：[制作考研做题本，给紧凑的习题册PDF增加做题空隙](https://www.bilibili.com/video/BV13N411c7yx)

### 获取 PDF

在这里，我用「李林880」作为示例。

首先，要得到试题册的扫描版 PDF：

- 有的考研博主会提供
- 也可以到淘宝上购买扫描服务，大概是1毛一页

注意，PDF 的页面尺寸一定要正常，有的博主提供的PDF就非常大，导入笔记软件就会让正常笔画非常细。

### 题目切片

用 PhotoShop 打开 PDF，例如打开第8、9页：

![01](assets/01.jpg)

![02](assets/02.jpg)


通过左下角的信息，注意到页面的宽度约 17 厘米，高度约 25.6 厘米，DPI 是 300，这就是正常的一比一扫描件大小。

以第 8 页为例，用参考线工具，为每一道题做切片：

![03](assets/03.jpg)

![04](assets/04.jpg)

导出第 8 页的切片：

![05](assets/05.jpg)

![05](assets/06.jpg)

![07](assets/07.jpg)

![07](assets/08.jpg)

以相同的方法，为第9页制作切片、导出切片：

![09](assets/09.jpg)

![09](assets/10.jpg)

### 合并跨页题

注意到，第 8 页的最后一道题，只印了一半，另一半在第9页上，于是就需要将这两个切片合并起来：

![11](assets/11.jpg)

![11](assets/12.jpg)

### 添加背景，合并为 PDF

![13](assets/13.jpg)

![13](assets/14.jpg)

![15](assets/15.jpg)

![15](assets/16.jpg)



## 注意点

如果你的扫描版电子书的 DPI 不是300，可能需要手动改一下 bat 脚本，更改为你 PDF 对应的 DPI。

当然，你也可以用 PS 一类的工具制作更好看的背景图片。

## ChatGPT 对话大致记录

这个项目所用到的脚本，都是在 ChatGPT 的帮助下，写出来的。这是一些对话的记录：

> 接下来我会让你写一些 bat 脚本，其中会用到一些工具，如 FFmpeg、ImageMagick 等，这些工具我已安装，添加到了环境目录，可以直接使用。
>
> 写一个 bat 脚本，它会使用 ImageMagick 生成一张图片，图片的大小是 148mm * 210mm，图片的 DPI 是 300，图片的背景色是白色，色彩模式使用 RGB，输出的文件名是「背景.png」
>
> 写一个BAT脚本，它会把传入的多张 jpg 图片用 ImageMagick 的 -append 选项纵向拼接起来，输出文件直接覆盖第一个文件，最后，把第一个以外的其他文件全部删除。
>
> 在当前目录已经有一个背景图片，文件名是「背景.png」。请写一个BAT脚本，给它输入一个文件夹后，它会用 ImageMagick 递归地修改文件夹里的每一张 jpg 图片。具体修改的做法是，将传入的图片作为前景，叠加到背景图上，起点位置为 (100, 100)，单位为像素。输出的时候，直接替代原文件即可。
>
> 写一个BAT脚本，它会把传入的所有 jpg 图片用 ImageMagick 的将 DPI 修改为 300，输出的时候，直接替代原文件即可。
>
> 写一个BAT脚本，它会把传入的所有 jpg 图片用 ImageMagick 合并为一个 pdf 文件，输出到当前位置。

---

# 二次开发 内容

# MakePracticeBook - 做题本生成器

## 项目简介

MakePracticeBook 是一个现代化的做题本生成工具，可以自动将 docx、doc 和 pdf 文件转换为适合手写练习的做题本格式。

### 核心功能

- ✨ **多格式支持**：支持 DOCX、DOC、PDF 文件
- 🔍 **智能 OCR**：自动识别扫描版 PDF 中的文本  
- 🤖 **AI 增强**：使用 AI 将内容重新组织为适合做题的格式
- 💻 **友好的 CLI**：提供清晰的命令行界面和进度显示
- 🔧 **灵活配置**：支持多种 AI 模型和 API 端点（OpenAI、Groq、ZhipuAI）

## 安装

### 依赖要求

- Python >= 3.13
- Tesseract OCR（用于 OCR 功能）

### 安装步骤

1. **克隆项目**：
```bash
git clone <repository-url>
cd MakePracticeBook
```

2. **安装依赖**：
```bash
pip install -e .
```

3. **安装 Tesseract OCR**（可选，用于扫描版 PDF）：
   - Windows: 下载并安装 [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
   - 下载中文语言包：chi_sim.traineddata

4. **配置环境变量**：

创建 `.env` 文件或设置环境变量：

```bash
# OpenAI API 配置
API_KEY=your_openai_api_key
API_BASE=https://api.openai.com/v1

# 或者使用 Groq
GROQ_API_KEY=your_groq_api_key

# 或者使用智谱 AI
ZHIPUAI_API_KEY=your_zhipuai_api_key
```

## 使用方法

### 基本命令

```bash
# 转换文档文件为做题本格式
mpb convert input.docx

# 指定输出文件
mpb convert input.pdf --output-file my_exercise_book.md

# 使用 Groq API
mpb convert input.docx --provider groq

# 使用智谱 AI
mpb convert input.pdf --provider zhipu

# 跳过 AI 处理，仅转换为 Markdown
mpb convert input.docx --skip-ai

# 处理长文档（分段处理）
mpb convert input.pdf --use-segments

# 查看项目信息
mpb info

# 查看版本
mpb version
```

### 使用 Python 模块运行

```bash
python -m make_practice_book convert input.docx
```

### 命令行选项

| 选项 | 说明 |
|------|------|
| `--output-file, -o` | 指定输出文件路径 |
| `--api-key` | AI API 密钥 |
| `--api-base` | AI API 基础 URL |
| `--model, -m` | 使用的 AI 模型 |
| `--provider, -p` | AI 提供商（openai, groq, zhipu） |
| `--skip-ai` | 跳过 AI 处理，仅转换为 Markdown |
| `--use-segments` | 分段处理长内容 |
| `--tesseract-cmd` | Tesseract 可执行文件路径 |

## 工作流程

```
输入文件 (DOCX/DOC/PDF)
    ↓
文件转换 (使用 OCR 处理扫描版 PDF)
    ↓
生成 Markdown
    ↓
AI 处理 (重新组织为做题本格式)
    ↓
输出做题本文件 (Markdown)
```

## 项目结构

```
make_practice_book/
├── __init__.py          # 包初始化
├── __main__.py          # 模块入口
├── version.py           # 版本信息
├── file_converter.py    # 文件转换模块
├── ai_processor.py      # AI 处理模块
└── cli.py              # CLI 接口
```

## 开发指南

### 模块说明

#### file_converter.py
负责将 docx/doc/pdf 文件转换为 Markdown 格式：
- 支持直接文本提取
- 使用 OCR 处理扫描版文档
- 图像预处理提高 OCR 准确率

#### ai_processor.py
使用 AI API 将 Markdown 内容转换为做题本格式：
- 支持多种 AI 提供商
- 分段处理长文档
- 自定义提示词

#### cli.py
提供友好的命令行界面：
- 使用 Typer 构建
- Rich 库提供美观的终端输出
- 进度条和状态提示

## 示例

### 转换 DOCX 文件

```bash
mpb convert 中国科学技术大学.docx
```

输出：
```
╭──────────────────────────────────────╮
│ Processing file: 中国科学技术大学.docx   │
│ Output file: 中国科学技术大学_exercise_book.md │
╰──────────────────────────────────────╯

⠋ Converting file to Markdown...
✓ File conversion completed
⠋ AI processing...
✓ AI processing completed
⠋ Saving file...
✓ File saved successfully

╭────────────────────────────────────────╮
│ Exercise book generated successfully!   │
│ Output: 中国科学技术大学_exercise_book.md  │
╰────────────────────────────────────────╯
```

## 常见问题

### Q: 如何处理扫描版 PDF？
A: 确保已安装 Tesseract OCR 及中文语言包，工具会自动检测并使用 OCR。

### Q: AI 处理失败怎么办？
A: 可以使用 `--skip-ai` 选项跳过 AI 处理，只生成 Markdown 文件。

### Q: 如何自定义 AI 提示词？
A: 可以直接修改 `ai_processor.py` 中的 `_get_default_prompt` 方法。

### Q: 支持哪些 AI 模型？
A: 支持所有兼容 OpenAI API 格式的模型，包括 OpenAI、Groq、智谱 AI 等。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

[根据你的项目许可证填写]

---

## GUI 使用（简体中文）

提供图形界面，便于不熟悉命令行的同学使用。

### 启动方式

- 命令行：

```bash
mpb-gui
```

- Python 模块：

```bash
python -m make_practice_book.gui
```

- Windows 双击脚本：

双击运行仓库根目录的 `make_practice_book_gui.bat`。

### GUI 功能

- 选择输入文件（.docx / .doc / .pdf）
- 可选 Tesseract 路径（用于扫描版 PDF 的 OCR）
- 选择 AI 提供商（OpenAI / Groq / 智谱AI）
- 可选分段处理长文档
- 跳过 AI 仅输出原始 Markdown
- 实时日志与忙碌指示

提示：.doc（老格式）在多数环境中需要先转换为 .docx 后再处理。

## 打包为 Windows EXE（无需安装 Python）

以下命令在 Windows PowerShell 中执行，建议提前创建并激活虚拟环境，且已执行 `pip install -e .`：

```powershell
pyinstaller --noconfirm --clean --windowed `
  --name MakePracticeBook-GUI `
  gui_entry.py
```

打包完成后，生成目录：`dist/MakePracticeBook-GUI/`，其中的 `MakePracticeBook-GUI.exe` 可直接运行。

注意事项：

- OCR 功能依赖 Tesseract，请单独安装，并在 GUI 中指定其路径（或将其添加到系统 PATH）。
- AI 功能需要 API Key，可在 GUI 中填写，或通过环境变量设置（`API_KEY`/`GROQ_API_KEY`/`ZHIPUAI_API_KEY`）。
- 首次运行可能较慢，后续会更快。

---

## 旧版本说明

以下是项目的旧版本内容，用于通过 PS 切片制作做题本：

