# -*- coding: utf-8 -*-
"""Procura uma imagem na internet ATÉ ACHAR e baixa (fotos de jogador, camisas, escudos...).

    python tools/busca_imagem.py "camisa 3 Flamengo 2026" [--exige flamengo,camisa] [--rosto]

Fontes, nesta ordem: Bing Imagens → DuckDuckGo → Wikimedia Commons → Openverse.
Só aceita a imagem quando o título/endereço cita as palavras exigidas (o time, o sobrenome do
jogador); com --rosto, a foto precisa ter UM rosto (YuNet) e é recortada no rosto/ombros.
Cache em tools/banco/web/ (a mesma busca não baixa de novo).
"""
import hashlib
import html
import json
import re
import subprocess
import sys
import unicodedata
import urllib.parse
from pathlib import Path

PONTE = Path(__file__).resolve().parents[1]
CACHE = PONTE / "tools" / "banco" / "web"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
RUIM = re.compile(r"logo|vector|clipart|cartoon|desenho|wallpaper|fifa\s?\d|pes\s?\d|efootball|figurinha|sticker|meme|montagem|png\s?tree", re.I)


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def pegar(url, binario=False, ref=""):
    """GET com cara de navegador (curl_cffi se instalado; senão curl)."""
    try:
        from curl_cffi import requests as cr
        r = cr.get(url, impersonate="chrome", timeout=25, headers={"Referer": ref} if ref else None)
        if r.status_code == 200:
            return r.content if binario else r.text
    except Exception:  # noqa: BLE001
        pass
    cmd = ["curl", "-sSL", "-m", "25", "-A", UA, "-H", "Accept-Language: pt-BR,pt;q=0.9,en;q=0.8"]
    if ref:
        cmd += ["-H", f"Referer: {ref}"]
    r = subprocess.run(cmd + [url], capture_output=True)
    if r.returncode != 0:
        return b"" if binario else ""
    return r.stdout if binario else r.stdout.decode("utf-8", "replace")


def bing(q):
    h = pegar("https://www.bing.com/images/search?form=HDRSC2&first=1&q=" + urllib.parse.quote(q))
    out = []
    for m in re.finditer(r'\bm="(\{[^"]+\})"', h or ""):
        try:
            d = json.loads(html.unescape(m.group(1)))
        except json.JSONDecodeError:
            continue
        if d.get("murl"):
            out.append({"url": d["murl"], "titulo": d.get("t", ""), "pagina": d.get("purl", ""), "fonte": "Bing"})
    return out


def duckduckgo(q):
    h = pegar("https://duckduckgo.com/?iax=images&ia=images&q=" + urllib.parse.quote(q))
    m = re.search(r'vqd=["\']?([\d-]+)', h or "")
    if not m:
        return []
    j = pegar(f"https://duckduckgo.com/i.js?l=br-pt&o=json&f=,,,,,&p=1&vqd={m.group(1)}&q=" + urllib.parse.quote(q),
              ref="https://duckduckgo.com/")
    try:
        res = json.loads(j).get("results", [])
    except (json.JSONDecodeError, AttributeError):
        return []
    return [{"url": r.get("image", ""), "titulo": r.get("title", ""), "pagina": r.get("url", ""), "fonte": "DuckDuckGo",
             "w": r.get("width", 0), "h": r.get("height", 0)} for r in res if r.get("image")]


def commons(q):
    u = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=20"
         "&prop=imageinfo&iiprop=url|size&iiurlwidth=1200&gsrsearch=" + urllib.parse.quote(q))
    try:
        pages = json.loads(pegar(u) or "{}").get("query", {}).get("pages", {})
    except json.JSONDecodeError:
        return []
    out = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("thumburl") or ii.get("url"):
            out.append({"url": ii.get("thumburl") or ii["url"], "titulo": p.get("title", ""), "pagina": ii.get("descriptionurl", ""),
                        "fonte": "Wikimedia Commons", "w": ii.get("width", 0), "h": ii.get("height", 0)})
    return out


