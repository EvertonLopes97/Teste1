# -*- coding: utf-8 -*-
"""EMPACOTA O TIKTOK SHOP SOZINHO — um .zip que instala só o gerador de vídeos de produto.

    python tools\\shop\\empacotar.py                      → DETTO-SHOP.zip aqui na pasta
    python tools\\shop\\empacotar.py --saida "D:\\envio"   → escolhe onde sai

PARA QUE SERVE
Ele quer mandar SÓ o TikTok Shop para o sócio, para os dois rodarem um em cada PC e dobrarem a produção
de vídeos. O resto do sistema (canais, reels, histórias, painel, postagem) não vai — nem o histórico, nem
as chaves, nem as contas dele.

COMO ELE ACHA O QUE COPIAR
Em vez de uma lista na mão (que envelhece calada no dia em que o shop.py passar a importar outra coisa),
ele SEGUE OS IMPORTS a partir do shop.py, de arquivo em arquivo, e copia o que achar dentro de `tools\\`.
Depois ele **se testa**: roda `python -c "import shop"` DENTRO do pacote e, se faltar qualquer arquivo,
o empacotamento falha aqui — e não no PC do sócio.
"""
from __future__ import annotations

import argparse
import ast
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent

# os .py de onde eu começo a seguir os imports
RAIZES = ["shop/shop.py", "shop/painel_shop.py", "painel/shop_painel.py"]

# o que NÃO é import mas o shop precisa: o desenho das cartelas e o palco dele
EXTRAS = [
    "shop/cartelas.js",
    "shop/palco/shop.html",
    "shop/palco/shop.css",
    "shop/LEIA-ME.txt",
    "shop/painel_shop.html",
    "ffcompat.py",
]

# bibliotecas de fora: não são arquivos nossos, vão no requirements
DE_FORA = {
    "argparse", "ast", "base64", "collections", "colorsys", "contextlib", "ctypes", "dataclasses",
    "datetime", "difflib", "fcntl", "functools", "glob", "hashlib", "html", "http", "importlib", "io",
    "itertools", "json", "locale", "logging", "math", "msvcrt", "os", "pathlib", "platform", "queue",
    "random", "re", "shlex", "shutil", "socket", "sqlite3", "statistics", "string", "subprocess", "sys",
    "tempfile", "textwrap", "threading", "time", "traceback", "types", "typing", "unicodedata", "urllib",
    "uuid", "wave", "webbrowser", "xml", "zipfile", "zlib",
    "cv2", "numpy", "PIL", "requests", "yt_dlp", "edge_tts", "google", "googleapiclient", "mediapipe",
    "faster_whisper", "playwright", "feedparser", "rembg", "docx", "soundfile", "scipy", "torch",
    "asyncio", "secrets", "signal", "site", "socketserver", "curl_cffi", "torchaudio", "chatterbox",
    "google_auth_oauthlib",
}

# O PACOTE JÁ VEM COM A POSTAGEM DESLIGADA. O shop.py importa o `postar.py` para pôr o vídeo na fila, e
# aqui isso é errado: o sócio não tem as contas nem os tokens, então o vídeo ficaria preso numa fila que
# ninguém esvazia. Ele gera o vídeo e posta pelo celular/TikTok Studio.
CONFIG_PADRAO = """{
  "postar": [],
  "arroba": "",
  "modo": "ia",
  "auto": false,
  "narracao": true,
  "legenda": true,
  "clipes_internet": true,
  "clipes_quantos": 10,
  "fotos_internet": true,
  "voz_neural": "pt-BR-AntonioNeural",
  "velocidade_voz": 1.1,
  "_nota": "postar vazio = o video fica em prontos\\\\ e voce posta no app. Nao mexa se nao souber."
}
"""

REQUISITOS = """# TikTok Shop do DETTO — só o que ESTE pacote usa
yt-dlp
Pillow
opencv-python
numpy
faster-whisper
edge-tts>=7.0.0
google-generativeai
requests
curl_cffi
yt-dlp-ejs
"""


def _modulos_do_arquivo(p: Path):
    """os módulos que ESTE arquivo importa, inclusive os de dentro de função (o shop usa muito isso)"""
    try:
        arvore = ast.parse(p.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as e:
        print(f"  !! não consegui ler {p.name}: {e}")
        return set()
    out = set()
    for n in ast.walk(arvore):
        if isinstance(n, ast.Import):
            for a in n.names:
                out.add(a.name)
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module)
    return out


