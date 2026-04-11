@echo off
setlocal

powershell -ExecutionPolicy Bypass -File "%~dp0scripts\start-dev-worktree-merge-origin-main-20260410.ps1"
if errorlevel 1 exit /b %errorlevel%
