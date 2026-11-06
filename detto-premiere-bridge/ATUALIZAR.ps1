# ATUALIZAR.ps1 — baixa o codigo novo, CONFERE se ele esta sao e reinicia o painel.
# Rode no PowerShell:   cd C:\Users\guebe\Teste1 ; .\detto-premiere-bridge\ATUALIZAR.ps1
#
# REDE DE PROTECAO (29/10): antes de baixar, guarda a versao que esta rodando em .ultima_boa.
# Depois do pull, roda tools\teste_rapido.py; se o codigo novo estiver quebrado, VOLTA SOZINHO para a
# versao de antes e avisa. Assim um envio errado meu nao derruba o seu dia.
# Para voltar na mao a qualquer momento:  .\detto-premiere-bridge\VOLTAR.ps1
$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot          # a pasta Teste1
$ponte = Join-Path $raiz "detto-premiere-bridge"
$marca = Join-Path $ponte ".ultima_boa"

Write-Host ""
Write-Host "=== 1/5  fechando o painel ===" -ForegroundColor Cyan
Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*painel*" } |
  ForEach-Object {
    Write-Host ("   fechando PID " + $_.ProcessId)
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "=== 2/5  guardando a versao de agora ===" -ForegroundColor Cyan
Set-Location $raiz
$antes = (git rev-parse HEAD) 2>$null
if ($antes) {
  Write-Host ("   versao de agora: " + $antes.Substring(0,8))
} else {
  Write-Host "   nao consegui ler a versao atual (git)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 3/5  baixando o codigo novo ===" -ForegroundColor Cyan
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
  # arquivo SOLTO no PC com o mesmo nome de um que veio no codigo novo ("untracked working tree files would be
  # overwritten"): o git se recusa a pisar nele. Tiro do caminho (guardo com .ANTIGO) e tento de novo.
  $saida = (git pull 2>&1 | Out-String)
  $presos = [regex]::Matches($saida, '(?m)^\s{8}(\S.*)$') | ForEach-Object { $_.Groups[1].Value.Trim() }
  $moveu = $false
  foreach ($f in $presos) {
    if (Test-Path $f) {
      $alvo = $f + ".ANTIGO"
      if (Test-Path $alvo) { Remove-Item $alvo -Force -ErrorAction SilentlyContinue }
      Write-Host ("   tirando da frente: " + $f) -ForegroundColor Yellow
      Move-Item $f $alvo -Force -ErrorAction SilentlyContinue
      $moveu = $true
    }
  }
  if ($moveu) { git pull }
}
if ($LASTEXITCODE -ne 0) {
  # CAMINHO INVALIDO NO WINDOWS (05/nov): um commit trouxe por engano uma pasta chamada "E:" (o ":" nao
  # vale em nome de arquivo aqui), e o pull morreu com "invalid path" em TODA tentativa — o repositorio
  # ficava impossivel de atualizar e nada que eu consertasse chegava no PC dele. Nesse caso o conserto e
  # ir direto para a versao nova do servidor: ela ja nao tem esses arquivos.
  $saida = (git pull 2>&1 | Out-String)
  if ($saida -match "invalid path") {
    Write-Host "   o codigo tinha um arquivo com nome invalido no Windows; indo direto para a versao nova" -ForegroundColor Yellow
    $ramo = (git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null)
    if (-not $ramo) { $ramo = "origin/claude/upbeat-sagan-y007mb" }
    git fetch --all --prune
    git reset --hard $ramo
  }
}
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Host "O git pull NAO funcionou. Copie o erro acima e me mande." -ForegroundColor Red
  Read-Host "Enter para fechar"
  exit 1
}

# yt-dlp + o componente que resolve o desafio do YouTube (sem ele: "Requested format is not available")
Write-Host "   atualizando yt-dlp e yt-dlp-ejs..." -ForegroundColor DarkGray
# o `| Out-Null` ENGOLIA o erro (06/nov): sem internet ou com o pip quebrado a atualizacao "passava"
# e so aparecia horas depois, como download falhando no canal. Agora a saida e guardada e mostrada.
$pipOut = python -m pip install -q -U yt-dlp yt-dlp-ejs 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "   NAO consegui atualizar o yt-dlp (sigo mesmo assim; o download pode falhar):" -ForegroundColor Yellow
  ($pipOut | Select-Object -Last 6) | ForEach-Object { Write-Host "     $_" -ForegroundColor DarkYellow }
} else {
  $v = (python -m pip show yt-dlp 2>$null | Select-String '^Version:') -replace 'Version:\s*', ''
  if ($v) { Write-Host "   yt-dlp $v" -ForegroundColor DarkGray }
}

Write-Host ""
Write-Host "=== 4/5  conferindo se o codigo novo esta sao ===" -ForegroundColor Cyan
Set-Location $ponte
python tools\teste_rapido.py
$sao = ($LASTEXITCODE -eq 0)
if (-not $sao) {
  Write-Host ""
  Write-Host "O CODIGO NOVO ESTA QUEBRADO. Voltando para a versao de antes..." -ForegroundColor Red
  Set-Location $raiz
  if ($antes) {
    git -c advice.detachedHead=false checkout $antes 2>$null
    Write-Host ("   voltei para " + $antes.Substring(0,8)) -ForegroundColor Yellow
  } elseif (Test-Path $marca) {
    $boa = (Get-Content $marca -Raw).Trim()
    git -c advice.detachedHead=false checkout $boa 2>$null
    Write-Host ("   voltei para a ultima versao boa " + $boa.Substring(0,8)) -ForegroundColor Yellow
  }
  Write-Host "   Mande a lista de problemas acima para o Claude." -ForegroundColor Yellow
  Set-Location $ponte
} else {
  if ($antes) { Set-Content -Path $marca -Value (git -C $raiz rev-parse HEAD) -Encoding ascii }
  $versao = (Select-String -Path "tools\painel\painel.py" -Pattern 'PAINEL_VERSAO = "(.+)"' |
             Select-Object -First 1).Matches.Groups[1].Value
  Write-Host ("   versao do painel no disco: " + $versao) -ForegroundColor Green
}

Write-Host ""
Write-Host "=== 5/5  abrindo o painel ===" -ForegroundColor Cyan
# o painel.py abre a aba do navegador sozinho (1 s depois de subir); abrir aqui também dava DUAS abas
Start-Process -FilePath "python" -ArgumentList "tools\painel\painel.py" -WorkingDirectory $ponte
Start-Sleep -Seconds 3
Write-Host ""
if ($sao) {
  Write-Host "Pronto. No painel, a versao tem que bater com a de cima." -ForegroundColor Green
} else {
  Write-Host "Abri o painel na versao ANTIGA (a nova estava quebrada)." -ForegroundColor Yellow
}
Write-Host "Se algo nao estiver rodando, rode:  python tools\doutor.py   e me mande o tools\diagnostico.txt"
Write-Host ""
