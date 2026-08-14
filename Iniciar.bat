@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo === People Data ^& Automation ===
echo 1) Produccion (LAN/VPN - un solo puerto, otros usuarios pueden conectarse)
echo 2) Desarrollo (solo esta notebook, hot reload)
echo 3) Salir
echo.
set /p opcion="Elegi una opcion: "

if "%opcion%"=="1" goto produccion
if "%opcion%"=="2" goto desarrollo
goto fin

:produccion
echo.
echo Compilando frontend (vite build)...
cd frontend
call node ".\node_modules\vite\bin\vite.js" build
if errorlevel 1 (
    echo.
    echo ERROR: fallo la compilacion del frontend. Revisa el mensaje de arriba.
    cd ..
    goto pausa
)
cd ..

set "IP="
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "(Get-NetIPConfiguration).Where({ $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq 'Up' })[0].IPv4Address.IPAddress"`) do set "IP=%%a"

echo.
echo === Accesos ===
echo   Esta notebook : http://localhost:8000
if defined IP (
    echo   Red LAN/VPN   : http://%IP%:8000
) else (
    echo   Red LAN/VPN   : no se pudo detectar la IP automaticamente, revisa ipconfig
)
echo   Nombre corto  : http://pda:8000, solo en PCs con la entrada en el archivo hosts
echo.
echo Levantando backend en 0.0.0.0:8000 (Ctrl+C para detener)...
echo.

call venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir backend
goto pausa

:desarrollo
echo.
echo Abriendo backend y frontend en ventanas separadas...
start "PDA - Backend" /D "%~dp0" cmd /k venv\Scripts\python.exe -m uvicorn backend.main:app --reload --reload-dir backend
start "PDA - Frontend" /D "%~dp0frontend" cmd /k node .\node_modules\vite\bin\vite.js

echo.
echo Esperando a que el backend responda (puede tardar unos segundos)...
set /a intentos=0
:esperar_backend
curl -s -o nul -w "%%{http_code}" http://localhost:8000/docs > "%TEMP%\pda_health.txt" 2>nul
set /p HTTPCODE=<"%TEMP%\pda_health.txt"
if "%HTTPCODE%"=="200" goto backend_listo
set /a intentos+=1
if %intentos% GEQ 30 goto backend_timeout
"%SystemRoot%\System32\timeout.exe" /t 1 /nobreak >nul
goto esperar_backend

:backend_listo
echo Backend listo.
goto mostrar_accesos

:backend_timeout
echo.
echo ADVERTENCIA: el backend no respondio en 30 segundos.
echo Revisa la ventana "PDA - Backend" - probablemente muestre el error ahi.
goto mostrar_accesos

:mostrar_accesos
echo.
echo === Accesos ===
echo   Frontend (dev) : http://localhost:5173
echo   Backend (API)  : http://localhost:8000
echo.
echo Se abrieron 2 ventanas nuevas - no las cierres mientras uses el sistema.
echo Esta ventana ya puede cerrarse.
goto pausa

:pausa
echo.
pause
goto fin

:fin
endlocal
