@echo off
title Crypto Strategy API - Windows Server
cd /d "%~dp0"

echo ============================================================
echo   Crypto Strategy API - Windows Server Runner
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan di PATH sistem!
    echo Silakan install Python 3.11 atau 3.12 dari python.org
    echo Pastikan centang "Add python.exe to PATH" saat instalasi.
    pause
    exit /b 1
)

REM Activate virtualenv if present
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Mengaktifkan virtual environment venv...
    call venv\Scripts\activate.bat
) else if exist "..\venv\Scripts\activate.bat" (
    echo [INFO] Mengaktifkan virtual environment ..\venv...
    call ..\venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Mengaktifkan virtual environment .venv...
    call .venv\Scripts\activate.bat
)

set PORT=8001
echo [INFO] Menjalankan Uvicorn di port %PORT% (0.0.0.0)...
echo [INFO] Swagger Docs : http://localhost:%PORT%/docs
echo [INFO] Health Check : http://localhost:%PORT%/health
echo.
echo [TIPS] Pastikan port %PORT% dibuka pada Windows Firewall VPS:
echo netsh advfirewall firewall add rule name="CryptoStrategy_8001" dir=in action=allow protocol=TCP localport=8001
echo.
echo Tekan Ctrl+C untuk menghentikan server.
echo ============================================================
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port %PORT%

if errorlevel 1 (
    echo.
    echo [ERROR] Server berhenti dengan error.
    pause
)
