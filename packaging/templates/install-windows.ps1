# Instalador OpsVenda (Windows, sem admin). Roda a partir da pasta
# descompactada do pacote (dist/OpsVenda-windows-x64.zip): copia tudo para
# %LOCALAPPDATA%\OpsVenda e cria um atalho na Área de Trabalho. Não requer
# Docker, não requer privilégios de administrador.

$ErrorActionPreference = "Stop"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Join-Path $env:LOCALAPPDATA "OpsVenda"

Write-Host "Instalando o OpsVenda em $InstallDir ..."
# Mensagens abaixo sem acento de propósito: o console do Windows costuma
# usar um codepage (OEM) diferente do UTF-8 do arquivo, e acentos saem
# corrompidos quando chamado via cmd /c (o instalador .bat).
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Path (Join-Path $SourceDir "*") -Destination $InstallDir -Recurse -Force -Exclude "install-windows.ps1"

$WshShell = New-Object -ComObject WScript.Shell
# [Environment]::GetFolderPath resolves the REAL Desktop folder from the
# registry - "$Home\Desktop" silently breaks when OneDrive's "Known Folder
# Move" redirects Desktop elsewhere (common on corporate machines).
$DesktopDir = [Environment]::GetFolderPath("Desktop")
$Shortcut = $WshShell.CreateShortcut((Join-Path $DesktopDir "OpsVenda.lnk"))
$Shortcut.TargetPath = Join-Path $InstallDir "python\pythonw.exe"
$Shortcut.Arguments = "`"$InstallDir\run_desktop.py`""
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Save()

Write-Host ""
Write-Host "Instalacao concluida. Use o atalho 'OpsVenda' na Area de Trabalho."
