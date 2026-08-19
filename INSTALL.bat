@echo off
REM FACTORtv setup. Installs the shared-memory plugin, switches it on in rF2's
REM own config, copies the artwork into your Pictures folder, and installs the
REM three Python packages. One run is the whole job.
REM
REM Drag a different plugin DLL onto this file to install that one instead.
cd /d "%~dp0"

REM PYTHON IS THE ONE THING THIS CANNOT INSTALL FOR YOU, and "python is not
REM recognized as an internal or external command" is not an error message
REM anybody should have to interpret. Both spellings are checked: the `py`
REM launcher ships with the python.org installer and `python` needs the PATH box
REM to have been ticked, and plenty of people miss it.
set PY=
where python >nul 2>nul && set PY=python
if "%PY%"=="" (where py >nul 2>nul && set PY=py)
if "%PY%"=="" (
    echo.
    echo   PYTHON IS NOT INSTALLED, or it was installed without being added to
    echo   your PATH. That is the only thing this installer cannot do for you.
    echo.
    echo     1. Get Python 3.9 or newer:  https://www.python.org/downloads/
    echo     2. TICK "Add python.exe to PATH" on the first screen of the
    echo        installer. It is off by default and it is the box everybody
    echo        misses.
    echo     3. Close this window, open a new one, and run INSTALL.bat again.
    echo.
    pause
    exit /b 1
)

if "%~1"=="" (
    %PY% install.py
) else (
    %PY% install.py --plugin "%~1"
)
echo.
pause
