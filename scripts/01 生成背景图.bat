@echo off
setlocal

REM 生成背景图 - 兼容性包装器
scripts\mpb.bat generate-background --size A5 --dpi 300 --output "背景.png" %*

exit /b %errorlevel%
