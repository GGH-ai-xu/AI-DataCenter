@echo off
setlocal

powershell -ExecutionPolicy Bypass -File "%~dp0scripts\start-dev.ps1"
if errorlevel 1 exit /b %errorlevel%
