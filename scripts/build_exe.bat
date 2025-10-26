@echo off
setlocal

REM Build portable one-folder EXE with PyInstaller
REM Prereqs: pip install pyinstaller

set ENTRY=make_practice_book\__main__.py
set NAME=make-practice-book
set DISTDIR=dist\%NAME%

py -3.13 -m PyInstaller ^
  --name %NAME% ^
  --onedir ^
  --console ^
  --collect-all make_practice_book ^
  --hidden-import fitz ^
  %ENTRY%

IF %ERRORLEVEL% NEQ 0 (
  echo Build failed.
  exit /b %ERRORLEVEL%
)

REM Bundle magick.exe next to the EXE if present in repo root
if exist magick.exe (
  copy /Y magick.exe "%DISTDIR%\magick.exe" >nul 2>&1
)

echo Build completed. Drag-and-drop a folder of JPG slices onto %DISTDIR%\%NAME%.exe
exit /b 0
