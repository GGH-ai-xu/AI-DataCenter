@echo off
setlocal

powershell -ExecutionPolicy Bypass -File "%~dp0scripts\setup-uv-env.ps1"
if errorlevel 1 exit /b %errorlevel%

powershell -ExecutionPolicy Bypass -File "%~dp0scripts\setup-frontend.ps1"
if errorlevel 1 exit /b %errorlevel%

powershell -ExecutionPolicy Bypass -File "%~dp0scripts\setup-desktop-shell.ps1"
if errorlevel 1 exit /b %errorlevel%

echo Dependency installation complete.
