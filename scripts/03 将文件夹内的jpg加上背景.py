#!/usr/bin/env python3
import os
import sys

# 将文件夹内的JPG加上背景 - 兼容性包装器
if len(sys.argv) < 2:
    print("用法: python {} <文件夹路径>".format(sys.argv[0]))
    sys.exit(1)

input_folder = sys.argv[1]
if not os.path.isdir(input_folder):
    print(f"{input_folder} 不是一个有效的文件夹路径")
    sys.exit(1)

# 调用mpb命令实现背景添加
os.system(f'scripts\mpb.bat add-background "{input_folder}" --background "背景.png" --offset-x 0 --offset-y 100 --gravity north --in-place')

input("按下回车键退出...")
