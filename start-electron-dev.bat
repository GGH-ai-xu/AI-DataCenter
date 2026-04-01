@echo off
setlocal

powershell -ExecutionPolicy Bypass -File "%~dp0scripts\start-electron-dev.ps1"
if errorlevel 1 exit /b %errorlevel%
