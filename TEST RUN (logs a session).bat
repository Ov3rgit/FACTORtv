@echo off
REM The same overlay, instrumented. Writes _session_log.txt: every line that
REM aired, what the overlay thought the car and season were, and every swallowed
REM error with a count.
REM
REM IF YOU ARE REPORTING A BUG, USE THIS AND SEND THAT FILE. Every hard bug in
REM this project was found in it and none of them by a test suite.
cd /d "%~dp0"
set PY=
where python >nul 2>nul && set PY=python
if "%PY%"=="" (where py >nul 2>nul && set PY=py)
if "%PY%"=="" (
    echo   Python is not installed or not on your PATH. Run INSTALL.bat first.
    pause
    exit /b 1
)
%PY% testrun.py
pause
