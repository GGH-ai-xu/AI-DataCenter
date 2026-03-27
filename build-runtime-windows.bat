@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\build-windows.ps1" %*
