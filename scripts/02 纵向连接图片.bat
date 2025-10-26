@echo off
setlocal EnableDelayedExpansion

REM 纵向连接图片 - 兼容性包装器
if "%~1"=="" (
    echo 用法: %~nx0 [图片文件1] [图片文件2] ...
    exit /b 1
)

REM 调用mpb命令实现纵向拼接
scripts\mpb.bat pairwise-extend %*

exit /b %errorlevel%
