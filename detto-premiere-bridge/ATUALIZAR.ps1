# ATUALIZAR.ps1 — baixa o codigo novo e reinicia o painel.
# Rode no PowerShell:   cd C:\Users\guebe\Teste1 ; .\detto-premiere-bridge\ATUALIZAR.ps1
$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot          # a pasta Teste1
$ponte = Join-Path $raiz "detto-premiere-bridge"
Write-Host ""
Write-Host "=== 1/4  fechando o painel ===" -ForegroundColor Cyan
Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*painel*" } |
  ForEach-Object {
    Write-Host ("   fechando PID " + $_.ProcessId)
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "=== 2/4  baixando o codigo novo ===" -ForegroundColor Cyan
Set-Location $raiz
git pull
if ($LASTEXITCODE -ne 0) {
  # a pasta detto-historias-panel solta no PC trava o pull; tira da frente e tenta de novo
  if (Test-Path "detto-historias-panel") {
    $bk = "detto-historias-panel-BACKUP"
    if (Test-Path $bk) { $bk = "detto-historias-panel-BACKUP-" + (Get-Date -Format "yyyyMMdd-HHmmss") }
    Write-Host ("   tirando a pasta detto-historias-panel da frente (vira " + $bk + ")") -ForegroundColor Yellow
    Rename-Item "detto-historias-panel" $bk
    git pull
  }
}
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Host "O git pull NAO funcionou. Copie o erro acima e me mande." -ForegroundColor Red
  Read-Host "Enter para fechar"
  exit 1
}

Write-Host ""
Write-Host "=== 3/4  conferindo ===" -ForegroundColor Cyan
Set-Location $ponte
$versao = (Select-String -Path "tools\painel\painel.py" -Pattern 'PAINEL_VERSAO = "(.+)"' |
           Select-Object -First 1).Matches.Groups[1].Value
Write-Host ("   versao do painel no disco: " + $versao)
if (Select-String -Path "tools\postar\postar.py" -Pattern "link conferido" -Quiet) {
  Write-Host "   correcao do Instagram: OK" -ForegroundColor Green
} else {
  Write-Host "   correcao do Instagram: NAO ESTA NO DISCO" -ForegroundColor Red
}
if (Test-Path "tools\historias\historias.py") {
  Write-Host "   historias: OK" -ForegroundColor Green
} else {
  Write-Host "   historias: FALTANDO" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== 4/4  abrindo o painel ===" -ForegroundColor Cyan
Start-Process -FilePath "python" -ArgumentList "tools\painel\painel.py" -WorkingDirectory $ponte
Start-Sleep -Seconds 6
Start-Process "http://localhost:8730"
Write-Host ""
Write-Host "Pronto. No painel, a versao tem que bater com a de cima." -ForegroundColor Green
Write-Host "Se aparecer o aviso VERMELHO de codigo antigo, feche a janela do painel e rode este script de novo."
Write-Host ""
