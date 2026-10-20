# -*- coding: utf-8 -*-
"""CANAL AUTOMÁTICO do Galo: notícias da imprensa + sua narração (voz clonada) + você de máscara + postagem sozinha.

    python tools\\canal\\canal.py                 → uma rodada: coleta, e se tiver material, monta e POSTA
    python tools\\canal\\canal.py --login         → liga o canal novo (uma vez)
    python tools\\canal\\canal.py --agendar       → o Windows roda a cada 2 h, das 8h às 23h (PC ligado)
    python tools\\canal\\canal.py --nao-postar    → monta e deixa em prontos\\ (para conferir antes)
    python tools\\canal\\canal.py --pasta "D:\\canal"

PASTA (padrão E:\\DETTO\\canal_galo, criada na 1ª vez):
  mascara\\     você de máscara, 5–10 s cada, o NOME diz o clima: rindo.mov, bravo.mov, comemorando.mov,
               pensativo.mov, concordando.mov, surpreso.mov, falando.mov (vários por clima: rindo 2.mov...)
  voz\\minha_voz.wav   20–30 s da sua voz falando normal, sem música (é a voz clonada)
  PELO DRIVE: suba em  Meu Drive\\DETTO\\canal_noticias\\mascara  e  ...\\voz  (qualquer áudio: .m4a do iPhone serve)
               → cada rodada copia sozinha para cá (a voz vira minha_voz.wav)
  client_secret.json / token.json   ligação com o canal (LEIA-ME.txt)
  config.json   fontes (canais da imprensa), nome do canal, tamanho do vídeo, quantos por dia
  fontes\\      vídeos baixados da imprensa (apagados depois de usados)
  prontos\\     vídeo, thumb e texto de cada postagem;  historico.json  o que já foi visto/usado/postado

RODADA: 1) vídeos novos das fontes que falam do Galo (título; canal oficial = tudo) → baixa e transcreve
2) o Gemini marca os trechos sobre o Galo (começo/fim, manchete, clima, nota de interesse) → banco de trechos
3) com trechos suficientes (min_trechos), monta: abertura falada → trecho → comentário → trecho … → fechamento
4) a narração na sua voz (Chatterbox), você de máscara no canto com o clima de cada parte, créditos das fontes
5) thumb (rostos dos apresentadores recortados + escudo + texto) e posta: título, descrição, tags, "feito com IA".
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
FONTES_DIR = PONTE / "fonts"
sys.path.insert(0, str(TOOLS / "reels"))
sys.path.insert(0, str(TOOLS))
from reels import audio_bom, baixa, cor_sdr, dur, gemini_json, grava_json, le_json, norm, slug, tamanho, ytdlp  # noqa: E402

W, H, FPS = 1920, 1080, 30
JANELA = (40, 120, 1440, 810)  # vídeo principal (x, y, w, h)
CANTO = (1510, 120, 370, 370)  # você de máscara
FAIXA = (40, 950, 1840, 100)  # manchete / legenda
CLIMAS = ["rindo", "bravo", "comemorando", "pensativo", "concordando", "surpreso", "falando"]

CONFIG_PADRAO = {
    "nome_canal": "GALO NOTÍCIAS",
    "time": "CAM",
    # prioridade: 1 = imprensa (o programa/corte original) · 2 = TV Galo (às vezes) · 3 = canais que já juntam as
    # notícias do Galo (cortes de Globo Esporte, Jogo Aberto, Itatiaia...) · 4 = qualquer outro achado na busca
    "fontes": [
        {"canal": "@JogoAberto", "id": "UCZaOZdn-Y-I5ikrofkWBLgQ", "nome": "Jogo Aberto (Band)", "filtro": "titulo"},
        {"canal": "@alterosaesporteAE", "id": "UCf69PDS9TfGvwbFWcjr4eaQ", "nome": "Alterosa Esporte", "filtro": "titulo"},
        {"canal": "@ESPNBrasil", "id": "UCw5-xj3AKqEizC7MvHaIPqA", "nome": "ESPN Brasil", "filtro": "titulo"},
        {"canal": "@cortestntsports", "nome": "TNT Sports", "filtro": "titulo"},
        {"canal": "@atletico", "id": "UC0BhAOfmm1tJaJkPyTM9D_g", "nome": "TV Galo", "filtro": "tudo", "max_min": 40, "max_trechos": 1,
         "max_videos": 1, "prioridade": 2},
        {"canal": "@diariodogalo940", "nome": "Notícias do Galo", "filtro": "titulo", "prioridade": 3, "juntador": True},
        {"canal": "@galoticiasoficial", "nome": "Galotícias", "filtro": "titulo", "prioridade": 3, "juntador": True},
        {"canal": "@noticiasdogalo-cortesdoatl4515", "nome": "Notícias do Galo - Cortes", "filtro": "titulo", "prioridade": 3, "juntador": True},
        {"canal": "@TrincaGalo", "nome": "Trinca Galo", "filtro": "titulo", "prioridade": 3, "juntador": True},
        {"canal": "@Resenhacam", "nome": "Resenha Atleticana", "filtro": "titulo", "prioridade": 3, "juntador": True},
        {"canal": "@ETERNOGALONEWS", "nome": "Eterno Galo News", "filtro": "titulo", "prioridade": 3, "juntador": True},
        {"canal": "@JornaldoGalo", "nome": "Jornal do Galo", "filtro": "titulo", "prioridade": 3, "juntador": True},
        {"canal": "@VIBRATORCEDOR", "nome": "Vibra Torcedor", "filtro": "titulo", "prioridade": 3, "juntador": True},
        {"canal": "@canalgalonoticiou", "nome": "Canal Galo Noticiou", "filtro": "titulo", "prioridade": 3, "juntador": True},
        {"canal": "@EUSOUGALO", "nome": "Eu Sou Galo", "filtro": "titulo", "prioridade": 3, "juntador": True},
    ],
    "fontes_versao": 5,
    # "qualquer coisa que for notícia": busca do YouTube por data — qualquer canal, se o título fala do Galo (prioridade 4)
    "busca": ["notícias do galo hoje", "atlético mineiro notícias", "galo atlético mg", "corte atlético mineiro programa"],
    "busca_qualquer_canal": True,
    "outras_fontes": ["itatiaia", "globo esporte", "ge globo", "sportv", "band", "cnn", "os donos da bola", "tnt sports",
                      "super fc", "o tempo", "hoje em dia", "rádio 98", "estado de minas", "premiere", "cazé"],
    "fora": ["react", "reage", "reagindo", "reacao", "reacoes", "ao vivo", "live", "jogo completo", "gameplay", "fifa", "efootball"],
    "max_horas": 48,  # notícias de hoje e de ontem que ainda não postamos
    "max_videos_rodada": 8,  # quantos vídeos novos baixa/transcreve por rodada (os melhores primeiro; o resto na próxima)
    "trecho_min_s": 15,
    "trecho_max_s": 180,  # a notícia INTEIRA (do começo ao fim do assunto); só corta se passar de 3 min
    "max_trechos_video": 3,
    "parecido_max": 0.35,  # notícia repetida (o mesmo assunto em 2 canais / já postada) fica de fora
    "por_fonte": 15,
    "max_min_fonte": 120,
    "duracao_alvo_min": 16,  # o vídeo tem PELO MENOS isso (imprensa + suas falas)
    "min_trechos": 4,
    "max_videos_dia": 2,
    "horas_entre_posts": 4,
    "privacidade": "public",
    "voz_ref": "voz/minha_voz.wav",
    "exagero_voz": 0.6,
    "cor": "#FFD400",
    "auto_postar": False,  # False = monta e espera você aprovar no painel (aba Canais); True = posta sozinho
    "shorts": 2,  # Shorts (9:16) por vídeo: as melhores notícias, cada uma com a sua fala antes
    "horas_entre_shorts": 3,
    "short_max_s": 55,
    "drive": "",  # pasta do Drive com mascara\ e voz\; vazio = <Meu Drive>\DETTO\canal_noticias
}


def log(m):
    print(m, flush=True)


def apelidos(cfg):
    t = next((x for x in json.loads((TOOLS / "roteiro" / "times.json").read_text(encoding="utf-8"))["times"] if x["sigla"] == cfg["time"]), {})
    return [norm(a) for a in [t.get("nome", "")] + t.get("apelidos", []) if a], [norm(a) for a in t.get("nao", [])], t


def fala_do_time(texto, aps, nao):
    n = f" {norm(texto)} "
    if any(f" {x} " in n for x in nao) and not any(f" {a} " in n for a in aps if a not in ("atletico", "cam")):
        return False
    return any(re.search(rf"\b{re.escape(a)}\b", n) for a in aps)


# ------------------------------------------------------------------ 1. coleta
def rss(canal_id):
    """os últimos 15 vídeos do canal com a HORA de publicação (o feed do YouTube; leve, sem login)"""
    import urllib.request
    import xml.etree.ElementTree as ET
    try:
        req = urllib.request.Request(f"https://www.youtube.com/feeds/videos.xml?channel_id={canal_id}", headers={"User-Agent": "Mozilla/5.0"})
        raiz = ET.fromstring(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        log(f"   feed {canal_id}: {e}")
        return []
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "m": "http://search.yahoo.com/mrss/"}
    out = []
    for e in raiz.findall("a:entry", ns):
        vid = e.findtext("yt:videoId", "", ns)
        pub = e.findtext("a:published", "", ns)
        desc = e.findtext("m:group/m:description", "", ns) or ""
        try:
            quando = dt.datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
        except ValueError:
            continue
        out.append({"id": vid, "titulo": e.findtext("a:title", "", ns), "quando": quando, "descricao": desc,
                    "canal_nome": e.findtext("a:author/a:name", "", ns)})
    return out


def duracoes(canal):
    """duração e tipo (vídeo / short / live) dos últimos vídeos do canal (o feed não traz)"""
    out = {}
    for aba, tipo in (("videos", "video"), ("shorts", "short"), ("streams", "live")):
        r = ytdlp(["--flat-playlist", "--dump-json", "--playlist-end", "25", f"https://www.youtube.com/{canal}/{aba}"])
        for linha in (r.stdout or "").splitlines():
            try:
                v = json.loads(linha)
                out.setdefault(v["id"], (v.get("duration") or 0, tipo))
            except (ValueError, KeyError):
                continue
    return out


def coleta(cfg, hist):
    """vídeos NOVOS de hoje sobre o time: feed de cada fonte (hora certa) + busca do YouTube por data (outras fontes de
    imprensa da lista). Mais novos primeiro."""
    aps, nao, _ = apelidos(cfg)
    limite = dt.datetime.now() - dt.timedelta(hours=cfg.get("max_horas", 30))
    ids = hist.setdefault("canais_id", {})
    novos, vistos_agora = [], set()

    def considera(v, f, dur_s, tipo="video"):
        if v["id"] in hist["vistos"] or v["id"] in vistos_agora or v["quando"] < limite:
            return
        vistos_agora.add(v["id"])
        # Short não é notícia; live só depois de acabar e dentro do tamanho (o programa do dia da Alterosa é live
        # gravada — entra; jogo/treino ao vivo de horas fica fora pela duração)
        if tipo == "short" or (tipo == "live" and not dur_s):
            return
        if f.get("max_videos") and sum(1 for x in novos if x["fonte"] == f.get("nome")) >= f["max_videos"]:
            return
        durm = (dur_s or 0) / 60
        if dur_s and (durm > f.get("max_min", cfg["max_min_fonte"]) or durm < 0.5):
            return
        if f.get("filtro", "titulo") == "titulo" and not fala_do_time(f"{v['titulo']} {v.get('descricao', '')}", aps, nao):
            return
        if any(re.search(rf"\b{re.escape(norm(x))}\b", norm(v["titulo"])) for x in cfg.get("fora", [])):
            return  # react / ao vivo / jogo: não é notícia de imprensa
        novos.append({"id": v["id"], "url": f"https://www.youtube.com/watch?v={v['id']}", "titulo": v["titulo"],
                      "fonte": f.get("nome") or v.get("canal_nome") or f.get("canal", ""), "canal": f.get("canal", ""),
                      "dur": dur_s or 0, "publicado": v["quando"].isoformat(timespec="minutes"), "max_trechos": f.get("max_trechos"),
                      "prioridade": f.get("prioridade", 1), "juntador": bool(f.get("juntador"))})

    for f in cfg["fontes"]:
        cid = f.get("id") or ids.get(f["canal"])
        if not cid:
            r = ytdlp(["--flat-playlist", "-J", "--playlist-end", "1", f"https://www.youtube.com/{f['canal']}/videos"])
            try:
                cid = json.loads(r.stdout).get("channel_id")
                ids[f["canal"]] = cid
            except ValueError:
                log(f"   {f['canal']}: não achei o canal")
                continue
        lista = [v for v in rss(cid) if v["quando"] >= limite]
        if not lista:
            continue
        durs = duracoes(f["canal"]) if f.get("canal") else {}
        for v in lista:
            d_, t_ = durs.get(v["id"], (0, "video"))
            considera(v, f, d_, t_)
    # "entre outras": busca por data; só canais de imprensa da lista, e a hora vem do feed do próprio canal
    ok_nomes = [norm(x) for x in cfg.get("outras_fontes", [])]
    ja = {f.get("id") or ids.get(f["canal"]) for f in cfg["fontes"]}
    feeds = {}
    for q in cfg.get("busca", []):
        import urllib.parse
        r = ytdlp(["--flat-playlist", "--dump-json", "--playlist-end", "15", "--extractor-args", "youtube:lang=pt",
                   "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q) + "&sp=CAI%253D"])
        for linha in (r.stdout or "").splitlines():
            try:
                v = json.loads(linha)
            except ValueError:
                continue
            cid, nome = v.get("channel_id"), v.get("channel") or ""
            imprensa = any(o in norm(nome) for o in ok_nomes)
            if not cid or cid in ja or not (imprensa or cfg.get("busca_qualquer_canal")):
                continue
            if cid not in feeds:
                feeds[cid] = {x["id"]: x for x in rss(cid)}
            if v.get("id") in feeds[cid]:
                considera(feeds[cid][v["id"]], {"nome": nome, "canal": v.get("uploader_id") or "", "filtro": "titulo",
                                                "prioridade": 1 if imprensa else 4, "juntador": not imprensa}, v.get("duration"))
    # imprensa (1), TV Galo (2), canais de notícias do Galo (3), resto da busca (4); dentro de cada, a mais nova primeiro.
    # Por rodada só os `max_videos_rodada` primeiros (baixar + transcrever pesa); os outros ficam para a próxima.
    novos.sort(key=lambda x: (x["prioridade"], "".join(chr(255 - ord(c)) for c in x["publicado"])))
    novos = novos[: int(cfg.get("max_videos_rodada", 8))]
    for v in novos:
        hist["vistos"][v["id"]] = dt.date.today().isoformat()
    log(f"coleta: {len(novos)} vídeo(s) de hoje sobre o {cfg['time']}: " + "; ".join(f"{x['fonte']} {x['publicado'][11:]}" for x in novos[:8]))
    return novos


# ------------------------------------------------------------------ 2. trechos sobre o time
def transcreve(video):
    cache = Path(video).with_suffix(".words.json")
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    from transcrever import dlls_nvidia, transcrever

    dlls_nvidia()
    try:
        w = transcrever(str(video), "small", "cuda")
    except Exception:
        w = transcrever(str(video), "small", "cpu")
    print()
    cache.write_text(json.dumps(w, ensure_ascii=False), encoding="utf-8")
    return w


def linhas_tempo(words, passo=8.0):
    out, atual, ini = [], [], None
    for w in words:
        ini = w["s"] if ini is None else ini
        atual.append(w["w"])
        if w["e"] - ini >= passo:
            out.append(f"[{int(ini)}] {' '.join(atual)}")
            atual, ini = [], None
    if atual:
        out.append(f"[{int(ini)}] {' '.join(atual)}")
    return "\n".join(out)


def acha_trechos(words, info, cfg, assunto=None):
    """trechos que falam do time (ou do ASSUNTO de uma pauta sua): Gemini (começo/fim certos, manchete, clima);
    sem chave: janelas pela palavra (pauta sem chave: o começo do vídeo)"""
    _, _, t = apelidos(cfg)
    alvo = (f"em que falam de: {assunto}" if assunto and assunto != "*" else "com a notícia/assunto principal deste vídeo") if assunto \
        else f"em que falam do {t.get('nome', cfg['time'])} (o Galo): análise, elogio, crítica, polêmica, notícia, entrevista"
    regra_canal = ("Este canal JUNTA notícias de vários programas: marque SÓ as partes em que fala a IMPRENSA (apresentador/jornalista "
                   "de TV, rádio, entrevista, coletiva). IGNORE a narração do dono do canal ('fala galera', 'se inscreve', leitura de "
                   "manchete, opinião do youtuber) e anúncios." if info.get("juntador") else
                   "Ignore vinheta, intervalo, propaganda e conversa sem notícia.")
    g = gemini_json([{"text": f"""Transcrição (segundos entre colchetes) de "{info['titulo']}" ({info['fonte']}).
