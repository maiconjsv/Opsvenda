# Roda numa máquina de desenvolvimento (precisa de internet) para gerar o
# pacote distribuível dist/OpsVenda-windows-x64.zip: um bundle autocontido
# com um Python portátil (embeddable) + todas as dependências já
# instaladas, pronto para o usuário final descompactar e instalar sem
# Docker e sem privilégios de administrador.
#
# A raiz do zip só expõe "Instalar OpsVenda.bat" (o resto - python, código,
# script de instalação de verdade - fica dentro de runtime\), pra não
# confundir quem for só descompactar e instalar.

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$PyVersion = "3.12.10"  # última versão 3.12 com build "embeddable" publicado no python.org
$BuildDir = Join-Path $RepoRoot "dist\windows"
$RuntimeDir = Join-Path $BuildDir "runtime"
$PyDir = Join-Path $RuntimeDir "python"
$DistZip = Join-Path $RepoRoot "dist\OpsVenda-windows-x64.zip"

if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $PyDir | Out-Null

Write-Host "Baixando Python $PyVersion embeddable..."
$EmbedZip = Join-Path $env:TEMP "python-embed-$PyVersion.zip"
Invoke-WebRequest -Uri "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-embed-amd64.zip" -OutFile $EmbedZip
Expand-Archive -Path $EmbedZip -DestinationPath $PyDir -Force

Write-Host "Habilitando site-packages no runtime embutido..."
$PthFile = Get-ChildItem -Path $PyDir -Filter "python3*._pth" | Select-Object -First 1
(Get-Content $PthFile.FullName) -replace '^#\s*import site', 'import site' | Set-Content $PthFile.FullName

Write-Host "Instalando pip..."
$GetPip = Join-Path $env:TEMP "get-pip.py"
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $GetPip
& "$PyDir\python.exe" $GetPip --no-warn-script-location

Write-Host "Instalando dependências do app..."
& "$PyDir\python.exe" -m pip install --no-warn-script-location -r (Join-Path $RepoRoot "requirements-desktop.txt")

Write-Host "Copiando código da aplicação..."
Copy-Item (Join-Path $RepoRoot "app") -Destination $RuntimeDir -Recurse -Force
Copy-Item (Join-Path $RepoRoot "wsgi.py") -Destination $RuntimeDir -Force
Copy-Item (Join-Path $RepoRoot "run_desktop.py") -Destination $RuntimeDir -Force
Copy-Item (Join-Path $PSScriptRoot "templates\install-windows.ps1") -Destination $RuntimeDir -Force

# Opcional: bundlar o WebView2 Fixed Version Runtime para garantir
# funcionamento mesmo em imagens Windows sem o runtime já instalado.
# Baixe manualmente em https://developer.microsoft.com/microsoft-edge/webview2/
# (seção "Fixed Version") e extraia para packaging\webview2-runtime antes de
# rodar este script; se a pasta existir, ela é incluída no pacote (como
# irmã de runtime\python\, pra bater com o layout final instalado).
$WebView2Src = Join-Path $PSScriptRoot "webview2-runtime"
if (Test-Path $WebView2Src) {
    Write-Host "Incluindo WebView2 Fixed Version Runtime..."
    Copy-Item $WebView2Src -Destination (Join-Path $RuntimeDir "webview2") -Recurse -Force
}

Write-Host "Gerando o instalador visível na raiz do pacote..."
Copy-Item (Join-Path $PSScriptRoot "templates\Instalar OpsVenda.bat") -Destination $BuildDir -Force
@"
OpsVenda - Instalação (Windows)

1. Dê dois cliques em "Instalar OpsVenda.bat".
2. Uma janela preta vai aparecer, mostrar o progresso e fechar sozinha
   (ou pedir pra apertar Enter no final - é normal).
3. Um atalho "OpsVenda" aparece na Área de Trabalho. Use ele a partir de
   agora, pode apagar essa pasta descompactada depois.

Não precisa de internet nem de acesso de administrador.

Se o Windows mostrar um aviso "Windows protegeu seu PC" (SmartScreen),
clique em "Mais informações" e depois em "Executar assim mesmo" - acontece
porque o instalador não é assinado digitalmente, não é um erro.
"@ | Set-Content -Encoding UTF8 (Join-Path $BuildDir "LEIA-ME.txt")

Write-Host "Gerando $DistZip (versão portátil, sem instalador de verdade) ..."
if (Test-Path $DistZip) { Remove-Item $DistZip -Force }
Compress-Archive -Path (Join-Path $BuildDir "*") -DestinationPath $DistZip -Force

Write-Host "Gerando o instalador de verdade (Setup.exe) com Inno Setup..."
$IsccCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    $onPath = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($onPath) { $Iscc = $onPath.Source }
}

if ($Iscc) {
    & $Iscc (Join-Path $PSScriptRoot "opsvenda.iss")
} else {
    Write-Host ""
    Write-Host "Inno Setup nao encontrado - pulando a geracao do Setup.exe."
    Write-Host "Instale com: winget install --id JRSoftware.InnoSetup -e"
    Write-Host "e rode este script de novo (o .zip portatil acima ja foi gerado normalmente)."
}

Write-Host ""
Write-Host "Pronto:"
Write-Host "  $DistZip (portátil, extrai + roda o .bat)"
$SetupExe = Join-Path $RepoRoot "dist\OpsVenda-Setup.exe"
if (Test-Path $SetupExe) {
    Write-Host "  $SetupExe (instalador de verdade, recomendado para o usuário final)"
}
