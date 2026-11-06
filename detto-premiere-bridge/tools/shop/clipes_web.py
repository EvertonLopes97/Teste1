#!/usr/bin/env python3
"""CLIPES DO PRODUTO VINDOS DA INTERNET (06/nov, pedido dele) — vídeo em vez de foto parada.

POR QUE ISTO EXISTE: o shop.py já buscava FOTOS na internet quando o produto não tinha mídia, mas foto
parada com zoom tem cara de anúncio velho. O que vende no TikTok Shop é o produto SENDO USADO. E existe
material disso de sobra: todo produto popular tem review, unboxing e demonstração no YouTube.

AS DUAS REGRAS QUE FAZEM ISSO PRESTAR:
  1. SEM A CARA DE NINGUÉM. Um review começa com o cara falando na câmera por 30 s — isso não serve para
     o seu vídeo e, pior, é o rosto de outra pessoa no seu anúncio. Cada pedaço é conferido com o YuNet
     (o mesmo detector que o canal usa) e o que tem rosto é DESCARTADO. Sobra a mão mexendo no produto,
     o close da embalagem, o produto funcionando — que é exatamente o que você quer.
  2. PEDAÇO CURTO, DO MEIO. O começo é apresentação e o fim é "se inscreva": o material bom está no meio.

Uso direto (para conferir):
    python tools\\shop\\clipes_web.py "suporte de celular para mesa" --quantos 6
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "reels"))

# um review começa com o apresentador falando: o material útil está depois
PULA_INICIO_S = 35.0
JANELA_S = 75.0          # quanto de cada vídeo é baixado (do PULA_INICIO em diante)
MIN_DUR, MAX_DUR = 60, 1800
# título que é outra coisa (não é o produto sendo mostrado)
FORA = ("live", "ao vivo", "reaction", "react", "shorts de", "compilado de memes")


def log(m):
    print(m, flush=True)


def _ytdlp(args, timeout=600):
    """o yt-dlp do projeto (cookies do PC + yt-dlp-ejs já configurados no reels.py)"""
    try:
        from reels import ytdlp as _y
        return _y(args, timeout=timeout)
    except Exception:
        return subprocess.run(["yt-dlp", *args], capture_output=True, text=True, timeout=timeout)


def candidatos(nome, quantos=4, extra="review"):
    """vídeos do YouTube que mostram o produto, dos mais relevantes"""
    busca = f"ytsearch{quantos * 3}:{nome} {extra}"
    r = _ytdlp(["--flat-playlist", "--dump-json", busca], timeout=180)
    out = []
    for linha in (r.stdout or "").splitlines():
        try:
            v = json.loads(linha)
        except ValueError:
            continue
        if not isinstance(v, dict) or not v.get("id"):
            continue
        dur = v.get("duration") or 0
        tit = (v.get("title") or "").lower()
        if dur and not (MIN_DUR <= dur <= MAX_DUR):
            continue
        if any(x in tit for x in FORA):
            continue
        out.append({"id": v["id"], "titulo": v.get("title") or "", "dur": dur,
                    "url": f"https://www.youtube.com/watch?v={v['id']}"})
        if len(out) >= quantos:
            break
    return out


def baixa_trecho(url, destino, ini=PULA_INICIO_S, dur=JANELA_S):
    """só um pedaço do meio, em 720p — baixar o vídeo inteiro seria desperdício de tempo e de disco"""
    args = ["-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]/b",
            "--download-sections", f"*{ini:.0f}-{ini + dur:.0f}",
            "--match-filter", "!is_live", "--no-playlist",
            "-o", str(destino), url]
    r = _ytdlp(args, timeout=900)
    return destino if destino.exists() and destino.stat().st_size > 50_000 else (r.stderr or "")[-300:]


def tem_rosto(arquivo, t, limite=0.012):
    """tem gente aparecendo neste segundo? (YuNet, o mesmo detector do canal)

    `limite` é a fração da tela ocupada pelo rosto: um rosto de review ocupa muito mais que 1,2% —
    um reflexo distante não conta.
    """
    import cv2
    import numpy as np

    os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
    modelo = TOOLS.parent / "yunet.onnx"
    if not modelo.exists():
        return False     # sem o detector eu não invento: deixo passar e digo no registro
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(arquivo), "-frames:v", "1",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, timeout=60)
    if not r.stdout:
        return False
    img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return False
    h, w = img.shape[:2]
    d = cv2.FaceDetectorYN.create(str(modelo), "", (w, h), 0.7)
    _, faces = d.detect(img)
    if faces is None:
        return False
    for f in faces:
        if (float(f[2]) * float(f[3])) / float(w * h) >= limite:
            return True
    return False


def dur_de(arquivo):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                        str(arquivo)], capture_output=True, text=True)
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


def corta_sem_rosto(fonte, destino_dir, quantos=4, dur=4.0, prefixo="clipe", log=log):
    """parte o trecho baixado em pedaços de `dur` s e devolve só os que NÃO têm ninguém na tela"""
    total = dur_de(fonte)
    if total < dur:
        return []
    destino_dir.mkdir(parents=True, exist_ok=True)
    out, t, n, descartados = [], 0.0, 0, 0
    while t + dur <= total and len(out) < quantos:
        meio = t + dur / 2
        if tem_rosto(fonte, meio) or tem_rosto(fonte, t + dur * 0.15):
            descartados += 1
            t += dur
            continue
        n += 1
        alvo = destino_dir / f"{prefixo}_{n:02d}.mp4"
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(fonte),
                            "-t", f"{dur:.2f}", "-an",
                            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(alvo)],
                           capture_output=True, text=True, timeout=300)
        if alvo.exists() and alvo.stat().st_size > 10_000:
            out.append(alvo)
        elif r.stderr:
            log(f"   corte falhou em {t:.0f}s: {r.stderr.strip()[:120]}")
        t += dur
    if descartados:
        log(f"   {descartados} pedaço(s) descartado(s): tinham a cara de alguém na tela")
    return out


def clipes_do_produto(nome, destino, quantos=6, dur=4.0, log=log, buscas=("review", "unboxing", "como usar")):
    """O CAMINHO INTEIRO: busca → baixa um pedaço → corta → descarta quem tem rosto → devolve os arquivos."""
    nome = (nome or "").strip()
    if not nome:
        return []
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    tmp = destino / "_baixando"
    tmp.mkdir(exist_ok=True)
    achados, vistos = [], set()
    try:
        for termo in buscas:
            if len(achados) >= quantos:
                break
            for c in candidatos(nome, quantos=2, extra=termo):
                if len(achados) >= quantos or c["id"] in vistos:
                    continue
                vistos.add(c["id"])
                log(f"   baixando um pedaço de: {c['titulo'][:60]}")
                bruto = tmp / f"{c['id']}.mp4"
                r = baixa_trecho(c["url"], bruto)
                if not isinstance(r, Path):
                    log(f"   não baixou ({str(r)[:120]})")
                    continue
                novos = corta_sem_rosto(bruto, destino, quantos=quantos - len(achados), dur=dur,
                                        prefixo=f"web_{c['id'][:6]}", log=log)
                achados += novos
                log(f"   +{len(novos)} clipe(s) sem rosto (total {len(achados)})")
                bruto.unlink(missing_ok=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not achados:
        log("   não consegui nenhum clipe sem rosto; o vídeo vai com as fotos")
    return achados


def main():
    ap = argparse.ArgumentParser(description="clipes do produto vindos da internet, sem a cara de ninguém")
    ap.add_argument("nome")
    ap.add_argument("--destino", default="")
    ap.add_argument("--quantos", type=int, default=6)
    ap.add_argument("--dur", type=float, default=4.0)
    a = ap.parse_args()
    destino = Path(a.destino) if a.destino else Path.cwd() / ("clipes_" + re.sub(r"\W+", "_", a.nome)[:30])
    fs = clipes_do_produto(a.nome, destino, quantos=a.quantos, dur=a.dur)
    for f in fs:
        print(f)
    print(f"{len(fs)} clipe(s) em {destino}")


if __name__ == "__main__":
    main()
