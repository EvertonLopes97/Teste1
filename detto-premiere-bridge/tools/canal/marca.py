# -*- coding: utf-8 -*-
"""IDENTIDADE dos canais do YouTube: banner, foto de perfil, marca d'água, moldes de thumb e os textos do canal.

    python tools\\canal\\marca.py                           → os dois canais em E:\\DETTO\\marca\\
    python tools\\canal\\marca.py --foto "eu.jpg"            → com a sua foto no canal Everton Lopes
    python tools\\canal\\marca.py --saida "pasta"

Canais (20/out):
  DETTO GALO NOTÍCIAS — notícias do Galo (imprensa + a resenha do Detto)   → <saida>\\noticias\\
  EVERTON LOPES       — vlogs, gameplays e outros vídeos                  → <saida>\\everton_lopes\\

Tamanhos do YouTube: banner 2560x1440 (área que aparece em TODOS os aparelhos: 1546x423 no meio — o texto fica
nela), foto de perfil 800x800 (aparece redonda), marca d'água 150x150 (PNG transparente), thumb 1280x720.
Sem escudo oficial do clube (canal de torcedor não pode parecer o oficial do Atlético).
Cada pasta ganha também CANAL.txt: nome, @, descrição, palavras-chave, playlists, links e o padrão de envio.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = Path(__file__).resolve().parent
FONTES = AQUI.parent.parent / "fonts"
AMARELO, PRETO, BRANCO, LIMA = (255, 212, 0), (12, 12, 12), (245, 245, 245), (200, 255, 61)
ROXO, VERMELHO, CINZA = (150, 90, 255), (230, 40, 45), (150, 150, 150)
W, H = 2560, 1440
SX, SY, SW, SH = (W - 1546) // 2, (H - 423) // 2, 1546, 423  # área segura do banner


def fonte(tam, nome="Anton-Regular.ttf"):
    return ImageFont.truetype(str(FONTES / nome), tam)


def listras(w, h, cor1=(18, 18, 18), cor2=(28, 28, 28), passo=46):
    """listras diagonais pretas (as do Galo, discretas) — o mesmo fundo do vídeo do canal"""
    img = Image.new("RGB", (w, h), cor1)
    d = ImageDraw.Draw(img)
    for x in range(-h, w + h, passo * 2):
        d.polygon([(x, 0), (x + passo, 0), (x + passo + h, h), (x + h, h)], fill=cor2)
    return img


def degrade(w, h, c1, c2, vertical=False):
    g = Image.linear_gradient("L").resize((w, h) if vertical else (h, w))
    if not vertical:
        g = g.rotate(90, expand=True)
    return Image.composite(Image.new("RGB", (w, h), c2), Image.new("RGB", (w, h), c1), g)


def vinheta(img, forca=0.75):
    w, h = img.size
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).ellipse((-w * 0.15, -h * 0.25, w * 1.15, h * 1.25), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(min(w, h) // 5))
    escuro = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(img, Image.blend(img, escuro, forca), m)


def texto_centro(d, xy, txt, f, cor, contorno=0, cor_contorno=PRETO):
    d.text(xy, txt, font=f, fill=cor, anchor="mm", stroke_width=contorno, stroke_fill=cor_contorno)


def encaixa(d, txt, nome, maximo, larg):
    """maior tamanho de fonte que cabe na largura"""
    t = maximo
    while t > 20 and d.textlength(txt, font=fonte(t, nome)) > larg:
        t -= 4
    return fonte(t, nome)


def pilula(d, cx, cy, txt, f, fundo, cor, pad=34, contorno=None):
    lw = d.textlength(txt, font=f)
    a = f.size // 2 + 18
    caixa = (cx - lw / 2 - pad, cy - a, cx + lw / 2 + pad, cy + a)
    d.rounded_rectangle(caixa, radius=a, fill=fundo, outline=contorno, width=6 if contorno else 0)
    texto_centro(d, (cx, cy + 2), txt, f, cor)
    return caixa


def icone_camera(d, cx, cy, t, cor):
    """câmera (vlog) desenhada: corpo, visor e lente"""
    d.rounded_rectangle((cx - t, cy - t * 0.62, cx + t, cy + t * 0.72), radius=t * 0.22, fill=cor)
    d.rounded_rectangle((cx - t * 0.42, cy - t * 0.9, cx + t * 0.22, cy - t * 0.5), radius=t * 0.1, fill=cor)
    d.ellipse((cx - t * 0.5, cy - t * 0.42, cx + t * 0.5, cy + t * 0.58), fill=PRETO)
    d.ellipse((cx - t * 0.32, cy - t * 0.24, cx + t * 0.32, cy + t * 0.4), fill=cor)
    d.ellipse((cx + t * 0.62, cy - t * 0.45, cx + t * 0.82, cy - t * 0.25), fill=PRETO)


def icone_controle(d, cx, cy, t, cor):
    """controle de videogame (gameplay) desenhado"""
    d.rounded_rectangle((cx - t, cy - t * 0.5, cx + t, cy + t * 0.42), radius=t * 0.4, fill=cor)
    d.ellipse((cx - t * 1.08, cy - t * 0.2, cx - t * 0.42, cy + t * 0.82), fill=cor)
    d.ellipse((cx + t * 0.42, cy - t * 0.2, cx + t * 1.08, cy + t * 0.82), fill=cor)
    b = t * 0.1  # cruz (direcional)
    x0 = cx - t * 0.55
    d.rectangle((x0 - b * 2.6, cy - b, x0 + b * 2.6, cy + b), fill=PRETO)
    d.rectangle((x0 - b, cy - b * 2.6, x0 + b, cy + b * 2.6), fill=PRETO)
    x1, r = cx + t * 0.55, t * 0.1
    for dx, dy in ((0, -2.2), (0, 2.2), (-2.2, 0), (2.2, 0)):
        d.ellipse((x1 + dx * r - r, cy + dy * r - r, x1 + dx * r + r, cy + dy * r + r), fill=PRETO)


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


def confere_area(img, saida):
    g = img.copy()
    ImageDraw.Draw(g).rectangle((SX, SY, SX + SW, SY + SH), outline=(255, 0, 0), width=6)
    g.resize((1280, 720)).save(saida / "banner_conferir_area_segura.jpg", quality=88)


# ------------------------------------------------------------------ DETTO GALO NOTÍCIAS
def galo_noticias(nome, saida):
    saida.mkdir(parents=True, exist_ok=True)
    img = vinheta(listras(W, H), 0.55)
    d = ImageDraw.Draw(img)
    # "GALO" gigante e apagado nas laterais (aparece na TV/computador; no celular some sem fazer falta)
    fg = fonte(620)
    for x in (SX - 380, SX + SW + 380):
        d.text((x, H // 2), "DG", font=fg, fill=(34, 34, 34), anchor="mm")
    # faixas de telejornal em cima e embaixo da área segura
    d.rectangle((0, SY - 70, W, SY - 56), fill=AMARELO)
    d.rectangle((0, SY + SH + 56, W, SY + SH + 70), fill=AMARELO)
    partes = nome.upper().split()
    topo, resto = (partes[0], " ".join(partes[1:])) if len(partes) > 2 else ("", nome.upper())
    if topo:
        pilula(d, W // 2, SY + 52, topo, fonte(54), BRANCO, PRETO, pad=40)
    f = encaixa(d, resto, "Anton-Regular.ttf", 186, SW - 100)
    texto_centro(d, (W // 2, SY + 204), resto, f, AMARELO, 7)
    # barra "plantão"
    by = SY + 345
    d.rectangle((SX + 40, by - 38, SX + SW - 40, by + 38), fill=PRETO, outline=AMARELO, width=4)
    d.rectangle((SX + 40, by - 38, SX + 300, by + 38), fill=VERMELHO)
    texto_centro(d, (SX + 170, by + 1), "PLANTÃO", fonte(46, "Inter-ExtraBold.otf"), BRANCO)
    fx = encaixa(d, "IMPRENSA + RESENHA DE TORCEDOR  •  VÍDEO NOVO TODO DIA", "Inter-Bold.otf", 38, SW - 40 - 330 - 30)
    d.text((SX + 330, by + 1), "IMPRENSA + RESENHA DE TORCEDOR  •  VÍDEO NOVO TODO DIA", font=fx, fill=BRANCO, anchor="lm")
    img.save(saida / "banner_2560x1440.png")
    confere_area(img, saida)
    # foto de perfil: DG + NOTÍCIAS
    P = 800
    av = listras(P, P, passo=30)
    da = ImageDraw.Draw(av)
    da.ellipse((30, 30, P - 30, P - 30), fill=(16, 16, 16), outline=AMARELO, width=28)
    texto_centro(da, (P // 2, P // 2 - 50), "DG", fonte(380), AMARELO, 8)
    da.rectangle((150, P // 2 + 150, P - 150, P // 2 + 250), fill=AMARELO)
    texto_centro(da, (P // 2, P // 2 + 200), "NOTÍCIAS", fonte(78), PRETO)
    av.save(saida / "perfil_800x800.png")
    # marca d'água
    M = 150
    wm = Image.new("RGBA", (M, M), (0, 0, 0, 0))
    dw = ImageDraw.Draw(wm)
    dw.ellipse((4, 4, M - 4, M - 4), fill=(12, 12, 12, 230), outline=AMARELO + (255,), width=6)
    texto_centro(dw, (M // 2, M // 2 - 4), "DG", fonte(72), AMARELO)
    wm.save(saida / "marca_dagua_150x150.png")
    # molde de thumb (o thumb.py segue o mesmo estilo: rosto recortado à direita + manchete Anton)
    th = vinheta(listras(1280, 720, passo=28), 0.45)
    dt_ = ImageDraw.Draw(th)
    dt_.rectangle((0, 620, 1280, 720), fill=AMARELO)
    texto_centro(dt_, (640, 670), nome.upper(), fonte(64), PRETO)
    dt_.rectangle((40, 40, 300, 110), fill=VERMELHO)
    texto_centro(dt_, (170, 76), "URGENTE", fonte(52), BRANCO)
    texto_centro(dt_, (410, 270), "MANCHETE", fonte(140), BRANCO, 6)
    texto_centro(dt_, (410, 430), "AQUI", fonte(140), AMARELO, 6)
    dt_.rounded_rectangle((820, 120, 1220, 600), radius=30, outline=CINZA, width=4)
    texto_centro(dt_, (1020, 360), "ROSTO", fonte(60), CINZA)
    th.save(saida / "thumb_molde_1280x720.png")
    (saida / "CANAL.txt").write_text(TEXTO_NOTICIAS.strip() + "\n", encoding="utf-8")
    return saida


# ------------------------------------------------------------------ EVERTON LOPES (vlogs + gameplays)
def everton_lopes(nome, saida, foto=None):
    saida.mkdir(parents=True, exist_ok=True)
    if foto:
        base = Image.open(foto).convert("RGB")
        bw, bh = base.size
        esc = max(W / bw, H / bh)
        base = base.resize((int(bw * esc), int(bh * esc)))
        base = base.crop(((base.width - W) // 2, (base.height - H) // 2, (base.width - W) // 2 + W, (base.height - H) // 2 + H))
        img = Image.blend(base.filter(ImageFilter.GaussianBlur(36)), Image.new("RGB", (W, H), (8, 8, 12)), 0.68)
    else:
        img = degrade(W, H, (10, 14, 12), (20, 10, 34))  # verde-escuro (vlog) → roxo-escuro (gameplay)
    img = vinheta(img, 0.6)
    d = ImageDraw.Draw(img)
    # brilho lima à esquerda, roxo à direita (as duas "metades" do canal)
    luz = Image.new("RGB", (W, H), (0, 0, 0))
    dl = ImageDraw.Draw(luz)
    dl.ellipse((SX - 700, SY - 300, SX + 500, SY + SH + 300), fill=(40, 60, 10))
    dl.ellipse((SX + SW - 500, SY - 300, SX + SW + 700, SY + SH + 300), fill=(40, 18, 70))
    from PIL import ImageChops
    img = ImageChops.add(img, luz.filter(ImageFilter.GaussianBlur(220)))
    d = ImageDraw.Draw(img)
    f = encaixa(d, nome.upper(), "Anton-Regular.ttf", 250, SW - 140)
    texto_centro(d, (W // 2, SY + 140), nome.upper(), f, BRANCO, 5)
    larg = d.textlength(nome.upper(), font=f)
    d.rectangle((W // 2 - larg // 2, SY + 262, W // 2, SY + 274), fill=LIMA)
    d.rectangle((W // 2, SY + 262, W // 2 + larg // 2, SY + 274), fill=ROXO)
    fp = fonte(50, "Inter-ExtraBold.otf")
    cy = SY + 352
    icone_camera(d, SX + 95, cy, 46, LIMA)
    tags = [("VLOGS", LIMA, PRETO, None), ("GAMEPLAYS", ROXO, BRANCO, None), ("RESENHA", None, BRANCO, BRANCO)]
    larg_t = [d.textlength(t[0], font=fp) + 68 for t in tags]
    vao = 44
    x = W // 2 - (sum(larg_t) + vao * (len(tags) - 1)) / 2
    for (txt, fundo, cor, cont), lt in zip(tags, larg_t):
        pilula(d, x + lt / 2, cy, txt, fp, fundo, cor, contorno=cont)
        x += lt + vao
    icone_controle(d, SX + SW - 95, cy, 50, ROXO)
    img.save(saida / "banner_2560x1440.png")
    confere_area(img, saida)
    # foto de perfil: sua foto com anel lima/roxo (ou o monograma EL)
    P = 800
    av = Image.new("RGB", (P, P), (14, 14, 18))
    da = ImageDraw.Draw(av)
    da.arc((14, 14, P - 14, P - 14), 135, 315, fill=LIMA, width=30)
    da.arc((14, 14, P - 14, P - 14), 315, 135, fill=ROXO, width=30)
    if foto:
        fr = foto_recortada(foto, P - 110)
        av.paste(fr, (55, 55), fr)
    else:
        texto_centro(da, (P // 2, P // 2 - 10), "EL", fonte(400), BRANCO, 6)
        da.rectangle((P // 2 - 150, P // 2 + 190, P // 2, P // 2 + 206), fill=LIMA)
        da.rectangle((P // 2, P // 2 + 190, P // 2 + 150, P // 2 + 206), fill=ROXO)
    av.save(saida / "perfil_800x800.png")
    # marca d'água
    M = 150
    wm = Image.new("RGBA", (M, M), (0, 0, 0, 0))
    dw = ImageDraw.Draw(wm)
    dw.ellipse((4, 4, M - 4, M - 4), fill=(12, 12, 16, 230))
    dw.arc((4, 4, M - 4, M - 4), 135, 315, fill=LIMA + (255,), width=7)
    dw.arc((4, 4, M - 4, M - 4), 315, 135, fill=ROXO + (255,), width=7)
    texto_centro(dw, (M // 2, M // 2 - 3), "EL", fonte(74), BRANCO)
    wm.save(saida / "marca_dagua_150x150.png")
    # moldes de thumb: VLOG (estilo AM3NIC: imagem bonita + frase curta) e GAMEPLAY
    tv = vinheta(degrade(1280, 720, (40, 52, 44), (16, 18, 20), vertical=True), 0.5)
    dv = ImageDraw.Draw(tv)
    texto_centro(dv, (640, 300), "FOTO BONITA DO LUGAR", fonte(64), CINZA)
    texto_centro(dv, (640, 560), "FUI NA APARECIDA?", fonte(96), BRANCO, 5)
    dv.rectangle((520, 625, 760, 635), fill=LIMA)
    tv.save(saida / "thumb_molde_vlog_1280x720.png")
    tg = degrade(1280, 720, (24, 10, 44), (8, 8, 12))
    dg = ImageDraw.Draw(tg)
    dg.rounded_rectangle((40, 40, 1240, 680), radius=26, outline=ROXO, width=6)
    dg.rectangle((40, 40, 380, 120), fill=ROXO)
    texto_centro(dg, (210, 80), "GAMEPLAY", fonte(58), BRANCO)
    texto_centro(dg, (430, 330), "NOME DO", fonte(120), BRANCO, 6)
    texto_centro(dg, (430, 470), "DESAFIO", fonte(120), LIMA, 6)
    icone_controle(dg, 1000, 560, 70, ROXO)
    dg.rounded_rectangle((820, 120, 1180, 470), radius=30, outline=CINZA, width=4)
    texto_centro(dg, (1000, 295), "ROSTO", fonte(56), CINZA)
    tg.save(saida / "thumb_molde_gameplay_1280x720.png")
    (saida / "CANAL.txt").write_text(TEXTO_EVERTON.strip() + "\n", encoding="utf-8")
    return saida


TEXTO_NOTICIAS = """
DETTO GALO NOTÍCIAS
Identificador sugerido: @dettogalonoticias   (alternativas: @dettogalo.noticias, @detto.noticias)

