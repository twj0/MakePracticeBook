@echo off
setlocal

REM Generate a blank background (A4/A5)
scripts\mpb.bat generate-background %*

exit /b %errorlevel%
