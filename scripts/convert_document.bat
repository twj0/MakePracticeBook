@echo off
setlocal

REM Convert DOC/DOCX/PDF to PDF
scripts\mpb.bat convert-document %*

exit /b %errorlevel%
