#!/usr/bin/env python3
"""VÍDEO NARRADO PARA REAGIR — o formato dos 3 vídeos que ele mandou (06/nov).

MEDIDO nos três (720x1280, 67 s / 70 s / 73 s), não chutado:
  · o corte entre o conteúdo e a reação fica em 68% / 72% / 68% da altura → uso 70%
  · o clipe de cima troca a cada 2,2 s (30 e 33 cortes de cena em 67 s e 73 s)
  · a narração corre a 192 palavras/min
  · a legenda é de 1 a 3 palavras por vez, CAIXA ALTA, contorno preto grosso, a palavra-chave colorida
  · o que aparece em cima é VÍDEO DE VERDADE — jogo, entrevista, treino, bastidor. Nunca foto parada.
    Os clipes MOSTRAM gente de propósito: ali o jogador e o técnico SÃO a notícia (é o contrário do
    Shop, onde a cara de outra pessoa no anúncio estraga).

    python tools\\narrado\\narrado.py --quente
    python tools\\narrado\\narrado.py --assunto "Cristiano Ronaldo anuncia aposentadoria da seleção"
    python tools\\narrado\\narrado.py --assunto "..." --reacao "C:\\...\\minha_reacao.mp4"

COMO ELE CONSEGUE 20 CLIPES SEM BAIXAR 20 VÍDEOS: baixa 3 ou 4 vídeos de notícia sobre o assunto (um
pedaço de cada) e corta cada um em vários pedaços de 2,2 s. Um vídeo de 75 s já dá 30 pedaços.
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
H_TOPO = 1344              # 70% — medido nos 3 vídeos dele (68%, 72%, 68%)
H_BAIXO = H - H_TOPO       # a reação dele
POR_CLIPE = 2.2            # medido: 30 cortes em 67 s e 33 em 73 s
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


def roda(args, o_que="", timeout=1800):
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
PALAVRAS_POR_MIN = 190     # medido no vídeo dele: 192

REGRAS = """Você escreve a NARRAÇÃO de um vídeo curto de notícia de futebol para o Instagram/TikTok, em
português do Brasil. Quem narra é um criador brasileiro, direto, que fala como gente — nunca como jornal
de TV. O vídeo é para o público REAGIR junto, então a narração tem de ser corrida e sem respiro.

COMO ESCREVER:
- Comece pelo FATO MAIS FORTE, na primeira frase. Sem "olá pessoal", sem apresentação, sem contexto antes.
- Texto CORRIDO, frases curtas emendadas, do jeito que se fala. Nada de tópicos.
- Cada frase traz um NOME, NÚMERO ou FATO concreto. Zero encheção.
- Termine com uma pergunta curta que peça comentário.
- PROIBIDO INVENTAR: use só o que está no assunto. Sem número chutado, sem declaração inventada.

Você também devolve:
- "sujeito": QUEM OU O QUE é a notícia, o nome completo mais usado ("Cristiano Ronaldo"). É quem tem de
  aparecer na tela durante o vídeo todo. "sujeito_pessoa": true se for uma pessoa, false se for time/lugar/coisa.
- "apelidos": outros nomes pelos quais ele é chamado nos títulos ("CR7", "CR 7").
- "buscas": 4 a 6 termos para procurar VÍDEO no YouTube. TODA busca tem de conter o nome do sujeito e pedir
  imagem DELE (jogadas, gols, melhores momentos, entrevista, despedida, homenagem) — nunca só o tema.
  Ruim: "aposentadoria seleção". Bom: "Cristiano Ronaldo melhores momentos seleção portuguesa".

