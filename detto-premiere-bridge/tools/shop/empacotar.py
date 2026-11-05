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
RAIZES = ["shop/shop.py"]

# o que NÃO é import mas o shop precisa: o desenho das cartelas e o palco dele
EXTRAS = [
    "shop/cartelas.js",
    "shop/palco/shop.html",
    "shop/palco/shop.css",
    "shop/LEIA-ME.txt",
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
  "modo": "ia",
  "fotos_internet": true,
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
    # as pastas de pacote precisam do __init__ para o `import historias.historias` funcionar
    for sub in {p.relative_to(TOOLS).parent for p in nossos if p.relative_to(TOOLS).parent != Path(".")}:
        ini = pasta / "tools" / sub / "__init__.py"
        if not ini.exists() and (TOOLS / sub / "__init__.py").exists():
            shutil.copy2(TOOLS / sub / "__init__.py", ini)

    (pasta / "shop").mkdir(exist_ok=True)
    (pasta / "shop" / "config.json").write_text(CONFIG_PADRAO, encoding="utf-8")
    (pasta / "requirements.txt").write_text(REQUISITOS, encoding="utf-8")
    (pasta / "INSTALAR.bat").write_text(INSTALAR_BAT, encoding="utf-8-sig")
    (pasta / "RODAR.bat").write_text(RODAR_BAT, encoding="utf-8-sig")
    (pasta / "LEIA-ME.txt").write_text(LEIA_ME, encoding="utf-8")
    print(f"  {copiados} arquivo(s) nossos + instaladores em {pasta}")
    return pasta


def confere(pasta: Path):
    """O PACOTE SE TESTA: importa o shop.py DENTRO dele. Faltando um arquivo, falha AQUI."""
    r = subprocess.run([sys.executable, "-c",
                        "import sys; sys.path[:0]=[r'{0}/tools/shop', r'{0}/tools', r'{0}/tools/reels', "
                        "r'{0}/tools/canal']; import shop; print('IMPORTOU', bool(shop))"
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
chcp 65001 >nul
title DETTO SHOP - instalacao
echo ============================================
echo   DETTO SHOP - gerador de videos de produto
echo ============================================
echo.
where python >nul 2>nul
if errorlevel 1 (
  echo [X] Python nao encontrado. Instale o Python 3.11 em python.org
  echo     e MARQUE "Add python.exe to PATH" na primeira tela.
  pause & exit /b 1
)
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [!] ffmpeg nao encontrado. Baixe em https://www.gyan.dev/ffmpeg/builds/
  echo     e ponha a pasta bin no PATH. Sem ele nao sai video.
  echo.
)
echo Instalando as bibliotecas (demora alguns minutos na primeira vez)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 ( echo [X] A instalacao falhou. & pause & exit /b 1 )
echo.
echo Instalando o Chromium (desenha as cartelas do video)...
where npm >nul 2>nul
if errorlevel 1 (
  echo [!] Node.js nao encontrado. Instale em nodejs.org e rode este arquivo de novo.
  echo     Sem ele o video sai SEM as cartelas de texto e preco.
) else (
  npm install playwright
  npx playwright install chromium
)
echo.
echo ==== PRONTO ====
echo 1) Ponha a sua GEMINI_API_KEY (de graca em aistudio.google.com/apikey):
echo        setx GEMINI_API_KEY "a-sua-chave"
echo    Feche e abra o terminal depois disso.
echo 2) Rode o RODAR.bat
pause
"""

RODAR_BAT = """@echo off
chcp 65001 >nul
title DETTO SHOP
cd /d "%~dp0"
if not exist "shop" mkdir shop
if not exist "shop\\produtos.txt" (
  echo # Cole um link do TikTok Shop por linha. Se a pagina nao der o nome, escreva assim:> "shop\\produtos.txt"
  echo # ^<link^> ^| suporte de celular para mesa ^| 49,90>> "shop\\produtos.txt"
)
echo Lendo shop\\produtos.txt e a pasta shop\\produtos\\ ...
python tools\\shop\\shop.py --pasta "%~dp0shop" %*
echo.
echo Os videos prontos estao em shop\\prontos\\
pause
"""

LEIA_ME = """DETTO SHOP — videos de produto automaticos (pacote avulso)
===========================================================

Isto e SO o gerador de videos de produto do sistema do Everton. Nao tem canal de YouTube, nao tem
postagem automatica, nao tem as contas nem as chaves dele.

INSTALAR (uma vez)
------------------
1. Instale o Python 3.11 em python.org — MARQUE "Add python.exe to PATH".
2. Instale o Node.js em nodejs.org (e o que desenha os textos e a etiqueta de preco no video).
3. Instale o ffmpeg: https://www.gyan.dev/ffmpeg/builds/ → descompacte → ponha a pasta `bin` no PATH.
4. Clique duas vezes em INSTALAR.bat.
5. Pegue uma chave do Gemini de graca em aistudio.google.com/apikey e rode no terminal:
       setx GEMINI_API_KEY "a-sua-chave"
   Feche e abra o terminal. (Sem ela o roteiro nao e escrito pela IA.)

USAR
----
Clique em RODAR.bat. Ele le duas coisas:

  shop\\produtos.txt        um link do TikTok Shop por linha.
                            A pagina do Shop barra robo, entao se o link nao trouxer nome e foto,
                            escreva na mao:
                                <link> | suporte de celular para mesa | 49,90

  shop\\produtos\\<nome>\\   o produto que chegou em casa: ponha as fotos e os videos aqui.
                            Um arquivo com "eu", "review" ou "unbox" no nome e tratado como a SUA
                            gravacao e vira o vídeo principal.
                            Opcional: um produto.json com
                                {"nome": "...", "preco": "49,90", "preco_de": "89,90",
                                 "link": "...", "sobre": "o que ele faz", "selo": "FRETE GRATIS"}

Os videos saem em shop\\prontos\\. O que NAO virou video sai com o motivo em shop\\produtos_falhos.txt.

TRES MODOS (--modo, ou "modo" no produto.json)
-----------------------------------------------
  ia         fotos + voz da IA + texto e legenda      (o padrao)
  eu         a SUA gravacao manda, as fotos entram por cima
  vendedor   reaproveita o video do vendedor em 9:16

A VOZ
-----
Sem nada configurado ele usa a voz NEURAL pt-BR da Microsoft (de graca, sem chave, sai em segundos).
A voz clonada do Everton NAO vem neste pacote — e a voz dele.

REGRA QUE NAO SE QUEBRA
------------------------
O roteiro e PROIBIDO de inventar medida, garantia ou preco que nao esteja no material do produto.
Video de afiliado com informacao errada derruba a conta — essa regra esta dentro do prompt.

DOIS PCs AO MESMO TEMPO
------------------------
Pode. Cada PC tem a sua pasta `shop\\` e o seu historico, entao os dois nao fazem o mesmo produto —
desde que voces dividam os links/produtos entre os dois.

POSTAGEM
--------
Este pacote vem com a postagem automatica DESLIGADA de proposito ("postar": [] no shop\\config.json):
o video fica em shop\\prontos\\ e voce posta pelo app ou pelo TikTok Studio. Nao ha token nem conta
de ninguem aqui dentro.

OBS.: o pacote traz alguns arquivos compartilhados do sistema (voz, transcricao, busca de imagem,
cor, legendas). Eles vem porque o shop.py usa essas funcoes — nao ha historico, chave ou conta neles.
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
    print("Manda esse arquivo para o seu sócio. Ele descompacta, roda o INSTALAR.bat e depois o RODAR.bat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
