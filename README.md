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

# MakePracticeBook - 考研做题本生成器

这个项目可以帮助你将扫描版试卷切片，加上统一的背景，然后合并为一个完整的PDF文件，方便在平板上做题。

## 项目功能

- 将试卷切片加上统一背景
- 将处理后的切片合并为PDF
- 支持A4和A5纸张尺寸
- 可以设置DPI和背景偏移量
- 支持一键处理完整流程

## 环境要求

- Python 3.13+
- ImageMagick
- Tesseract OCR (可选，用于Phase 2功能)
- Microsoft Word 或 LibreOffice (用于doc/docx转换)

## 安装和使用

### 使用uv管理项目（推荐）

本项目支持使用[uv](https://docs.astral.sh/uv/)工具来管理Python环境和依赖。uv是一个极快的Python包和项目管理器，可以替代传统的pip和venv。

1. 安装uv:
   ```bash
   # Windows (使用pip)
   pip install uv
   
   # macOS/Linux (使用pip)
   pip install uv
   
   # 或者参考uv官方文档的其他安装方式
   ```

2. 克隆项目并设置环境:
   ```bash
   # 克隆项目
   git clone <repository-url>
   cd MakePracticeBook
   
   # 创建虚拟环境并安装依赖
   uv venv
   
   # 使用清华镜像源安装依赖（可选）
   uv pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
   
   # 或使用默认源安装依赖
   uv pip install -e .
   ```

3. 运行命令:
   ```bash
   # 查看帮助
   uv run mpb --help
   
   # 生成背景图
   uv run mpb generate-background --size A4 --dpi 300 --output background.png
   
   # 处理切片并生成做题本
   uv run mpb process "your_slices_directory" --size A4 --dpi 300 --output-pdf "做题本.pdf"
   
   # 使用Phase 2功能（文档转换、OCR分割等）
   uv run mpb convert-document "input.docx" --output-pdf "output.pdf"
   uv run mpb ocr-segment "input.pdf" --out-dir "segments"
   uv run mpb auto-process "input.docx" --size A4 --dpi 300 --output-pdf "做题本.pdf"
   ```

### 传统方式安装

1. 克隆项目:
   ```bash
   git clone <repository-url>
   cd MakePracticeBook
   ```

2. 创建虚拟环境并激活:
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. 安装依赖:
   ```bash
   pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple  # 使用清华源（可选）
   pip install -e .
   ```

4. 运行命令:
   ```bash
   mpb --help
   ```

## 构建可执行文件

使用PyInstaller构建可执行文件:

```bash
# 使用uv运行构建脚本
uv run scripts/build_exe.bat

# 或直接运行构建脚本
scripts/build_exe.bat
```

构建后的可执行文件位于 `dist/make-practice-book/` 目录中。

## 使用可执行文件

构建完成后，你可以将PDF切片文件夹拖拽到 `make-practice-book.exe` 上，程序会自动生成名为 `做题本.pdf` 的文件。

## ChatGPT 对话大致记录

这个项目所用到的脚本，都是在 ChatGPT 的帮助下，写出来的。这是一些对话的记录：