Responda SÓ este JSON:
{"titulo":"...","narracao":"o texto corrido inteiro","sujeito":"...","sujeito_pessoa":true,"apelidos":["..."],
 "buscas":["...","..."],
 "legenda":"legenda do post, 1 a 2 linhas","tags":["#tag1","#tag2","#tag3","#tag4","#tag5"]}"""


TEMA = {"v": "futebol"}   # "futebol" (o de sempre) | "gta" (reels de GTA 6 do dia do lançamento)

REGRAS_GTA = REGRAS.replace("notícia de futebol", "notícia de GTA 6 / games").replace(
    "Termine com uma pergunta curta que peça comentário.",
    "Termine com uma pergunta curta que peça comentário (ex.: \"vai comprar no dia 19?\").").replace(
    "(jogadas, gols, melhores momentos, entrevista, despedida, homenagem)",
    "(trailer, gameplay, mapa, personagens, comparativo, bastidores)").replace(
    "Cristiano Ronaldo melhores momentos seleção portuguesa", "GTA 6 trailer 3 mapa de Leonida").replace(
    "aposentadoria seleção", "novidades").replace(
    '("Cristiano Ronaldo")', '("GTA 6", "Lucia Caminos", "Rockstar Games")').replace(
    "Ruim:", "Ruim:")


def roteiro(assunto, segundos, log=log):
    from reels import gemini_json

    alvo = int(segundos * PALAVRAS_POR_MIN / 60)
    pedido = (f"{REGRAS_GTA if TEMA['v'] == 'gta' else REGRAS}\n\nASSUNTO: {assunto}\n\nA narração tem de ter cerca de {alvo} palavras "
              f"(o vídeo é de ~{segundos} segundos a {PALAVRAS_POR_MIN} palavras por minuto).")
    d = gemini_json([{"text": pedido}], temperatura=0.8) or {}
    texto = re.sub(r"\s+", " ", (d.get("narracao") or "")).strip()
    if len(texto.split()) < 20:
        raise RuntimeError("a IA não devolveu narração (sem GEMINI_API_KEY e sem IA grátis?)")
    buscas = [b for b in (d.get("buscas") or []) if str(b).strip()][:6] or [assunto]
    sujeito = (d.get("sujeito") or "").strip() or " ".join(assunto.split()[:2])
    # a busca SEM o nome do sujeito traz qualquer vídeo do tema (foi o que trouxe a Euro 2016 inteira)
    primeiro = norm(sujeito).split()[0] if norm(sujeito) else ""
    buscas = [b if primeiro and primeiro in norm(b) else f"{sujeito} {b}" for b in map(str, buscas)]
    extras = ((f"{sujeito} trailer", f"{sujeito} gameplay", f"{sujeito} novidades") if TEMA["v"] == "gta"
              else (f"{sujeito} melhores momentos", f"{sujeito} gols e jogadas", f"{sujeito} entrevista"))
    for extra in extras:
        if extra not in buscas:
            buscas.append(extra)
    return {"titulo": (d.get("titulo") or assunto)[:120], "narracao": texto,
            "sujeito": sujeito, "sujeito_pessoa": d.get("sujeito_pessoa", True) is not False,
            "apelidos": [str(a) for a in (d.get("apelidos") or [])][:4],
            "buscas": [str(b)[:80] for b in buscas],
            "legenda": d.get("legenda") or "", "tags": d.get("tags") or []}


# ------------------------------------------------------------------ 3) A VOZ
def narra(texto, saida, cfg, log=log):
    """a narração INTEIRA de uma vez: a entonação fica muito melhor que frase a frase"""
    import voz as V

    falado = V.pronuncia(texto)
    url = cfg.get("voicestudio") or V.voicestudio_url()
    if V.voicestudio_pronto(url):
        vid, vnome = V.voicestudio_escolhe(url, cfg.get("voz_voicestudio"), log)
        log(f"voz: VoiceStudio — \"{vnome}\"")
        V.voicestudio_fala(falado, saida, vid, url, velocidade=float(cfg.get("velocidade_voz", 1.0)),
                           instrucao=cfg.get("instrucao_voz") or V.INSTRUCAO_PADRAO)
        if saida.exists():
            return saida
    chave = os.environ.get("FISH_API_KEY")
    if chave:
        try:
            log("voz: Fish Audio")
            V.fish_fala(falado, saida, V.fish_voz_dele(chave, log), chave)
            if saida.exists():
                return saida
        except Exception as e:
            log(f"voz: o Fish falhou ({str(e)[:120]})")
    log("voz: neural pt-BR (abra o VoiceStudio com a sua voz para narrar com a SUA)")
    V.edge_fala(falado, saida, cfg.get("voz_neural") or "pt-BR-AntonioNeural")
    return saida


def tempos_das_palavras(wav, texto, log=log):
    """quando cada palavra é dita — é o que faz a legenda bater com a fala.

    O whisper com `word_timestamps` é o jeito certo. Se ele não estiver disponível, reparto o tempo
    pelo TAMANHO de cada palavra, que erra pouco numa narração corrida e nunca deixa o vídeo sem legenda.
    """
    total = dur(wav)
    try:
        from transcrever import transcrever
        ps = transcrever(wav, "base", "cpu", idioma="pt")
        if isinstance(ps, tuple):
            ps = ps[0]
        ps = [p for p in (ps or []) if (p.get("w") or "").strip()]
        if len(ps) >= max(8, len(texto.split()) * 0.5):
            log(f"   legenda sincronizada pela transcrição ({len(ps)} palavras)")
            return [{"w": p["w"].strip(), "s": float(p["s"]), "e": float(p["e"])} for p in ps]
        log("   a transcrição veio curta; reparto o tempo pelo tamanho das palavras")
    except Exception as e:
        log(f"   sem transcrição ({str(e)[:90]}); reparto o tempo pelo tamanho das palavras")
    ws = texto.split()
    pesos = [len(w) + 1 for w in ws]
    soma = sum(pesos) or 1
    out, t = [], 0.0
    for w, p in zip(ws, pesos):
        d = total * p / soma
        out.append({"w": w, "s": t, "e": t + d})
        t += d
    return out


# ------------------------------------------------------------------ 4) OS CLIPES (o que aparece em cima)
def pool_de_clipes(rot, total, pasta, log=log):
    """os planos certos, na ordem certa (a lógica toda está em pessoa.py)"""
    from pessoa import pool

    return pool(rot["sujeito"], rot.get("apelidos", []), rot["buscas"], total, pasta, W, H_TOPO,
                log=log, e_pessoa=rot.get("sujeito_pessoa", True))


# ------------------------------------------------------------------ 5) A LEGENDA
def _fonte(tam):
    from PIL import ImageFont
    cam = FONTES / "TikTokSans.ttf"
    if not cam.exists():
        cam = FONTES / "Inter-ExtraBold.otf"
    return ImageFont.truetype(str(cam), tam)


def legenda_png(palavras, saida, chave_idx=None, largura=W, altura=270):
    """1 a 3 palavras em caixa alta, contorno preto grosso, a palavra-chave em amarelo.

    PIL e não `drawtext`: o drawtext não quebra linha nem pinta uma palavra de outra cor.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    tam = 86
    f = _fonte(tam)
    cheio = [p.upper() for p in palavras]
    # diminui até caber; chegando no mínimo legível, QUEBRA EM DUAS LINHAS em vez de cortar na borda
    while d.textlength(" ".join(cheio), font=f) > largura - 80 and tam > 54:
        tam -= 6
        f = _fonte(tam)
    linhas = [list(range(len(cheio)))]
    if d.textlength(" ".join(cheio), font=f) > largura - 80 and len(cheio) > 1:
        meio = (len(cheio) + 1) // 2
        linhas = [list(range(meio)), list(range(meio, len(cheio)))]
    alt_linha = tam + 10
    y = (altura - alt_linha * len(linhas)) / 2
    for ln in linhas:
        larg_ln = d.textlength(" ".join(cheio[i] for i in ln), font=f)
        x = (largura - larg_ln) / 2
        for k, i in enumerate(ln):
            w = cheio[i] + (" " if k < len(ln) - 1 else "")
            cor = (255, 214, 0, 255) if i == chave_idx else (255, 255, 255, 255)
            d.text((x, y), w, font=f, fill=cor, stroke_width=9, stroke_fill=(0, 0, 0, 240))
            x += d.textlength(w, font=f)
        y += alt_linha
    img.save(saida)
    return saida


