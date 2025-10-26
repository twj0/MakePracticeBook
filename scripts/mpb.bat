@echo off
setlocal

REM Development shim to run the CLI easily and support drag-and-drop
set PY=py -3.13
%PY% -m make_practice_book %*

exit /b %errorlevel%
