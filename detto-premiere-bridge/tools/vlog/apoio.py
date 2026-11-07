# -*- coding: utf-8 -*-
"""CENAS DE APOIO DA INTERNET para o vlog: quando você fala de um lugar/momento e não tem imagem sua dele
("fui na Aparecida", "o dia na Arena MRV"), busca um vídeo HORIZONTAL do lugar, SEM marca d'água, e usa 2–4 s.

    python tools\\vlog\\apoio.py "Basílica de Aparecida vista aérea" --segundos 3      (teste)

Onde procura, nesta ordem (o primeiro que der certo fica):
  1. Pexels   (PEXELS_API_KEY, grátis)  — banco de vídeos livre, sem marca d'água, sem crédito obrigatório
  2. Pixabay  (PIXABAY_API_KEY, grátis) — idem
  3. YouTube  — primeiro só vídeos com licença Creative Commons; se não tiver, os mais relevantes (drone/4K/tour).
     Pega um pedaço do MEIO (sem abertura/encerramento) e confere: sem logo/marca fixa nos cantos e sem faixa de texto.
Cache: <DETTO>\\vlog_apoio\\ (o mesmo lugar não é baixado de novo). Créditos em <job>\\creditos_apoio.txt.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent


def pasta_cache():
    p = Path(os.environ.get("DETTO_APOIO") or ("E:/DETTO/vlog_apoio" if os.name == "nt" and Path("E:/").exists()
                                               else Path.home() / "DETTO" / "vlog_apoio"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", **(headers or {})})
    return json.loads(urllib.request.urlopen(req, timeout=40).read())


def _baixa(url, saida):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as r, open(saida, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    return saida


def sonda(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                        "-of", "json", str(f)], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        s = d["streams"][0]
        return int(s["width"]), int(s["height"]), float(d["format"]["duration"])
    except Exception:
        return 0, 0, 0.0


def tem_marca(video, ini=0.0, dur=None):
    """marca d'água / logo fixo / faixa de texto: região que NÃO muda (parada) mas tem muito contorno, num vídeo
    que se mexe — nos cantos (logo de canal/TV) ou na faixa de baixo (letreiro). Devolve o motivo ou ""."""
    import numpy as np
    w = 320
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{ini:.2f}", "-i", str(video)]
    if dur:
        cmd += ["-t", f"{dur:.2f}"]
    cmd += ["-vf", f"fps=3,scale={w}:-2,format=gray", "-f", "rawvideo", "-"]
    r = subprocess.run(cmd, capture_output=True)
    vw, vh, _ = sonda(video)
    h = int(round(w * (vh or 9) / (vw or 16) / 2)) * 2
    a = np.frombuffer(r.stdout, np.uint8)
    n = a.size // (w * h)
    if n < 4:
        return "vídeo curto demais para conferir"
    q = a[: n * w * h].reshape(n, h, w).astype(np.float32)
    var = q.std(axis=0)
    med = np.median(q, axis=0)
    gx = np.abs(np.diff(med, axis=1, prepend=med[:, :1]))
    gy = np.abs(np.diff(med, axis=0, prepend=med[:1, :]))
    borda = (gx + gy) > 45
    parado = var < 3.0
    if float(np.mean(var)) < 4.0:
        return ""  # cena quase parada inteira: não dá para separar logo de fundo; aceita
    fixo = borda & parado
    ch, cw = int(h * 0.2), int(w * 0.24)
    cantos = {"canto sup. esq.": fixo[:ch, :cw], "canto sup. dir.": fixo[:ch, -cw:], "canto inf. esq.": fixo[-ch:, :cw],
              "canto inf. dir.": fixo[-ch:, -cw:]}
    for nome, reg in cantos.items():
        if float(reg.mean()) > 0.012:
            return f"marca/logo no {nome}"
    faixa = fixo[int(h * 0.82):, int(w * 0.1): int(w * 0.9)]
    if float(faixa.mean()) > 0.02:
        return "texto/letreiro fixo embaixo"
    return ""


def _corta(origem, ini, dur, saida):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ini:.2f}", "-i", str(origem), "-t", f"{dur:.2f}", "-an",
                        "-vf", "scale='min(1920,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
                        str(saida)], capture_output=True)
    return r.returncode == 0 and Path(saida).exists()


def pexels(termo, tmp):
    chave = os.environ.get("PEXELS_API_KEY")
    if not chave:
        return None
    d = _json("https://api.pexels.com/videos/search?" + urllib.parse.urlencode({"query": termo, "orientation": "landscape", "per_page": 8}),
              {"Authorization": chave})
    for v in d.get("videos", []):
        arqs = sorted([f for f in v.get("video_files", []) if (f.get("width") or 0) >= (f.get("height") or 1) and (f.get("width") or 0) <= 1920],
                      key=lambda f: -(f.get("width") or 0))
        if arqs:
            f = _baixa(arqs[0]["link"], tmp / f"pexels_{v['id']}.mp4")
            return f, f"Pexels — {v.get('user', {}).get('name', '')} ({v.get('url', '')})"
    return None


def pixabay(termo, tmp):
    chave = os.environ.get("PIXABAY_API_KEY")
    if not chave:
        return None
    d = _json("https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": chave, "q": termo, "per_page": 8, "safesearch": "true"}))
    for v in d.get("hits", []):
        vids = v.get("videos", {})
        for k in ("large", "medium"):
            x = vids.get(k) or {}
            if x.get("url") and (x.get("width") or 0) >= (x.get("height") or 1):
                f = _baixa(x["url"], tmp / f"pixabay_{v['id']}.mp4")
                return f, f"Pixabay — {v.get('user', '')} ({v.get('pageURL', '')})"
    return None


def youtube(termo, tmp, segundos, log=print, cookies=None):
    """YouTube: primeiro Creative Commons; vídeo horizontal de 30 s a 40 min; pedaço do meio, sem marca"""
    sys.path.insert(0, str(TOOLS / "reels"))
    from reels import ytdlp
    vistos = set()
    for filtro, nome in (("&sp=EgIwAQ%253D%253D", "Creative Commons"), ("", "busca normal")):
        r = ytdlp(["--flat-playlist", "--dump-json", "--playlist-end", "12", "--extractor-args", "youtube:lang=pt",
                   "https://www.youtube.com/results?search_query=" + urllib.parse.quote(termo) + filtro], cookies)
        for linha in (r.stdout or "").splitlines():
            try:
                v = json.loads(linha)
            except ValueError:
                continue
            vid, d = v.get("id"), v.get("duration") or 0
            if not vid or vid in vistos or not (30 <= d <= 2400) or "/shorts/" in str(v.get("url", "")):
                continue
            if re.search(r"\b(react|reage|ao vivo|live|podcast|entrevista)\b", (v.get("title") or "").lower()):
                continue
            vistos.add(vid)
            # pedaços do meio do vídeo (pula abertura e encerramento); confere a marca em cada um
            for frac in (0.35, 0.55, 0.7):
                ini = max(8.0, d * frac)
                bruto = tmp / f"yt_{vid}_{int(ini)}.mp4"
                rr = ytdlp(["-f", "bv*[height<=1080][vcodec^=avc1]/bv*[height<=1080]/b[height<=1080]", "--download-sections",
                            f"*{ini:.0f}-{ini + segundos + 6:.0f}", "--force-keyframes-at-cuts", "-o", str(bruto),
                            f"https://www.youtube.com/watch?v={vid}"], cookies)
                if rr.returncode != 0 or not bruto.exists():
                    break
                w, h, dd = sonda(bruto)
                if w < h or dd < segundos:
                    bruto.unlink(missing_ok=True)
                    break  # vertical/curto: próximo vídeo
                motivo = tem_marca(bruto)
                if motivo:
                    log(f"      {v.get('title', '')[:50]}: {motivo} — tento outro")
                    bruto.unlink(missing_ok=True)
                    continue
                return bruto, f"YouTube ({nome}) — {v.get('channel') or v.get('uploader') or ''}: {v.get('title', '')} (https://youtu.be/{vid})"
    return None


def busca(termo, segundos=3.0, log=print, cookies=None):
    """o clipe de apoio pronto (horizontal, sem som, `segundos` + folga) e o crédito; None se não achou"""
    cache = pasta_cache()
    chave = hashlib.sha1(f"{termo.lower().strip()}|{segundos:.1f}".encode()).hexdigest()[:12]
    nome = re.sub(r"[^\w]+", "_", termo.lower())[:40]
    final = cache / f"{nome}_{chave}.mp4"
    cred_f = final.with_suffix(".txt")
    if final.exists() and cred_f.exists():
        return final, cred_f.read_text(encoding="utf-8")
    tmp = cache / "tmp"
    tmp.mkdir(exist_ok=True)
    for fonte in (pexels, pixabay):
        try:
            r = fonte(termo, tmp)
        except Exception as e:
            log(f"      {fonte.__name__}: {str(e)[:100]}")
            r = None
        if r:
            f, cred = r
            _, _, dd = sonda(f)
            if _corta(f, max(0.0, dd * 0.3 if dd > segundos * 3 else 0.0), segundos + 1.0, final):
                cred_f.write_text(cred, encoding="utf-8")
                Path(f).unlink(missing_ok=True)
                return final, cred
    try:
        r = youtube(termo, tmp, segundos, log, cookies)
    except Exception as e:
        log(f"      YouTube: {str(e)[:100]}")
        r = None
    if r:
        f, cred = r
        if _corta(f, 2.0, segundos + 1.0, final):
            cred_f.write_text(cred, encoding="utf-8")
            Path(f).unlink(missing_ok=True)
            return final, cred
    return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="cena de apoio da internet (teste)")
    ap.add_argument("termo")
    ap.add_argument("--segundos", type=float, default=3.0)
    a = ap.parse_args()
    print(busca(a.termo, a.segundos))
