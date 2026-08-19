@echo off
REM FACTORtv setup. Copies the artwork where the overlay looks for it, finds
REM rFactor 2, and says whether the shared-memory plugin is in place.
REM
REM Drag the plugin DLL onto this file to install it at the same time.
cd /d "%~dp0"
if "%~1"=="" (
    python install.py
) else (
    python install.py --plugin "%~1"
)
echo.
pause