def _acha_arquivo(modulo: str):
    """o .py do módulo dentro de tools\\, em qualquer subpasta (o shop importa `voz`, `reels`, `historias`…)"""
    alvo = modulo.replace(".", "/")
    for c in (TOOLS / f"{alvo}.py", TOOLS / alvo / "__init__.py"):
        if c.is_file():
            return c
    # `from reels import baixa` → tools\reels\reels.py; `import voz` → tools\canal\voz.py
    nome = modulo.split(".")[0]
    achados = sorted(TOOLS.glob(f"*/{nome}.py")) + sorted(TOOLS.glob(f"{nome}.py"))
    return achados[0] if achados else None


def dependencias():
    """todos os nossos arquivos que o shop precisa, seguindo os imports de verdade"""
    fila = [TOOLS / r for r in RAIZES]
    vistos, nossos, faltando = set(), set(), set()
    while fila:
        p = fila.pop()
        if p in vistos or not p.is_file():
            continue
        vistos.add(p)
        nossos.add(p)
        for m in _modulos_do_arquivo(p):
            base = m.split(".")[0]
            if base in DE_FORA:
                continue
            arq = _acha_arquivo(m)
            if arq:
                fila.append(arq)
            elif base not in DE_FORA:
                faltando.add(m)
    return sorted(nossos), sorted(faltando)


def monta(saida: Path):
    nossos, faltando = dependencias()
    if faltando:
        print(f"  (não são arquivos nossos, devem ser bibliotecas: {', '.join(sorted(faltando))})")
    pasta = saida / "DETTO-SHOP"
    if pasta.exists():
        shutil.rmtree(pasta)
    (pasta / "tools").mkdir(parents=True)

    copiados = 0
    for p in nossos:
        rel = p.relative_to(TOOLS)
        dest = pasta / "tools" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
        copiados += 1
    for e in EXTRAS:
        o = TOOLS / e
        if not o.is_file():
            print(f"  !! extra que não achei: {e}")
            continue
        d = pasta / "tools" / e
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(o, d)
        copiados += 1
    # O DETECTOR DE ROSTO (06/nov): o clipes_web.py descarta os pedaços de vídeo em que aparece gente,
    # e para isso ele precisa do yunet.onnx — que mora na RAIZ do projeto, não em tools\, então não
    # entra por import nenhum. Sem ele `tem_rosto` devolve False e o filtro passa a deixar TUDO passar,
    # calado: o sócio receberia vídeos com a cara de estranhos. Por isso ele vem junto.
    yunet = TOOLS.parent / "yunet.onnx"
    if yunet.is_file():
        shutil.copy2(yunet, pasta / "yunet.onnx")
        copiados += 1
    else:
        print("  !! não achei o yunet.onnx: o filtro de rosto dos clipes NÃO vai funcionar lá")

    # as pastas de pacote precisam do __init__ para o `import historias.historias` funcionar
    for sub in {p.relative_to(TOOLS).parent for p in nossos if p.relative_to(TOOLS).parent != Path(".")}:
        ini = pasta / "tools" / sub / "__init__.py"
        if not ini.exists() and (TOOLS / sub / "__init__.py").exists():
            shutil.copy2(TOOLS / sub / "__init__.py", ini)

    fonte = PONTE / "fonts" / "TikTokSans.ttf"   # o shop.css aponta para ..\..\..\fonts\TikTokSans.ttf
    if fonte.is_file():
        (pasta / "fonts").mkdir(exist_ok=True)
        shutil.copy2(fonte, pasta / "fonts" / fonte.name)
        lic = fonte.with_name("TikTokSans-OFL.txt")
        if lic.is_file():
            shutil.copy2(lic, pasta / "fonts" / lic.name)
    (pasta / "shop").mkdir(exist_ok=True)
    (pasta / "shop" / "config.json").write_text(CONFIG_PADRAO, encoding="utf-8")
    (pasta / "requirements.txt").write_text(REQUISITOS, encoding="utf-8")
    # .bat em ASCII puro e com CRLF (BOM ou LF quebram o cmd); .ps1 em UTF-8 COM BOM (o PowerShell 5 exige)
    (pasta / "INSTALAR.bat").write_bytes(INSTALAR_BAT.replace("\n", "\r\n").encode("ascii"))
    (pasta / "ABRIR PAINEL.bat").write_bytes(ABRIR_BAT.replace("\n", "\r\n").encode("ascii"))
    (pasta / "RODAR.bat").write_bytes(RODAR_BAT.replace("\n", "\r\n").encode("ascii"))
    (pasta / "instalar.ps1").write_bytes(b"\xef\xbb\xbf" + INSTALAR_PS1.replace("\n", "\r\n").encode("utf-8"))
    (pasta / "LEIA-ME.txt").write_text(LEIA_ME, encoding="utf-8")
    print(f"  {copiados} arquivo(s) nossos + instaladores em {pasta}")
    return pasta


