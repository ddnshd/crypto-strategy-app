param (
    [ValidateSet("start", "stop", "restart", "status", "logs", "setup-firewall")]
    [string]$Action = "status",
    [int]$Port = 8001
)

$BackendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BackendDir
$LogFile = Join-Path $BackendDir "cryptostrategy-backend.log"
$ErrFile = Join-Path $BackendDir "cryptostrategy-backend.err.log"
$MaxLogSize = 5MB

function Rotate-Log {
    param ([string]$Path)
    if (Test-Path $Path) {
        $size = (Get-Item $Path).Length
        if ($size -ge $MaxLogSize) {
            Write-Host "[INFO] Merotasi log $Path ($size bytes)..." -ForegroundColor Yellow
            $old3 = "$Path.3"; $old2 = "$Path.2"; $old1 = "$Path.1"
            if (Test-Path $old3) { Remove-Item $old3 -Force }
            if (Test-Path $old2) { Move-Item $old2 $old3 -Force }
            if (Test-Path $old1) { Move-Item $old1 $old2 -Force }
            Move-Item $Path $old1 -Force
        }
    }
}

function Test-PortOpen {
    param ([int]$p)
    $connections = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    return ($connections -ne $null)
}

function Get-PortPID {
    param ([int]$p)
    $connections = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        return $connections[0].OwningProcess
    }
    return $null
}

switch ($Action) {
    "start" {
        if (Test-PortOpen -p $Port) {
            $pidRunning = Get-PortPID -p $Port
            Write-Host "[INFO] Backend sudah berjalan di port $Port (PID: $pidRunning)" -ForegroundColor Yellow
            return
        }
        Write-Host "[INFO] Menjalankan Crypto Strategy API di port $Port..." -ForegroundColor Green

        # Start-Process menimpa file target, jadi rotasi dulu agar tidak bengkak
        Rotate-Log -Path $LogFile
        Rotate-Log -Path $ErrFile

        $venvActivate = Join-Path $BackendDir "venv\Scripts\Activate.ps1"
        if (Test-Path $venvActivate) {
            & $venvActivate
        }

        # stdout -> .log, stderr -> .err.log (file terpisah agar tidak saling menimpa)
        "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') starting on port $Port =====" | Out-File $LogFile -Encoding utf8
        $proc = Start-Process -FilePath "python" -ArgumentList "-m uvicorn app.main:app --host 0.0.0.0 --port $Port" -RedirectStandardOutput $LogFile -RedirectStandardError $ErrFile -PassThru -WindowStyle Hidden
        Start-Sleep -Seconds 3

        if (Test-PortOpen -p $Port) {
            Write-Host "[SUCCESS] Backend aktif! (PID: $($proc.Id))" -ForegroundColor Green
            Write-Host "URL: http://localhost:$Port" -ForegroundColor Cyan
            Write-Host "Docs: http://localhost:$Port/docs" -ForegroundColor Cyan
        } else {
            Write-Host "[ERROR] Backend gagal menyala. Cek log: $LogFile" -ForegroundColor Red
            if (Test-Path $LogFile) { Get-Content $LogFile -Tail 15 }
        }
    }

    "stop" {
        $pidRunning = Get-PortPID -p $Port
        if ($pidRunning) {
            Write-Host "[INFO] Menghentikan proses PID $pidRunning di port $Port..." -ForegroundColor Yellow
            Stop-Process -Id $pidRunning -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
            Write-Host "[SUCCESS] Backend dihentikan." -ForegroundColor Green
        } else {
            Write-Host "[INFO] Backend tidak sedang berjalan di port $Port." -ForegroundColor Yellow
        }
    }

    "restart" {
        & $PSCommandPath -Action stop -Port $Port
        Start-Sleep -Seconds 2
        & $PSCommandPath -Action start -Port $Port
    }

    "status" {
        if (Test-PortOpen -p $Port) {
            $pidRunning = Get-PortPID -p $Port
            Write-Host "[STATUS] Backend AKTIF di port $Port (PID: $pidRunning)" -ForegroundColor Green
            try {
                $res = Invoke-RestMethod -Uri "http://localhost:$Port/health" -TimeoutSec 3 -ErrorAction Stop
                Write-Host "Health Check: OK ($($res | ConvertTo-Json -Compress))" -ForegroundColor Cyan
            } catch {
                Write-Host "Health Check: Belum merespon ($($_.Exception.Message))" -ForegroundColor Yellow
            }
        } else {
            Write-Host "[STATUS] Backend TIDAK AKTIF di port $Port." -ForegroundColor Red
        }
    }

    "logs" {
        if (Test-Path $LogFile) {
            Get-Content $LogFile -Tail 50
        } else {
            Write-Host "[INFO] File log belum ditemukan: $LogFile" -ForegroundColor Yellow
        }
        if (Test-Path $ErrFile) {
            Write-Host "--- stderr ($ErrFile) ---" -ForegroundColor Yellow
            Get-Content $ErrFile -Tail 20
        }
    }

    "setup-firewall" {
        Write-Host "[INFO] Membuka port inbound $Port TCP di Windows Defender Firewall..." -ForegroundColor Cyan
        try {
            New-NetFirewallRule -DisplayName "Crypto Strategy API ($Port)" -Direction Inbound -LocalPort $Port -Protocol TCP -Action Allow -ErrorAction Stop | Out-Null
            Write-Host "[SUCCESS] Rule Firewall berhasil ditambahkan untuk port $Port!" -ForegroundColor Green
        } catch {
            Write-Host "[WARNING] Gagal otomatis. Jalankan PowerShell sebagai Administrator, atau ketik:" -ForegroundColor Yellow
            Write-Host "netsh advfirewall firewall add rule name=`"CryptoStrategy_$Port`" dir=in action=allow protocol=TCP localport=$Port" -ForegroundColor White
        }
    }
}
