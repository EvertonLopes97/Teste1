# VOLTAR.ps1 — volta o codigo para a ultima versao que PASSOU no teste (ou para a de ontem).
# Rode no PowerShell:   cd C:\Users\guebe\Teste1 ; .\detto-premiere-bridge\VOLTAR.ps1
#
# Use quando o sistema parar depois de uma atualizacao: isto devolve o PC ao estado que funcionava, sem
# esperar correcao. Seus videos, pastas e configuracoes (E:\DETTO) NAO sao tocados — so o codigo.
# Para andar para frente de novo:  .\detto-premiere-bridge\ATUALIZAR.ps1
param([string]$Versao = "")
$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot
$ponte = Join-Path $raiz "detto-premiere-bridge"
$marca = Join-Path $ponte ".ultima_boa"

Write-Host ""
Write-Host "=== fechando o painel ===" -ForegroundColor Cyan
Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*painel*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

Set-Location $raiz
if (-not $Versao) {
  if (Test-Path $marca) {
    $Versao = (Get-Content $marca -Raw).Trim()
    Write-Host ("ultima versao boa guardada: " + $Versao.Substring(0,8)) -ForegroundColor Cyan
  } else {
    $Versao = (git rev-parse "HEAD~1") 2>$null
    Write-Host "nao tinha versao boa guardada: volto uma atras" -ForegroundColor Yellow
  }
}
if (-not $Versao) {
  Write-Host "nao consegui descobrir para onde voltar. Me mande o que aparece em:  git log --oneline -5" -ForegroundColor Red
  Read-Host "Enter para fechar"
  exit 1
}

Write-Host ""
Write-Host "=== as 5 ultimas versoes (para voce saber onde esta) ===" -ForegroundColor Cyan
git log --oneline -5

Write-Host ""
git -c advice.detachedHead=false checkout $Versao
if ($LASTEXITCODE -ne 0) {
  Write-Host "nao deu para voltar (git). Me mande o erro acima." -ForegroundColor Red
  Read-Host "Enter para fechar"
  exit 1
}

Set-Location $ponte
python tools\teste_rapido.py
Write-Host ""
Write-Host "=== abrindo o painel ===" -ForegroundColor Cyan
Start-Process -FilePath "python" -ArgumentList "tools\painel\painel.py" -WorkingDirectory $ponte
Start-Sleep -Seconds 6
Start-Process "http://localhost:8730"
Write-Host ""
Write-Host "Voltei o codigo. Quando a correcao estiver pronta, rode o ATUALIZAR.ps1." -ForegroundColor Green
Write-Host ""