def confere(pasta: Path):
    """O PACOTE SE TESTA: importa o shop.py DENTRO dele. Faltando um arquivo, falha AQUI."""
    r = subprocess.run([sys.executable, "-c",
                        "import sys; sys.path[:0]=[r'{0}/tools/shop', r'{0}/tools', r'{0}/tools/reels', "
                        "r'{0}/tools/canal', r'{0}/tools/painel']; import shop, painel_shop, shop_painel; print('IMPORTOU', bool(shop))"
                        .format(pasta.as_posix())],
                       capture_output=True, text=True, timeout=300)
    if "IMPORTOU" in (r.stdout or ""):
        print("  conferido: o shop.py importa dentro do pacote ✔")
        return True
    falta = re.findall(r"No module named '([^']+)'", r.stderr or "")
    print("  !! o pacote NÃO importa:", (falta and f"falta o módulo {falta[0]}")
          or ((r.stderr or "").strip().splitlines() or [""])[-1][:200])
    if falta and falta[0] in DE_FORA:
        print("     (esse é de fora: está no requirements.txt, o sócio instala com o INSTALAR.bat — tudo bem)")
        return True
    return False


INSTALAR_BAT = """@echo off
title DETTO SHOP - instalacao
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
echo.
pause
"""

ABRIR_BAT = """@echo off
title DETTO SHOP - painel (deixe esta janela aberta)
cd /d "%~dp0"
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0navegador"
set "PYTHONIOENCODING=utf-8"
where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Rode o INSTALAR.bat primeiro.
  pause
  exit /b 1
)
python tools\\shop\\painel_shop.py
pause
"""

RODAR_BAT = """@echo off
title DETTO SHOP - sem painel
cd /d "%~dp0"
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0navegador"
set "DETTO_SHOP=%~dp0shop"
set "PYTHONIOENCODING=utf-8"
python tools\\shop\\shop.py --pasta "%~dp0shop" --nao-postar %*
echo.
echo Os videos prontos estao em shop\\prontos
pause
"""

