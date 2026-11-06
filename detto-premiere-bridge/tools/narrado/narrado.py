#!/usr/bin/env python3
"""VÍDEO NARRADO PARA REAGIR (06/nov, pedido dele) — o formato do @d.brenoofc.

O QUE ELE PEDIU: "um local que crie com apenas narração vídeos virais, para ficar embaixo minha reação e
em cima o vídeo que você vai gerar com as notícias quentes e clipes e fotos que falam na narração".

ENTÃO É ISSO: assunto quente → a IA escreve a narração → a SUA voz narra → cada frase ganha a imagem ou o
clipe DAQUILO QUE ELA CITA → sai um vídeo 9:16 com o conteúdo EM CIMA e o espaço da sua reação EMBAIXO.

    python tools\\narrado\\narrado.py --quente
    python tools\\narrado\\narrado.py --assunto "Rockstar divulgou novas imagens do GTA 6"
    python tools\\narrado\\narrado.py --assunto "..." --reacao "C:\\...\\minha_reacao.mp4"

DUAS COISAS QUE DECIDEM SE PRESTA:
  1. A IMAGEM TEM DE SER DO QUE ESTÁ SENDO DITO. Por isso cada cena do roteiro traz um termo de busca
     próprio, e não uma imagem genérica repetida — é a diferença entre vídeo de notícia e slideshow.
  2. SEM A CARA DE OUTRA PESSOA. A reação é a SUA; clipe de terceiro falando na câmera estraga o formato.
     Os clipes passam pelo mesmo filtro do shop (YuNet) e os que têm rosto são descartados.

Saídas em `<DETTO>\\narrado\\prontos\\<data>\\<assunto>\\`:
  topo.mp4      — só o conteúdo (1080x1200), para você montar no CapCut do seu jeito
  completo.mp4  — 1080x1920 já com a sua reação embaixo (ou o espaço marcado, se você ainda não gravou)
  post.txt      — legenda e tags
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
for _p in (TOOLS, TOOLS / "reels", TOOLS / "canal", TOOLS / "shop", TOOLS / "viral"):
    sys.path.insert(0, str(_p))

W, H = 1080, 1920
H_TOPO = 1200              # o conteúdo
H_BAIXO = H - H_TOPO       # a reação dele
FPS = 30
FONTES = PONTE / "fonts"
LOG_F = None


def log(m):
    print(m, flush=True)
    if LOG_F:
        try:
            with open(LOG_F, "a", encoding="utf-8") as f:
                f.write(f"{dt.datetime.now():%H:%M} {m}\n")
        except OSError:
            pass


def norm(t):
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


def slug(t, n=40):
    s = re.sub(r"[^\w]+", "-", norm(t)).strip("-")
    return (s[:n] or "assunto").strip("-")


def roda(args, o_que="", timeout=900):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{o_que or args[0]} falhou: {(r.stderr or '')[-400:]}")
    return r


def dur(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


def raiz():
    """a pasta de mídia (E:\\DETTO no PC dele)"""
    for v in ("DETTO_MIDIA", "DETTO_RAIZ"):
        if os.environ.get(v):
            return Path(os.environ[v])
    for d in ("E:/DETTO", "D:/DETTO", "C:/DETTO"):
        if Path(d).exists():
            return Path(d)
    return Path.home() / "DETTO"


# ------------------------------------------------------------------ 1) O ASSUNTO
def assunto_quente(log=log):
    """a notícia mais quente dos portais (os mesmos feeds conferidos do viral.py)"""
    try:
        import viral as V
    except Exception as e:
        log(f"não consegui ler os portais ({str(e)[:120]})")
        return ""
    quentes = []
    for url in getattr(V, "FEEDS", []):
        try:
            for it in V._itens_do_feed(url):
                t = norm(it.get("titulo", ""))
                if any(f in t for f in getattr(V, "FRIAS", [])):
                    continue
                peso = sum(1 for q in getattr(V, "QUENTES", []) if q in t)
                if peso:
                    quentes.append((peso, it.get("titulo", "")))
        except Exception:
            continue
    if not quentes:
        return ""
    quentes.sort(key=lambda x: -x[0])
    log(f"assunto quente: {quentes[0][1]}")
    return quentes[0][1]


# ------------------------------------------------------------------ 2) O ROTEIRO
REGRAS = """Você escreve a NARRAÇÃO de um vídeo curto de notícia para o Instagram/TikTok, em português do Brasil.
Quem narra é um criador brasileiro, direto, que fala como gente — nunca como jornal de TV.

