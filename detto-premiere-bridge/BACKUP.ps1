# BACKUP.ps1 — guarda o que NÃO dá para refazer: as configurações, o estado das contas e os logins.
# Rode no PowerShell:   cd C:\Users\guebe\Teste1 ; .\detto-premiere-bridge\BACKUP.ps1
#
# O que entra: todo config.json / estado.json / historico.json / painel_*.json das pastas do E:\DETTO,
# os tokens de login (Instagram, TikTok, YouTube), o serie.json das histórias e a versão do código.
# O que NÃO entra: vídeo (são gigantes e dá para refazer) — só o miolo que te faria perder dias.
#
# Fica em  E:\DETTO\backups\<data-hora>\  e guarda os 10 últimos.
# Para voltar:  .\detto-premiere-bridge\RESTAURAR.ps1
$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot
$detto = if (Test-Path "E:\DETTO") { "E:\DETTO" } else { Join-Path $HOME "DETTO" }
$quando = Get-Date -Format "yyyy-MM-dd_HHmm"
$destino = Join-Path $detto "backups\$quando"
New-Item -ItemType Directory -Force -Path $destino | Out-Null

Write-Host ""
Write-Host "=== guardando as configuracoes de $detto ===" -ForegroundColor Cyan
$padroes = @("config.json", "estado.json", "estado.bak", "historico.json", "painel*.json", "serie.json",
             "post.json", "_ordem.json", "jogo.json", "produto.json")
$n = 0
foreach ($p in $padroes) {
  Get-ChildItem -Path $detto -Filter $p -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike "*\backups\*" -and $_.FullName -notlike "*\tmp*" } |
    ForEach-Object {
      $rel = $_.FullName.Substring($detto.Length).TrimStart("\")
      $alvo = Join-Path $destino $rel
      New-Item -ItemType Directory -Force -Path (Split-Path $alvo) | Out-Null
      Copy-Item $_.FullName $alvo -Force
      $n++
    }
}
Write-Host ("   " + $n + " arquivo(s) de configuracao")

Write-Host "=== guardando os logins (tokens) ===" -ForegroundColor Cyan
foreach ($t in @("postar\tokens", "canal_galo\token.json", "canal_vlogs\token.json", "canal_gta6\token.json", "youtube")) {
  $o = Join-Path $detto $t
  if (Test-Path $o) {
    $alvo = Join-Path $destino $t
    New-Item -ItemType Directory -Force -Path (Split-Path $alvo) | Out-Null
    Copy-Item $o $alvo -Recurse -Force
    Write-Host ("   " + $t)
  }
}

Write-Host "=== guardando a versao do codigo ===" -ForegroundColor Cyan
Set-Location $raiz
$commit = (git rev-parse HEAD) 2>$null
"$commit" | Set-Content (Join-Path $destino "VERSAO-DO-CODIGO.txt") -Encoding ascii
(git log -1 --format="%h %ad %s" --date=iso) 2>$null | Add-Content (Join-Path $destino "VERSAO-DO-CODIGO.txt")
Write-Host ("   " + $commit)

# so os 10 ultimos
$todos = Get-ChildItem (Join-Path $detto "backups") -Directory | Sort-Object Name -Descending
if ($todos.Count -gt 10) { $todos | Select-Object -Skip 10 | Remove-Item -Recurse -Force }

Write-Host ""
Write-Host ("PRONTO: " + $destino) -ForegroundColor Green
Write-Host "Para voltar um backup:  .\detto-premiere-bridge\RESTAURAR.ps1"
Write-Host ""
