@echo off
chcp 65001 >nul
title OSD Provisioning Tool
cd /d "%~dp0"

set "PY="

py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PY=py -3"

if not defined PY (
  python -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)

if not defined PY (
  echo.
  echo   Python 3 not found.
  echo   Install Python 3 from python.org and tick "Add Python to PATH".
  echo.
  pause
  exit /b 1
)

%PY% "%~dp0hik_osd_setup.py" --menu
echo.
pause
