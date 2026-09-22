@echo off
setlocal enabledelayedexpansion
title Crypto Strategy API Manager
cd /d "%~dp0"

set PORT=8001
set LOG_FILE=cryptostrategy-backend.log

if "%1"=="start" goto do_start
if "%1"=="stop" goto do_stop
if "%1"=="restart" goto do_restart
if "%1"=="status" goto do_status
if "%1"=="logs" goto do_logs

echo Penggunaan: server.bat {start^|stop^|restart^|status^|logs}
echo Atau jalankan run_server.bat untuk mode interaktif langsung.
exit /b 0

:do_start
echo [INFO] Menyalakan Crypto Strategy API di background port %PORT%...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)
start /B python -m uvicorn app.main:app --host 0.0.0.0 --port %PORT% > "%LOG_FILE%" 2>&1
timeout /t 3 /nobreak >nul
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
timeout /t 2 /nobreak >nul
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
    type "%LOG_FILE%"
) else (
    echo [INFO] File log %LOG_FILE% belum ada.
)
exit /b 0
