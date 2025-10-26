@echo off
setlocal

REM Composite images onto a background
scripts\mpb.bat add-background %*

exit /b %errorlevel%
