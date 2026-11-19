@echo off
:: Comprobar si se ejecuta como administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [AVISO] Debes ejecutar este archivo como Administrador.
    echo Haz clic derecho sobre este archivo y selecciona "Ejecutar como administrador".
    pause
    exit /b 1
)

echo Abriendo el puerto 5000 en el Firewall de Windows para el celular...
netsh advfirewall firewall add rule name="Asistencia_SENA_5000" dir=in action=allow protocol=TCP localport=5000 profile=any

echo.
echo ======================================================================
echo  PUERTO 5000 DESBLOQUEADO CORRECTAMENTE EN EL FIREWALL DE WINDOWS
echo  Direccion para tu celular: http://192.168.20.21:5000
echo ======================================================================
echo.
pause
