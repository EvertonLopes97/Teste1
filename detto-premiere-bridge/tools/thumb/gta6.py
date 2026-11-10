# -*- coding: utf-8 -*-
"""THUMB DO CANAL DE GTA 6 (10/nov, "as thumbs estão ruins").

O que estava errado (renderizei e olhei): quadro escuro e borrado, com a LEGENDA de outro canal queimada no meio,
texto pequeno brigando com o que havia no quadro, metade da área escurecida e uma faixa com o nome do canal
gastando o rodapé. O que os canais grandes de GTA fazem (Gigaton, SaninPlay, Dulebio): o JOGO em tela cheia, com
cor viva; 2 linhas GIGANTES (a 1ª branca, a 2ª amarela) com contorno preto grosso; um número quando existe; e uma
seta/aro vermelho no que importa. Nada de faixa de canal.

Feito em PIL (sem Chromium): é rápido e funciona sempre.
"""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
FONTES = PONTE / "fonts"
W, H = 1280, 720


def _fonte(tam):
    from PIL import ImageFont
    for nome in ("Anton-Regular.ttf", "Inter-ExtraBold.otf"):
        f = FONTES / nome
        if f.exists():
            return ImageFont.truetype(str(f), tam)
    return ImageFont.load_default()


def _quadro(video, t, saida):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t):.2f}", "-i", str(video), "-frames:v", "1",
                    "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", "-q:v", "2", str(saida)],
                   capture_output=True)
    return Path(saida) if Path(saida).exists() else None


def _vivo(img):
    """cor de thumb: mais saturação e contraste, e nitidez (o quadro de vídeo sai lavado)"""
    from PIL import ImageEnhance, ImageFilter
    img = ImageEnhance.Color(img).enhance(1.35)
    img = ImageEnhance.Contrast(img).enhance(1.12)
    img = ImageEnhance.Brightness(img).enhance(1.04)
    return img.filter(ImageFilter.UnsharpMask(radius=2, percent=110, threshold=2))


def _sujeito(img):
    """(cx, cy, raio) do personagem: rosto (YuNet) ou corpo (HOG); None se não há"""
    try:
        import cv2
        import numpy as np
        a = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        sys.path.insert(0, str(AQUI))
        from viral import _caixa_rosto
        c = _caixa_rosto(a)
        if c and c[3] > H * 0.06:
            x, y, w, h = c
            return (x + w / 2, y + h / 2, max(w, h) * 0.95)
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        cs, pesos = hog.detectMultiScale(a, winStride=(8, 8), scale=1.05)
        bons = [c for c, p in zip(cs, list(pesos)) if float(p) > 1.0 and c[3] > H * 0.25]
        if bons:
            x, y, w, h = max(bons, key=lambda b: b[2] * b[3])
            return (x + w / 2, y + h * 0.35, max(w, h * 0.5) * 0.7)
    except Exception:  # noqa: BLE001
        pass
    return None


def _linhas(texto, destaque):
    t = " ".join(texto.upper().split())
    d = " ".join((destaque or "").upper().split())
    if d and d in t:
        a = t.replace(d, "").strip(" -:") or t
        return [a, d]
    ws = t.split()
    if len(ws) <= 2:
        return [t]
    meio = (len(ws) + 1) // 2
    return [" ".join(ws[:meio]), " ".join(ws[meio:])]


def desenha(quadro_jpg, texto, destaque, saida, lado="esq"):
    from PIL import Image, ImageDraw
    img = _vivo(Image.open(quadro_jpg).convert("RGB").resize((W, H)))
    suj = _sujeito(img)
    # o texto vai no lado OPOSTO ao personagem
    if suj:
        lado = "dir" if suj[0] < W * 0.45 else "esq"
    # sombra suave só atrás do texto
    grad = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(grad)
    for x in range(W):
        f = x / W if lado == "dir" else 1 - x / W
        gd.line([(x, 0), (x, H)], fill=int(170 * max(0.0, f - 0.35) / 0.65))
    preto = Image.new("RGB", (W, H), (0, 0, 0))
    img = Image.composite(preto, img, grad)
    d = ImageDraw.Draw(img)
    linhas = _linhas(texto, destaque)[:2]
    larg_max = W * 0.62
    tam = 210
    while tam > 70:
        f = _fonte(tam)
        if all(d.textlength(l, font=f) <= larg_max for l in linhas) and tam * 1.05 * len(linhas) <= H * 0.78:
            break
        tam -= 6
    f = _fonte(tam)
    alt_l = int(tam * 1.04)
    y = int((H - alt_l * len(linhas)) / 2) - 10
    for i, l in enumerate(linhas):
        lw = d.textlength(l, font=f)
        x = 40 if lado == "esq" else int(W - 40 - lw)
        cor = (255, 255, 255) if (i == 0 and len(linhas) > 1) else (255, 212, 0)
        d.text((x + 8, y + 10), l, font=f, fill=(0, 0, 0), stroke_width=12, stroke_fill=(0, 0, 0))
        d.text((x, y), l, font=f, fill=cor, stroke_width=10, stroke_fill=(0, 0, 0))
        y += alt_l
    if suj:   # aro vermelho no personagem
        cx, cy, r = suj
        r = min(max(r, 70), 200)
        for k in range(10):
            d.ellipse([cx - r - k, cy - r - k, cx + r + k, cy + r + k], outline=(230, 20, 30))
    img.save(saida, quality=93)
    return Path(saida)


def thumb_gta6(pasta, video, faixas, texto, destaque, log=print, n=3):
    """devolve as thumbs (a 1ª é a principal)"""
    sys.path.insert(0, str(AQUI))
    from viral import melhores_quadros
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    tempos = melhores_quadros(video, faixas, n=n)
    out = []
    for i, t in enumerate(tempos):
        q = _quadro(video, t, pasta / f"_q{i}.jpg")
        if q:
            out.append(desenha(q, texto, destaque, pasta / f"gta6_{i + 1}.jpg"))
    log(f"thumb GTA 6: {len(out)} pronta(s) — \"{texto}\" ({destaque or '-'})")
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("texto")
    ap.add_argument("--destaque", default="")
    ap.add_argument("--saida", default="thumbs_gta6")
    a = ap.parse_args()
    print(thumb_gta6(a.saida, a.video, None, a.texto, a.destaque))