DESCRIÇÃO (Studio → Personalização → Informações básicas)
Todas as notícias do Galo, todo dia, num vídeo só. 🐓📰
O que a imprensa falou do Atlético hoje — Jogo Aberto, Alterosa Esporte, ESPN, TNT, Band Minas, Itatiaia e mais —
com a resenha do Detto, torcedor que vive o Galo: contratação, escalação, bastidor, polêmica, VAR e o que vem por aí.

🔔 Vídeo novo todo dia. Ative o sininho para não perder nada do Galo.
📲 Instagram e TikTok: @detto.galo
🎬 Vlogs e gameplays: Everton Lopes

Canal de torcedor, sem ligação oficial com o Clube Atlético Mineiro. Trechos de imprensa usados com comentário e
crédito a quem produziu (na descrição e nos comentários de cada vídeo). Narração com voz gerada por IA a partir da
voz do Detto.

PALAVRAS-CHAVE DO CANAL (Configurações → Canal)
galo, atlético mineiro, atlético-mg, notícias do galo, galo hoje, galo doido, cam, arena mrv, atletico mineiro noticias,
notícias do atlético, detto galo, mercado da bola galo, escalação do galo, brasileirão, libertadores

PLAYLISTS
1. Notícias do dia (todo vídeo diário)
2. Mercado da bola do Galo
3. Pré-jogo e escalação
4. Pós-jogo: o que a imprensa falou
5. Polêmicas e VAR
6. Shorts do Galo

