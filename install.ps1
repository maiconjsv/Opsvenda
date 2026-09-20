# Instalador Windows: sobe o backend via Docker Desktop e cria um atalho
# na Area de Trabalho para o launcher desktop (pywebview).

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker nao encontrado. Instale o Docker Desktop antes de continuar: https://docs.docker.com/desktop/install/windows-install/"
    exit 1
}

if (-not (Test-Path ".env")) {
    Write-Host "Criando .env a partir de .env.example..."
    Copy-Item ".env.example" ".env"

    $secret = -join ((48..57) + (97..102) | Get-Random -Count 48 | ForEach-Object {[char]$_})
    (Get-Content ".env") -replace '^SECRET_KEY=.*', "SECRET_KEY=$secret" | Set-Content ".env"

    $securePassword = Read-Host "Defina a senha do usuario administrador (usuario: admin)" -AsSecureString
    $adminPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    )
    (Get-Content ".env") -replace '^ADMIN_PASSWORD=.*', "ADMIN_PASSWORD=$adminPassword" | Set-Content ".env"
}

Write-Host "Subindo o backend com Docker Compose..."
docker compose up -d --build

Write-Host "Aguardando o backend responder..."
$port = (Get-Content ".env" | Select-String '^APP_PORT=(.*)').Matches.Groups[1].Value
if (-not $port) { $port = "5000" }
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:$port/health" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { break }
    } catch { Start-Sleep -Seconds 2 }
}

Write-Host "Preparando o launcher desktop..."
if (-not (Test-Path ".venv-desktop")) {
    python -m venv .venv-desktop
}
& ".\.venv-desktop\Scripts\pip.exe" install --quiet --upgrade pip
& ".\.venv-desktop\Scripts\pip.exe" install --quiet -r requirements-desktop.txt

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$Home\Desktop\OpsVenda.lnk")
$Shortcut.TargetPath = "$ScriptDir\.venv-desktop\Scripts\pythonw.exe"
$Shortcut.Arguments = "`"$ScriptDir\run_desktop.py`""
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.Save()

Write-Host ""
Write-Host "Instalacao concluida. Use o atalho 'OpsVenda' na Area de Trabalho."
