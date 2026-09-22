@echo off
setlocal enabledelayedexpansion
title Crypto Strategy API Manager
cd /d "%~dp0"

set PORT=8001
set LOG_FILE=cryptostrategy-backend.log
set MAX_LOG_SIZE=5242880

if "%1"=="start" goto do_start
if "%1"=="stop" goto do_stop
if "%1"=="restart" goto do_restart
if "%1"=="status" goto do_status
if "%1"=="logs" goto do_logs

echo Penggunaan: server.bat {start^|stop^|restart^|status^|logs}
echo Atau jalankan run_server.bat untuk mode interaktif langsung.
exit /b 0

:rotate_logs
if not exist "%LOG_FILE%" exit /b 0
for %%A in ("%LOG_FILE%") do set LOG_SIZE=%%~zA
if %LOG_SIZE% GEQ %MAX_LOG_SIZE% (
    echo [INFO] Merotasi log ^(%LOG_SIZE% bytes^)...
    if exist "%LOG_FILE%.3" del "%LOG_FILE%.3"
    if exist "%LOG_FILE%.2" ren "%LOG_FILE%.2" "%LOG_FILE%.3"
    if exist "%LOG_FILE%.1" ren "%LOG_FILE%.1" "%LOG_FILE%.2"
    ren "%LOG_FILE%" "%LOG_FILE%.1"
)
exit /b 0

:do_start
echo [INFO] Menyalakan Crypto Strategy API di background port %PORT%...
call :rotate_logs
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)
set PYTHONUNBUFFERED=1
>>"%LOG_FILE%" echo ===== %DATE% %TIME% starting on port %PORT% =====
start "" /B python -m uvicorn app.main:app --host 0.0.0.0 --port %PORT% >> "%LOG_FILE%" 2>&1
ping -n 4 127.0.0.1 >nul
goto do_status

:do_stop
echo [INFO] Menghentikan proses Uvicorn pada port %PORT%...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo [INFO] Berhasil menghentikan PID %%a
)
echo [INFO] Selesai.
exit /b 0

:do_restart
call :do_stop
ping -n 3 127.0.0.1 >nul
goto do_start

:do_status
echo [INFO] Memeriksa status server di port %PORT%...
netstat -aon | findstr ":%PORT%" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [STATUS] Backend TIDAK AKTIF pada port %PORT%.
) else (
    echo [STATUS] Backend AKTIF pada port %PORT%.
    curl -s http://localhost:%PORT%/health 2>nul
    echo.
)
exit /b 0

:do_logs
if exist "%LOG_FILE%" (
    powershell -NoProfile -Command "Get-Content '%LOG_FILE%' -Tail 100"
) else (
    echo [INFO] File log %LOG_FILE% belum ada.
)
exit /b 0
