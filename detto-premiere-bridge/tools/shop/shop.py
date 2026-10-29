#!/usr/bin/env python3
"""VÍDEOS DE TIKTOK SHOP AUTOMÁTICOS — do produto ao reels 9:16 pronto para a fila de postagem.

    python tools\\shop\\shop.py [--quantos 3]            # faz a fila: links colados, pastas e achados
    python tools\\shop\\shop.py --link "<link do produto ou do vídeo>" [--modo ia|eu|vendedor]
    python tools\\shop\\shop.py --produto "<pasta do produto>"   # o que você já tem em casa
    python tools\\shop\\shop.py --achar cozinha                  # ele procura o que está vendendo
    python tools\\shop\\shop.py --so-links                       # só o produtos.txt (o painel usa)

TRÊS ORIGENS DE PRODUTO (as três ligadas; cada uma vira um vídeo igual no fim):
  1. `produtos.txt`  — você cola os links do TikTok Shop (ou do vídeo do produto), um por linha.
  2. `produtos\\<nome>\\` — o que CHEGOU NA SUA CASA: as fotos/vídeos que você gravou + `produto.json`
     ({"nome","preco","link","sobre"}). É a origem mais certeira, porque a mídia é sua.
  3. `--achar <categoria>` — ele procura os vídeos de Shop que mais bombaram na categoria (yt-dlp) e a IA diz
     qual é o produto. Cai em `achados\\`.

TRÊS MODOS DE VÍDEO (`--modo`, ou "modo" no produto.json / no config):
  ia       — sem você na tela: fotos/vídeos do produto + VOZ clonada + texto na tela + legenda.
  eu       — a SUA gravação (review/unboxing) manda, e as fotos do produto entram por cima nos momentos certos.
  vendedor — reaproveita o vídeo que o vendedor já tem: corta, amplia para 9:16, texto novo e voz nova.

O roteiro é da IA (Gemini → IAs grátis → Claude, a mesma cadeia do resto do projeto), no formato que vende:
gancho de problema nos 2 primeiros segundos → o produto resolvendo → 3 vantagens com NÚMERO → preço/cupom →
CTA apontando para a vitrine. Saída em `prontos\\AAAA-MM-DD\\NN - nome.mp4` (+ `.txt` com legenda e tags) e,
com `"postar"` no config, já entra na fila do painel.
"""

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
for p in (str(TOOLS), str(TOOLS / "reels"), str(TOOLS / "canal")):
    if p not in sys.path:
        sys.path.insert(0, p)

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
FOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
W, H = 1080, 1920
FPS = 30

LOG_F = None


def log(m):
    print(m, flush=True)
    if LOG_F:
        try:
            with open(LOG_F, "a", encoding="utf-8") as f:
                f.write(f"{m}\n")
        except OSError:
            pass


def pasta_padrao():
    if os.name == "nt" and Path("E:/").exists():
        return Path("E:/DETTO/shop")
    return Path.home() / "DETTO" / "shop"


def le_json(f, padrao=None):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def grava_json(f, d):
    f = Path(f)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)


def slug(s, n=46):
    s = re.sub(r"[^\w\s-]", "", str(s or ""), flags=re.UNICODE).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:n].strip() or "produto"