FRACAS = {"a", "o", "e", "de", "da", "do", "em", "no", "na", "que", "um", "uma", "os", "as", "com",
          "por", "para", "se", "ao", "dos", "das", "mas", "ja", "foi", "é", "the"}


def grupos_de_legenda(palavras, por=3):
    """junta as palavras em grupos de até `por`, marcando a mais forte do grupo para o amarelo"""
    grupos = []
    for i in range(0, len(palavras), por):
        g = palavras[i:i + por]
        if not g:
            continue
        forte, melhor = None, 0
        for j, p in enumerate(g):
            limpa = norm(p["w"]).strip(".,!?:;")
            peso = len(limpa) + (6 if any(c.isdigit() for c in limpa) else 0) + (4 if p["w"][:1].isupper() else 0)
            if limpa not in FRACAS and peso > melhor:
                forte, melhor = j, peso
        grupos.append({"palavras": [p["w"] for p in g], "chave": forte,
                       "ini": g[0]["s"], "fim": g[-1]["e"]})
    return grupos


# ------------------------------------------------------------------ 6) A MONTAGEM
def faixa_titulo(texto, saida, largura=W):
    from PIL import Image, ImageDraw, ImageFont

    alt = 120
    img = Image.new("RGBA", (largura, alt), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([24, 18, largura - 24, alt - 14], 16, fill=(200, 16, 32, 235))
    f = ImageFont.truetype(str(FONTES / "Inter-Bold.otf"), 42)
    t = texto.upper()[:46]
    while d.textlength(t, font=f) > largura - 110 and len(t) > 10:
        t = t[:-2]
    d.text(((largura - d.textlength(t, font=f)) / 2, 34), t, font=f, fill=(255, 255, 255, 255))
    img.save(saida)
    return saida


def esteira(planos, total, tmp, log=log):
    """a linha do tempo de cima: cada plano entra INTEIRO (já cortado na troca de câmera do vídeo-fonte)"""
    if not planos:
        raise RuntimeError("não consegui nenhum clipe para pôr na tela")
    lista = tmp / "esteira.txt"
    lista.write_text("".join(f"file '{Path(p['arq']).as_posix()}'\n" for p in planos), encoding="utf-8")
    saida = tmp / "esteira.mp4"
    roda(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista), "-t", f"{total:.3f}",
          "-c:v", "libx264", "-crf", "19", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS),
          "-y", str(saida)], "emenda")
    log(f"   {len(planos)} plano(s) na tela, em média {sum(p['dur'] for p in planos) / len(planos):.1f}s cada")
    return saida


