@echo off
setlocal EnableDelayedExpansion

REM 将文件夹内的JPG合并为PDF - 兼容性包装器
if "%~1"=="" (
    echo 用法: %~nx0 [文件夹路径]
    exit /b 1
)

set input_dir=%~dpn1
set output_file=%~n1.pdf

REM 调用mpb命令实现JPG转PDF
scripts\mpb.bat jpgs-to-pdf "%input_dir%" --output-pdf "%output_file%" --quality 80

exit /b %errorlevel%
