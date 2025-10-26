#!/usr/bin/env python3
import os
import sys

# 将文件夹内的JPG两两拼接 - 兼容性包装器
if len(sys.argv) < 2:
    print("用法: python {} <文件夹路径>".format(sys.argv[0]))
    sys.exit(1)

dir_path = sys.argv[1]
if not os.path.isdir(dir_path):
    print(f"{dir_path} 不是一个有效的文件夹路径")
    sys.exit(1)

# 调用mpb命令实现两两拼接
os.system(f'scripts\mpb.bat pairwise-concat "{dir_path}" --extend-last')

input("按下回车键退出...")
