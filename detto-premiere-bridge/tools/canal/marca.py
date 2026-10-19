# -*- coding: utf-8 -*-
"""IDENTIDADE dos canais do YouTube: banner, foto de perfil, marca d'água e molde de thumb.

    python tools\\canal\\marca.py                       → os dois canais (notícias e vlogs) em E:\\DETTO\\marca\\
    python tools\\canal\\marca.py --noticias "GALO NOTÍCIAS" --vlogs "DETTO VLOG" --foto "eu.jpg" --saida "pasta"

Tamanhos do YouTube: banner 2560x1440 (área que aparece em TODOS os aparelhos: 1546x423 no meio — o texto fica
nela), foto de perfil 800x800 (aparece redonda), marca d'água 150x150 (PNG transparente), thumb 1280x720.
Sem escudo oficial do clube (canal de torcedor não pode parecer o oficial do Atlético).
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = Path(__file__).resolve().parent
FONTES = AQUI.parent.parent / "fonts"
AMARELO, PRETO, BRANCO, LIMA = (255, 212, 0), (12, 12, 12), (245, 245, 245), (200, 255, 61)


def fonte(tam, nome="Anton-Regular.ttf"):
    return ImageFont.truetype(str(FONTES / nome), tam)


def listras(w, h, cor1=(18, 18, 18), cor2=(28, 28, 28), passo=46):
    """listras diagonais pretas (as do Galo, discretas) — o mesmo fundo do vídeo do canal"""
    img = Image.new("RGB", (w, h), cor1)
    d = ImageDraw.Draw(img)
    for x in range(-h, w + h, passo * 2):
        d.polygon([(x, 0), (x + passo, 0), (x + passo + h, h), (x + h, h)], fill=cor2)
    return img


def texto_centro(d, xy, txt, f, cor, contorno=0, cor_contorno=PRETO):
    d.text(xy, txt, font=f, fill=cor, anchor="mm", stroke_width=contorno, stroke_fill=cor_contorno)


def encaixa(d, txt, nome, maximo, larg):
    """maior tamanho de fonte que cabe na largura"""
    t = maximo
    while t > 20 and d.textlength(txt, font=fonte(t, nome)) > larg:
        t -= 4
    return fonte(t, nome)


def foto_recortada(foto, tam):
    """sua foto em círculo (rosto no centro, quadrado do meio)"""
    im = Image.open(foto).convert("RGB")
    w, h = im.size
    lado = min(w, h)
    im = im.crop(((w - lado) // 2, max(0, (h - lado) // 3), (w - lado) // 2 + lado, max(0, (h - lado) // 3) + lado)).resize((tam, tam))
    m = Image.new("L", (tam, tam), 0)
    ImageDraw.Draw(m).ellipse((0, 0, tam, tam), fill=255)
    out = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    out.paste(im, (0, 0), m)
    return out


def galo_noticias(nome, saida):
    saida.mkdir(parents=True, exist_ok=True)
    palavras = nome.split()
    sigla = "".join(p[0] for p in palavras[:2]).upper()
    # banner
    W, H = 2560, 1440
    img = listras(W, H)
    d = ImageDraw.Draw(img)
    sx, sy, sw, sh = (W - 1546) // 2, (H - 423) // 2, 1546, 423
    d.rectangle((0, sy - 60, W, sy - 50), fill=AMARELO)
    d.rectangle((0, sy + sh + 50, W, sy + sh + 60), fill=AMARELO)
    f = encaixa(d, nome.upper(), "Anton-Regular.ttf", 210, sw - 120)
    texto_centro(d, (W // 2, sy + 165), nome.upper(), f, AMARELO, 6)
    texto_centro(d, (W // 2, sy + 300), "AS NOTÍCIAS DO GALO NA VOZ DO TORCEDOR", fonte(64, "Inter-ExtraBold.otf"), BRANCO)
    texto_centro(d, (W // 2, sy + 380), "VÍDEO NOVO TODO DIA  •  ATIVE O SININHO", fonte(44, "Inter-Bold.otf"), AMARELO)
    img.save(saida / "banner_2560x1440.png")
    # conferência da área segura
    g = img.copy()
    ImageDraw.Draw(g).rectangle((sx, sy, sx + sw, sy + sh), outline=(255, 0, 0), width=6)
    g.resize((1280, 720)).save(saida / "banner_conferir_area_segura.jpg", quality=88)
    # foto de perfil
    P = 800
    av = listras(P, P, passo=30)
    da = ImageDraw.Draw(av)
    da.ellipse((40, 40, P - 40, P - 40), outline=AMARELO, width=26)
    texto_centro(da, (P // 2, P // 2 - 30), sigla, fonte(360), AMARELO, 8)
    texto_centro(da, (P // 2, P // 2 + 200), "NOTÍCIAS", fonte(86), BRANCO, 4)
    av.save(saida / "perfil_800x800.png")
    # marca d'água
    M = 150
    wm = Image.new("RGBA", (M, M), (0, 0, 0, 0))
    dw = ImageDraw.Draw(wm)
    dw.ellipse((4, 4, M - 4, M - 4), fill=(12, 12, 12, 230), outline=AMARELO + (255,), width=6)
    texto_centro(dw, (M // 2, M // 2 - 4), sigla, fonte(70), AMARELO)
    wm.save(saida / "marca_dagua_150x150.png")
    # molde de thumb (o thumb.py usa o mesmo estilo: texto Anton amarelo/branco + rosto recortado)
    th = listras(1280, 720, passo=28)
    dt_ = ImageDraw.Draw(th)
    dt_.rectangle((0, 610, 1280, 720), fill=AMARELO)
    texto_centro(dt_, (640, 665), nome.upper(), fonte(70), PRETO)
    texto_centro(dt_, (420, 250), "MANCHETE", fonte(150), BRANCO, 6)
    texto_centro(dt_, (420, 420), "AQUI", fonte(150), AMARELO, 6)
    th.save(saida / "thumb_molde_1280x720.png")
    return saida


def vlog(nome, saida, foto=None):
    saida.mkdir(parents=True, exist_ok=True)
    W, H = 2560, 1440
    if foto:
        base = Image.open(foto).convert("RGB")
        bw, bh = base.size
        esc = max(W / bw, H / bh)
        base = base.resize((int(bw * esc), int(bh * esc)))
        base = base.crop(((base.width - W) // 2, (base.height - H) // 2, (base.width - W) // 2 + W, (base.height - H) // 2 + H))
        img = Image.blend(base.filter(ImageFilter.GaussianBlur(40)), Image.new("RGB", (W, H), (10, 10, 10)), 0.7)
    else:
        img = Image.new("RGB", (W, H), (14, 14, 14))
    d = ImageDraw.Draw(img)
    sx, sy, sw, sh = (W - 1546) // 2, (H - 423) // 2, 1546, 423
    f = encaixa(d, nome.upper(), "Anton-Regular.ttf", 240, sw - 120)
    texto_centro(d, (W // 2, sy + 150), nome.upper(), f, BRANCO, 6)
    larg = d.textlength(nome.upper(), font=f)
    d.rectangle((W // 2 - larg // 2, sy + 262, W // 2 + larg // 2, sy + 276), fill=LIMA)
    texto_centro(d, (W // 2, sy + 340), "O DIA A DIA DO DETTO  •  FUTEBOL, RESENHA E BH", fonte(56, "Inter-ExtraBold.otf"), LIMA)
    img.save(saida / "banner_2560x1440.png")
    g = img.copy()
    ImageDraw.Draw(g).rectangle((sx, sy, sx + sw, sy + sh), outline=(255, 0, 0), width=6)
    g.resize((1280, 720)).save(saida / "banner_conferir_area_segura.jpg", quality=88)
    P = 800
    av = Image.new("RGB", (P, P), (14, 14, 14))
    if foto:
        av.paste(foto_recortada(foto, P - 60), (30, 30), foto_recortada(foto, P - 60))
        ImageDraw.Draw(av).ellipse((22, 22, P - 22, P - 22), outline=LIMA, width=18)
    else:
        da = ImageDraw.Draw(av)
        da.ellipse((40, 40, P - 40, P - 40), outline=LIMA, width=26)
        texto_centro(da, (P // 2, P // 2), "DV", fonte(380), LIMA, 6)
    av.save(saida / "perfil_800x800.png")
    M = 150
    wm = Image.new("RGBA", (M, M), (0, 0, 0, 0))
    dw = ImageDraw.Draw(wm)
    dw.ellipse((4, 4, M - 4, M - 4), fill=(12, 12, 12, 230), outline=LIMA + (255,), width=6)
    texto_centro(dw, (M // 2, M // 2 - 4), "DV", fonte(72), LIMA)
    wm.save(saida / "marca_dagua_150x150.png")
    return saida


def main():
    ap = argparse.ArgumentParser(description="banner, perfil e marca d'água dos canais")
    ap.add_argument("--noticias", default="GALO NOTÍCIAS")
    ap.add_argument("--vlogs", default="DETTO VLOG")
    ap.add_argument("--foto", help="sua foto (rosto) para o canal de vlogs")
    ap.add_argument("--saida", default=r"E:\DETTO\marca")
    a = ap.parse_args()
    s = Path(a.saida)
    print(galo_noticias(a.noticias, s / "noticias"))
    print(vlog(a.vlogs, s / "vlogs", a.foto))


if __name__ == "__main__":
    main()
