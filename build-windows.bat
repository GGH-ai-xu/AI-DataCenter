@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\build-desktop-shell.ps1" %*
