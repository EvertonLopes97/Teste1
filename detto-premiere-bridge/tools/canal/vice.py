"""O CENÁRIO VICE CITY desenhado por código — a cara que TODO canal grande de GTA 6 usa.

Olhei os três maiores (SanInPlay 1,36 mi · GameplayRJ 8,59 mi · NobertoGamer 85 mil) e a receita é sempre a
mesma: céu rosa→laranja de pôr do sol, sol listrado, coqueiros pretos em silhueta, skyline de Miami no
horizonte, água refletindo, grão de filme por cima e o nome em letra condensada com franja ciano/magenta
(aberração cromática). Aqui isso é feito em PIL, sem baixar nada e sem usar NADA da Rockstar.

Usado pelo marca.py (banner, perfil, emblema, molde de thumb) e pode servir para qualquer peça do canal.
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFilter

# a paleta medida nos banners deles
ROSA = (255, 45, 120)
ROSA_CLARO = (255, 120, 150)
LARANJA = (255, 150, 50)
AMARELO_SOL = (255, 220, 90)
ROXO = (90, 30, 120)
ROXO_ESCURO = (26, 10, 44)
CIANO = (60, 240, 255)
MAGENTA = (255, 60, 200)
NOITE = (18, 8, 32)


def _mistura(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def ceu(w, h, horizonte=0.62):
    """o degradê do pôr do sol: roxo no alto → rosa → laranja → amarelo no horizonte"""
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    hy = int(h * horizonte)
    paradas = [(0.0, ROXO_ESCURO), (0.30, (160, 40, 120)), (0.58, ROSA), (0.85, LARANJA), (1.0, AMARELO_SOL)]
    for y in range(hy):
        t = y / max(1, hy - 1)
        for i in range(len(paradas) - 1):
            a, ca = paradas[i]
            b, cb = paradas[i + 1]
            if a <= t <= b:
                d.line((0, y, w, y), fill=_mistura(ca, cb, (t - a) / (b - a)))
                break
    # a água: o céu espelhado e mais escuro, com faixas de brilho
    for y in range(hy, h):
        t = (y - hy) / max(1, h - hy)
        d.line((0, y, w, y), fill=_mistura(_mistura(LARANJA, ROSA, t), ROXO_ESCURO, 0.25 + 0.5 * t))
    return img


def sol(img, cx, cy, raio, bandas=10):
    """o sol retrô: disco amarelo→rosa cortado por faixas horizontais que engrossam para baixo"""
    w, h = img.size
    cam = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    for i in range(raio * 2):
        t = i / max(1, raio * 2 - 1)
        y = cy - raio + i
        meia = math.sqrt(max(0.0, raio * raio - (y - cy) ** 2))
        d.line((cx - meia, y, cx + meia, y), fill=_mistura(AMARELO_SOL, ROSA, t) + (255,))
    # as fatias: do MEIO do disco para baixo, engrossando (o corte clássico do sol synthwave)
    for i in range(bandas):
        t = (i + 0.5) / bandas
        y = cy - raio * 0.40 + (raio * 1.30) * t
        alt = 3 + 20 * (t ** 1.8)
        d.rectangle((cx - raio - 4, y, cx + raio + 4, y + alt), fill=(0, 0, 0, 0))
    img.paste(Image.alpha_composite(img.convert("RGBA"), cam).convert("RGB"), (0, 0))
    return img


def skyline(img, base_y, cor=(40, 14, 58), densidade=26, altura_max=0.26, janelas=True, semente=7):
    """a linha de prédios no horizonte, com janelas acesas"""
    w, h = img.size
    r = random.Random(semente)
    d = ImageDraw.Draw(img)
    x = -40
    while x < w:
        lg = r.randint(60, 190)
        al = int(h * altura_max * r.uniform(0.25, 1.0))
        topo = base_y - al
        d.rectangle((x, topo, x + lg, base_y), fill=cor)
        if r.random() < 0.3:    # antena
            d.line((x + lg // 2, topo, x + lg // 2, topo - r.randint(20, 70)), fill=cor, width=5)
        if janelas:
            jc = _mistura(cor, AMARELO_SOL, 0.55)
            for jy in range(topo + 16, base_y - 10, 26):
                for jx in range(x + 12, x + lg - 12, 22):
                    if r.random() < 0.45:
                        d.rectangle((jx, jy, jx + 7, jy + 11), fill=jc)
        x += lg + r.randint(8, 30)
    return img


def coqueiro(img, x, base_y, altura, cor=(16, 6, 26), inclina=0.18, folhas=9, semente=3):
    """um coqueiro em silhueta: tronco curvo cheio + folhas em forma de FOLHA (não de pente)"""
    d = ImageDraw.Draw(img)
    r = random.Random(semente)
    topo_x = x + altura * inclina
    topo_y = base_y - altura

    def no_tronco(t):
        return (x + (topo_x - x) * (t ** 1.7), base_y + (topo_y - base_y) * t)

    # tronco: um polígono só (a corrente de bolinhas ficava com cara de zíper)
    esq, dire = [], []
    for i in range(34):
        t = i / 33
        px, py = no_tronco(t)
        gr = altura * 0.034 * (1 - t * 0.62)
        esq.append((px - gr, py))
        dire.append((px + gr, py))
    d.polygon(esq + dire[::-1], fill=cor)
    for i in range(7):   # os anéis do tronco
        t = 0.1 + i * 0.12
        px, py = no_tronco(t)
        gr = altura * 0.034 * (1 - t * 0.62)
        d.line((px - gr, py, px + gr, py - gr * 0.5), fill=_mistura(cor, (255, 255, 255), 0.10), width=max(1, int(altura * 0.006)))

    for k in range(folhas):
        ang = math.pi * (1.02 + 0.96 * (k / max(1, folhas - 1)))   # do lado esquerdo ao direito, por cima
        comp = altura * r.uniform(0.38, 0.56)
        queda = altura * r.uniform(0.16, 0.34)
        # a NERVURA da folha
        eixo = []
        for i in range(20):
            t = i / 19
            fx = topo_x + math.cos(ang) * comp * t
            fy = topo_y + math.sin(ang) * comp * t * 0.5 + queda * (t ** 2.2)
            eixo.append((fx, fy))
        # a folha é um polígono em volta da nervura, gordo no meio e fino nas pontas
        larg = altura * r.uniform(0.055, 0.075)
        a, b = [], []
        for i, (fx, fy) in enumerate(eixo):
            t = i / 19
            e = larg * math.sin(math.pi * min(1.0, t * 1.15)) ** 0.7
            nx, ny = -math.sin(ang) * e, math.cos(ang) * e * 0.55 + e * 0.45
            a.append((fx + nx, fy + ny))
            b.append((fx - nx, fy - ny))
        d.polygon(a + b[::-1], fill=cor)
    d.ellipse((topo_x - altura * 0.045, topo_y - altura * 0.045, topo_x + altura * 0.045, topo_y + altura * 0.045), fill=cor)
    return img


def grao(img, forca=14, semente=11):
    """o grão de filme que todos eles põem por cima (tira o ar de 'feito no computador')"""
    w, h = img.size
    r = random.Random(semente)
    ruido = Image.new("L", (w // 2, h // 2))
    ruido.putdata([128 + int(r.gauss(0, forca)) for _ in range(ruido.width * ruido.height)])
    ruido = ruido.resize((w, h), Image.BILINEAR)
    return Image.blend(img, Image.merge("RGB", (ruido, ruido, ruido)), 0.10)


def brilho(img, forca=0.55, raio=26):
    """o brilho (bloom) dos neons"""
    b = img.filter(ImageFilter.GaussianBlur(raio))
    return Image.blend(img, Image.blend(img, b, 0.9), forca * 0.5)


def texto_neon(d, xy, txt, f, cor=(255, 255, 255), franja=7, contorno=0, ancora="mm"):
    """a letra com franja ciano de um lado e magenta do outro (a 'aberração cromática' deles)"""
    x, y = xy
    d.text((x - franja, y), txt, font=f, fill=CIANO, anchor=ancora)
    d.text((x + franja, y), txt, font=f, fill=MAGENTA, anchor=ancora)
    if contorno:
        d.text((x, y), txt, font=f, fill=cor, anchor=ancora, stroke_width=contorno, stroke_fill=(10, 4, 20))
    else:
        d.text((x, y), txt, font=f, fill=cor, anchor=ancora)


def cena(w, h, horizonte=0.62, com_sol=True, com_skyline=True, coqueiros=True, semente=7):
    """o fundo completo: céu + sol + skyline + água + coqueiros + grão"""
    img = ceu(w, h, horizonte)
    hy = int(h * horizonte)
    if com_sol:
        sol(img, w // 2, int(hy - h * 0.14), int(h * 0.25))   # bem acima do horizonte: as fatias têm que APARECER
    if com_skyline:
        skyline(img, hy, densidade=26, altura_max=0.22, semente=semente)
    # reflexo da cidade na água
    faixa = img.crop((0, int(hy - h * 0.20), w, hy)).transpose(Image.FLIP_TOP_BOTTOM)
    faixa = faixa.filter(ImageFilter.GaussianBlur(6))
    img.paste(Image.blend(img.crop((0, hy, w, hy + faixa.height)), faixa, 0.35), (0, hy))
    d = ImageDraw.Draw(img)
    for i in range(14):   # a ondulação da água
        y = hy + int((i + 1) ** 1.7 * h * 0.004)
        if y < h:
            d.line((0, y, w, y), fill=_mistura(ROSA_CLARO, ROXO_ESCURO, i / 14), width=max(1, i // 5))
    if coqueiros:
        base = hy + int(h * 0.02)
        coqueiro(img, int(w * 0.055), base, int(h * 0.80), inclina=0.10, semente=1)
        coqueiro(img, int(w * 0.165), base - int(h * 0.04), int(h * 0.52), inclina=-0.14, semente=2)
        coqueiro(img, int(w * 0.945), base, int(h * 0.84), inclina=-0.12, semente=4)
        coqueiro(img, int(w * 0.835), base - int(h * 0.05), int(h * 0.50), inclina=0.16, semente=5)
    return grao(img)
