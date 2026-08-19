@echo off
title FACTORtv - TEST RUN (logging)
cd /d "%~dp0"

echo.
echo   ============================================================
echo     FACTORtv  -  INSTRUMENTED TEST RUN
echo   ============================================================
echo.
echo   Launch this FIRST, then start rFactor 2. It will wait and
echo   attach by itself once the game is up and a session loads.
echo.
echo   Before you drive:
echo     - rFactor 2 Settings - Video - Display Mode must be
echo       BORDERLESS or WINDOWED. Exclusive Fullscreen hides
echo       every overlay, including this one.
echo     - If rF2 was ALREADY running before the plugin was
echo       installed, restart it. rF2 loads plugins at startup only.
echo.
echo   While driving:
echo     Ctrl+Shift+O   hide / show the overlay
echo     Ctrl+Shift+C   commentary on / off
echo     Ctrl+Shift+R   team radio on / off
echo     Ctrl+Shift+D   debug panel
echo     Ctrl+Shift+Q   QUIT (do this when you're done)
echo.
echo   Everything is written to  _session_log.txt  next to this file.
echo   Closing this window is also fine - the log is flushed as it goes.
echo.
echo   ============================================================
echo.

REM -- find a usable Python. "py" is the launcher, "python" the PATH entry.
where py >nul 2>&1
if %errorlevel%==0 (
    py -3 "testrun.py"
    goto done
)
where python >nul 2>&1
if %errorlevel%==0 (
    python "testrun.py"
    goto done
)

echo   ERROR: Python was not found on this system.
echo   Install Python 3.11+ and tick "Add python.exe to PATH".

:done
echo.
echo   ------------------------------------------------------------
echo   Test run finished. The log is:
echo     %~dp0_session_log.txt
echo   ------------------------------------------------------------
echo.
pause