Marque os trechos {alvo}.
Cada trecho é UMA notícia INTEIRA: do começo ao fim do assunto (a informação + a análise/opinião sobre ela), começo e fim
NATURAIS (frase completa, nunca cortar no meio), entre {cfg.get("trecho_min_s", 15)} e {cfg.get("trecho_max_s", 180)} segundos — o tamanho que a notícia precisar.
{regra_canal}
{"Ignore o resto." if assunto else "Ignore trechos sobre outros times."} Responda SÓ JSON:
{{"trechos": [{{"ini": <s>, "fim": <s>, "manchete": "<MANCHETE CURTA EM MAIÚSCULAS, até 60 letras>", "resumo": "<1 frase>",
 "programa": "<de onde é a fala, se der para saber: ex. Globo Esporte MG, Jogo Aberto, Rádio Itatiaia, coletiva; senão vazio>",
 "clima": "<um de: {', '.join(CLIMAS)}>", "nota": <1 a 10: o quanto é NOVIDADE importante e prende o torcedor (notícia velha/repetida = nota baixa)>}}]}}

{linhas_tempo(words)[:60000]}"""}])
    trechos = (g or {}).get("trechos") or []
    if not trechos and assunto and not os.environ.get("GEMINI_API_KEY") and words:
        fim = min(words[-1]["e"], 90.0)
        trechos = [{"ini": words[0]["s"], "fim": fim, "manchete": info["titulo"][:60].upper(), "resumo": "", "clima": "falando", "nota": 8}]
    elif not trechos and not os.environ.get("GEMINI_API_KEY"):
        aps, _, _ = apelidos(cfg)
        hits = [w["s"] for w in words if any(norm(w["w"]) == a for a in aps)]
        janelas = []
        for h in hits:
            if janelas and h - janelas[-1][1] < 25:
                janelas[-1][1] = h + 30
            else:
                janelas.append([max(0, h - 15), h + 30])
        trechos = [{"ini": a, "fim": b, "manchete": info["titulo"][:60].upper(), "resumo": "", "clima": "falando", "nota": 5} for a, b in janelas if b - a >= 20]
    ok = []
    mx, mn = float(cfg.get("trecho_max_s", 45)), float(cfg.get("trecho_min_s", 15))
    for x in trechos:
        try:
            a, b = float(x["ini"]), float(x["fim"])
        except (KeyError, TypeError, ValueError):
            continue
        if b - a > mx + 5:
            b = fim_de_frase(words, a, a + mx)  # notícia longa: corta no fim da frase mais perto do máximo
        if b - a >= mn:
            ok.append({**x, "ini": a, "fim": b, "clima": x.get("clima") if x.get("clima") in CLIMAS else "falando"})
    ok.sort(key=lambda x: -float(x.get("nota", 5)))
    for x in ok:
        x["texto"] = " ".join(w["w"] for w in words if x["ini"] <= w["s"] < x["fim"])[:4000]
    return ok[: int(info.get("max_trechos") or cfg.get("max_trechos_video", 3))]


def _palavras_chave(txt):
    """as palavras que dizem o ASSUNTO (sem as comuns) — para achar a mesma notícia contada em outro canal"""
    comuns = set("que de da do das dos para pra com uma um no na nos nas por mais mas como ele ela isso esse essa ja não nao "
                 "sim tem ter foi vai ser está esta estao tá ta aqui ali muito bem então entao porque pois sobre agora hoje "
                 "galo atletico atlético time jogo gente voce você eu nós nos ele eles elas também tambem quando onde".split())
    return {w for w in re.findall(r"\w{4,}", norm(txt)) if w not in comuns}


def parecido(a, b):
    """0..1: quanto os dois textos falam do mesmo (palavras do assunto em comum)"""
    A, B = _palavras_chave(a), _palavras_chave(b)
    if not A or not B:
        return 0.0
    return len(A & B) / min(len(A), len(B))


def fim_de_frase(words, ini, alvo):
    """fim da última frase completa antes de `alvo` (ponto ou pausa ≥ 0,5 s); sem achar, o próprio alvo"""
    melhor = None
    for k, w in enumerate(words):
        if w["e"] <= ini + 8 or w["e"] > alvo:
            continue
        prox = words[k + 1] if k + 1 < len(words) else None
        if re.search(r"[.!?]$", w["w"]) or (prox and prox["s"] - w["e"] >= 0.5):
            melhor = w["e"] + 0.15
    return melhor or alvo


# ------------------------------------------------------------------ 3. roteiro da narração
def origem(x):
    """de onde veio o trecho, para falar no vídeo e dar o crédito: o programa original (se o Gemini achou) + o canal"""
    prog = (x.get("programa") or "").strip()
    if prog and norm(prog) not in norm(x["fonte"]):
        return f"{prog} (via {x['fonte']})"
    return x["fonte"]


def origem_falada(x):
    """a origem do jeito de falar: Globo Esporte MG, no canal Notícias do Galo / Jogo Aberto, da Band"""
    prog = (x.get("programa") or "").strip()
    fonte = re.sub(r"\s*\((.+?)\)", r", da \1", x["fonte"])
    if prog and norm(prog) not in norm(x["fonte"]):
        return f"{prog}, no canal {fonte}"
    return fonte


def ponto_de_pausa(x, alvo):
    """onde pausar a reportagem para o seu comentário: o fim de frase mais perto do alvo (nunca nos 10 s das pontas)"""
    try:
        words = json.loads(Path(x["arquivo"]).with_suffix(".words.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    lo, hi = x["ini"] + 10, x["fim"] - 10
    if hi <= lo:
        return None
    melhor = None
    for k, w in enumerate(words):
        if not (lo <= w["e"] <= hi):
            continue
        prox = words[k + 1] if k + 1 < len(words) else None
        if re.search(r"[.!?]$", w["w"]) or (prox and prox["s"] - w["e"] >= 0.45):
            if melhor is None or abs(w["e"] - alvo) < abs(melhor - alvo):
                melhor = w["e"] + 0.12
    return melhor if melhor is not None and abs(melhor - alvo) <= 12 else None


def falas_do_trecho(x, passo=7.0):
    """o que é dito no trecho, com o segundo (contado do começo do trecho) — para o comentário no meio dele"""
    try:
        words = json.loads(Path(x["arquivo"]).with_suffix(".words.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    out, atual, t0 = [], [], None
    for w in words:
        if w["s"] < x["ini"] or w["s"] >= x["fim"]:
            continue
        t0 = w["s"] if t0 is None else t0
        atual.append(w["w"])
        if w["e"] - t0 >= passo:
            out.append(f"[+{int(t0 - x['ini'])}s] {' '.join(atual)}")
            atual, t0 = [], None
    if atual:
        out.append(f"[+{int(t0 - x['ini'])}s] {' '.join(atual)}")
    return "\n".join(out)[:3500]


def roteiro(sel, cfg):
    lista = "\n".join(f"{i + 1}. [ORIGEM: {origem(x)}] {x['manchete']} — {x.get('resumo', '')} (clima: {x['clima']}; {x['fim'] - x['ini']:.0f} s)"
                      for i, x in enumerate(sel))
    longos = "\n\n".join(f"TRECHO {i + 1} ({x['fim'] - x['ini']:.0f} s) — o que é dito:\n{falas_do_trecho(x)}"
                          for i, x in enumerate(sel) if x["fim"] - x["ini"] >= cfg.get("comentario_min_s", 45))
    g = gemini_json([{"text": f"""Você narra o canal "{cfg['nome_canal']}", de notícias do Atlético-MG (o Galo), como um torcedor apaixonado
