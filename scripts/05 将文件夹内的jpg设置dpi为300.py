#!/usr/bin/env python3
import os
import sys

# 将文件夹内的JPG设置DPI为300 - 兼容性包装器
if len(sys.argv) < 2:
    print("用法: python {} <文件夹路径>".format(sys.argv[0]))
    sys.exit(1)

input_folder = sys.argv[1]
if not os.path.isdir(input_folder):
    print(f"{input_folder} 不是一个有效的文件夹路径")
    sys.exit(1)

# 调用mpb命令设置DPI
os.system(f'scripts\mpb.bat set-dpi "{input_folder}" --dpi 300')

input("按下回车键退出...")
