@echo off
setlocal

REM Pairwise vertical concat of images
scripts\mpb.bat pairwise-concat %*

exit /b %errorlevel%