e engraçado de BH (gírias leves, "Massa", "Galo doido"), opinando sobre o que a imprensa falou (alguns trechos podem ser de OUTROS assuntos do futebol que você escolheu
comentar: fale deles com o mesmo jeito, sempre como torcedor do Galo). Os trechos, em ordem:
{lista}

Escreva a narração que liga os trechos. Responda SÓ JSON:
{{"titulo": "<título do YouTube em MAIÚSCULAS, chamativo, até 95 letras, com o principal nome/placar>",
 "thumb_texto": "<2 a 4 palavras de impacto>", "thumb_destaque": "<1 palavra do thumb_texto para destacar>",
 "descricao": "<2 a 3 frases sobre o vídeo>", "tags": ["<10 a 15 tags>"],
 "abertura": {{"texto": "<gancho de 2 a 3 frases, até 45 palavras>", "clima": "<{'|'.join(CLIMAS)}>"}},
 "falas": [{{"antes_do": <número do trecho>, "texto": "<sua opinião/ponte para o trecho, 1 a 3 frases, até 40 palavras>", "clima": "..."}}],
 "comentarios": [{{"trecho": <número>, "depois_de": <segundo do trecho, logo DEPOIS de uma frase forte>, "texto": "<sua reação curta ao que ACABOU de ser dito, 6 a 20 palavras>", "clima": "..."}}],
 "fechamento": {{"texto": "<opinião final + pedir like, inscrição e comentário, até 40 palavras>", "clima": "..."}}}}
COMENTÁRIOS NO MEIO: nos trechos longos abaixo, entre UMA reação sua no meio da reportagem (2 se passar de 2 min), como
quem pausa e comenta o que acabou de ouvir ("Olha isso, Massa!", "Concordo demais com ele", "Aí não, né?") — só onde
combina, nunca nos primeiros 10 s nem nos últimos 10 s do trecho.
{longos}