# O INSTALADOR DE VERDADE (11/nov): tudo sozinho, do zero, num PC que nunca viu o projeto. PowerShell porque
# o .bat não consegue RELER o PATH depois de instalar o Python/ffmpeg/Node — e aí "python não encontrado" logo
# depois de instalar o Python. Pode ser rodado de novo quantas vezes quiser: pula o que já está pronto.
INSTALAR_PS1 = """$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $aqui
$falhas = @()

function Titulo($t) { Write-Host ''; Write-Host "== $t" -ForegroundColor Cyan }
function RelePath {
  $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
}
function Tem($nome) { return [bool](Get-Command $nome -ErrorAction SilentlyContinue) }
function PythonBom {
  # o "python" da Microsoft Store e so um atalho para a loja: nao serve
  $c = Get-Command python -ErrorAction SilentlyContinue
  if (-not $c) { return $false }
  if ($c.Source -like '*WindowsApps*') { return $false }
  $v = & python -c "import sys; print(sys.version_info >= (3, 10))" 2>$null
  return ($v -eq 'True')
}
function InstalaWinget($id, $nome) {
  if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
    Write-Host "   Este Windows nao tem o winget. Instale o $nome na mao e rode o INSTALAR.bat de novo." -ForegroundColor Yellow
    return
  }
  Write-Host "   instalando o $nome (pode pedir permissao de administrador)..."
  winget.exe install --id $id -e --silent --accept-package-agreements --accept-source-agreements
  RelePath
}

Write-Host '============================================'
Write-Host '  DETTO SHOP - instalacao completa'
Write-Host '  Pode levar de 10 a 30 minutos. Deixe esta janela aberta.'
Write-Host '============================================'
RelePath

Titulo '1 de 6 - Python'
if (PythonBom) { Write-Host '   ja tem' } else {
  InstalaWinget 'Python.Python.3.11' 'Python 3.11'
  $pasta = Join-Path $env:LOCALAPPDATA 'Programs\\Python\\Python311'
  if (Test-Path (Join-Path $pasta 'python.exe')) { $env:Path = "$pasta;$pasta\\Scripts;" + $env:Path }
}
if (-not (PythonBom)) {
  Write-Host '   [X] Nao consegui instalar o Python sozinho.' -ForegroundColor Red
  Write-Host '       Baixe em https://www.python.org/downloads/ , MARQUE "Add python.exe to PATH" e rode o INSTALAR.bat de novo.'
  exit 1
}

Titulo '2 de 6 - ffmpeg (monta o video)'
if (Tem ffmpeg) { Write-Host '   ja tem' } else { InstalaWinget 'Gyan.FFmpeg' 'ffmpeg' }
if (-not (Tem ffmpeg)) {
  # plano B sem winget: baixa o zip e deixa dentro do pacote
  try {
    $zip = Join-Path $env:TEMP 'ffmpeg-detto.zip'
    Write-Host '   baixando o ffmpeg direto (uns 90 MB)...'
    Invoke-WebRequest 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile $zip -UseBasicParsing
    $dest = Join-Path $aqui 'ffmpeg'
    Expand-Archive $zip -DestinationPath $dest -Force
    $bin = (Get-ChildItem $dest -Recurse -Filter ffmpeg.exe | Select-Object -First 1).DirectoryName
    if ($bin) {
      $u = [Environment]::GetEnvironmentVariable('Path','User')
      [Environment]::SetEnvironmentVariable('Path', "$u;$bin", 'User')
      RelePath
    }
  } catch { Write-Host "   nao deu: $($_.Exception.Message)" -ForegroundColor Yellow }
}
if (-not (Tem ffmpeg)) { $falhas += 'ffmpeg (sem ele NAO sai video): feche tudo e rode o INSTALAR.bat de novo' }

Titulo '3 de 6 - Node.js (desenha os textos e o preco no video)'
if (Tem node) { Write-Host '   ja tem' } else { InstalaWinget 'OpenJS.NodeJS.LTS' 'Node.js' }
if (-not (Tem node)) { $falhas += 'Node.js (sem ele o video sai sem as cartelas de texto e preco)' }

Titulo '4 de 6 - bibliotecas do Python (a parte mais demorada)'
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
  Write-Host '   deu erro; tento de novo uma vez...' -ForegroundColor Yellow
  python -m pip install -r requirements.txt
  if ($LASTEXITCODE -ne 0) { $falhas += 'bibliotecas do Python (confira a internet e rode o INSTALAR.bat de novo)' }
}

Titulo '5 de 6 - navegador das cartelas (Chromium, uns 150 MB)'
if (Tem node) {
  $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $aqui 'navegador'
  if (-not (Test-Path (Join-Path $aqui 'node_modules\\playwright'))) { cmd /c "npm install playwright --no-fund --no-audit" }
  cmd /c "npx playwright install chromium"
  if ($LASTEXITCODE -ne 0) { $falhas += 'Chromium das cartelas (rode o INSTALAR.bat de novo)' }
} else { Write-Host '   pulei (sem Node.js)' -ForegroundColor Yellow }

Titulo '6 de 6 - modelo da legenda (uns 480 MB, so nesta primeira vez)'
python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8'); print('   modelo pronto')"
if ($LASTEXITCODE -ne 0) { Write-Host '   nao baixou agora; ele baixa sozinho no primeiro video' -ForegroundColor Yellow }

Titulo 'Conferindo'
$env:DETTO_SHOP = Join-Path $aqui 'shop'
python -c "import sys; sys.path[:0]=['tools/shop','tools','tools/reels','tools/canal','tools/painel']; import shop, painel_shop, cv2, PIL, edge_tts, yt_dlp; print('   programa OK')"
if ($LASTEXITCODE -ne 0) { $falhas += 'o programa nao abriu (mande um print desta janela)' }

try {   # atalho na Area de Trabalho
  $ws = New-Object -ComObject WScript.Shell
  $lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'DETTO Shop.lnk'))
  $lnk.TargetPath = Join-Path $aqui 'ABRIR PAINEL.bat'
  $lnk.WorkingDirectory = $aqui
  $lnk.Save()
  Write-Host '   atalho "DETTO Shop" criado na Area de Trabalho'
} catch {}

Write-Host ''
if ($falhas.Count) {
  Write-Host '==== TERMINOU COM PENDENCIAS ====' -ForegroundColor Yellow
  $falhas | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
  Write-Host 'Feche esta janela e rode o INSTALAR.bat de novo: ele continua de onde parou.'
} else {
  Write-Host '==== TUDO PRONTO ====' -ForegroundColor Green
  Write-Host 'Abrindo o painel no navegador. Nos proximos dias, use o atalho "DETTO Shop" da Area de Trabalho.'
  Start-Process (Join-Path $aqui 'ABRIR PAINEL.bat')
}
"""

