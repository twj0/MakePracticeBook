@echo off
setlocal

REM Convert JPGs in a directory to a single PDF
scripts\mpb.bat jpgs-to-pdf %*

exit /b %errorlevel%