def poe_legendas(base, grupos, tmp, saida, log=log):
    """queima as legendas: cada grupo aparece no segundo em que é falado.

    São dezenas de PNGs; um `overlay` por grupo num filtro só é o jeito mais rápido (um passe de vídeo).
    """
    if not grupos:
        shutil.copyfile(base, saida)
        return saida
    pngs, filtros, entradas = [], [], ["-i", str(base)]
    y = H_TOPO - 430
    for i, g in enumerate(grupos):
        p = tmp / f"leg{i:03d}.png"
        legenda_png(g["palavras"], p, g.get("chave"))
        pngs.append(p)
        entradas += ["-i", str(p)]
    atual = "0:v"
    for i, g in enumerate(grupos):
        prox = f"v{i}"
        filtros.append(f"[{atual}][{i + 1}:v]overlay=0:{y}:enable='between(t,{g['ini']:.2f},{g['fim']:.2f})'[{prox}]")
        atual = prox
    roda(["ffmpeg", "-v", "error", *entradas, "-filter_complex", ";".join(filtros), "-map", f"[{atual}]",
          "-c:v", "libx264", "-crf", "19", "-preset", "veryfast", "-pix_fmt", "yuv420p",
          "-y", str(saida)], "legendas")
    return saida


def monta_tela_cheia(topo, saida, log=log):
    """REELS sem a sua reação (GTA, o dia todo): o conteúdo 1080x1344 centralizado num fundo borrado dele mesmo, 1080x1920"""
    t = dur(topo)
    fc = (f"[0:v]split[a][b];[a]scale={W}:1920:force_original_aspect_ratio=increase,crop={W}:1920,"
          f"scale=135:240,scale={W}:1920,eq=brightness=-0.12[bg];[b]scale={W}:-2[fg];"
          f"[bg][fg]overlay=(W-w)/2:(H-h)/2,fps={FPS}[v]")
    roda(["ffmpeg", "-v", "error", "-i", str(topo), "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
          "-t", f"{t:.3f}", "-c:v", "libx264", "-crf", "19", "-preset", "veryfast", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "192k", "-y", str(saida)], "tela cheia")
    return saida