Uma fala antes de CADA trecho (antes_do = 1, 2, 3...). CADA fala DIZ DE ONDE VEM o trecho seguinte, pelo nome do programa/emissora
da ORIGEM (ex.: "olha o que falaram no Globo Esporte Minas", "o pessoal do Jogo Aberto, da Band, comentou"; se for "via" um canal,
cite o programa e o canal). No fechamento, diga que os créditos de tudo que foi usado estão nos comentários e na descrição."""}])
    if not g:
        nomes = ", ".join(x["fonte"] for x in sel[:3])
        g = {"titulo": f"IMPRENSA FALA DO GALO! {sel[0]['manchete']}"[:95], "thumb_texto": "OLHA ISSO", "thumb_destaque": "ISSO",
             "descricao": f"O que {nomes} falaram do Galo hoje.", "tags": ["galo", "atlético mineiro", "notícias do galo", "atlético-mg"],
             "abertura": {"texto": "Fala, Massa! Olha o que a imprensa falou do Galo hoje.", "clima": "falando"},
             "falas": [{"antes_do": i + 1, "texto": f"Agora olha o que falaram no {origem_falada(x)}: {x['manchete'].lower()}.",
                        "clima": x["clima"]} for i, x in enumerate(sel)],
             "fechamento": {"texto": "E aí, Massa, concorda? Comenta aí, deixa o like e se inscreve. Os créditos de tudo estão nos comentários e na descrição. Galo doido!", "clima": "comemorando"}}
    return g


# ------------------------------------------------------------------ 4. montagem
def fonte_pil(tam, nome="Anton-Regular.ttf"):
    from PIL import ImageFont

    return ImageFont.truetype(str(FONTES_DIR / nome), tam)


def molde(cfg, saida):
    """fundo fixo do canal: preto/grafite com listras do Galo, molduras amarelas, nome do canal e escudo"""
    from PIL import Image, ImageDraw

    cor = cfg["cor"]
    img = Image.new("RGB", (W, H), "#0b0b0d")
    d = ImageDraw.Draw(img)
    for x in range(-H, W, 90):  # listras diagonais discretas (preto e branco do Galo)
        d.polygon([(x, H), (x + 45, H), (x + 45 + H, 0), (x + H, 0)], fill="#121216")
    d.rectangle([0, 0, W, 100], fill="#000000")
    d.text((40, 18), cfg["nome_canal"], font=fonte_pil(62), fill=cor)
    d.text((W - 40, 34), "NOTÍCIAS DO GALO HOJE", font=fonte_pil(40), fill="#ffffff", anchor="ra")
    x, y, w, h = JANELA
    d.rectangle([x - 6, y - 6, x + w + 5, y + h + 5], outline=cor, width=6)
    x, y, w, h = CANTO
    d.rectangle([x - 6, y - 6, x + w + 5, y + h + 5], outline=cor, width=6)
    esc = TOOLS / "banco" / "escudos" / f"{cfg['time']}.png"
    if esc.exists():
        e = Image.open(esc).convert("RGBA")
        e.thumbnail((300, 300))
        img.paste(e, (CANTO[0] + (CANTO[2] - e.width) // 2, 560 + (330 - e.height) // 2), e)
    x, y, w, h = FAIXA
    d.rectangle([x, y, x + w, y + h], fill="#000000")
    d.rectangle([x, y, x + 14, y + h], fill=cor)
    img.save(saida)
    return saida


def faixa_png(texto, sub, saida, cor):
    """manchete na faixa de baixo + crédito da fonte (transparente, por cima do molde)"""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x, y, w, h = FAIXA
    tam = 58
    f = fonte_pil(tam)
    while d.textlength(texto, font=f) > w - 80 and tam > 30:
        tam -= 3
        f = fonte_pil(tam)
    d.text((x + 40, y + h // 2), texto, font=f, fill="#ffffff", anchor="lm")
    if sub:
        d.text((JANELA[0] + 16, JANELA[1] + JANELA[3] - 14), sub, font=fonte_pil(26, "Inter-Bold.otf"), fill=cor, anchor="lb",
               stroke_width=3, stroke_fill="#000000")
    img.save(saida)
    return saida


ANIMADOS = {"comemorando", "bravo", "surpreso", "rindo"}  # pedem gravação com mais gesto
CALMOS = {"pensativo", "concordando", "falando"}
_ULTIMA_MASC = []


def movimento(video, fps=10):
    """quanto muda cada quadro (0..255), quadro a quadro: mostra o toque no botão (tudo treme) e o quanto você gesticula"""
    import numpy as np
    w = 96
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={fps},scale={w}:-2,format=gray", "-f", "rawvideo", "-"],
                       capture_output=True)
    vw, vh = tamanho(video)
    h = int(round(w * (vh or 16) / (vw or 9) / 2)) * 2
    a = np.frombuffer(r.stdout, np.uint8)
    n = a.size // (w * h)
    if n < 3:
        return np.zeros(0)
    q = a[: n * w * h].reshape(n, h, w).astype(np.float32)
    return np.abs(np.diff(q, axis=0)).mean(axis=(1, 2))


def cortes_do_botao(mv, fps=10):
    """sem o botão nas pontas (o mesmo dos reels): tremor do toque no começo e a MÃO indo dar pause no fim"""
    from reels import cortes_pontas
    return cortes_pontas(mv, fps, 1.0, 1.5)


def prepara_mascaras(pasta):
    """cada gravação de máscara: converte para SDR, CORTA o começo/fim (o botão) e AVALIA o quanto você gesticula.
    O resultado fica em mascara\\sdr\\ e em mascara\\avaliacao.txt (para você ver)."""
    import numpy as np
    pm = pasta / "mascara"
    vs = [p for p in pm.glob("*") if p.suffix.lower() in VIDEO_EXT]
    av_f = pm / "avaliacao.json"
    av = le_json(av_f, {})
    mudou = False
    for v in vs:
        sig = f"v2:{v.stat().st_size}:{int(v.stat().st_mtime)}"  # v2 = corte novo do fim (a mão indo dar pause)
        saida = pm / "sdr" / f"{v.stem}.mp4"
        if av.get(v.stem, {}).get("sig") == sig and saida.exists():
            continue
        saida.parent.mkdir(parents=True, exist_ok=True)
        try:
            from sdr import master_sdr
            base = master_sdr(v, saida=pm / "sdr" / f"{v.stem}__inteiro.mp4", log=log)
        except Exception:
            base = v
        mv = movimento(base)
        ini, fim = cortes_do_botao(mv)
        meio = mv[int(ini * 10): int(fim * 10)] if len(mv) else mv
        gesto = float(np.mean(meio)) if len(meio) else 0.0
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ini:.2f}", "-to", f"{fim:.2f}", "-i", str(base), "-an",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(saida)])
        if r.returncode != 0:
            log(f"máscara {v.name}: não consegui cortar")
            continue
        if base != v and Path(base).name.endswith("__inteiro.mp4"):
            Path(base).unlink(missing_ok=True)
        av[v.stem] = {"sig": sig, "ini": ini, "fim": fim, "dur_total": round(len(mv) / 10, 1), "gesto": round(gesto, 2)}
        mudou = True
        log(f"máscara {v.name}: cortei {ini:.1f} s do começo e {max(0.0, len(mv) / 10 - fim):.1f} s do fim; gesto {gesto:.1f}")
    for k in [k for k in av if not any(v.stem == k for v in vs)]:
        av.pop(k)
        mudou = True
    if av:
        # nível de gesto: comparando as suas gravações entre si (terços) — muito / médio / pouco
        ordem = sorted(av, key=lambda k: av[k]["gesto"])
        for i, k in enumerate(ordem):
            nivel = "pouco" if i < len(ordem) / 3 else ("muito" if i >= len(ordem) * 2 / 3 else "médio")
            if av[k].get("nivel") != nivel:
                av[k]["nivel"] = nivel
                mudou = True
    if mudou:
        grava_json(av_f, av)
        linhas = ["AVALIAÇÃO DAS GRAVAÇÕES DE MÁSCARA (o sistema usa as de MUITO gesto nas partes animadas — comemorando,",
                  "bravo, surpreso, rindo — e as de POUCO nas calmas — pensativo, concordando, falando)", ""]
        for k in sorted(av, key=lambda k: -av[k]["gesto"]):
            x = av[k]
            linhas.append(f"{k:30s} gesto {x['gesto']:5.1f} ({x['nivel']:5s})  usa de {x['ini']:.1f} s a {x['fim']:.1f} s "
                          f"(de {x['dur_total']:.1f} s; o resto era o botão)")
        (pm / "avaliacao.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return av


def mascara_de(clima, pasta, durante_reportagem=False):
    """a gravação de máscara para esse clima: pelo NOME do arquivo (rindo.mov...) ou, se o nome não diz (teste 1.mov),
    pelo GESTO avaliado (animado → muito gesto; calmo → pouco). Já cortada (sem o botão) e em SDR. Não repete a última."""
    pm = pasta / "mascara"
    av = le_json(pm / "avaliacao.json", {})
    vs = [p for p in (pm / "sdr").glob("*.mp4") if p.stem in av and not p.stem.endswith("__inteiro")]
    if not vs:
        return None
    # durante a REPORTAGEM você está ouvindo: só as gravações com POUCO gesto (as calmas), sempre
    if durante_reportagem:
        calmas = [p for p in vs if av[p.stem].get("nivel") == "pouco"] or [p for p in vs if av[p.stem].get("nivel") == "médio"]
        if calmas:
            vs = calmas
    certas = [] if durante_reportagem else [p for p in vs if clima in norm(p.stem)]
    if not certas and not durante_reportagem:
        quer = ["muito", "médio"] if clima in ANIMADOS else ["pouco", "médio"]
        for nv in quer:
            certas = [p for p in vs if av[p.stem].get("nivel") == nv]
            if certas:
                break
    opcoes = [p for p in (certas or vs) if p not in _ULTIMA_MASC[-1:]] or (certas or vs)
    esc = random.choice(opcoes)
    _ULTIMA_MASC.append(esc)
    return esc


def cobre(w, h):
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"


def enc():
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]


def peca_trecho(base, clip, ini, fim, masc, faixa, saida):
    """o trecho da imprensa na janela grande; você de máscara (sem som) no canto"""
    d = fim - ini
    ins = ["-loop", "1", "-i", str(base), "-ss", f"{ini:.2f}", "-t", f"{d:.2f}", "-i", str(clip), "-loop", "1", "-i", str(faixa)]
    x, y, w, h = JANELA
    cx, cy, cw, ch = CANTO
    vw, vh = tamanho(clip)
    if vw and vh and vw / vh < 1.4:
        # vídeo vertical/quadrado (TikTok, Reels): o próprio vídeo desfocado preenche as laterais, sem barra preta
        f = (f"[1:v]{cor_sdr(clip)}split[v1][v2];[v1]{cobre(w // 4, h // 4)},boxblur=8:2,scale={w}:{h},eq=brightness=-0.08[fundo];"
             f"[v2]scale={w}:{h}:force_original_aspect_ratio=decrease,setsar=1[fr];[fundo][fr]overlay=(W-w)/2:(H-h)/2,setsar=1[v];"
             f"[0:v][v]overlay={x}:{y}[a0];")
    else:
        f = (f"[1:v]{cor_sdr(clip)}scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1[v];"
             f"[0:v][v]overlay={x}:{y}[a0];")
    if masc:
        ins += ["-stream_loop", "-1", "-i", str(masc)]
        f += f"[3:v]{cor_sdr(masc)}{cobre(cw, ch)},setsar=1[m];[a0][m]overlay={cx}:{cy}[a1];"
    else:
        f += "[a0]null[a1];"
    f += f"[a1][2:v]overlay=0:0,fps={FPS},format=yuv420p[vo]"
    ac = audio_bom(clip)
    af = ["-map", f"1:a:{ac}", "-af", "loudnorm=I=-16:TP=-1.5,aresample=48000"] if ac is not None else []
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", f, "-map", "[vo]", *af, "-t", f"{d:.2f}", *enc(), str(saida)])
    return r.returncode == 0


def legendas(texto, dur_audio, pasta, idx):
    """a fala em pedaços de ~6 palavras, com tempo proporcional (PNG por pedaço, na faixa)"""
    from PIL import Image, ImageDraw

    ws = texto.split()
    pedacos = [" ".join(ws[i:i + 6]) for i in range(0, len(ws), 6)] or [""]
    tot = sum(len(p) for p in pedacos) or 1
    out, t = [], 0.0
    for k, p in enumerate(pedacos):
        dd = dur_audio * len(p) / tot
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        x, y, w, h = FAIXA
        dr.text((x + w // 2, y + h // 2), p.upper(), font=fonte_pil(56), fill="#FFD400", anchor="mm", stroke_width=2, stroke_fill="#000000")
        f = pasta / f"leg_{idx}_{k}.png"
        img.save(f)
        out.append((f, t, t + dd))
        t += dd
    return out


def peca_fala(base, wav, masc, texto, pasta, idx, saida, logo):
    """você falando (narração clonada): sua gravação de máscara GRANDE na janela, legenda na faixa"""
    da = dur(wav) + 0.25
    x, y, w, h = JANELA
    cx, cy, cw, ch = CANTO
    legs = legendas(texto, da - 0.25, pasta, idx)
    ins = ["-loop", "1", "-i", str(base), "-i", str(wav)]
    if masc:
        ins += ["-stream_loop", "-1", "-i", str(masc)]
        f = f"[2:v]{cor_sdr(masc)}{cobre(w, h)},setsar=1[m];[0:v][m]overlay={x}:{y}[b0];"
    else:
        ins += ["-f", "lavfi", "-i", f"color=c=0x111111:s={w}x{h}:r={FPS}"]
        f = f"[0:v][2:v]overlay={x}:{y}[b0];"
    ins += ["-loop", "1", "-i", str(logo)]
    f += f"[3:v]{cobre(cw, ch)}[lg];[b0][lg]overlay={cx}:{cy}[b1];"
    ult = "b1"
    for k, (png, a, b) in enumerate(legs):
        ins += ["-loop", "1", "-i", str(png)]
        f += f"[{ult}][{4 + k}:v]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[c{k}];"
        ult = f"c{k}"
    f += f"[{ult}]fps={FPS},format=yuv420p[vo];[1:a]atempo=1.05,loudnorm=I=-16:TP=-1.5,aresample=48000,apad=pad_dur=0.3[ao]"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", f, "-map", "[vo]", "-map", "[ao]", "-t", f"{da / 1.05 + 0.3:.2f}", *enc(), str(saida)])
    return r.returncode == 0


def logo_png(cfg, saida):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (CANTO[2], CANTO[3]), "#000000")
    d = ImageDraw.Draw(img)
    esc = TOOLS / "banco" / "escudos" / f"{cfg['time']}.png"
    if esc.exists():
        e = Image.open(esc).convert("RGBA")
        e.thumbnail((240, 240))
        img.paste(e, ((CANTO[2] - e.width) // 2, 30), e)
    d.text((CANTO[2] // 2, CANTO[3] - 50), "AO VIVO NA RESENHA", font=fonte_pil(34), fill=cfg["cor"], anchor="mm")
    img.save(saida)
    return saida


def monta(sel, rot, cfg, pasta, tmp, saida):
    base = molde(cfg, tmp / "molde.png")
    logo = logo_png(cfg, tmp / "logo.png")
    # 1) falas na sua voz
    falas = [{"id": "f00", "texto": rot["abertura"]["texto"], "clima": rot["abertura"].get("clima", "falando")}]
    por_trecho = {int(f.get("antes_do", 0)): f for f in rot.get("falas", [])}
    for i in range(len(sel)):
        f = por_trecho.get(i + 1)
        if f and f.get("texto"):
            falas.append({"id": f"f{i + 1:02d}", "texto": f["texto"], "clima": f.get("clima", "falando"), "antes": i})
    # comentários seus NO MEIO da reportagem (pausa → você comenta → a reportagem continua de onde parou)
    for k, c in enumerate(rot.get("comentarios") or []):
        try:
            i = int(c.get("trecho", 0)) - 1
            dep = float(c.get("depois_de", 0))
        except (TypeError, ValueError):
            continue
        if not (0 <= i < len(sel)) or not str(c.get("texto", "")).strip():
            continue
        x = sel[i]
        corte = ponto_de_pausa(x, x["ini"] + dep)
        if corte is None:
            continue
        falas.append({"id": f"c{i + 1:02d}{k}", "texto": c["texto"], "clima": c.get("clima", "falando"), "comenta": i, "em": corte})
    falas.append({"id": "f99", "texto": rot["fechamento"]["texto"], "clima": rot["fechamento"].get("clima", "comemorando")})
    fj = tmp / "falas.json"
    grava_json(fj, falas)
    ref = pasta / cfg["voz_ref"]
    subprocess.run([sys.executable, str(AQUI / "voz.py"), str(fj), str(pasta / "voz" / "cache"), "--ref", str(ref), "--exagero", str(cfg["exagero_voz"])], check=True)
    falas = json.loads(fj.read_text(encoding="utf-8"))
    fala_antes = {f["antes"]: f for f in falas if "antes" in f}
    comenta = {}
    for f in falas:
        if "comenta" in f:
            comenta.setdefault(f["comenta"], []).append(f)
    # 2) peças: abertura → (fala → trecho [→ comentário → resto do trecho])… → fechamento
    pecas = []

    def add_fala(f):
        p = tmp / f"p{len(pecas):03d}.mp4"
        if peca_fala(base, f["arquivo"], mascara_de(f["clima"], pasta), f["texto"], tmp, len(pecas), p, logo):
            pecas.append(p)

    add_fala(falas[0])
    for i, x in enumerate(sel):
        if i in fala_antes:
            add_fala(fala_antes[i])
        p = tmp / f"p{len(pecas):03d}.mp4"
        fx = faixa_png(x["manchete"], f"Imagens: {origem(x)}", tmp / f"faixa_{i}.png", cfg["cor"])
        log(f"   trecho {i + 1}/{len(sel)}: {x['manchete']} ({x['fim'] - x['ini']:.0f}s, {x['fonte']})")
        cortes = sorted({round(c["em"], 2) for c in comenta.get(i, [])})
        partes = list(zip([x["ini"]] + cortes, cortes + [x["fim"]]))
        coms = sorted(comenta.get(i, []), key=lambda c: c["em"])
        for n, (a0, b0) in enumerate(partes):
            p = tmp / f"p{len(pecas):03d}.mp4"
            if peca_trecho(base, x["arquivo"], a0, b0, mascara_de(x["clima"], pasta, durante_reportagem=True), fx, p):
                pecas.append(p)
            if n < len(coms):
                log(f"      comentário seu no meio: {coms[n]['texto'][:60]}")
                add_fala(coms[n])
    add_fala(falas[-1])
    lista = tmp / "pecas.txt"
    lista.write_text("".join(f"file '{p.as_posix()}'\n" for p in pecas), encoding="utf-8")
    bruto = tmp / "bruto.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(bruto)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(bruto), "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", str(saida)], check=True)
    return saida


# ------------------------------------------------------------------ 5. thumb
def thumb(video, rot, cfg, pasta_saida):
    """rostos com reação forte dos apresentadores (recortados) + escudo + texto — mesma ferramenta das suas thumbs"""
    try:
        sys.path.insert(0, str(TOOLS / "thumb"))
        from thumb import reacoes, recorte

        out = Path(pasta_saida)
        melhores = reacoes(video, 4)
        cortes = []
        for i, (nota, t, f) in enumerate(melhores):
            fq = out / f"quadro_{i + 1}.jpg"
            shutil.copyfile(f, fq)
            cortes.append({"t": t, "nota": nota, "quadro": str(fq), "recorte": str(recorte(fq, out / f"rosto_{i + 1}.png"))})
        if not cortes:
            return None
        esc = TOOLS / "banco" / "escudos" / f"{cfg['time']}.png"
        spec = {"texto": rot.get("thumb_texto", "OLHA ISSO").upper(), "destaque": rot.get("thumb_destaque", "").upper(), "cortes": cortes,
                "jogador": {"nome": "GALO", "foto": str(esc)} if esc.exists() else {}, "fundo": "", "saida": str(out), "fontes": str(FONTES_DIR)}
        (out / "thumbs.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        subprocess.run(["node", str(TOOLS / "thumb" / "thumb.js"), str(out / "thumbs.json")], check=True, capture_output=True)
        return out / "thumb_1.jpg"
    except Exception as e:
        log(f"   thumb falhou ({e}); posta sem thumb (o YouTube escolhe um quadro)")
        return None


# ------------------------------------------------------------------ pautas suas (outras notícias quando quiser)
def le_pautas(pasta):
    """pautas.txt: uma por linha — um LINK (vídeo da notícia), um ARQUIVO do PC ou um ASSUNTO ("Cruzeiro demite técnico").
    Entram no próximo vídeo, na frente das notícias do Galo."""
    f = pasta / "pautas.txt"
    if not f.exists():
        f.write_text("# uma pauta por linha: link de um vídeo da notícia OU o assunto (ex.: Cruzeiro demite o técnico)\n", encoding="utf-8")
        return []
    return list(dict.fromkeys(l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith("#")))


def tira_pauta(pasta, linha, ok):
    f = pasta / "pautas.txt"
    linhas = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip() != linha]
    f.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    with open(pasta / "pautas_feitas.txt", "a", encoding="utf-8") as g:
        g.write(f"{dt.date.today()} {'ok' if ok else 'NÃO ACHEI'} {linha}\n")


def busca_pauta(assunto, cfg, quantos=2):
    """vídeos recentes no YouTube sobre o assunto (os mais relevantes, até max_min_fonte)"""
    r = ytdlp(["--flat-playlist", "--dump-json", f"ytsearch10:{assunto}"])
    out = []
    for linha in (r.stdout or "").splitlines():
        try:
            v = json.loads(linha)
        except ValueError:
            continue
        durm = (v.get("duration") or 0) / 60
        if not v.get("id") or durm < 0.5 or durm > cfg["max_min_fonte"] or v.get("live_status") in ("is_live", "is_upcoming"):
            continue
        out.append({"id": v["id"], "url": f"https://www.youtube.com/watch?v={v['id']}", "titulo": v.get("title", ""),
                    "fonte": v.get("channel") or v.get("uploader") or "YouTube", "canal": v.get("channel_url", "").split("/")[-1] if v.get("channel_url") else "",
                    "dur": v.get("duration") or 0})
        if len(out) >= quantos:
            break
    return out


def pautas(pasta, cfg, hist, log=log):
    """processa as pautas do pautas.txt → trechos marcados como pauta (entram primeiro)"""
    hoje = dt.date.today().isoformat()
    n = 0
    for linha in le_pautas(pasta):
        arquivo = Path(linha.strip('"')) if not linha.startswith("http") and Path(linha.strip('"')).is_file() else None
        link = linha.startswith("http") or arquivo is not None
        vids = [{"id": "pauta_" + hashlib.sha1(linha.encode()).hexdigest()[:10], "url": linha, "titulo": linha, "fonte": "", "canal": "",
                 **({"arquivo": arquivo} if arquivo else {})}] if link else busca_pauta(linha, cfg)
        achou = 0
        for v in vids:
            log(f"\npauta: {v['titulo'][:80]}")
            arq, info = (v["arquivo"], {"title": v["arquivo"].stem, "channel": "arquivo seu"}) if v.get("arquivo") else baixa(v["url"], pasta / "fontes")
            if not arq:
                log(f"   não baixou: {info}")
                continue
            if link:
                v.update(titulo=info.get("title") or linha, fonte=info.get("channel") or info.get("uploader") or "vídeo",
                         canal=(info.get("channel_url") or "").split("/")[-1])
            words = transcreve(arq)
            tr = acha_trechos(words, v, cfg, assunto="*" if link else linha)
            log(f"   {len(tr)} trecho(s) da pauta")
            for x in tr:
                hist["trechos"].append({**x, "nota": max(9.0, float(x.get("nota", 8))), "pauta": linha, "video": v["id"], "arquivo": str(arq),
                                        "fonte": v["fonte"], "canal": v.get("canal", ""), "data": hoje, "usado": False})
            achou += len(tr)
        tira_pauta(pasta, linha, achou > 0)
        n += achou
        grava_json(pasta / "historico.json", hist)
    return n


# ------------------------------------------------------------------ Shorts (9:16)
VW, VH = 1080, 1920


def cabeca_v(cfg, texto, saida):
    """moldura do Short: nome do canal + manchete em cima (transparente)"""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, VW, 150], fill="#000000")
    d.text((VW // 2, 75), cfg["nome_canal"], font=fonte_pil(70), fill=cfg["cor"], anchor="mm")
    linhas, atual, f = [], "", fonte_pil(80)
    for w in texto.upper().split():
        t = (atual + " " + w).strip()
        if d.textlength(t, font=f) > VW - 100 and atual:
            linhas.append(atual)
            atual = w
        else:
            atual = t
    linhas.append(atual)
    y = 230
    for l in linhas[:3]:
        d.text((VW // 2, y), l, font=f, fill="#ffffff", anchor="mt", stroke_width=5, stroke_fill="#000000")
        y += 95
    img.save(saida)
    return saida


def legendas_v(texto, dur_audio, pasta, idx, cor):
    from PIL import Image, ImageDraw

    ws = texto.split()
    pedacos = [" ".join(ws[i:i + 4]) for i in range(0, len(ws), 4)] or [""]
    tot = sum(len(p) for p in pedacos) or 1
    out, t = [], 0.0
    for k, p in enumerate(pedacos):
        dd = dur_audio * len(p) / tot
        img = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((VW // 2, 1560), p.upper(), font=fonte_pil(84), fill=cor, anchor="mm", stroke_width=6, stroke_fill="#000000")
        f = pasta / f"legv_{idx}_{k}.png"
        img.save(f)
        out.append((f, t, t + dd))
        t += dd
    return out


def short(cfg, pasta, fala, trecho, tmp, idx, saida):
    """Short = a sua fala (você de máscara grande + legenda) → a notícia (vídeo da imprensa no meio, fundo desfocado,
    você pequeno embaixo). Manchete em cima o tempo todo."""
    cab = cabeca_v(cfg, trecho["manchete"], tmp / f"cabv_{idx}.png")
    pecas = []
    if fala and fala.get("arquivo") and Path(fala["arquivo"]).exists():
        da = dur(fala["arquivo"]) + 0.2
        masc = mascara_de(fala.get("clima", "falando"), pasta)
        legs = legendas_v(fala["texto"], da - 0.2, tmp, idx, cfg["cor"])
        ins = ["-i", str(fala["arquivo"])]
        if masc:
            ins += ["-stream_loop", "-1", "-i", str(masc)]
            f = f"[1:v]{cor_sdr(masc)}split[m1][m2];[m1]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=8:2,scale={VW}:{VH},eq=brightness=-0.15[bg];[m2]{cobre(1000, 1000)}[fg];[bg][fg]overlay=40:470[b0];"
        else:
            ins += ["-f", "lavfi", "-i", f"color=c=0x111111:s={VW}x{VH}:r={FPS}"]
            f = "[1:v]null[b0];"
        ins += ["-loop", "1", "-i", str(cab)]
        f += "[b0][2:v]overlay=0:0[b1];"
        ult = "b1"
        for k, (png, a, b) in enumerate(legs):
            ins += ["-loop", "1", "-i", str(png)]
            f += f"[{ult}][{3 + k}:v]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[c{k}];"
            ult = f"c{k}"
        f += f"[{ult}]fps={FPS},format=yuv420p[vo];[0:a]atempo=1.05,loudnorm=I=-16:TP=-1.5,aresample=48000,apad=pad_dur=0.3[ao]"
        p = tmp / f"sv_{idx}_a.mp4"
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", f, "-map", "[vo]", "-map", "[ao]", "-t", f"{da / 1.05 + 0.3:.2f}",
                            *enc(), str(p)])
        if r.returncode == 0:
            pecas.append(p)
    ini = trecho["ini"]
    fim = min(trecho["fim"], ini + float(cfg.get("short_max_s", 55)) - sum(dur(x) for x in pecas))
    if fim - ini < 8:
        fim = min(trecho["fim"], ini + 15)
    clip = trecho["arquivo"]
    masc = mascara_de(trecho.get("clima", "falando"), pasta, durante_reportagem=True)
    ins = ["-ss", f"{ini:.2f}", "-t", f"{fim - ini:.2f}", "-i", str(clip), "-loop", "1", "-i", str(cab)]
    f = (f"[0:v]{cor_sdr(clip)}split[v1][v2];[v1]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=8:2,scale={VW}:{VH},eq=brightness=-0.25[bg];"
         f"[v2]scale={VW}:-2[fg];[bg][fg]overlay=0:(H-h)/2-60[b0];")
    if masc:
        ins += ["-stream_loop", "-1", "-i", str(masc)]
        f += f"[2:v]{cor_sdr(masc)}{cobre(380, 380)}[m];[b0][m]overlay=(W-w)/2:1330[b1];"
    else:
        f += "[b0]null[b1];"
    f += f"[b1][1:v]overlay=0:0,fps={FPS},format=yuv420p[vo]"
    ac = audio_bom(clip)
    af = ["-map", f"0:a:{ac}", "-af", "loudnorm=I=-16:TP=-1.5,aresample=48000"] if ac is not None else []
    p = tmp / f"sv_{idx}_b.mp4"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", f, "-map", "[vo]", *af, "-t", f"{fim - ini:.2f}", *enc(), str(p)])
    if r.returncode == 0:
        pecas.append(p)
    if not pecas:
        return None
    lista = tmp / f"sv_{idx}.txt"
    lista.write_text("".join(f"file '{x.as_posix()}'\n" for x in pecas), encoding="utf-8")
    bruto = tmp / f"sv_{idx}_bruto.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(bruto)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(bruto), "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", str(saida)], check=True)
    return saida


# ------------------------------------------------------------------ principal
def pasta_padrao():
    if os.name == "nt" and Path("E:/").exists():
        return Path("E:/DETTO/canal_galo")
    return Path.home() / "DETTO" / "canal_galo"


def raiz_drive():
    """onde o Google Drive para computador aparece no PC (G:\\Meu Drive...)"""
    for letra in "GHIJKFED":
        for nome in ("Meu Drive", "My Drive"):
            p = Path(f"{letra}:/{nome}")
            if p.is_dir():
                return p
    for p in (Path.home() / "Google Drive", Path.home() / "Meu Drive", Path.home() / "My Drive"):
        if p.is_dir():
            return p
    return None


VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv", ".webm"}
AUDIO_EXT = VIDEO_EXT | {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".opus", ".flac", ".caf", ".amr", ".3gp"}


def traz_do_drive(pasta, cfg):
    """copia do Drive (DETTO\\canal_noticias) as gravações de máscara e a sua voz — você sobe pelo celular e pronto"""
    if cfg.get("drive"):
        raiz = Path(cfg["drive"])
    else:
        d = raiz_drive()
        raiz = d / "DETTO" / "canal_noticias" if d else None
    if not raiz or not raiz.is_dir():
        return
    m = raiz / "mascara"
    if m.is_dir():
        for f in sorted(m.iterdir()):
            if not f.is_file() or f.suffix.lower() not in VIDEO_EXT:
                continue
            dest = pasta / "mascara" / f.name
            try:
                if dest.exists() and dest.stat().st_size == f.stat().st_size:
                    continue
                shutil.copy2(f, dest)
                log(f"Drive: máscara {f.name} copiada")
            except OSError as e:  # ainda baixando do Drive: pega na próxima rodada
                log(f"Drive: {f.name} ainda não dá para copiar ({e}); tento na próxima")
    v = raiz / "voz"
    if v.is_dir():
        auds = [f for f in v.iterdir() if f.is_file() and f.suffix.lower() in AUDIO_EXT]
        if auds:
            f = max(auds, key=lambda x: x.stat().st_mtime)
            marca = f"{f.name}|{f.stat().st_size}|{int(f.stat().st_mtime)}"
            reg = pasta / "voz" / "origem_drive.txt"
            if not reg.exists() or reg.read_text(encoding="utf-8").strip() != marca:
                ref = pasta / cfg["voz_ref"]
                ref.parent.mkdir(parents=True, exist_ok=True)
                tmp = ref.with_name("_nova_voz.wav")
                # mono, 44,1 kHz, até 40 s, sem graves de vento e com volume certo (a clonagem gosta de voz limpa)
                r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(f), "-vn", "-ac", "1", "-ar", "44100", "-t", "40",
                                    "-af", "highpass=f=70,loudnorm=I=-18:TP=-2", str(tmp)], capture_output=True, text=True)
                if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 50_000:
                    tmp.replace(ref)
                    reg.write_text(marca, encoding="utf-8")
                    log(f"Drive: sua voz atualizada a partir de {f.name}")
                else:
                    tmp.unlink(missing_ok=True)
                    log(f"Drive: não consegui ler a voz {f.name} (ainda baixando?) — tento na próxima")


def prepara(pasta):
    for p in ("mascara", "voz", "fontes", "prontos"):
        (pasta / p).mkdir(parents=True, exist_ok=True)
    cfg_f = pasta / "config.json"
    if not cfg_f.exists():
        grava_json(cfg_f, CONFIG_PADRAO)
    cfg = dict(CONFIG_PADRAO)
    seu = le_json(cfg_f, {})
    if seu.get("fontes_versao", 1) < CONFIG_PADRAO["fontes_versao"]:
        # 20/out: imprensa (Jogo Aberto, Alterosa, ESPN, TNT), TV Galo às vezes, canais de notícias do Galo e busca;
        # notícia INTEIRA; hoje e ontem; sem repetir notícia
        for k_ in ("fontes", "fontes_versao", "busca", "busca_qualquer_canal", "outras_fontes", "fora", "max_horas", "max_videos_rodada",
                   "trecho_min_s", "trecho_max_s", "max_trechos_video", "parecido_max"):
            seu[k_] = CONFIG_PADRAO[k_]
        if seu.get("duracao_alvo_min", 12) < 16:
            seu["duracao_alvo_min"] = CONFIG_PADRAO["duracao_alvo_min"]
        grava_json(cfg_f, seu)
        log("config: fontes novas (imprensa + TV Galo + canais de notícias do Galo + busca), notícias inteiras de hoje e ontem")
    cfg.update(seu)
    leia = pasta / "LEIA-ME.txt"
    if not leia.exists():
        shutil.copyfile(AQUI / "LEIA-ME.txt", leia)
    return cfg


def agendar(pasta):
    if os.name != "nt":
        sys.exit("O agendamento é do Windows. Aqui use o cron.")
    bat = pasta / "rodar_canal.bat"
    bat.write_text(f'@echo off\ncd /d "{PONTE}"\n"{sys.executable}" "{Path(__file__).resolve()}" --pasta "{pasta}" >> "{pasta / "canal.log"}" 2>&1\n', encoding="utf-8")
    r = subprocess.run(["schtasks", "/Create", "/F", "/SC", "HOURLY", "/MO", "2", "/ST", "08:00", "/ET", "23:30", "/TN", "DETTO canal Galo", "/TR", f'"{bat}"'],
                       capture_output=True, text=True)
    print(r.stdout or r.stderr)
    if r.returncode == 0:
        print(f"Agendado: a cada 2 h, das 8h às 23h. Log: {pasta / 'canal.log'}. Tirar: schtasks /Delete /TN \"DETTO canal Galo\" /F")


TRAVA = None


def main():
    ap = argparse.ArgumentParser(description="canal automático do Galo")
    ap.add_argument("--pasta", default=str(pasta_padrao()))
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--preparar", action="store_true", help="só cria as pastas e o config.json")
    ap.add_argument("--agendar", action="store_true")
    ap.add_argument("--nao-postar", action="store_true", help="monta e deixa em prontos\\ (não sobe)")
    ap.add_argument("--forcar", action="store_true", help="monta agora mesmo com poucos trechos / fora do intervalo")
    ap.add_argument("--video", action="append", default=[], help="(teste) arquivo local da imprensa em vez de buscar; pode repetir")
    ap.add_argument("--postar", metavar="PASTA_DO_PRONTO", help="posta um vídeo pronto que estava esperando aprovação")
    ap.add_argument("--sem-coleta", action="store_true", help="não busca vídeos novos da imprensa (só pautas / o que já tem)")
    a = ap.parse_args()
    pasta = Path(a.pasta)
    cfg = prepara(pasta)
    traz_do_drive(pasta, cfg)
    try:
        prepara_mascaras(pasta)
    except Exception as e:
        log(f"máscaras: {e}")
    le_pautas(pasta)
    if a.preparar:
        return
    if a.agendar:
        return agendar(pasta)
    sys.path.insert(0, str(AQUI))
    import youtube_up

    if a.login:
        youtube_up.credenciais(pasta, abrir_navegador=True)
        nome, cid = youtube_up.canal_logado(pasta)
        print(f"Ligado ao canal: {nome} ({cid}). Pronto: o sistema posta sozinho nesse canal.")
        return
    import comum

    if a.postar:
        comum.publica(pasta, Path(a.postar), cfg, log=log)
        return
    # UMA rodada por vez: duas juntas (painel + tarefa do Windows / "Rodar agora") apagavam o tmp\ uma da outra
    # no meio da voz → "falas.json não encontrado"
    global TRAVA
    from reels import trava_rodada
    TRAVA = trava_rodada(pasta, ".canal_rodando")
    if not TRAVA:
        log("outra rodada do canal já está montando agora — saio (essa termina sozinha)")
        return
    hist = le_json(pasta / "historico.json", {"vistos": {}, "trechos": [], "postados": []})
    hoje = dt.date.today().isoformat()

    # 1-2) coleta → baixa → transcreve → trechos
    def local(v):
        """arquivo da imprensa no PC; o .info.json do yt-dlp ao lado (se tiver) dá o título e a fonte"""
        d = le_json(Path(v).with_suffix(".info.json"), {})
        fonte = d.get("uploader") or d.get("channel") or "teste"
        fonte = {"atletico": "TV Galo", "espnbrasil": "ESPN Brasil"}.get(str(fonte).lower(), fonte)
        return {"id": "local_" + hashlib.sha1(v.encode()).hexdigest()[:8], "arquivo": v, "fonte": fonte, "canal": "",
                "titulo": re.sub(r"\s+", " ", d.get("description") or d.get("title") or Path(v).stem)[:200]}
    novos = [local(v) for v in a.video] if a.video else ([] if a.sem_coleta else coleta(cfg, hist))
    grava_json(pasta / "historico.json", hist)
    try:
        pautas(pasta, cfg, hist)
    except Exception as e:
        log(f"pautas: {e}")
    for v in novos:
        if not v.get("arquivo"):
            log(f"\nbaixando: {v['titulo']} ({v['fonte']})")
            arq, info = baixa(v["url"], pasta / "fontes")
            if not arq:
                log(f"   não baixou: {info}")
                continue
            v["arquivo"] = str(arq)
        log(f"transcrevendo: {Path(v['arquivo']).name}")
        words = transcreve(v["arquivo"])
        tr = acha_trechos(words, v, cfg)
        log(f"   {len(tr)} trecho(s) sobre o Galo")
        dv = dur(v["arquivo"]) or 1e9
        tr = [{**x, "fim": min(x["fim"], dv - 0.2)} for x in tr if min(x["fim"], dv - 0.2) - x["ini"] >= 8]  # nunca além do fim do vídeo
        for x in tr:
            hist["trechos"].append({**x, "video": v["id"], "arquivo": v["arquivo"], "fonte": v["fonte"], "canal": v.get("canal", ""), "data": hoje,
                                    "publicado": v.get("publicado") or dt.datetime.now().isoformat(timespec="minutes"), "usado": False,
                                    "prioridade": v.get("prioridade", 1)})
        grava_json(pasta / "historico.json", hist)

    # 3) hora de montar?
    lim = dt.datetime.now() - dt.timedelta(hours=cfg.get("max_horas", 30))

    def do_dia(x):
        if x.get("pauta"):
            return (dt.date.today() - dt.date.fromisoformat(x["data"])).days <= 5
        try:
            return dt.datetime.fromisoformat(x.get("publicado") or x["data"]) >= lim
        except ValueError:
            return False

    recentes = [x for x in hist["trechos"] if not x["usado"] and Path(x["arquivo"]).exists() and do_dia(x)]
    tem_pauta = any(x.get("pauta") for x in recentes)
    esperando = [d for _, d in comum.prontos(pasta) if d.get("status") == "aguardando"]
    postados_hoje = [p for p in hist["postados"] if p["data"] == hoje]
    ultimo = max((dt.datetime.fromisoformat(p["quando"]) for p in hist["postados"]), default=None)
    if not a.forcar:
        if len(esperando) >= 2:
            log(f"{len(esperando)} vídeos esperando você aprovar no painel (aba Canais); não monto mais até lá")
            return
        if len(recentes) < cfg["min_trechos"] and not tem_pauta:
            log(f"ainda poucos trechos ({len(recentes)}/{cfg['min_trechos']}); espera a próxima rodada")
            return
        if len(postados_hoje) >= cfg["max_videos_dia"]:
            log("já postou o máximo de hoje")
            return
        if ultimo and (dt.datetime.now() - ultimo).total_seconds() < cfg["horas_entre_posts"] * 3600:
            log("postou há pouco; espera o intervalo")
            return
    if not recentes:
        log("sem trechos para montar")
        return
    # os melhores (nota) até o tamanho do vídeo, sem repetir muito a mesma fonte seguida
    alvo = cfg["duracao_alvo_min"] * 60
    sel, tot = [], 0.0

    def total_estimado():
        # imprensa + suas falas (~12 s antes de cada notícia) + abertura e fechamento (~30 s)
        return tot + 12 * len(sel) + 30
    por_video = {}
    # pautas primeiro; depois as melhores notas, desempate pela mais nova (notícia do dia na frente)
    for x in sorted(recentes, key=lambda x: (not x.get("pauta"), -round(float(x.get("nota", 5))), int(x.get("prioridade", 1)),
                                             "".join(chr(255 - ord(c)) for c in x.get("publicado", "")))):
        if total_estimado() >= alvo:
            break
        if por_video.get(x["video"], 0) >= int(cfg.get("max_trechos_video", 3)):
            continue
        lim_p = float(cfg.get("parecido_max", 0.35))
        tx = x.get("texto") or x.get("manchete", "")
        if any(parecido(tx, y.get("texto") or y.get("manchete", "")) >= lim_p for y in sel):
            continue  # a mesma notícia já entrou por outro canal
        if any(parecido(tx, t) >= lim_p for t in [u["texto"] for u in hist.get("ja_postado", [])]):
            x["usado"] = True  # já saiu num vídeo nosso (hoje/ontem): não repete
            continue
        por_video[x["video"]] = por_video.get(x["video"], 0) + 1
        sel.append(x)
        tot += x["fim"] - x["ini"]
    # no vídeo, a ordem é da mais nova para a mais antiga (manchete do dia abre)
    sel = [x for x in sel if x.get("pauta")] + sorted([x for x in sel if not x.get("pauta")], key=lambda x: x.get("publicado", ""), reverse=True)
    if total_estimado() < alvo:
        if not a.forcar:
            log(f"ainda não dá {cfg['duracao_alvo_min']} min (tem ~{total_estimado() / 60:.1f} min de notícia nova); espera a próxima rodada")
            return
        log(f"AVISO: só tem ~{total_estimado() / 60:.1f} min de notícia nova (menos de {cfg['duracao_alvo_min']}); monto assim porque você mandou")
    log(f"\nmontando: {len(sel)} trechos, {tot / 60:.1f} min de imprensa (~{total_estimado() / 60:.1f} min de vídeo)")
    rot = roteiro(sel, cfg)
    tmp = pasta / "tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    pronto = pasta / "prontos" / f"{dt.datetime.now():%Y-%m-%d_%H%M} - {slug(rot['titulo'], 50)}"
    pronto.mkdir(parents=True, exist_ok=True)
    video = monta(sel, rot, cfg, pasta, tmp, pronto / "video.mp4")
    th = thumb(video, rot, cfg, pronto)
    creditos = sorted({origem(x) + (f" — youtube.com/{x['canal']}" if x.get("canal") else "") for x in sel})
    tags = [t.strip("#") for t in rot.get("tags", [])][:15]
    hashtags = " ".join("#" + re.sub(r"\W", "", t) for t in tags[:3])
    descricao = (f"{rot.get('descricao', '')}\n\n{hashtags}\n\nCréditos das imagens:\n"
                 + "\n".join(f"• {c}" for c in creditos) + "\n\nNarração com voz gerada por inteligência artificial.")
    (pronto / "post.txt").write_text(f"{rot['titulo']}\n\n{descricao}\n\nTags: {', '.join(tags)}\n", encoding="utf-8")
    # Shorts: as melhores notícias (pautas primeiro), cada uma com a sua fala antes
    falas = le_json(tmp / "falas.json", [])
    fala_antes = {f["antes"]: f for f in falas if "antes" in f}
    ordem = sorted(range(len(sel)), key=lambda i: (not sel[i].get("pauta"), -float(sel[i].get("nota", 5))))
    shorts = []
    for n, i in enumerate(ordem[: int(cfg.get("shorts", 0))]):
        log(f"   short {n + 1}: {sel[i]['manchete']}")
        sv = short(cfg, pasta, fala_antes.get(i), sel[i], tmp, n, pronto / f"short_{n + 1}.mp4")
        if sv:
            shorts.append({"arquivo": sv.name, "titulo": sel[i]["manchete"].title(), "descricao": sel[i].get("resumo", "")})
    for x in sel:
        x["usado"] = True
    # lembra o que foi postado (3 dias) para a mesma notícia não voltar por outro canal
    hist["ja_postado"] = [u for u in hist.get("ja_postado", []) if (dt.date.today() - dt.date.fromisoformat(u["data"])).days <= 3] + \
        [{"data": hoje, "texto": (x.get("texto") or x.get("manchete", ""))[:1500]} for x in sel]
    # crédito também num COMENTÁRIO no vídeo (o sistema comenta logo depois de postar)
    comentario = ("📺 Créditos — trechos de TV/rádio/canais usados neste vídeo (comentados pelo canal):\n"
                  + "\n".join(f"• {c}" for c in creditos) + "\n\nTodos os direitos dos trechos são dos seus donos. Narração com voz gerada por IA.")
    post = {"titulo": rot["titulo"], "descricao": descricao, "tags": tags, "video": "video.mp4", "thumb": th.name if th else "",
            "comentario": comentario,
            "shorts": shorts, "status": "aguardando", "criado": dt.datetime.now().isoformat(timespec="seconds"),
            "trechos": [{"fonte": x["fonte"], "manchete": x["manchete"], "pauta": x.get("pauta", "")} for x in sel]}
    comum.grava(pronto / "post.json", post)
    reg = {"data": hoje, "quando": dt.datetime.now().isoformat(timespec="seconds"), "titulo": rot["titulo"], "pasta": str(pronto)}
    if a.nao_postar or not cfg.get("auto_postar"):
        log(f"PRONTO, esperando você aprovar (painel → Canais): {pronto}")
    else:
        post = comum.publica(pasta, pronto, cfg, log=log)
        reg["youtube"] = post.get("youtube")
    hist["postados"].append(reg)
    grava_json(pasta / "historico.json", hist)
    # fontes já usadas por inteiro saem do disco (disco cheio)
    usados = {x["arquivo"] for x in hist["trechos"] if x["usado"]}
    pendentes = {x["arquivo"] for x in hist["trechos"] if not x["usado"]}
    for f in usados - pendentes:
        for g in Path(f).parent.glob(Path(f).stem + "*"):
            g.unlink(missing_ok=True)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
    os._exit(0)