FORMATO (é o que faz o vídeo prender):
- GANCHO nos 2 primeiros segundos: a informação mais chocante primeiro, sem "olá pessoal", sem apresentação.
- 5 a 8 cenas. Cada cena é UMA frase falada, de 8 a 18 palavras.
- Cada cena traz um NÚMERO, NOME ou FATO concreto. Nada de encheção.
- A última cena termina com uma pergunta curta para o comentário.
- PROIBIDO INVENTAR: só use o que está no assunto. Sem dado que você não recebeu, sem valor chutado.

Para CADA cena você também escreve "busca": o que mostrar na tela ENQUANTO essa frase é dita, em 2 a 5
palavras, concreto e visual (o nome da pessoa, do lugar, do produto, do time). Nunca abstrato.
"tipo": "clipe" quando a cena pede movimento (algo acontecendo), "foto" quando um retrato basta.

Responda SÓ este JSON:
{"titulo":"...","legenda":"legenda do post com 1 a 2 linhas","tags":["#tag1","#tag2","#tag3","#tag4","#tag5"],
 "cenas":[{"fala":"...","busca":"...","tipo":"foto"}]}"""


def roteiro(assunto, segundos, log=log):
    from reels import gemini_json

    quantas = max(4, min(9, round(segundos / 4.5)))
    pedido = (f"{REGRAS}\n\nASSUNTO: {assunto}\n\nFaça {quantas} cenas, para um vídeo de cerca de "
              f"{segundos} segundos no total.")
    d = gemini_json([{"text": pedido}], temperatura=0.8) or {}
    cenas = [c for c in (d.get("cenas") or []) if (c.get("fala") or "").strip()]
    if not cenas:
        raise RuntimeError("a IA não devolveu roteiro nenhum (sem GEMINI_API_KEY e sem IA grátis?)")
    for c in cenas:
        c["fala"] = re.sub(r"\s+", " ", c["fala"]).strip()
        c["busca"] = (c.get("busca") or assunto)[:80]
        c["tipo"] = "clipe" if str(c.get("tipo", "")).lower().startswith("cl") else "foto"
    return {"titulo": (d.get("titulo") or assunto)[:120],
            "legenda": d.get("legenda") or "", "tags": d.get("tags") or [], "cenas": cenas}


# ------------------------------------------------------------------ 3) A VOZ (uma por cena = tempo exato)
def narra_cenas(cenas, tmp, cfg, log=log):
    """uma fala por cena: a duração sai do próprio arquivo, então a imagem troca exatamente com a frase.

    (O caminho do whisper existe no resto do sistema porque lá a fala já veio pronta; aqui eu MANDO na
    narração, então medir cada pedaço é mais simples e não erra.)
    """
    import voz as V

    out = []
    for i, c in enumerate(cenas):
        alvo = tmp / f"fala{i:02d}.wav"
        texto = V.pronuncia(c["fala"])
        url = cfg.get("voicestudio") or V.voicestudio_url()
        feito = False
        if V.voicestudio_pronto(url):
            try:
                vid, vnome = V.voicestudio_escolhe(url, cfg.get("voz_voicestudio"), log if i == 0 else (lambda *a: None))
                V.voicestudio_fala(texto, alvo, vid, url, velocidade=float(cfg.get("velocidade_voz", 1.0)),
                                   instrucao=cfg.get("instrucao_voz") or V.INSTRUCAO_PADRAO)
                feito = alvo.exists()
                if feito and i == 0:
                    log(f"voz: VoiceStudio — \"{vnome}\"")
            except Exception as e:
                log(f"voz: VoiceStudio falhou ({str(e)[:100]})")
        if not feito and os.environ.get("FISH_API_KEY"):
            try:
                chave = os.environ["FISH_API_KEY"]
                V.fish_fala(texto, alvo, V.fish_voz_dele(chave, log), chave)
                feito = alvo.exists()
                if feito and i == 0:
                    log("voz: Fish Audio")
            except Exception as e:
                log(f"voz: o Fish falhou ({str(e)[:100]})")
        if not feito:
            if i == 0:
                log("voz: neural pt-BR (abra o VoiceStudio com a sua voz para narrar com a SUA)")
            V.edge_fala(texto, alvo, cfg.get("voz_neural") or "pt-BR-AntonioNeural")
        d = dur(alvo)
        if d < 0.3:
            raise RuntimeError(f"a fala {i + 1} saiu vazia")
        c["dur"] = d
        out.append(alvo)
    return out


# ------------------------------------------------------------------ 4) A IMAGEM DO QUE ESTÁ SENDO DITO
# baixar vídeo é o passo lento de todos (~1 min por cena). Num vídeo de 7 cenas isso seria a rodada
# inteira esperando download. Dois ou três clipes já dão movimento ao vídeo; o resto é foto, que é
# instantânea. MAX_CLIPES é o teto por vídeo.
MAX_CLIPES = 3


def midia_da_cena(c, pasta, i, usar_clipes=True, log=log, feitos=None):
    """o visual DAQUELA frase: clipe sem rosto quando a cena pede movimento, senão foto"""
    busca = c["busca"]
    if usar_clipes and c["tipo"] == "clipe" and (feitos is None or feitos["clipes"] < MAX_CLIPES):
        try:
            from clipes_web import clipes_do_produto
            fs = clipes_do_produto(busca, pasta / f"clipes{i:02d}", quantos=1,
                                   dur=max(2.5, min(6.0, c["dur"])), log=log, buscas=("",))
            if fs:
                if feitos is not None:
                    feitos["clipes"] += 1
                return fs[0], "clipe"
        except Exception as e:
            log(f"   clipe de \"{busca}\": não deu ({str(e)[:90]})")
    try:
        import busca_imagem as BI
        destino = pasta / f"foto{i:02d}"
        r = BI.buscar(busca, destino=destino, minimo=400, log=(lambda *a: None))
        if r and r.get("file"):
            return Path(r["file"]), "foto"
    except Exception as e:
        log(f"   foto de \"{busca}\": não deu ({str(e)[:90]})")
    return None, ""


# ------------------------------------------------------------------ 5) A LEGENDA QUEIMADA
def legenda_png(texto, saida, largura=W, altura=260, destaque=""):
    """legenda GRANDE em caixa alta, com a palavra-chave colorida — o padrão dos virais.

    PIL e não drawtext: o drawtext NÃO quebra linha (uma frase de 15 palavras sairia numa linha só, metade
    fora da tela). Isso já tinha mordido o projeto na gameplay narrada.
    """
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cam = FONTES / "TikTokSans.ttf"
    if not cam.exists():
        cam = FONTES / "Inter-ExtraBold.otf"
    tam = 62
    fonte = ImageFont.truetype(str(cam), tam)
    palavras, linhas, atual = texto.upper().split(), [], ""
    for p in palavras:
        teste = (atual + " " + p).strip()
        if d.textlength(teste, font=fonte) > largura - 90 and atual:
            linhas.append(atual)
            atual = p
        else:
            atual = teste
    if atual:
        linhas.append(atual)
    while len(linhas) > 3 and tam > 34:          # frase comprida: diminui em vez de cortar
        tam -= 6
        fonte = ImageFont.truetype(str(cam), tam)
        linhas, atual = [], ""
        for p in palavras:
            teste = (atual + " " + p).strip()
            if d.textlength(teste, font=fonte) > largura - 90 and atual:
                linhas.append(atual)
                atual = p
            else:
                atual = teste
        if atual:
            linhas.append(atual)
    alt = tam + 14
    y = altura - len(linhas) * alt - 24
    # PALAVRA INTEIRA, nunca "está contida em" (o teste de substring pintava o "A" solto de amarelo,
    # porque "a" aparece dentro de "gta 6"). E só palavra com 4+ letras: artigo destacado não é destaque.
    chave = {p for p in norm(destaque).split() if len(p) >= 4}
    for ln in linhas:
        x = (largura - d.textlength(ln, font=fonte)) / 2
        for w in ln.split(" "):
            lw = d.textlength(w + " ", font=fonte)
            cor = (255, 214, 0, 255) if norm(w).strip(".,!?:;") in chave else (255, 255, 255, 255)
            d.text((x, y), w, font=fonte, fill=cor, stroke_width=7, stroke_fill=(0, 0, 0, 235))
            x += lw
        y += alt
    img.save(saida)
    return saida


def faixa_titulo(texto, saida, largura=W):
    from PIL import Image, ImageDraw, ImageFont

    alt = 110
    img = Image.new("RGBA", (largura, alt), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([24, 18, largura - 24, alt - 12], 14, fill=(200, 16, 32, 235))
    cam = FONTES / "Inter-Bold.otf"
    f = ImageFont.truetype(str(cam), 40)
    t = texto.upper()[:46]
    while d.textlength(t, font=f) > largura - 110 and len(t) > 10:
        t = t[:-2]
    d.text(((largura - d.textlength(t, font=f)) / 2, 30), t, font=f, fill=(255, 255, 255, 255))
    img.save(saida)
    return saida


# ------------------------------------------------------------------ 6) A MONTAGEM
def peca(arq, tipo, seg, saida, i):
    """uma cena: a mídia ocupando o quadro de cima, com movimento lento (nunca zoompan: ~57 s por cena)"""
    if arq is None:
        roda(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x0d1117:s={W}x{H_TOPO}:r={FPS}",
              "-t", f"{seg:.3f}", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-y", str(saida)], "fundo")
        return saida
    if tipo == "clipe":
        roda(["ffmpeg", "-v", "error", "-stream_loop", "-1", "-i", str(arq), "-t", f"{seg:.3f}", "-an",
              "-vf", f"scale={W}:{H_TOPO}:force_original_aspect_ratio=increase,crop={W}:{H_TOPO},fps={FPS}",
              "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p",
              "-y", str(saida)], "clipe")
        return saida
    # foto: fundo desfocado dela mesma + zoom lento (scale com eval=frame, não zoompan)
    z = 1.0 + 0.05 * (1 if i % 2 == 0 else -1)
    de, ate = (1.0, z) if i % 2 == 0 else (z, 1.0)
    esc = f"{W}*({de}+({ate}-{de})*t/{max(0.1, seg):.3f})"
    fc = (f"[0:v]split=2[a][b];"
          f"[a]scale={W}:{H_TOPO}:force_original_aspect_ratio=increase,crop={W}:{H_TOPO},boxblur=30[bg];"
          f"[b]scale='{esc}':-2:eval=frame[fg];"
          f"[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,crop={W}:{H_TOPO},fps={FPS}[v]")
    roda(["ffmpeg", "-v", "error", "-loop", "1", "-i", str(arq), "-t", f"{seg:.3f}",
          "-filter_complex", fc, "-map", "[v]",
          "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p",
          "-y", str(saida)], "foto")
    return saida


def monta_topo(rot, cenas_midia, falas, tmp, log=log):
    """as cenas emendadas + legenda de cada frase + faixa do título = o vídeo de CIMA"""
    partes = []
    for i, c in enumerate(rot["cenas"]):
        arq, tipo = cenas_midia[i]
        p = peca(arq, tipo, c["dur"], tmp / f"p{i:02d}.mp4", i)
        leg = legenda_png(c["fala"], tmp / f"leg{i:02d}.png", destaque=c.get("busca", ""))
        com = tmp / f"pl{i:02d}.mp4"
        roda(["ffmpeg", "-v", "error", "-i", str(p), "-i", str(leg),
              "-filter_complex", f"[0:v][1:v]overlay=0:{H_TOPO - 330}",
              "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p",
              "-y", str(com)], "legenda")
        partes.append(com)
    lista = tmp / "partes.txt"
    lista.write_text("".join(f"file '{p.as_posix()}'\n" for p in partes), encoding="utf-8")
    emendado = tmp / "emendado.mp4"
    roda(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
          "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p",
          "-y", str(emendado)], "emenda")
    # faixa do título por cima, nos 4 primeiros segundos
    tit = faixa_titulo(rot["titulo"], tmp / "titulo.png")
    com_tit = tmp / "topo_mudo.mp4"
    roda(["ffmpeg", "-v", "error", "-i", str(emendado), "-i", str(tit),
          "-filter_complex", "[0:v][1:v]overlay=0:28:enable='lt(t,4)'",
          "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p",
          "-y", str(com_tit)], "titulo")
    # o áudio: as falas emendadas na ordem
    la = tmp / "falas.txt"
    la.write_text("".join(f"file '{p.as_posix()}'\n" for p in falas), encoding="utf-8")
    aud = tmp / "narracao.wav"
    roda(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(la),
          "-ar", "48000", "-ac", "2", "-y", str(aud)], "audio")
    topo = tmp / "topo.mp4"
    roda(["ffmpeg", "-v", "error", "-i", str(com_tit), "-i", str(aud),
          "-filter_complex", "[1:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]", "-map", "0:v", "-map", "[a]",
          "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-y", str(topo)], "som")
    return topo


def monta_completo(topo, reacao, saida, log=log):
    """1080x1920: o conteúdo em cima, a SUA reação embaixo (ou o espaço marcado, se ainda não gravou)"""
    t = dur(topo)
    if reacao and Path(reacao).exists():
        fc = (f"[1:v]scale={W}:{H_BAIXO}:force_original_aspect_ratio=increase,crop={W}:{H_BAIXO},fps={FPS}[b];"
              f"[0:v][b]vstack=inputs=2[v]")
        roda(["ffmpeg", "-v", "error", "-i", str(topo), "-stream_loop", "-1", "-i", str(reacao),
              "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", "-t", f"{t:.3f}",
              "-c:v", "libx264", "-crf", "19", "-preset", "veryfast", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "192k", "-y", str(saida)], "completo")
        return saida
    from PIL import Image, ImageDraw, ImageFont
    marca = Path(str(saida) + ".png")
    img = Image.new("RGB", (W, H_BAIXO), (14, 16, 22))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(str(FONTES / "Inter-Bold.otf"), 46)
    txt = "SUA REAÇÃO AQUI"
    d.text(((W - d.textlength(txt, font=f)) / 2, H_BAIXO / 2 - 30), txt, font=f, fill=(90, 96, 110))
    img.save(marca)
    roda(["ffmpeg", "-v", "error", "-i", str(topo), "-loop", "1", "-i", str(marca),
          "-filter_complex", f"[1:v]fps={FPS}[b];[0:v][b]vstack=inputs=2[v]",
          "-map", "[v]", "-map", "0:a?", "-t", f"{t:.3f}",
          "-c:v", "libx264", "-crf", "19", "-preset", "veryfast", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "192k", "-y", str(saida)], "completo")
    marca.unlink(missing_ok=True)
    return saida


# ------------------------------------------------------------------ o caminho inteiro
def faz(assunto, base, cfg, segundos=40, reacao="", usar_clipes=True, log=log):
    global LOG_F
    base = Path(base)
    (base / "prontos").mkdir(parents=True, exist_ok=True)
    LOG_F = base / "narrado.log"
    dia = base / "prontos" / dt.date.today().isoformat() / slug(assunto)
    shutil.rmtree(dia, ignore_errors=True)
    dia.mkdir(parents=True, exist_ok=True)
    tmp = base / "tmp" / slug(assunto, 30)
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)

    log(f"\n== {assunto}")
    rot = roteiro(assunto, segundos, log)
    log(f"   roteiro: {len(rot['cenas'])} cenas — \"{rot['titulo'][:70]}\"")
    falas = narra_cenas(rot["cenas"], tmp, cfg, log)
    total = sum(c["dur"] for c in rot["cenas"])
    log(f"   narração: {total:.0f}s")
    midias = []
    feitos = {"clipes": 0}
    for i, c in enumerate(rot["cenas"]):
        arq, tipo = midia_da_cena(c, tmp, i, usar_clipes=usar_clipes, log=log, feitos=feitos)
        log(f"   cena {i + 1}: {'✔' if arq else '—'} {c['busca'][:42]} ({tipo or 'fundo'})")
        midias.append((arq, tipo))
    if not any(a for a, _ in midias):
        raise RuntimeError("não achei imagem nenhuma para as cenas — o vídeo sairia só com fundo liso")
    topo = monta_topo(rot, midias, falas, tmp, log)
    shutil.copyfile(topo, dia / "topo.mp4")
    monta_completo(topo, reacao, dia / "completo.mp4", log)
    (dia / "post.txt").write_text(
        f"{rot['titulo']}\n\n{rot.get('legenda', '')}\n\n{' '.join(rot.get('tags', []))}\n", encoding="utf-8")
    (dia / "roteiro.json").write_text(json.dumps(rot, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    log(f"PRONTO: {dia}")
    return dia


def main():
    ap = argparse.ArgumentParser(description="vídeo narrado de notícia para você reagir por baixo")
    ap.add_argument("--assunto", default="")
    ap.add_argument("--quente", action="store_true", help="pega a notícia mais quente dos portais")
    ap.add_argument("--segundos", type=int, default=40)
    ap.add_argument("--reacao", default="", help="o vídeo da sua reação (vai embaixo)")
    ap.add_argument("--sem-clipes", action="store_true", help="só fotos (mais rápido, não baixa vídeo)")
    ap.add_argument("--pasta", default="")
    a = ap.parse_args()
    base = Path(a.pasta) if a.pasta else raiz() / "narrado"
    base.mkdir(parents=True, exist_ok=True)
    cfg_f = base / "config.json"
    cfg = {}
    if cfg_f.exists():
        try:
            cfg = json.loads(cfg_f.read_text(encoding="utf-8-sig"))
        except ValueError:
            cfg = {}
    assunto = a.assunto or (assunto_quente() if a.quente else "")
    if not assunto:
        sys.exit("diga o assunto: --assunto \"...\"  (ou --quente para pegar dos portais)")
    faz(assunto, base, cfg, segundos=a.segundos, reacao=a.reacao, usar_clipes=not a.sem_clipes)


if __name__ == "__main__":
    main()
