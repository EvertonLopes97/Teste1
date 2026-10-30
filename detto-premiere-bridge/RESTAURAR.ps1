# RESTAURAR.ps1 — devolve as configurações e os logins de um backup, e (se quiser) o código daquele dia.
# Rode no PowerShell:   cd C:\Users\guebe\Teste1 ; .\detto-premiere-bridge\RESTAURAR.ps1
#
# Sem argumento ele LISTA os backups e pergunta qual. Com -Backup <pasta> vai direto.
# -ComCodigo também volta o código para a versão daquele backup.
# Antes de sobrescrever qualquer coisa, ele faz um backup do estado de agora (nunca perde o atual).
param([string]$Backup = "", [switch]$ComCodigo)
$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot
$ponte = Join-Path $raiz "detto-premiere-bridge"
$detto = if (Test-Path "E:\DETTO") { "E:\DETTO" } else { Join-Path $HOME "DETTO" }
$pasta = Join-Path $detto "backups"

if (-not (Test-Path $pasta)) {
  Write-Host "Nao existe backup ainda. Rode primeiro:  .\detto-premiere-bridge\BACKUP.ps1" -ForegroundColor Yellow
  Read-Host "Enter para fechar"; exit 1
}
$lista = Get-ChildItem $pasta -Directory | Sort-Object Name -Descending
if (-not $Backup) {
  Write-Host ""
  Write-Host "=== backups que voce tem ===" -ForegroundColor Cyan
  for ($i = 0; $i -lt $lista.Count; $i++) {
    $v = Join-Path $lista[$i].FullName "VERSAO-DO-CODIGO.txt"
    $txt = if (Test-Path $v) { (Get-Content $v -Tail 1) } else { "" }
    Write-Host ("  [" + $i + "] " + $lista[$i].Name + "   " + $txt)
  }
  $esc = Read-Host "Qual numero (Enter = o mais novo)"
  $idx = if ($esc -eq "") { 0 } else { [int]$esc }
  $Backup = $lista[$idx].FullName
}
if (-not (Test-Path $Backup)) { Write-Host "nao achei esse backup" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "=== 1/3  guardando o estado de AGORA (para nao perder) ===" -ForegroundColor Cyan
& (Join-Path $ponte "BACKUP.ps1")

Write-Host ""
Write-Host "=== 2/3  fechando o painel ===" -ForegroundColor Cyan
Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*painel*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

Write-Host ""
Write-Host ("=== 3/3  devolvendo " + (Split-Path $Backup -Leaf) + " ===") -ForegroundColor Cyan
Get-ChildItem $Backup -Recurse -File | Where-Object { $_.Name -ne "VERSAO-DO-CODIGO.txt" } | ForEach-Object {
  $rel = $_.FullName.Substring($Backup.Length).TrimStart("\")
  $alvo = Join-Path $detto $rel
  New-Item -ItemType Directory -Force -Path (Split-Path $alvo) | Out-Null
  Copy-Item $_.FullName $alvo -Force
}
Write-Host "   configuracoes e logins devolvidos" -ForegroundColor Green

if ($ComCodigo) {
  $v = Join-Path $Backup "VERSAO-DO-CODIGO.txt"
  if (Test-Path $v) {
    $commit = (Get-Content $v -First 1).Trim()
    Set-Location $raiz
    git -c advice.detachedHead=false checkout $commit
    Write-Host ("   codigo voltou para " + $commit.Substring(0,8)) -ForegroundColor Green
  }
}

Set-Location $ponte
python tools\teste_rapido.py
Start-Process -FilePath "python" -ArgumentList "tools\painel\painel.py" -WorkingDirectory $ponte
Start-Sleep -Seconds 6
Start-Process "http://localhost:8730"
Write-Host ""
Write-Host "Pronto." -ForegroundColor Green
Write-Host ""