def dur(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def roda(args, erro=""):
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((erro or "comando falhou") + ": " + (r.stderr or r.stdout)[-600:])
    return r.stdout


CFG_PADRAO = {
    "modo": "ia",
    "duracao": 34,
    "postar": ["todas"],
    "categorias": ["cozinha", "organização", "celular", "beleza", "fitness"],
    "max_dias": 45,
    "arroba": "@detto.galo",
    "cta": "LINK NA *VITRINE*",
    "musica": "",
    "voz_voicestudio": "",
    "velocidade_voz": 1.0,
    "instrucao_voz": "",
    "sfx": 0.3,
}


def prepara(base):
    global LOG_F
    base = Path(base)
    for p in ("produtos", "achados", "prontos", "tmp", "baixados"):
        (base / p).mkdir(parents=True, exist_ok=True)
    if not (base / "produtos.txt").exists():
        (base / "produtos.txt").write_text(
            "# Cole aqui os links do TikTok Shop (ou do vídeo do produto), um por linha.\n"
            "# LINK DE VITRINE: o TikTok Shop barra robô na página, então escreva o NOME do produto depois do\n"
            "# link, separado por | (o preço é opcional). Com o nome eu busco as fotos na internet:\n"
            "#   https://vt.tiktok.com/XXXX | suporte de celular para mesa | 49,90\n", encoding="utf-8")
    cfg = le_json(base / "config.json", {}) or {}
    mudou = False
    for k, v in CFG_PADRAO.items():
        if k not in cfg:
            cfg[k] = v
            mudou = True
    if mudou:
        grava_json(base / "config.json", cfg)
    LOG_F = base / "shop.log"
    return cfg


# ------------------------------------------------------------------ 1) DE ONDE VEM O PRODUTO
PLATAFORMAS = ("tiktok.com", "instagram.com", "youtube.com", "youtu.be", "kwai.com", "kwai-video.com",
               "facebook.com", "shopee.com", "shein.com")


def link_de_video(url):
    """este link é de um VÍDEO?

    Os links que ele cola são os CURTOS do app (vt.tiktok.com/ZS9y..., vm.tiktok.com, youtu.be/...): não têm
    /video/ nem /@ no endereço, então caíam fora e o vídeo do vendedor NUNCA era baixado — o produto ficava
    sem imagem nenhuma e a IA inventava um roteiro sobre nada.
    """
    u = url.lower()
    if re.search(r"/(video|reel|reels|shorts|watch|clip)/|tiktok\.com/@|/t/", u):
        return True
    return any(h in u for h in ("vt.tiktok.com", "vm.tiktok.com", "youtu.be", "instagram.com/share"))


def endereco_inteiro(url):
    """segue o redirecionamento do link curto (vt.tiktok.com → o endereço de verdade), para a página do
    produto/vídeo ser lida certo. Não deu, devolve o que veio."""
    try:
        r = subprocess.run(["curl", "-sSIL", "-m", "20", "-o", os.devnull, "-w", "%{url_effective}", url],
                           capture_output=True, text=True, timeout=30)
        novo = (r.stdout or "").strip()
        return novo if novo.startswith("http") else url
    except Exception:  # noqa: BLE001
        return url


def _info_da_pagina(url):
    """título, preço e fotos da PÁGINA do produto (og:/JSON-LD). O TikTok Shop barra robô com frequência:
    não deu, a gente segue com o que tiver (o link e o nome do arquivo já bastam para a IA)."""
    import urllib.request

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read(1_500_000).decode("utf-8", "replace")
    except Exception as e:
        return {}, f"não li a página ({str(e)[:90]})"
    d = {}
    for prop, campo in (("og:title", "nome"), ("og:description", "sobre"), ("product:price:amount", "preco")):
        m = re.search(rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)', html, re.I)
        if m:
            d[campo] = m.group(1).strip()
    fotos = re.findall(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I)
    if not d.get("preco"):
        m = re.search(r'R\$\s?([\d]{1,4}[.,]\d{2})', html)
        if m:
            d["preco"] = m.group(1)
    d["fotos_url"] = list(dict.fromkeys(fotos))[:6]
    return d, ""


def _baixa_fotos(urls, pasta):
    import urllib.request

    pasta.mkdir(parents=True, exist_ok=True)
    out = []
    for i, u in enumerate(urls):
        alvo = pasta / f"foto{i + 1}.jpg"
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                alvo.write_bytes(r.read(12_000_000))
            if alvo.stat().st_size > 8000:
                out.append(alvo)
        except Exception:
            continue
    return out


def produto_de_link(linha, base, cookies=None):
    """link colado → produto. Link de VÍDEO (TikTok/Reels/Shorts) traz o vídeo do vendedor junto.

    A linha do produtos.txt pode trazer o NOME (e o preço) depois do link, separados por | — é o que salva o
    LINK DE VITRINE, porque o TikTok Shop barra robô na página e de lá não vem nem nome nem foto:

        https://vt.tiktok.com/ZS9y... | suporte de celular para mesa | 49,90
    """
    from reels import baixa

    partes = [x.strip() for x in re.split(r"\s*[|;]\s*", linha) if x.strip()]
    url = partes[0]
    nome_dado = partes[1] if len(partes) > 1 else ""
    preco_dado = partes[2] if len(partes) > 2 else ""
    pasta = base / "tmp" / slug(re.sub(r"\W+", "_", url)[-40:], 40)
    pasta.mkdir(parents=True, exist_ok=True)
    p = {"link": url, "fotos": [], "video": None, "nome": nome_dado, "preco": preco_dado, "sobre": "",
         "origem": "link"}
    inteiro = endereco_inteiro(url) if link_de_video(url) or any(h in url.lower() for h in PLATAFORMAS) else url
    if inteiro != url:
        log(f"   o link curto é {inteiro[:110]}")
    # resolvido o link curto, quem decide é o endereço de VERDADE: link de vitrine (shop.tiktok.com/view/
    # product/...) não é vídeo e não vale gastar o yt-dlp nele
    e_video = link_de_video(inteiro) if inteiro != url else link_de_video(url)
    if e_video:
        clip, info = baixa(inteiro, pasta, cookies, base / "cookies.txt")
        if clip:
            p["video"] = Path(clip)
            p["nome"] = (info.get("title") or "").strip()
            p["sobre"] = (info.get("description") or "")[:600]
            log(f"   vídeo do vendedor baixado: {Path(clip).name}")
        else:
            log(f"   não baixei o vídeo do link ({info}) — sigo pela página")
    d, erro = _info_da_pagina(inteiro)
    p["nome"] = p["nome"] or d.get("nome", "")
    p["sobre"] = p["sobre"] or d.get("sobre", "")
    p["preco"] = p["preco"] or d.get("preco", "")
    if d.get("fotos_url"):
        p["fotos"] = _baixa_fotos(d["fotos_url"], pasta / "fotos")
    if nome_dado:
        p["nome"] = nome_dado   # o que VOCÊ escreveu manda (a página do Shop costuma vir vazia ou com lixo)
    if not p["video"] and not p["fotos"] and not p["nome"]:
        raise RuntimeError(
            f"deste link não veio nada{f' ({erro})' if erro else ''} — o TikTok Shop barra robô na página da "
            "vitrine, então não tenho nome nem foto do produto. RESOLVE ASSIM: escreva o nome do produto "
            "depois do link, separado por | , na mesma linha do produtos.txt — "
            "ex.: \"<link> | suporte de celular para mesa | 49,90\". Com o nome eu busco as fotos na internet. "
            "Se tiver o produto em casa, a pasta produtos\\<nome>\\ com as fotos é melhor ainda.")
    return p


def produto_da_pasta(d):
    """o que chegou na sua casa: produtos\\<nome>\\ com as mídias + produto.json"""
    d = Path(d)
    info = le_json(d / "produto.json", {}) or {}
    midias = sorted(p for p in d.iterdir() if p.suffix.lower() in VIDEO_EXT | FOTO_EXT)
    return {
        "nome": info.get("nome") or d.name,
        "preco": str(info.get("preco") or ""),
        "preco_de": str(info.get("preco_de") or ""),
        "link": info.get("link") or "",
        "sobre": info.get("sobre") or "",
        "modo": info.get("modo") or "",
        "selo": info.get("selo") or "",
        "fotos": [p for p in midias if p.suffix.lower() in FOTO_EXT],
        "video": next((p for p in midias if p.suffix.lower() in VIDEO_EXT), None),
        "eu": next((p for p in midias if p.suffix.lower() in VIDEO_EXT and re.search(r"\beu\b|review|unbox|grav", p.stem, re.I)), None),
        "pasta": d,
        "origem": "pasta",
    }


def acha_produtos(categoria, base, cfg, quantos=3, cookies=None):
    """os vídeos de Shop que mais bombaram na categoria → a IA diz qual é o produto de cada um"""
    from reels import baixa, gemini_json, video_pequeno, recente

    busca = f"ytsearch{quantos * 3}:{categoria} tiktok shop achadinho vale a pena"
    out = []
    clip, info = None, {}
    r = subprocess.run(["yt-dlp", "--flat-playlist", "-J", busca], capture_output=True, text=True)
    try:
        itens = (json.loads(r.stdout).get("entries") or [])
    except Exception:
        itens = []
    itens = [i for i in itens if (i.get("duration") or 0) <= 180]
    itens.sort(key=lambda i: i.get("view_count") or 0, reverse=True)
    for i in itens[: quantos * 2]:
        if len(out) >= quantos:
            break
        url = i.get("url") or i.get("webpage_url") or ""
        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={i.get('id')}"
        pasta = base / "achados" / slug(i.get("id") or str(time.time()), 24)
        clip, info = baixa(url, pasta, cookies, base / "cookies.txt")
        if not clip:
            continue
        if not recente(info, cfg.get("max_dias", 45)):
            continue
        g = gemini_json([{"text": "Este vídeo mostra um produto à venda. Responda em JSON: "
                                  '{"produto":"nome curto do produto","preco":"se aparecer","sobre":"o que ele resolve, 1 frase",'
                                  '"vale":true/false}. vale=false se não der para saber qual é o produto.'},
                         {"video": str(video_pequeno(clip, pasta / "peq.mp4"))}], essencial=False)
        if not g or not g.get("vale") or not g.get("produto"):
            log(f"   {url}: não deu para saber o produto — pulo")
            continue
        out.append({"nome": g["produto"], "preco": str(g.get("preco") or ""), "sobre": g.get("sobre", ""),
                    "link": url, "video": Path(clip), "fotos": [], "origem": "achado", "modo": "vendedor"})
        log(f"   achei: {g['produto']}")
    return out


# ------------------------------------------------------------------ 2) O ROTEIRO (a IA)
REGRAS = """Você escreve roteiros de vídeo de TikTok Shop (afiliado) em PORTUGUÊS DO BRASIL, para um criador de
conteúdo brasileiro. O vídeo é vertical (9:16), tem {dur} segundos e precisa VENDER.

O que faz esse tipo de vídeo vender (siga TUDO):
- Os 2 PRIMEIROS SEGUNDOS são o problema de quem assiste, não o produto ("minha cozinha vivia um caos até...").
- Depois o produto RESOLVENDO, em uso, nunca parado numa foto de catálogo.
- 3 vantagens, cada uma com NÚMERO CONCRETO (cabe 18 potes, aguenta 9 kg, monta em 2 minutos). Número é o que
  faz salvar e mandar para alguém.
- Uma objeção respondida ("parece frágil, mas...").
- Preço e cupom perto do fim, com urgência de verdade (não invente promoção que não existe).
- CTA final mandando para a VITRINE / o link do produto que aparece no vídeo.
- Fala de gente: frases curtas, sem palavra difícil, sem "incrível", "revolucionário", "transforme sua vida".
- NUNCA invente característica, medida, garantia ou preço que não esteja no material. Sem o dado, não fale dele.

Responda SÓ um JSON:
{{"gancho":"a frase dos 2 primeiros segundos",
  "cenas":[{{"fala":"o que a narração diz nesta cena","tela":"2 a 5 PALAVRAS na tela (caixa alta); *palavra* fica amarela",
             "midia":"foto1|foto2|video|eu","movimento":"zoom|afasta|direita|esquerda","sfx":"pop|whoosh|ding|click|"}}],
  "vantagens":["cabe *18 POTES*","aguenta *9 KG*","monta em *2 MINUTOS*"],
  "selo":"ESGOTANDO ou FRETE GRÁTIS ou NOVIDADE (ou vazio)",
  "fim":"a frase da cartela final (3 a 5 palavras)",
  "legenda":"a legenda do post, 1 ou 2 linhas",
  "tags":["#achadinhos","#tiktokshop"]}}
Entre 5 e 9 cenas, cada fala de 3 a 7 segundos. A soma das falas tem que dar perto de {dur} segundos."""


def roteiro(produto, modo, cfg, log=log):
    from reels import gemini_json

    mid = []
    if produto.get("eu") and modo == "eu":
        mid.append("eu (a gravação dele com o produto)")
    if produto.get("video"):
        mid.append("video (o vídeo do produto)")
    for i in range(len(produto.get("fotos") or [])):
        mid.append(f"foto{i + 1}")
    p = (REGRAS.format(dur=int(cfg.get("duracao", 34)))
         + f"\n\nPRODUTO: {produto.get('nome') or '(sem nome)'}"
         + (f"\nPREÇO: R$ {produto['preco']}" if produto.get("preco") else "\nPREÇO: não sei (não fale de preço)")
         + (f"\nSOBRE: {produto.get('sobre')}" if produto.get("sobre") else "")
         + f"\nMÍDIA DISPONÍVEL (use só estas em \"midia\"): {', '.join(mid) or 'foto1'}"
         + ("\nMODO: a narração é a VOZ DELE gravada; escreva as falas como ele falaria, em 1ª pessoa."
            if modo == "eu" else "\nMODO: narração em off, 1ª pessoa, como quem já usou o produto."))
    g = gemini_json([{"text": p}], temperatura=0.9)
    if not g or not g.get("cenas"):
        raise RuntimeError("nenhuma IA escreveu o roteiro (sem GEMINI_API_KEY / IAs grátis / Claude?)")
    g["cenas"] = [c for c in g["cenas"] if c.get("fala")][:9]
    if not g["cenas"]:
        raise RuntimeError("a IA não devolveu cena nenhuma com fala")
    g.setdefault("gancho", g["cenas"][0].get("tela") or "OLHA SÓ ISSO")
    g.setdefault("fim", "TÁ NA MINHA *VITRINE*")
    g.setdefault("vantagens", [])
    g.setdefault("tags", ["#achadinhos", "#tiktokshop"])
    return g


# ------------------------------------------------------------------ 3) VOZ E LEGENDA
def narra(texto, saida, cfg, log=log):
    """a narração na voz clonada (VoiceStudio → Fish), a mesma cadeia do canal de notícias e das histórias"""
    import voz as V

    falado = V.pronuncia(texto)
    url = cfg.get("voicestudio") or V.voicestudio_url()
    if V.voicestudio_pronto(url):
        voz_id, voz_nome = V.voicestudio_escolhe(url, cfg.get("voz_voicestudio"), log)
        log(f"voz: VoiceStudio — \"{voz_nome}\"")
        V.voicestudio_fala(falado, saida, voz_id, url, velocidade=float(cfg.get("velocidade_voz", 1.0)),
                           instrucao=cfg.get("instrucao_voz") or V.INSTRUCAO_PADRAO)
    else:
        chave = os.environ.get("FISH_API_KEY")
        if not chave:
            raise RuntimeError("sem voz: cadastre a sua voz clonada no VoiceStudio (sem nenhuma voz ele sorteia "
                               "uma qualquer) ou ponha a FISH_API_KEY")
        log("voz: Fish Audio (o VoiceStudio está fechado ou sem voz cadastrada)")
        V.fish_fala(falado, saida, os.environ.get("FISH_VOZ", ""), chave)
    try:
        V.sem_pausas(saida)
    except Exception:
        pass
    return saida


def palavras(audio, log=log):
    """o que a voz falou, palavra a palavra (faster-whisper) — é daí que saem as legendas e os tempos das cenas"""
    out = Path(audio).with_suffix(".words.json")
    try:
        roda([sys.executable, str(TOOLS / "transcrever.py"), str(audio), str(out)], "transcrição")
        d = le_json(out, [])
        # o transcrever.py grava uma LISTA de {"w","s","e"} — tratar como dicionário estourava
        # ('list' object has no attribute 'get') e o vídeo saía SEM legenda nenhuma
        if isinstance(d, list):
            return d
        return (d or {}).get("words") or (d or {}).get("palavras") or []
    except Exception as e:
        log(f"legenda: não transcrevi ({str(e)[:120]}) — sigo sem legenda")
        return []


def encaixa(rot, words, total):
    """cada cena termina onde caiu a ÚLTIMA palavra da fala dela (alinhamento global, o mesmo jeito das histórias);
    sem transcrição, divide o tempo pelo tamanho da fala"""
    cenas = rot["cenas"]
    if not words:
        pesos = [max(1, len((c.get("fala") or "").split())) for c in cenas]
        t = 0.0
        for c, p in zip(cenas, pesos):
            c["ini"], t = t, t + total * p / sum(pesos)
            c["fim"] = t
        return cenas
    # o alinhamento já existe nas histórias, mas lá a fala se chama "narracao" e o fim de cada cena é "ate":
    # chamar direto com as cenas do shop não marcava NADA e, com o setdefault, TODA cena ficava 0 → total
    # (as cartelas todas na tela ao mesmo tempo e a imagem parada). Aqui traduzimos as chaves nos dois sentidos.
    try:
        import historias.historias as HI

        espelho = {"cenas": [{"narracao": c.get("fala") or ""} for c in cenas]}
        HI.encaixa_cenas(espelho, words)
        ates = [float(e.get("ate") or 0) for e in espelho["cenas"]]
        if any(ates):
            t0 = 0.0
            for c, ate in zip(cenas, ates):
                c["ini"] = t0
                c["fim"] = t0 = max(t0 + 0.6, ate)
            cenas[-1]["fim"] = max(cenas[-1]["fim"], total)
            return cenas
    except Exception as e:  # noqa: BLE001 — cai no plano B em vez de derrubar o vídeo
        log(f"   encaixe pelo alinhamento falhou ({str(e)[:90]}) — divido pelas palavras")
    # plano B: pelas palavras, na ordem
    nomes = [(c.get("fala") or "").split() for c in cenas]
    i, t0 = 0, 0.0
    for c, ws in zip(cenas, nomes):
        i = min(len(words) - 1, i + len(ws))
        fim = float(words[i].get("e") or words[i].get("end") or words[i].get("fim") or t0)
        c["ini"], c["fim"] = t0, max(t0 + 0.8, fim)
        t0 = c["fim"]
    cenas[-1]["fim"] = total
    return cenas


def blocos_legenda(words, ate, por=3):
    """legenda em blocos de 2–3 palavras (é como ela entra nos vídeos que vendem)"""
    out = []
    bloco, ini = [], None
    for w in words:
        t0 = float(w.get("s") or w.get("start") or w.get("ini") or 0)
        t1 = float(w.get("e") or w.get("end") or w.get("fim") or t0)
        txt = (w.get("w") or w.get("word") or w.get("texto") or "").strip()
        if not txt:
            continue
        if ini is None:
            ini = t0
        bloco.append(txt)
        if len(bloco) >= por:
            out.append({"ini": ini, "fim": t1, "txt": " ".join(bloco)})
            bloco, ini = [], None
    if bloco and ini is not None:
        out.append({"ini": ini, "fim": ate, "txt": " ".join(bloco)})
    for b, prox in zip(out, out[1:] + [None]):
        b["fim"] = min(ate, prox["ini"] if prox else ate)
    return [b for b in out if b["fim"] > b["ini"] + 0.05]


# ------------------------------------------------------------------ 4) A IMAGEM: fotos e vídeo viram 9:16
def _tamanho(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    try:
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
        return w, h
    except Exception:
        return W, H


# fundo desfocado BARATO: borra em miniatura e volta ao tamanho. O boxblur direto em 1080x1920 quadro a quadro
# deixava cada cena em dezenas de segundos no PC dele.
FUNDO = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
         f"scale=136:240,boxblur=7:1,scale={W}:{H},eq=brightness=-0.09")


def _ken_burns(foto, saida, segundos, movimento="zoom"):
    """foto parada mata o vídeo: ela entra com zoom/paneio lento dentro do 9:16, com o fundo desfocado.
    O zoom é feito com scale+eval=frame (e NÃO com zoompan: o zoompan reescalava a foto inteira a cada quadro e
    levava ~57 s por cena; assim leva ~2 s)."""
    iw, ih = _tamanho(foto)
    esc = min(W / max(1, iw), H / max(1, ih))
    fw, fh = max(2, int(iw * esc) // 2 * 2), max(2, int(ih * esc) // 2 * 2)
    t = max(0.3, float(segundos))
    z = 0.16
    if movimento == "afasta":
        larg = f"{fw}*({1 + z:.3f}-{z}*t/{t:.3f})"
        x, y = "(iw-ow)/2", "(ih-oh)/2"
    elif movimento in ("direita", "esquerda"):
        larg = f"{fw}*{1 + z:.3f}"
        andar = f"t/{t:.3f}" if movimento == "direita" else f"(1-t/{t:.3f})"
        x, y = f"(iw-ow)*{andar}", "(ih-oh)/2"
    else:  # zoom
        larg = f"{fw}*(1+{z}*t/{t:.3f})"
        x, y = "(iw-ow)/2", "(ih-oh)/2"
    filtro = (f"[0:v]{FUNDO}[bg];"
              f"[0:v]scale={fw}:{fh},scale=w='{larg}':h=-2:eval=frame,crop={fw}:{fh}:{x}:{y}[fr];"
              f"[bg][fr]overlay=(W-w)/2:(H-h)/2,fps={FPS},format=yuv420p[v]")
    roda(["ffmpeg", "-v", "error", "-loop", "1", "-t", f"{t:.3f}", "-i", str(foto),
          "-filter_complex", filtro, "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "18",
          "-preset", "veryfast", "-y", str(saida)], "foto → vídeo")
    return saida


def _trecho(video, saida, segundos, de=0.0):
    """um pedaço do vídeo em 9:16 (o horizontal entra ampliado com o fundo desfocado, como nos reels dele)"""
    filtro = (f"[0:v]{FUNDO}[bg];"
              f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease[fr];"
              f"[bg][fr]overlay=(W-w)/2:(H-h)/2,fps={FPS},format=yuv420p[v]")
    roda(["ffmpeg", "-v", "error", "-ss", f"{de:.3f}", "-t", f"{segundos:.3f}", "-i", str(video),
          "-filter_complex", filtro, "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "18",
          "-preset", "veryfast", "-y", str(saida)], "trecho do vídeo")
    return saida


def midia_da_cena(c, produto, modo, i=0):
    """qual arquivo entra nesta cena (a IA pede; se faltar, a gente arruma o que tem)"""
    pedido = str(c.get("midia") or "").strip().lower()
    fotos = produto.get("fotos") or []
    m = re.match(r"foto(\d+)", pedido)
    if m and fotos:
        return fotos[min(len(fotos) - 1, int(m.group(1)) - 1)], "foto"
    if pedido == "eu" and produto.get("eu"):
        return produto["eu"], "video"
    if pedido in ("video", "vendedor") and produto.get("video"):
        return produto["video"], "video"
    if modo == "eu" and produto.get("eu"):
        return produto["eu"], "video"
    if produto.get("video"):
        return produto["video"], "video"
    if fotos:
        return fotos[i % len(fotos)], "foto"   # roda as fotos: a mesma em todas as cenas parecia vídeo travado
    return None, ""


def fotos_da_internet(produto, base, quantas=4, log=log):
    """produto SEM nenhuma foto/vídeo → busca imagens dele na internet (o mesmo buscador das camisas).

    Sem isso o vídeo saía com fundo escuro liso em todas as cenas: narração e cartelas por cima de NADA.
    """
    nome = (produto.get("nome") or "").strip()
    if not nome:
        return []
    sys.path.insert(0, str(TOOLS))
    import busca_imagem as BI

    pasta = base / "fotos_web" / slug(nome, 40)
    pasta.mkdir(parents=True, exist_ok=True)
    achadas = sorted(p for p in pasta.glob("*") if p.suffix.lower() in FOTO_EXT)
    if achadas:
        log(f"   fotos da internet (do cache): {len(achadas)}")
        return achadas[:quantas]
    palavras_nome = [w for w in re.split(r"\W+", nome) if len(w) > 2][:4]
    buscas = [nome, f"{nome} produto foto", f"{nome} review"]
    for k, q in enumerate(buscas):
        if len(achadas) >= quantas:
            break
        try:
            r = BI.buscar(q, exige=palavras_nome[:2], destino=pasta / f"web{k}.jpg", minimo=500, log=lambda *_: None)
        except Exception as e:  # noqa: BLE001 — buscador fora do ar não derruba a rodada
            log(f"   busca de foto falhou ({str(e)[:90]})")
            r = None
        if r and Path(r["file"]).exists():
            achadas.append(Path(r["file"]))
    log(f"   fotos da internet: {len(achadas)}" if achadas else "   não achei foto deste produto na internet")
    return achadas


def base_visual(rot, produto, modo, tmp, log=log, cauda=2.2):
    """monta a BASE (só imagem, sem texto): cada cena vira um pedaço 9:16 e tudo é emendado"""
    partes, t_video = [], 0.0
    fonte_video = produto.get("eu") if modo == "eu" else produto.get("video")
    dur_fonte = dur(fonte_video) if fonte_video else 0.0
    for i, c in enumerate(rot["cenas"]):
        seg = max(0.9, float(c["fim"]) - float(c["ini"]))
        arq, tipo = midia_da_cena(c, produto, modo, i)
        saida = tmp / f"cena{i:02d}.mp4"
        if arq is None:
            roda(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x10121a:s={W}x{H}:r={FPS}",
                  "-t", f"{seg:.3f}", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-y", str(saida)], "fundo")
        elif tipo == "foto":
            _ken_burns(arq, saida, seg, c.get("movimento") or "zoom")
        else:
            de = t_video if dur_fonte > seg else 0.0
            if dur_fonte and de + seg > dur_fonte:
                de = max(0.0, (dur_fonte - seg) * (i / max(1, len(rot["cenas"]))))
            _trecho(arq, saida, seg, de)
            t_video = de + seg
        partes.append(saida)
    lista = tmp / "partes.txt"
    lista.write_text("".join(f"file '{p.as_posix()}'\n" for p in partes), encoding="utf-8")
    base = tmp / "base.mp4"
    # a cartela final entra DEPOIS da última fala: o último quadro congela por ela (sem isso o vídeo acabava
    # junto com a narração e a chamada de compra não aparecia)
    roda(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
          "-vf", f"tpad=stop_mode=clone:stop_duration={cauda:.2f},fps={FPS}",
          "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-y", str(base)], "emenda")
    return base


# ------------------------------------------------------------------ 5) AS CARTELAS (texto por cima)
def cartelas(rot, produto, cfg, cenas, legendas, tmp, log=log):
    """desenha no Chromium as peças de texto e devolve [(png, ini, fim)] para o FFmpeg pôr por cima"""
    pecas, tempos = [], []
    cta = cfg.get("cta") or "LINK NA *VITRINE*"
    preco = str(produto.get("preco") or "")
    meio = len(cenas) // 2
    for i, c in enumerate(cenas):
        p = {"saida": f"cart{i:02d}.png", "texto": (c.get("tela") or "").strip()}
        if i == 0:
            p["texto"] = p["texto"] or rot.get("gancho", "")
            p["topo_alto"] = True
            if rot.get("selo") or produto.get("selo"):
                p["selo"] = (produto.get("selo") or rot.get("selo"))[:18]
        if i == meio and rot.get("vantagens"):
            p["tipo"] = "vantagens"
            p["itens"] = rot["vantagens"][:4]
        if preco and i >= len(cenas) - 3:
            p["preco"] = preco
            if produto.get("preco_de"):
                p["preco_de"] = f"R$ {produto['preco_de']}"
        if i >= len(cenas) - 2:
            p["cta"] = cta
        if not any(p.get(k) for k in ("texto", "preco", "cta", "itens", "selo")):
            continue
        pecas.append(p)
        tempos.append((p["saida"], float(c["ini"]), float(c["fim"])))
    # a cartela final: o pedido de compra, 2,2 s
    fim_ini = float(cenas[-1]["fim"])
    pecas.append({"saida": "cart_fim.png", "tipo": "fim", "texto": rot.get("fim") or "TÁ NA MINHA *VITRINE*",
                  "sub": "é o primeiro da vitrine" if not produto.get("link") else "link na vitrine deste vídeo",
                  "arroba": cfg.get("arroba", ""), "preco": preco})
    tempos.append(("cart_fim.png", fim_ini, fim_ini + 2.2))
    # as legendas da fala
    for i, b in enumerate(legendas):
        pecas.append({"saida": f"leg{i:03d}.png", "legenda": b["txt"]})
        tempos.append((f"leg{i:03d}.png", b["ini"], b["fim"]))
    pedido = tmp / "cartelas.json"
    grava_json(pedido, {"largura": W, "altura": H, "pecas": pecas})
    roda(["node", str(AQUI / "cartelas.js"), str(pedido)], "cartelas")
    return [(tmp / n, a, b) for n, a, b in tempos if (tmp / n).exists()]


def poe_cartelas(base, pecas, saida, total):
    """um overlay por cartela, cada um ligado só no tempo dele (filtro em cadeia)"""
    from ffcompat import filtro_complexo

    entradas = ["-i", str(base)]
    for p, _, _ in pecas:
        entradas += ["-i", str(p)]
    filtro, atual = [], "[0:v]"
    for i, (_, a, b) in enumerate(pecas, start=1):
        alvo = f"[v{i}]" if i < len(pecas) else "[vf]"
        filtro.append(f"{atual}[{i}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'{alvo}")
        atual = alvo
    if not pecas:
        filtro.append("[0:v]null[vf]")
    f = Path(saida).with_suffix(".filtro.txt")
    f.write_text(";".join(filtro), encoding="utf-8")
    args = ["ffmpeg", "-v", "error"] + entradas + filtro_complexo(f) + [
        "-map", "[vf]", "-t", f"{total:.3f}", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-y", str(saida)]
    roda(args, "cartelas no vídeo")
    return saida


# ------------------------------------------------------------------ 6) O SOM
def som(video, voz, rot, cenas, cfg, tmp, saida, produto=None, modo="ia", log=log):
    """narração (ou a voz dele) + efeitos nas viradas + trilha, tudo nivelado em -14 LUFS"""
    efeitos = []
    try:
        import historias.historias as HI

        pasta_sons = Path(os.environ.get("DETTO_SONS") or (HI.pasta_padrao() / "sons"))
        for c in cenas:
            cat = (c.get("sfx") or "").strip().lower()
            if not cat:
                continue
            # primeiro a pasta de efeitos das histórias (myinstants); sem ela, o som sai sintetizado pelo FFmpeg
            achados = sorted((pasta_sons / cat).glob("*")) if (pasta_sons / cat).is_dir() else []
            if achados:
                efeitos.append((achados[len(efeitos) % len(achados)], float(c["ini"])))
                continue
            alvo = tmp / f"sfx_{len(efeitos):02d}.wav"
            try:
                HI.som_sintetico(cat, alvo)
            except Exception:
                continue
            if alvo.exists():
                efeitos.append((alvo, float(c["ini"])))
    except Exception as e:
        log(f"efeitos: sem som desta vez ({str(e)[:80]})")
    entradas = ["-i", str(video)]
    if voz:
        entradas += ["-i", str(voz)]
    for f, _ in efeitos:
        entradas += ["-i", str(f)]
    n_voz = 1 if voz else 0
    partes, mix = [], []
    if voz:
        partes.append("[1:a]aresample=48000,alimiter=limit=0.95[vz]")
        mix.append("[vz]")
    elif modo == "eu":
        partes.append("[0:a]aresample=48000[vz]")
        mix.append("[vz]")
    vol = float(cfg.get("sfx", 0.3))
    for i, (_, t) in enumerate(efeitos):
        idx = 1 + n_voz + i
        partes.append(f"[{idx}:a]aresample=48000,adelay={int(t * 1000)}|{int(t * 1000)},volume={vol}[s{i}]")
        mix.append(f"[s{i}]")
    if not mix:
        roda(["ffmpeg", "-v", "error", "-i", str(video), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
              "-t", f"{dur(video):.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-y", str(saida)], "áudio vazio")
        return saida
    # apad: a cartela final vem DEPOIS da última fala — com "-shortest" o vídeo era cortado no fim da narração
    partes.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:dropout_transition=0,"
                                 "loudnorm=I=-14:TP=-1.5:LRA=11,apad[a]")
    from ffcompat import filtro_complexo

    f = Path(saida).with_suffix(".som.txt")
    f.write_text(";".join(partes), encoding="utf-8")
    roda(["ffmpeg", "-v", "error"] + entradas + filtro_complexo(f) +
         ["-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
          "-t", f"{dur(video):.3f}", "-y", str(saida)], "som")
    return saida


# ------------------------------------------------------------------ 7) O VÍDEO INTEIRO
def faz_video(produto, base, cfg, modo="", log=log):
    """produto → reels 9:16 pronto. Devolve (mp4, txt)."""
    modo = (modo or produto.get("modo") or cfg.get("modo") or "ia").lower()
    if modo == "eu" and not produto.get("eu") and not produto.get("video"):
        log("modo \"eu\": não achei a sua gravação na pasta — faço no modo ia (voz clonada)")
        modo = "ia"
    nome = slug(produto.get("nome") or "produto")
    tmp = base / "tmp" / slug(nome, 30)
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    log(f"\n== {nome} ({modo})")

    # A IMAGEM VEM ANTES DO ROTEIRO: sem material a IA escrevia um roteiro inventado ("minha cozinha vivia
    # uma bagunça") sobre um produto que ela não conhece — e o vídeo sairia com fundo preto.
    if not produto.get("fotos") and not produto.get("video") and not produto.get("eu"):
        if cfg.get("fotos_internet", True):
            produto["fotos"] = fotos_da_internet(produto, base, log=log)
        if not produto.get("fotos"):
            raise RuntimeError(
                f'o produto "{produto.get("nome") or nome}" não tem NENHUMA imagem nem vídeo e eu não achei foto '
                "dele na internet — o vídeo sairia com fundo preto. Ponha as fotos em "
                f"produtos\\{nome}\\ (ou cole o link do VÍDEO do produto).")

    rot = roteiro(produto, modo, cfg, log)
    log(f"   roteiro: {len(rot['cenas'])} cenas — \"{rot.get('gancho', '')[:60]}\"")

    voz_f, words = None, []
    if modo == "eu" and (produto.get("eu") or produto.get("video")):
        fonte = produto.get("eu") or produto["video"]
        voz_f = None
        words = palavras(fonte, log)
        total = dur(fonte)
    else:
        texto = " ".join(c["fala"] for c in rot["cenas"])
        voz_f = narra(texto, tmp / "voz.wav", cfg, log)
        words = palavras(voz_f, log)
        total = dur(voz_f)
    if total < 3:
        raise RuntimeError("a narração saiu vazia (a voz não gerou áudio)")
    cenas = encaixa(rot, words, total)
    legendas = blocos_legenda(words, total)
    log(f"   {total:.0f}s de fala, {len(legendas)} legendas")

    vis = base_visual(rot, produto, modo, tmp, log)
    pecas = cartelas(rot, produto, cfg, cenas, legendas, tmp, log)
    total_v = max(total, float(cenas[-1]["fim"])) + 2.2  # a cartela final fica depois da última fala
    com_texto = poe_cartelas(vis, pecas, tmp / "com_texto.mp4", total_v)
    com_som = som(com_texto, voz_f, rot, cenas, cfg, tmp, tmp / "com_som.mp4", produto, modo, log)

    final = com_som
    musica = cfg.get("musica")
    if musica and Path(musica).exists():
        faixas = sorted(p for p in Path(musica).glob("*") if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg"})
        if faixas:
            try:
                roda([sys.executable, str(TOOLS / "trilha.py"), str(com_som), f"0:00={faixas[0]}"], "trilha")
                t = com_som.with_name(com_som.stem + " com trilha.mp4")
                if t.exists():
                    final = t
            except Exception as e:
                log(f"trilha: deixei sem música ({str(e)[:100]})")

    dia = dt.date.today().isoformat()
    destino = base / "prontos" / dia
    destino.mkdir(parents=True, exist_ok=True)
    n = len(list(destino.glob("*.mp4"))) + 1
    saida = destino / f"{n:02d} - {nome}.mp4"
    shutil.copyfile(final, saida)
    tags = " ".join(dict.fromkeys([t if t.startswith("#") else f"#{t}" for t in (rot.get("tags") or [])]))
    txt = destino / f"{saida.stem}.txt"
    txt.write_text(f"{rot.get('legenda') or rot.get('gancho', '')}\n\n{tags}\n\n---\n"
                   f"Produto: {produto.get('nome', '')}\nPreço: {produto.get('preco') or '-'}\n"
                   f"Link: {produto.get('link') or '-'}\nModo: {modo}\n", encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    log(f"   pronto: {saida}")
    return saida, txt


def para_fila(cfg, video, txt, log=log):
    """manda para a fila de postagem do painel (as mesmas contas dos reels)"""
    destinos = cfg.get("postar") or []
    if not destinos:
        return []
    try:
        sys.path.insert(0, str(TOOLS / "postar"))
        import postar as P
        from reels import destinos_reels

        pb = P.pasta_padrao()
        alvos = destinos_reels({"postar": destinos}, pb)
        postos = P.enfileira(pb, video, alvos, txt)
        log(f"   na fila: {', '.join(Path(p).parent.name for p in postos)}")
        return postos
    except Exception as e:
        log(f"   não consegui pôr na fila ({str(e)[:140]}) — o vídeo está em prontos\\")
        return []


# ------------------------------------------------------------------ 8) A FILA DE PRODUTOS
def _tira_link(base, url, ok, motivo=""):
    f = base / "produtos.txt"
    linhas = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip() != url]
    f.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    with open(base / "produtos_feitos.txt", "a", encoding="utf-8") as g:
        g.write(f"{dt.date.today()} {'ok' if ok else 'FALHOU'} {url}" + (f" — {motivo}" if motivo else "") + "\n")
    if not ok:
        with open(base / "produtos_falhos.txt", "a", encoding="utf-8") as g:
            g.write(f"{dt.datetime.now():%d/%m %H:%M}\t{url}\t{motivo or 'veja o registro'}\n")


def pastas_pendentes(base, hist):
    """pastas de produto que ainda não viraram vídeo (produtos\\<nome>\\)"""
    out = []
    for d in sorted((base / "produtos").iterdir() if (base / "produtos").is_dir() else []):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if hist.get("pastas", {}).get(d.name) and not (d / ".refazer").exists():
            continue
        if not any(p.suffix.lower() in VIDEO_EXT | FOTO_EXT for p in d.iterdir()):
            continue
        out.append(d)
    return out


def trava_rodada(base, nome=".shop_rodando"):
    """só UM shop.py por vez (o painel e a tarefa do Windows juntos fariam o mesmo produto duas vezes)"""
    f = open(Path(base) / nome, "a+")
    try:
        if os.name == "nt":
            import msvcrt

            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except OSError:
        f.close()
        return None


def main():
    ap = argparse.ArgumentParser(description="vídeos de TikTok Shop automáticos (9:16)")
    ap.add_argument("--pasta", default=str(pasta_padrao()))
    ap.add_argument("--quantos", type=int, default=3)
    ap.add_argument("--link", help="um link de produto/vídeo (faz só esse)")
    ap.add_argument("--produto", help="uma pasta de produto (o que você tem em casa)")
    ap.add_argument("--achar", help="categoria: ele procura o que está vendendo")
    ap.add_argument("--so-links", action="store_true", help="só os links do produtos.txt (o painel usa)")
    ap.add_argument("--modo", choices=["ia", "eu", "vendedor"], help="o que entra na imagem")
    ap.add_argument("--cookies", help="chrome, edge ou firefox (TikTok/Instagram pedindo login)")
    ap.add_argument("--nao-postar", action="store_true", help="não põe na fila de postagem")
    a = ap.parse_args()

    base = Path(a.pasta)
    cfg = prepara(base)
    trava = trava_rodada(base)
    if not trava:
        log("outro shop.py já está rodando (painel ou tarefa do Windows) — saio para não fazer o mesmo produto duas vezes")
        return
    hist = le_json(base / "historico.json", {"pastas": {}, "links": {}}) or {"pastas": {}, "links": {}}
    fila, feitos = [], 0

    if a.link:
        fila.append(("link", a.link))
    elif a.produto:
        fila.append(("pasta", Path(a.produto)))
    elif a.achar:
        for p in acha_produtos(a.achar, base, cfg, a.quantos, a.cookies):
            fila.append(("pronto", p))
    else:
        links = [l.strip() for l in (base / "produtos.txt").read_text(encoding="utf-8").splitlines()
                 if l.strip().startswith("http")]
        fila += [("link", u) for u in dict.fromkeys(links)]
        if not a.so_links:
            fila += [("pasta", d) for d in pastas_pendentes(base, hist)]
            if not fila:
                for cat in (cfg.get("categorias") or [])[:1]:
                    log(f"nada na lista — procurando em \"{cat}\"")
                    fila += [("pronto", p) for p in acha_produtos(cat, base, cfg, a.quantos, a.cookies)]

    if not fila:
        log("nada para fazer: cole um link em produtos.txt ou ponha as fotos numa pasta em produtos\\")
        return
    log(f"{len(fila)} produto(s) na fila")

    for tipo, item in fila:
        if feitos >= max(1, a.quantos):
            break
        try:
            if tipo == "link":
                p = produto_de_link(item, base, a.cookies)
            elif tipo == "pasta":
                p = produto_da_pasta(item)
            else:
                p = item
            video, txt = faz_video(p, base, cfg, a.modo, log)
        except Exception as e:
            log(f"   NÃO FIZ: {str(e)[:300]}")
            if tipo == "link":
                _tira_link(base, item, ok=False, motivo=str(e)[:200])
            else:  # pasta/achado: o motivo também aparece no painel ("Produtos que NÃO viraram vídeo")
                nome_item = Path(item).name if tipo == "pasta" else str(item.get("nome") or "produto")
                with open(base / "produtos_falhos.txt", "a", encoding="utf-8") as g:
                    g.write(f"{dt.datetime.now():%d/%m %H:%M}\t{nome_item}\t{str(e)[:200]}\n")
            continue
        if not a.nao_postar:
            para_fila(cfg, video, txt, log)
        if tipo == "link":
            _tira_link(base, item, ok=True)
            hist.setdefault("links", {})[item] = {"dia": dt.date.today().isoformat(), "arquivo": video.name}
        elif tipo == "pasta":
            hist.setdefault("pastas", {})[Path(item).name] = {"dia": dt.date.today().isoformat(), "arquivo": video.name}
            (Path(item) / ".refazer").unlink(missing_ok=True)
        grava_json(base / "historico.json", hist)
        feitos += 1

    log(f"\n{feitos} vídeo(s) de Shop prontos em {base / 'prontos' / dt.date.today().isoformat()}")


if __name__ == "__main__":
    main()
