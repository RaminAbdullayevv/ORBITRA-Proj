@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-orbitra.ps1"
if errorlevel 1 (
  echo ORBITRA baslatma xetasi. Yuxaridaki mesaji yoxlayin.
  pause
)
