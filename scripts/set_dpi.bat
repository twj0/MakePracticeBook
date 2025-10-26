@echo off
setlocal

REM Set DPI for JPG images (directory or file)
scripts\mpb.bat set-dpi %*

exit /b %errorlevel%
