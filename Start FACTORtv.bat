@echo off
title FACTORtv
cd /d "%~dp0"

echo.
echo   FACTORtv  -  rFactor 2 broadcast overlay
echo   ---------------------------------------
echo   Waiting for rFactor 2. Start the game whenever you like.
echo.
echo   Ctrl+Shift+O  hide/show     Ctrl+Shift+C  commentary
echo   Ctrl+Shift+R  team radio    Ctrl+Shift+V  relative panel
echo   Ctrl+Shift+E  tower         Ctrl+Shift+T  dash
echo   Ctrl+Shift+M  gap mode      Ctrl+Shift+D  debug
echo   Ctrl+Shift+Q  quit
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    start "" /b pyw -3 "factor_tv.py"
    goto done
)
where pythonw >nul 2>&1
if %errorlevel%==0 (
    start "" /b pythonw "factor_tv.py"
    goto done
)
where python >nul 2>&1
if %errorlevel%==0 (
    python "factor_tv.py"
    goto done
)
echo   ERROR: Python was not found. Install Python 3.11+ with
echo   "Add python.exe to PATH" ticked.
pause

:done
