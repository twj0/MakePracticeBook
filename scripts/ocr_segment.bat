@echo off
setlocal

REM OCR segment a PDF into question images
scripts\mpb.bat ocr-segment %*

exit /b %errorlevel%