PADRÃO DE ENVIO (Configurações → Padrões de envio)
Título: GALO HOJE: <manchete> | Notícias do Atlético
Categoria: Esportes · Idioma: Português (Brasil) · Comentários: permitir
Conteúdo alterado ou sintético: SIM (a narração é voz gerada por IA)
Marca d'água: marca_dagua_150x150.png, "Vídeo inteiro"

LINKS DO CANAL
Instagram  https://instagram.com/detto.galo
TikTok     https://tiktok.com/@detto.galo
Everton Lopes (vlogs e gameplays)  <link do canal>

ARQUIVOS DESTA PASTA
banner_2560x1440.png (Studio → Personalização → Imagem do banner; confira banner_conferir_area_segura.jpg)
perfil_800x800.png · marca_dagua_150x150.png · thumb_molde_1280x720.png
"""

TEXTO_EVERTON = """
EVERTON LOPES
Identificador sugerido: @evertonlopes   (alternativas: @evertonlopes.vlog, @evertonlopesoficial, @oevertonlopes)

DESCRIÇÃO (Studio → Personalização → Informações básicas)
Oi, eu sou o Everton Lopes — o Detto do @detto.galo. 🎬🎮
Aqui é o meu lado fora das notícias: vlogs dos lugares onde eu vou (viagens, estádio, BH e Minas), o dia a dia,
gameplays e resenha. Vlog com cara de filme e gameplay sem enrolação.

