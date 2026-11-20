@echo off
chcp 65001 >nul
cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
  echo.
  echo   Git not found. Install Git for Windows first:
  echo   https://git-scm.com/download/win
  echo.
  pause
  exit /b 1
)

echo ==================================================
echo   Push this folder to GitHub
echo ==================================================
echo.

if not exist ".git" (
  git init
  git config core.quotepath false
)

for /f "delims=" %%i in ('git config --local user.email') do set HAVE_EMAIL=1
if not defined HAVE_EMAIL (
  set /p GNAME=Your git user name:
  set /p GMAIL=Your git email:
  git config user.name "%GNAME%"
  git config user.email "%GMAIL%"
)

git add -A
git commit -m "Hikvision OSD provisioning tool" 
if errorlevel 1 echo   (nothing new to commit)

set /p URL=GitHub repo URL (https://github.com/USER/REPO.git):
if "%URL%"=="" goto done

git remote remove origin 2>nul
git remote add origin %URL%
git branch -M main
git push -u origin main

:done
echo.
echo Done. Check your GitHub page.
pause
