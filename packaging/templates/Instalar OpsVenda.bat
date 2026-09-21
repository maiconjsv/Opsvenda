@echo off
title Instalar OpsVenda
echo Instalando o OpsVenda...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime\install-windows.ps1"
echo.
pause
