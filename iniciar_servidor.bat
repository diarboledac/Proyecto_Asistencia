@echo off
title Servidor de Asistencia SENA
echo ======================================================================
echo           INICIANDO SERVIDOR DE CONTROL DE ASISTENCIA SENA
echo ======================================================================
echo.
echo Presiona Ctrl+C en cualquier momento para detener el servidor.
echo.
cd /d "%~dp0"
python app.py %*
pause