def para_fila(cfg, video, txt, log=log):
    """cada reel pronto entra na fila de postagem (as mesmas contas dos reels)"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "postar"))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reels"))
        import postar as P
        from reels import destinos_reels

        pb = P.pasta_padrao()
        alvos = destinos_reels({"postar": cfg.get("postar") or ["todas"]}, pb)
        postos = P.enfileira(pb, video, alvos, txt)
        log(f"   na fila: {', '.join(Path(p).parent.name for p in postos)}")
    except Exception as e:   # noqa: BLE001
        log(f"   não consegui pôr na fila ({str(e)[:140]}) — o vídeo está em prontos\\")


def proximo_do_canal(pasta_canal, base, log=log):
    """o próximo assunto JÁ coletado pelo canal (manchete + texto da notícia, nada inventado), que ainda não virou reel"""
    h = Path(pasta_canal) / "historico.json"
    try:
        trechos = json.loads(h.read_text(encoding="utf-8-sig")).get("trechos", [])
    except (OSError, ValueError):
        return ""
    _nome = Path(pasta_canal).name.lower()
    uf = Path(base) / ("gta_usados.json" if "gta" in _nome else f"usados_{_nome}.json")
    try:
        usados = set(json.loads(uf.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        usados = set()
    for t in sorted(trechos, key=lambda x: (x.get("data", ""), x.get("nota", 0)), reverse=True):
        m = (t.get("manchete") or "").strip()
        k = norm(m)[:60]
        if not m or k in usados:
            continue
        usados.add(k)
        uf.write_text(json.dumps(sorted(usados)[-400:], ensure_ascii=False), encoding="utf-8")
        resumo = (t.get("resumo") or t.get("texto") or "")[:700]
        log(f"assunto do canal GTA: {m}")
        return f"{m}. {resumo}".strip()
    return ""


def monta_completo(topo, reacao, saida, log=log):
    """1080x1920: o conteúdo em cima (70%), a reação dele embaixo (30%) — a proporção medida nos 3 vídeos"""
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
    f = ImageFont.truetype(str(FONTES / "Inter-Bold.otf"), 44)
    txt = "SUA REAÇÃO AQUI"
    d.text(((W - d.textlength(txt, font=f)) / 2, H_BAIXO / 2 - 28), txt, font=f, fill=(90, 96, 110))
    img.save(marca)
    roda(["ffmpeg", "-v", "error", "-i", str(topo), "-loop", "1", "-i", str(marca),
          "-filter_complex", f"[1:v]fps={FPS}[b];[0:v][b]vstack=inputs=2[v]",
          "-map", "[v]", "-map", "0:a?", "-t", f"{t:.3f}",
          "-c:v", "libx264", "-crf", "19", "-preset", "veryfast", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "192k", "-y", str(saida)], "completo")
    marca.unlink(missing_ok=True)
    return saida


# ------------------------------------------------------------------ o caminho inteiro
def faz(assunto, base, cfg, segundos=60, reacao="", usar_clipes=True, log=log, tela_cheia=False, fila=False):
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
    log(f"   roteiro: {len(rot['narracao'].split())} palavras — \"{rot['titulo'][:70]}\"")
    log(f"   buscas: {', '.join(rot['buscas'])}")

    wav = narra(rot["narracao"], tmp / "narracao.wav", cfg, log)
    total = dur(wav)
    if total < 5:
        raise RuntimeError("a narração saiu vazia")
    log(f"   narração: {total:.0f}s")

    palavras = tempos_das_palavras(wav, rot["narracao"], log)
    grupos = grupos_de_legenda(palavras)

    clipes = pool_de_clipes(rot, total, tmp / "clipes", log) if usar_clipes else []
    if not clipes:
        raise RuntimeError("não consegui vídeo nenhum sobre o assunto — sem isso o vídeo sairia com fundo liso. "
                           "Confira a internet e o cookies.txt do YouTube.")

    vis = esteira(clipes, total, tmp, log)
    com_leg = poe_legendas(vis, grupos, tmp, tmp / "com_legenda.mp4", log)
    tit = faixa_titulo(rot["titulo"], tmp / "titulo.png")
    com_tit = tmp / "topo_mudo.mp4"
    roda(["ffmpeg", "-v", "error", "-i", str(com_leg), "-i", str(tit),
          "-filter_complex", "[0:v][1:v]overlay=0:30:enable='lt(t,4)'",
          "-c:v", "libx264", "-crf", "19", "-preset", "veryfast", "-pix_fmt", "yuv420p",
          "-y", str(com_tit)], "titulo")
    topo = tmp / "topo.mp4"
    roda(["ffmpeg", "-v", "error", "-i", str(com_tit), "-i", str(wav),
          "-filter_complex", "[1:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]", "-map", "0:v", "-map", "[a]",
          "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-y", str(topo)], "som")

    shutil.copyfile(topo, dia / "topo.mp4")
    if tela_cheia:
        monta_tela_cheia(topo, dia / "completo.mp4", log)
    else:
        monta_completo(topo, reacao, dia / "completo.mp4", log)
    (dia / "post.txt").write_text(
        f"{rot['titulo']}\n\n{rot.get('legenda', '')}\n\n{' '.join(rot.get('tags', []))}\n", encoding="utf-8")
    if fila:
        para_fila(cfg, dia / "completo.mp4", dia / "post.txt", log)
    (dia / "roteiro.json").write_text(json.dumps(rot, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    log(f"PRONTO: {dia}")
    return dia


def monta_depois(pasta, reacao, log=log):
    """ELE GRAVA A REAÇÃO DEPOIS, olhando o topo.mp4 — e aí só falta juntar.

    Sem isto, pôr a reação no vídeo obrigava a refazer tudo (narração, download, render). Aqui é só
    o empilhamento: segundos, não minutos.
    """
    pasta = Path(pasta)
    topo = pasta / "topo.mp4"
    if not topo.exists():
        raise RuntimeError(f"não achei o topo.mp4 em {pasta}")
    if not reacao or not Path(reacao).exists():
        raise RuntimeError(f"não achei a gravação da reação: {reacao}")
    monta_completo(topo, reacao, pasta / "completo.mp4", log)
    log(f"PRONTO: {pasta / 'completo.mp4'}")
    return pasta / "completo.mp4"


def main():
    ap = argparse.ArgumentParser(description="vídeo narrado de notícia para você reagir por baixo")
    ap.add_argument("--montar", default="", help="pasta de um pronto: só junta a sua reação ao topo.mp4 que já existe")
    ap.add_argument("--assunto", default="")
    ap.add_argument("--quente", action="store_true", help="pega a notícia mais quente dos portais")
    ap.add_argument("--segundos", type=int, default=60)
    ap.add_argument("--reacao", default="", help="o vídeo da sua reação (vai embaixo)")
    ap.add_argument("--sem-clipes", action="store_true", help="(teste) não baixa vídeo nenhum")
    ap.add_argument("--pasta", default="")
    ap.add_argument("--tema", default="futebol", choices=["futebol", "gta"])
    ap.add_argument("--fonte-canal", default="", help="pasta de um canal (ex. canal_gta6): o assunto vem das notícias que ele já coletou")
    ap.add_argument("--tela-cheia", action="store_true", help="reels 1080x1920 sem o espaço da sua reação")
    ap.add_argument("--fila", action="store_true", help="põe o pronto na fila de postagem")
    a = ap.parse_args()
    TEMA["v"] = a.tema
    base = Path(a.pasta) if a.pasta else raiz() / "narrado"
    base.mkdir(parents=True, exist_ok=True)
    cfg_f = base / "config.json"
    cfg = {}
    if cfg_f.exists():
        try:
            cfg = json.loads(cfg_f.read_text(encoding="utf-8-sig"))
        except ValueError:
            cfg = {}
    if a.montar:
        monta_depois(a.montar, a.reacao)
        return
    assunto = a.assunto or (proximo_do_canal(a.fonte_canal, base) if a.fonte_canal else "") or (assunto_quente() if a.quente and a.tema == "futebol" else "")
    if not assunto:
        sys.exit("diga o assunto: --assunto \"...\"  (ou --quente para pegar dos portais)")
    faz(assunto, base, cfg, segundos=a.segundos, reacao=a.reacao, usar_clipes=not a.sem_clipes,
        tela_cheia=a.tela_cheia, fila=a.fila)


if __name__ == "__main__":
    main()