📅 Vlogs e gameplays toda semana. Ative o sininho 🔔
⚽ Notícias do Galo todo dia: DETTO GALO NOTÍCIAS
📲 Instagram e TikTok: @detto.galo

PALAVRAS-CHAVE DO CANAL
everton lopes, detto, detto galo, vlog, vlog de viagem, vlog bh, minas gerais, arena mrv, dia a dia, gameplay,
gameplay pt-br, ea fc, efootball, resenha, viagem

PLAYLISTS
1. Vlogs (viagens e passeios)
2. Gameplays
3. Arena MRV e dia de jogo
4. Dia a dia / resenha
5. Shorts

PADRÃO DE ENVIO
Título vlog:     <frase curiosa, estilo AM3NIC> (ex.: "FUI NA APARECIDA SEM PLANEJAR NADA")
Título gameplay: <JOGO>: <desafio/resultado> | Everton Lopes
Categoria: Pessoas e blogs (vlogs) · Jogos (gameplays; mude no envio) · Idioma: Português (Brasil)
Marca d'água: marca_dagua_150x150.png, "Vídeo inteiro"
Gameplay: em Studio → Detalhes → "Jogo" escolha o jogo (entra na página do jogo no YouTube)

LINKS DO CANAL
Instagram  https://instagram.com/detto.galo
TikTok     https://tiktok.com/@detto.galo
DETTO GALO NOTÍCIAS  <link do canal>

ARQUIVOS DESTA PASTA
banner_2560x1440.png (confira banner_conferir_area_segura.jpg) · perfil_800x800.png (rode com --foto "sua foto.jpg"
para usar o seu rosto) · marca_dagua_150x150.png · thumb_molde_vlog_1280x720.png · thumb_molde_gameplay_1280x720.png
"""


def main():
    ap = argparse.ArgumentParser(description="banner, perfil, marca d'água e textos dos canais")
    ap.add_argument("--noticias", default="DETTO GALO NOTÍCIAS")
    ap.add_argument("--everton", "--vlogs", dest="everton", default="EVERTON LOPES")
    ap.add_argument("--foto", help="sua foto (rosto) para o canal Everton Lopes")
    ap.add_argument("--saida", default=r"E:\DETTO\marca")
    a = ap.parse_args()
    s = Path(a.saida)
    print(galo_noticias(a.noticias, s / "noticias"))
    print(everton_lopes(a.everton, s / "everton_lopes", a.foto))


if __name__ == "__main__":
    main()
