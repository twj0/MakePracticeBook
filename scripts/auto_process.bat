@echo off
setlocal

REM End-to-end process: convert -> OCR segment -> compose practice book
scripts\mpb.bat auto-process %*

exit /b %errorlevel%