LEIA_ME = """DETTO SHOP - videos de produto para o TikTok Shop (pacote avulso, com painel)
=============================================================================

Isto e SO o gerador de videos de produto. Nao tem canal de YouTube, postagem automatica, contas nem chaves
de ninguem.

INSTALAR (uma vez, Windows 10 ou 11)
------------------------------------
1. Descompacte a pasta DETTO-SHOP num lugar simples (ex.: C:\\DETTO-SHOP). Nao rode de dentro do .zip.
2. Clique duas vezes em INSTALAR.bat e espere. Ele instala sozinho o Python, o ffmpeg, o Node.js, as
   bibliotecas, o navegador das cartelas e o modelo da legenda (10 a 30 minutos, uns 2 GB).
   Se o Windows pedir permissao de administrador, aceite. Se o SmartScreen avisar, clique em
   "Mais informacoes" e "Executar assim mesmo".
3. No fim o painel abre no navegador e aparece o atalho "DETTO Shop" na Area de Trabalho.
   Deu "TERMINOU COM PENDENCIAS"? Rode o INSTALAR.bat de novo: ele continua de onde parou.

USAR
----
Abra o atalho "DETTO Shop" (ou ABRIR PAINEL.bat). Deixe a janela preta aberta enquanto usa.

  1. COMO QUERO O VIDEO
       Autoral          junta cenas de 3 ou mais videos do produto, descarta as que mostram rosto, escreve
                        roteiro novo e narra. E o mais original.
       Copia do link    usa o video do link que voce colar, com narracao e textos novos por cima.
                        Menos original: e o video de outra pessoa.
       Minha gravacao   o video que voce gravou com o produto e o principal (a sua voz fica).
     Mais: narracao ligada ou desligada, legenda, voz, velocidade, duracao, seu @ e a frase final.

  2. QUAL PRODUTO: pelo nome, por link, varios links, ou a pasta de um produto que voce tem em casa
     (shop\\produtos\\<nome>\\ com as fotos e videos; arquivo com "eu", "review" ou "unbox" no nome = a sua
     gravacao).

  3. FAZER O VIDEO. O andamento aparece ao lado; o video pronto aparece embaixo com a legenda do post.
     Os arquivos ficam em shop\\prontos\\<data>.

CHAVES DA IA (de graca, 2 minutos)
----------------------------------
No painel, em "Chaves da IA que escreve o roteiro", cole a chave do Gemini (aistudio.google.com/apikey) ou
do Groq (console.groq.com/keys). Elas ficam so neste PC, no arquivo chaves.json.
Sem chave nenhuma o video SAI, mas com um roteiro-modelo generico. Para video autoral de verdade, ponha a chave.

A VOZ
-----
Voz neural pt-BR da Microsoft (de graca, sem chave). No painel da para trocar entre 4 vozes e a velocidade.

REGRA QUE NAO SE QUEBRA
-----------------------
O roteiro e PROIBIDO de inventar medida, garantia ou preco que nao esteja no material do produto.
Video de afiliado com informacao errada derruba a conta.

SE ALGO NAO FUNCIONAR
---------------------
- O painel mostra no topo o que falta (ffmpeg, Node, chave).
- "Nao viraram video" mostra o motivo de cada produto que falhou.
- YouTube pedindo login ("Sign in to confirm you are not a bot"): instale o Firefox, entre no YouTube nele e
  tente de novo.
- Mande um print do "Andamento" para o Everton.

DOIS PCs AO MESMO TEMPO
-----------------------
Pode. Cada PC tem a sua pasta shop\\ e o seu historico. So dividam os produtos entre os dois.
"""


def main():
    ap = argparse.ArgumentParser(description="monta o .zip do TikTok Shop avulso")
    ap.add_argument("--saida", help="onde sai o pacote (padrão: a pasta detto-premiere-bridge)")
    ap.add_argument("--sem-zip", action="store_true", help="deixa só a pasta, sem compactar")
    a = ap.parse_args()
    saida = Path(a.saida) if a.saida else PONTE
    saida.mkdir(parents=True, exist_ok=True)

    print("EMPACOTANDO O TIKTOK SHOP")
    pasta = monta(saida)
    if not confere(pasta):
        print("\nNÃO vou gerar o .zip com o pacote quebrado. Veja o módulo que falta acima.")
        return 1
    if a.sem_zip:
        print(f"\nPronto: {pasta}")
        return 0
    zipe = saida / "DETTO-SHOP.zip"
    with zipfile.ZipFile(zipe, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(pasta.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                z.write(p, p.relative_to(pasta.parent))
    mb = zipe.stat().st_size / 1e6
    print(f"\nPronto: {zipe}  ({mb:.1f} MB)")
    print("Manda esse arquivo para o seu sócio. Ele descompacta, roda o INSTALAR.bat e o painel abre sozinho.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