def openverse(q):
    try:
        d = json.loads(pegar("https://api.openverse.org/v1/images/?page_size=20&q=" + urllib.parse.quote(q)) or "{}")
    except json.JSONDecodeError:
        return []
    return [{"url": r["url"], "titulo": r.get("title", ""), "pagina": r.get("foreign_landing_url", ""), "fonte": "Openverse",
             "w": r.get("width", 0), "h": r.get("height", 0)} for r in d.get("results", []) if r.get("url")]


FONTES = [bing, duckduckgo, commons, openverse]


def um_rosto(img):
    """Recorte de rosto+ombros quando há exatamente um rosto; senão None."""
    import cv2
    modelo = PONTE / "yunet.onnx"
    if not modelo.exists():
        return img
    h, w = img.shape[:2]
    det = cv2.FaceDetectorYN.create(str(modelo), "", (w, h), 0.7)
    _, faces = det.detect(img)
    if faces is None or len(faces) != 1:
        return None
    x, y, fw, fh = faces[0][:4]
    if fw < 40:
        return None
    lado = int(fw * 2.6)
    cx, cy = x + fw / 2, y + fh * 0.75
    x0, y0 = int(max(0, cx - lado / 2)), int(max(0, cy - lado * 0.42))
    x1, y1 = int(min(w, x0 + lado)), int(min(h, y0 + lado))
    return img[y0:y1, x0:x1]


def buscar(q, exige=(), rosto=False, destino=None, minimo=300, log=print):
    """Devolve {file, fonte, titulo, pagina} ou None. Tenta todas as fontes até achar."""
    import cv2
    import numpy as np
    exige = [norm(e) for e in exige if norm(e)]
    chave = hashlib.sha1(f"{q}|{','.join(exige)}|{rosto}".encode()).hexdigest()[:16]
    CACHE.mkdir(parents=True, exist_ok=True)
    meta = CACHE / f"{chave}.json"
    if meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        if Path(m.get("file", "")).exists():
            return m
    for fonte in FONTES:
        try:
            cands = fonte(q)
        except Exception as e:  # noqa: BLE001
            log(f"  {fonte.__name__}: {e}")
            continue
        for c in cands[:25]:
            texto = norm(f"{c['titulo']} {c['pagina']} {urllib.parse.unquote(c['url'])}")
            if exige and not all(re.search(rf"\b{re.escape(e)}", texto) for e in exige):
                continue
            if RUIM.search(c["titulo"] or ""):
                continue
            dado = pegar(c["url"], binario=True, ref=c.get("pagina", ""))
            if not dado or len(dado) < 5000:
                continue
            img = cv2.imdecode(np.frombuffer(dado, np.uint8), cv2.IMREAD_COLOR)
            if img is None or min(img.shape[:2]) < minimo:
                continue
            if rosto:
                img = um_rosto(img)
                if img is None or min(img.shape[:2]) < 120:
                    continue
            if max(img.shape[:2]) > 1400:
                k = 1400 / max(img.shape[:2])
                img = cv2.resize(img, (int(img.shape[1] * k), int(img.shape[0] * k)), interpolation=cv2.INTER_AREA)
            out = Path(destino) if destino else CACHE / f"{chave}.jpg"
            out.parent.mkdir(parents=True, exist_ok=True)
            ok, buf = cv2.imencode(out.suffix or ".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90] if out.suffix != ".webp" else [cv2.IMWRITE_WEBP_QUALITY, 85])
            if not ok:
                continue
            out.write_bytes(buf.tobytes())
            m = {"file": str(out), "fonte": c["fonte"], "titulo": c["titulo"], "pagina": c["pagina"], "busca": q}
            meta.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
            return m
    return None


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("busca")
    ap.add_argument("--exige", default="")
    ap.add_argument("--rosto", action="store_true")
    a = ap.parse_args()
    r = buscar(a.busca, [x for x in a.exige.split(",") if x], a.rosto)
    print(json.dumps(r, ensure_ascii=False, indent=1) if r else "Nada encontrado.")
    sys.exit(0 if r else 1)
