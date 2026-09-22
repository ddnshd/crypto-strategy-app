# Panduan Menjalankan Backend di Windows Server VPS

Dokumen ini menjelaskan langkah-langkah menjalankan backend **Crypto Strategy API** pada **Windows Server VPS**.

---

## 1. Persyaratan Sistem
* Windows Server 2019 / 2022 / 2025 (atau Windows 10/11 Pro)
* Python 3.11 atau 3.12 (64-bit) dari [python.org](https://www.python.org/downloads/)
  * **PENTING**: Saat instalasi, centang kotak **"Add python.exe to PATH"**.
* Git for Windows (opsional jika clone manual).

---

## 2. Langkah Instalasi Cepat

Buka **Command Prompt (CMD)** atau **PowerShell**:

```cmd
cd C:\path\to\crypto-strategy-app\apps\backend

:: 1. (Opsional tapi disarankan) Buat virtual environment
python -m venv venv
call venv\Scripts\activate

:: 2. Install dependensi
pip install -r requirements.txt
```

---

## 3. Konfigurasi Port di Windows Defender Firewall

Agar API dapat diakses dari Web browser atau aplikasi Android (APK), port **8001** harus diizinkan masuk (*Inbound*):

Jalankan perintah ini di **Command Prompt (Run as Administrator)**:
```cmd
netsh advfirewall firewall add rule name="CryptoStrategy_8001" dir=in action=allow protocol=TCP localport=8001
```

Atau di **PowerShell (Run as Administrator)**:
```powershell
.\server.ps1 -Action setup-firewall
```

---

## 4. Menjalankan Server

Tersedia beberapa cara mudah:

### Cara A: Klik Ganda (Interactive Console)
Cukup klik ganda file `run_server.bat`. Jendela console akan terbuka menampilkan logs Uvicorn.

### Cara B: Background Service / Script
Gunakan file `server.bat`:
```cmd
:: Menyalakan di background
server.bat start

:: Memeriksa status
server.bat status

:: Melihat log
server.bat logs

:: Menghentikan
server.bat stop
```

Atau gunakan PowerShell:
```powershell
.\server.ps1 -Action start
.\server.ps1 -Action status
.\server.ps1 -Action logs
.\server.ps1 -Action stop
```

---

## 5. Menjalankan Otomatis Saat VPS Restart (Auto-Start)

Agar backend menyala otomatis setiap kali Windows Server restart:

1. Buka **Task Scheduler** di Windows Server.
2. Buat task baru: **Create Basic Task** -> Beri nama `CryptoStrategyBackend`.
3. Trigger: **When the computer starts**.
4. Action: **Start a program**.
5. Program/script: `C:\path\to\crypto-strategy-app\apps\backend\server.bat`
6. Arguments: `start`
7. Start in: `C:\path\to\crypto-strategy-app\apps\backend`
8. Centang **"Run whether user is logged on or not"** dan centang **"Run with highest privileges"**.

---

## 6. Verifikasi Koneksi
* Akses Swagger UI di browser: `http://<IP-VPS-ANDA>:8001/docs`
* Akses Health Endpoint: `http://<IP-VPS-ANDA>:8001/health`
* Di aplikasi Web / Android APK, masuk ke menu **Settings** -> **Server Backend (VPS)**, masukkan `http://<IP-VPS-ANDA>:8001` dan klik **Simpan & Hubungkan**.

---

## 7. Log & Rotasi
* File log: `cryptostrategy-backend.log` (stdout) + `cryptostrategy-backend.err.log` (stderr, PowerShell).
* Setiap `start` otomatis: jika log >= 5MB, dirotasi ke `.1` / `.2` / `.3` (yang lama dihapus). Mode append (`>>`) sehingga riwayat tidak hilang.
* Lihat log: `server.bat logs` atau `.\server.ps1 -Action logs` (50 baris terakhir + 20 baris error).
* Jika log tetap bengkak dalam satu sesi panjang, restart berkala: `server.bat restart`.
