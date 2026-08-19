@echo off
REM FACTORtv. Start rFactor 2 first, or start this first — it waits for the game
REM either way and attaches on its own.
cd /d "%~dp0"
set PY=
where python >nul 2>nul && set PY=python
if "%PY%"=="" (where py >nul 2>nul && set PY=py)
if "%PY%"=="" (
    echo   Python is not installed or not on your PATH. Run INSTALL.bat first.
    pause
    exit /b 1
)
%PY% factor_tv.py
if errorlevel 1 pause
