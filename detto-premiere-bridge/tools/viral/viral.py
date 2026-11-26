# -*- coding: utf-8 -*-
"""CATCHER DE TENDÊNCIAS VIRAIS DE CURTO PRAZO — o cérebro de monitoramento do ecossistema do Everton.

    pip install -r requirements.txt     (feedparser, yt-dlp, requests, google-api-python-client são opcionais;
                                         sem eles o programa AINDA roda, pelos caminhos de reserva)

O QUE ELE FAZ
  1. Lê os RSS dos grandes portais (G1, Globo Esporte, CNN...) e acha a NOTÍCIA QUENTE pelas palavras de
     impacto (morre, tragédia, urgente, anúncio...). O termo achado vira a palavra-chave de busca.
  2. Procura vídeos CURTOS (Shorts/Reels/TikToks) sobre esse termo e cruza TRÊS variáveis:
        tempo de publicação  ·  velocidade de views  ·  TAMANHO do perfil (filtro antigigantes)
  3. Calcula o FATOR DE URGÊNCIA (views por minuto de vida) e, passando do corte, grita "FAÇA AGORA".
  4. Baixa o vídeo na pasta `videos_para_react` e avisa no seu celular (Telegram ou Discord).

DOIS MODOS
    python tools\\viral\\viral.py                      automático (uma rodada; --vigiar fica em laço)
    python tools\\viral\\viral.py --termo "nome que explodiu"      manual, você manda o termo

POR QUE A VELOCIDADE E NÃO AS VIEWS (a regra de ouro deste arquivo)
Um vídeo com 15 mil views pode ser velho e morto; 15 mil em 29 MINUTOS é um foguete subindo. E se o perfil
tem 2 milhões de inscritos, as 15 mil views são só o tamanho dele — não há onda para pegar. É o cruzamento
das três coisas que diz "corre": RECENTE + RÁPIDO + PERFIL PEQUENO.

ONDE ISSO ENTRA NO SISTEMA DELE
  - O vídeo baixado fica em `<DETTO>\\viral\\videos_para_react\\` e já serve de `original` para o
    `tools\\react\\react.py` (é só gravar a sua reação e apontar o react.json para ele).
  - O ASSUNTO vai para `pautas_virais.txt`, que o canal de notícias lê como pauta — então o mesmo assunto
    que está explodindo vira também um vídeo de notícia na sua voz, sem você digitar nada.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS / "reels"))
sys.path.insert(0, str(TOOLS / "canal"))

# ------------------------------------------------------------------ OS PARÂMETROS DE CORTE (mexa aqui)
# Ficam também em `<DETTO>\viral\config.json`, que manda nestes quando existir.
MIN_VIEWS = 15000                   # views mínimas para o vídeo contar como viral
MAX_TIME_WINDOW_MINUTES = 60        # postado há no máximo 1 hora (a janela dura; a frouxa é a de baixo)
JANELA_FOLGADA_MINUTES = 24 * 60    # até 24 h ainda entra, mas precisa de MUITO mais tração
MAX_SUBSCRIBERS_OR_FOLLOWERS = 20000   # filtro ANTIGIGANTES: perfil maior que isso não conta
URGENCIA_FAZ_AGORA = 300            # views por MINUTO que já é "🚨 FAÇA AGORA" (15k/29min = 517)
URGENCIA_MINIMA = 60                # abaixo disso não é onda, é vídeo normal

# os portais (RSS). Acrescente o que quiser; cada linha é só um endereço.
# CONFERIDOS um por um em 05/nov (contei os <item> de cada): endereço de feed é coisa que morre calada e
# um feed morto só tira notícia da mesa. O da CNN é o `admin.`; o `www.cnnbrasil.com.br/feed/` redireciona
# e o `/esportes/feed/` dá 404. O do Lance e o do R7 não devolvem item nenhum e por isso não entram.
FEEDS = [
    "https://g1.globo.com/rss/g1/",                                    # 60 itens
    "https://ge.globo.com/rss/ge/",                                    # geral do esporte
    "https://ge.globo.com/rss/ge/futebol/times/atletico-mg/",          # 100 itens, o Galo
    "https://admin.cnnbrasil.com.br/feed/",                            # 60 itens
    "https://rss.uol.com.br/feed/noticias.xml",                        # 15 itens
    "https://rss.uol.com.br/feed/esporte.xml",                         # 15 itens
]

# palavras de IMPACTO/URGÊNCIA no título: achando uma, o assunto daquela notícia vira a busca
QUENTES = [
    "morre", "morreu", "morte", "falece", "faleceu", "morto", "tragedia", "tragico",
    "urgente", "grave", "gravissimo", "acidente", "desaba", "desabou", "explosao", "incendio",
    "anuncio", "anuncia", "anunciou", "oficializa", "confirmado", "confirma",
    "demitido", "demissao", "afastado", "preso", "prisao", "escandalo", "polemica",
    "renuncia", "aposenta", "aposentadoria", "contratado", "fechado", "assinou",
    "vazou", "bomba", "chocante", "inacreditavel", "absurdo", "historico", "recorde",
]
# notícia de rotina: não é onda, não gasta busca
FRIAS = ["veja a tabela", "onde assistir", "escalacoes provaveis", "horario dos jogos", "previsao do tempo"]

# o que NUNCA vale a pena reagir (respeito e segurança: criança, crime sexual, suicídio)
PROIBIDO = ["crianca morta", "estupro", "abuso sexual", "pedofil", "suicidio", "se matou",
            "menor de idade morto", "feminicidio"]


# ------------------------------------------------------------------ utilidades
def log(m):
    print(f"{dt.datetime.now():%H:%M} {m}", flush=True)


def norm(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip()


def raiz_midia():
    """a pasta da mídia dele. FORA DO WINDOWS o "E:/DETTO" vira uma pasta LITERAL chamada "E:" dentro de
    onde o programa estiver rodando — e foi assim que um teste meu criou `detto-premiere-bridge/E:/DETTO/...`
    dentro do repositório, que entrou no commit e QUEBROU o `git pull` no PC dele ("invalid path", porque
    ":" não vale em nome de arquivo no Windows). Então aqui fora isso cai no /tmp."""
    d = os.environ.get("DETTO_MIDIA")
    if d:
        return Path(d)
    if os.name == "nt":
        return Path("E:/DETTO")
    import tempfile
    return Path(tempfile.gettempdir()) / "DETTO"


def le_json(p, padrao):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def grava_json(p, d):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def config(base):
    """os cortes, com o config.json da pasta mandando quando existir"""
    c = {"min_views": MIN_VIEWS, "janela_min": MAX_TIME_WINDOW_MINUTES, "janela_folgada_min": JANELA_FOLGADA_MINUTES,
         "max_seguidores": MAX_SUBSCRIBERS_OR_FOLLOWERS, "urgencia_faz_agora": URGENCIA_FAZ_AGORA,
         "urgencia_minima": URGENCIA_MINIMA, "feeds": FEEDS, "quantos_termos": 3, "por_termo": 12,
         "baixar": True, "telegram_chat": "", "discord_webhook": "", "pauta_para_o_canal": True,
         "nicho": ["futebol", "atletico", "galo", "gta", "games"], "so_do_nicho": False}
    c.update(le_json(base / "config.json", {}))
    return c


# ------------------------------------------------------------------ 1) MONITORAMENTO DE NOTÍCIAS
def _baixa_texto(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DETTO viral catcher)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:   # noqa: BLE001
        log(f"   feed {url.split('/')[2]}: {str(e)[:70]}")
        return ""


def _itens_do_feed(url):
    """(titulo, quando) de cada notícia. Usa o feedparser quando existe; senão lê o XML na mão.

    O caminho na mão existe porque o PC dele não tem o feedparser instalado e eu não quero que o programa
    deixe de rodar por causa de uma biblioteca que não é essencial."""
    try:
        import feedparser   # noqa: PLC0415
        d = feedparser.parse(url)
        out = []
        for e in d.entries:
            quando = None
            if getattr(e, "published_parsed", None):
                quando = dt.datetime(*e.published_parsed[:6])
            out.append((getattr(e, "title", "") or "", quando, getattr(e, "link", "") or ""))
        return out
    except ImportError:
        pass
    txt = _baixa_texto(url)
    if not txt:
        return []
    out = []
    for bloco in re.findall(r"<item\b.*?</item>|<entry\b.*?</entry>", txt, re.S | re.I):
        t = re.search(r"<title[^>]*>(.*?)</title>", bloco, re.S | re.I)
        d_ = re.search(r"<(?:pubDate|published|updated)[^>]*>(.*?)</", bloco, re.S | re.I)
        l_ = re.search(r"<link[^>]*>(.*?)</link>|<link[^>]*href=\"([^\"]+)\"", bloco, re.S | re.I)
        titulo = re.sub(r"<!\[CDATA\[|\]\]>|<[^>]+>", "", t.group(1)).strip() if t else ""
        quando = None
        if d_:
            quando = _data_do_feed(d_.group(1).strip())
        link = ""
        if l_:
            link = (l_.group(1) or l_.group(2) or "").strip()
        if titulo:
            out.append((titulo, quando, link))
    return out


def _data_do_feed(s):
    for f in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            d = dt.datetime.strptime(s, f)
            return d.astimezone().replace(tzinfo=None) if d.tzinfo else d
        except ValueError:
            continue
    return None


# palavra que começa manchete e NÃO é nome próprio, apesar da maiúscula. Sem esta lista saía "Saiba Saiba
# quem" como termo de busca (medido contra os títulos reais do G1/GE em 05/nov).
ABRE_MANCHETE = {
    "saiba", "veja", "confira", "entenda", "assista", "apos", "antes", "como", "porque", "por", "quem",
    "onde", "quando", "quanto", "qual", "quais", "com", "sem", "em", "no", "na", "ao", "de", "da", "do",
    "um", "uma", "os", "as", "e", "o", "a", "exclusivo", "urgente", "video", "fotos", "foto", "agora",
    "ele", "ela", "eles", "elas", "isso", "este", "esta", "nesta", "neste", "hoje", "ontem", "ainda",
    "sera", "foi", "tem", "diz", "disse", "fala", "falou", "mais", "menos", "tudo", "nada", "nao",
}
PALAVRAS_VAZIAS = ANOS_FORA = {
    "de", "da", "do", "das", "dos", "e", "o", "a", "os", "as", "em", "no", "na", "nos", "nas", "um", "uma",
    "para", "por", "com", "sem", "que", "ao", "aos", "apos", "anos", "ano", "ex", "sobre", "contra",
    "diz", "veja", "video", "foto", "fotos", "nesta", "neste", "hoje", "ontem", "mais", "menos", "seu", "sua",
}


def _assunto(titulo):
    """o TERMO DE BUSCA que sai de um título de notícia.

    Não dá para jogar o título inteiro na busca ("Morre aos 82 anos o ex-jogador X, ídolo do Y" não acha
    Short nenhum). O que viraliza é o NOME.

    O JEITO CERTO, achado testando contra os títulos reais do G1 e do GE (05/nov): nome próprio é uma
    SEQUÊNCIA de palavras com maiúscula ("Cristiano Ronaldo", "Jorge Jesus"), não palavras maiúsculas
    espalhadas. Pegar as 3 primeiras maiúsculas soltas dava "Saiba Saiba quem" e "Réver Réver manifesta" —
    busca que não acha nada. Então: acho as SEQUÊNCIAS, descarto a que começa a manchete sem ser nome, e
    fico com a maior."""
    t = re.sub(r"\s+", " ", titulo or "").strip()
    # o selo do começo ("URGENTE:", "EXCLUSIVO:", "AO VIVO:") não é o assunto — sem tirar isso o termo de
    # busca saía literalmente "URGENTE"
    t = re.sub(r"^(?:[A-ZÁÂÃÉÊÍÓÔÕÚÜÇ\s]{3,20}|🚨|⚠️?)\s*[:\-–—]\s*", "", t).strip() or t
    pedacos = re.split(r"[:;|–—]| - ", t)
    if len(t) > 45 and len(pedacos[0]) >= 18:
        t = pedacos[0]      # só corto no primeiro pedaço quando ele já é uma frase, não um selo
    quentes = set(norm(" ".join(QUENTES)).split())
    fora = PALAVRAS_VAZIAS | quentes

    # sequências de palavras com maiúscula = nomes próprios ("Jorge Jesus", "Cristiano Ronaldo")
    seqs = []
    for m in re.finditer(r"[A-ZÁÂÃÉÊÍÓÔÕÚÜÇ][\wÀ-ÿ'’\-]+(?:\s+(?:d[aeoi]s?\s+)?[A-ZÁÂÃÉÊÍÓÔÕÚÜÇ][\wÀ-ÿ'’\-]+)*", t):
        ps = m.group(0).split()
        # tira do começo o que só está em maiúscula por abrir a manchete, e as palavras quentes
        while ps and (norm(ps[0]) in ABRE_MANCHETE or norm(ps[0]) in quentes):
            ps.pop(0)
        while ps and (norm(ps[-1]) in fora or norm(ps[-1]) in ABRE_MANCHETE):
            ps.pop()
        if ps and not (len(ps) == 1 and len(ps[0]) <= 2):
            seqs.append(" ".join(ps))

    # sem repetir e a maior primeiro (a maior é a mais específica: "Cristiano Ronaldo" > "Cristiano")
    vistas, limpas = set(), []
    for s in sorted(seqs, key=lambda x: -len(x.split())):
        n = norm(s)
        if n in vistas or any(n in v for v in vistas):
            continue
        vistas.add(n)
        limpas.append(s)
    if limpas:
        termo = limpas[0]
        # um nome sozinho e curto ganha o segundo nome, para a busca não ficar genérica demais
        if len(termo.split()) == 1 and len(limpas) > 1:
            termo += " " + limpas[1]
        return " ".join(dict.fromkeys(termo.split()))

    grandes = [p for p in re.findall(r"[\wÀ-ÿ\-]{4,}", t) if norm(p) not in fora and norm(p) not in ABRE_MANCHETE]
    return " ".join(dict.fromkeys(grandes[:3])) or t[:40]


def Capturar_Noticias(cfg, visto=None):   # noqa: N802  (o nome é o que ele pediu)
    """AS NOTÍCIAS QUENTES de agora → [{termo, titulo, palavra, quando, fonte, link}], a mais quente primeiro."""
    visto = visto or set()
    achados, por_termo = [], {}
    for url in cfg["feeds"]:
        for titulo, quando, link in _itens_do_feed(url):
            n = norm(titulo)
            if any(p in n for p in PROIBIDO):
                continue           # assunto que não se reage, por respeito
            if any(p in n for p in [norm(x) for x in FRIAS]):
                continue
            palavra = next((q for q in QUENTES if re.search(rf"\b{re.escape(q)}", n)), "")
            if not palavra:
                continue
            if cfg.get("so_do_nicho") and not any(norm(x) in n for x in cfg.get("nicho", [])):
                continue
            idade = (dt.datetime.now() - quando).total_seconds() / 60 if quando else 999
            if idade > cfg["janela_folgada_min"]:
                continue           # notícia de ontem não é onda
            termo = _assunto(titulo)
            if not termo or norm(termo) in visto:
                continue
            # o MESMO assunto em vários portais = notícia de verdade: guarda a mais nova e conta os portais
            k = norm(termo)
            if k in por_termo:
                por_termo[k]["portais"] += 1
                por_termo[k]["idade"] = min(por_termo[k]["idade"], idade)
                continue
            por_termo[k] = {"termo": termo, "titulo": titulo.strip(), "palavra": palavra, "idade": idade,
                            "fonte": url.split("/")[2], "link": link, "portais": 1}
    achados = sorted(por_termo.values(), key=lambda x: (-x["portais"], x["idade"]))
    for a in achados:
        a["quando"] = (dt.datetime.now() - dt.timedelta(minutes=a["idade"])).isoformat(timespec="minutes")
    return achados


# ------------------------------------------------------------------ 2+3) CAPTURA E FILTRO NAS REDES
def _youtube_api(termo, cfg, quantos):
    """YouTube Data API v3 (google-api-python-client): Shorts do termo, com views e inscritos do dono.

    Só roda com `YOUTUBE_API_KEY`. Sem a chave eu caio no yt-dlp, que não precisa de chave nenhuma — é
    assim que o resto do sistema dele funciona e é o que garante que isto rode no PC dele hoje."""
    chave = os.environ.get("YOUTUBE_API_KEY") or os.environ.get("YT_API_KEY")
    if not chave:
        return None
    try:
        from googleapiclient.discovery import build   # noqa: PLC0415
    except ImportError:
        return None
    try:
        yt = build("youtube", "v3", developerKey=chave, cache_discovery=False)
        depois = (dt.datetime.utcnow() - dt.timedelta(minutes=cfg["janela_folgada_min"])).strftime("%Y-%m-%dT%H:%M:%SZ")
        busca = yt.search().list(q=termo, part="id,snippet", type="video", videoDuration="short",
                                 order="date", publishedAfter=depois, maxResults=min(50, quantos * 3),
                                 regionCode="BR", relevanceLanguage="pt").execute()
        ids = [i["id"]["videoId"] for i in busca.get("items", []) if i.get("id", {}).get("videoId")]
        if not ids:
            return []
        vs = yt.videos().list(part="statistics,snippet,contentDetails", id=",".join(ids[:50])).execute()
        canais = {v["snippet"]["channelId"] for v in vs.get("items", [])}
        cs = yt.channels().list(part="statistics", id=",".join(list(canais)[:50])).execute()
        inscritos = {c["id"]: int(c.get("statistics", {}).get("subscriberCount") or 0) for c in cs.get("items", [])}
        out = []
        for v in vs.get("items", []):
            s, st = v["snippet"], v.get("statistics", {})
            quando = _data_do_feed(s.get("publishedAt") or "") or dt.datetime.now()
            out.append({"url": f"https://www.youtube.com/shorts/{v['id']}", "titulo": s.get("title") or "",
                        "rede": "youtube", "perfil": s.get("channelTitle") or "",
                        "views": int(st.get("viewCount") or 0), "seguidores": inscritos.get(s["channelId"], 0),
                        "quando": quando, "chave": f"yt:{v['id']}"})
        return out
    except Exception as e:   # noqa: BLE001
        log(f"   a API do YouTube recusou ({str(e)[:90]}); vou pelo yt-dlp")
        return None


# o `sp=` da busca do YouTube: o filtro que o site usa. Com ele eu peço DIRETO "da última hora e curto",
# que é exatamente o que este programa procura. O `ytsearchdate:` que eu tinha usado primeiro NÃO EXISTE
# MAIS no yt-dlp (2026.10.26 responde "Unsupported url scheme") — só o `ytsearch:`, que ignora a data.
SP_BUSCA = [("última hora", "CAISBAgBEAE", 60), ("hoje", "CAISBAgCEAE", 24 * 60)]


def _relevante(titulo, termo, noticia):
    """o vídeo é MESMO sobre o assunto?

    Buscar "Réver" (o zagueiro) trouxe "Rêver de laver du linge" em francês — e este programa BAIXA sozinho
    o que aprova, então lixo aprovado é lixo no disco. A regra: ou o título tem o termo INTEIRO, ou tem o
    termo e mais uma palavra forte da manchete. Um nome sozinho nunca basta."""
    t = norm(titulo)

    def tem_no_titulo(p):
        # compara pelo COMEÇO da palavra: o viral costuma estar em outra língua ("Paraguay President
        # Resigns" para a notícia "Presidente do Paraguai renuncia") e exigir a palavra idêntica jogava
        # fora exatamente o vídeo gringo que ele quer reagir.
        return p in t or (len(p) >= 5 and re.search(rf"\b{re.escape(p[:5])}", t) is not None)

    ps = [p for p in norm(termo).split() if len(p) > 2]
    if not ps:
        return False
    tem = [p for p in ps if tem_no_titulo(p)]
    if len(ps) >= 2 and len(tem) >= 2:
        return True                      # "Jorge Jesus" inteiro no título: é sobre isso
    if not tem:
        return False
    fortes = [p for p in norm(noticia or "").split()
              if len(p) > 4 and p not in PALAVRAS_VAZIAS and p not in ABRE_MANCHETE and p not in ps]
    return any(tem_no_titulo(p) for p in fortes)


def _youtube_ytdlp(termo, cfg, quantos):
    """o mesmo, SEM chave nenhuma: a busca do site com o filtro de data+curto.

    A listagem já traz DURAÇÃO e VIEWS (conferido), então o filtro grosso sai de graça; os inscritos e a
    hora exata vêm depois, só para quem já tem views suficientes (`_detalha`)."""
    try:
        from reels import ytdlp   # noqa: PLC0415
    except ImportError:
        log("   não achei o reels.py (ytdlp): sem busca no YouTube")
        return []
    out, vistos = [], set()
    for nome, sp, janela in SP_BUSCA:
        alvo = f"https://www.youtube.com/results?search_query={urllib.parse.quote(termo)}&sp={sp}"
        r = ytdlp(["--flat-playlist", "--dump-json", "--playlist-end", str(min(30, quantos * 2)),
                   "--match-filter", "!is_live", alvo], timeout=180)
        achou = 0
        for linha in (r.stdout or "").splitlines():
            try:
                v = json.loads(linha)
            except ValueError:
                continue
            if (v.get("ie_key") or "") != "Youtube":
                continue                   # a busca devolve CANAIS também; esses não são vídeo
            vid = v.get("id")
            if not vid or vid in vistos:
                continue
            dur = v.get("duration") or 0
            if dur and dur > 180:
                continue                   # só vídeo CURTO (Short/Reels/TikTok reaproveitado)
            vistos.add(vid)
            achou += 1
            out.append({"url": f"https://www.youtube.com/watch?v={vid}", "titulo": v.get("title") or "",
                        "rede": "youtube", "perfil": v.get("channel") or v.get("uploader") or "",
                        "views": int(v.get("view_count") or 0),
                        "seguidores": int(v.get("channel_follower_count") or 0),
                        "quando": None, "janela_max_min": janela, "achado_em": nome,
                        "chave": f"yt:{vid}", "_precisa_detalhe": True})
        if achou >= quantos:
            break                          # achei o bastante na janela mais apertada; não preciso abrir mais
        if not achou and "Unsupported url scheme" in (r.stderr or ""):
            log(f"   a busca por {nome} não foi aceita pelo yt-dlp; atualize com: python -m pip install -U yt-dlp")
    return out


def _detalha(v, cfg):
    """a HORA exata e os inscritos de um candidato (a busca não traz os dois de forma confiável)"""
    try:
        from reels import ytdlp   # noqa: PLC0415
    except ImportError:
        return v
    r = ytdlp(["--skip-download", "--print",
               "%(timestamp)s|%(channel_follower_count)s|%(view_count)s|%(duration)s|%(uploader_id)s",
               v["url"]], timeout=120)
    linha = (r.stdout or "").strip().splitlines()[-1:] or [""]
    partes = linha[0].split("|")
    if len(partes) >= 3:
        try:
            if partes[0] not in ("NA", ""):
                v["quando"] = dt.datetime.fromtimestamp(int(partes[0]))
        except (ValueError, OSError):
            pass
        for k, i in (("seguidores", 1), ("views", 2)):
            try:
                v[k] = int(partes[i]) if partes[i] not in ("NA", "") else v.get(k, 0)
            except ValueError:
                pass
        if len(partes) >= 5 and partes[4] not in ("NA", ""):
            v["perfil_id"] = partes[4]
    v["_precisa_detalhe"] = False
    return v


def _playwright_rede(termo, rede, cfg, quantos=8):
    """TIKTOK e INSTAGRAM pelo navegador (Playwright), que é o único jeito sem API aprovada.

    ESTRUTURAL e DESLIGADO por padrão (`"playwright": true` no config liga): as duas redes mudam o HTML
    toda semana e bloqueiam robô agressivamente. A leitura é feita pelos dados que a própria página carrega
    (JSON embutido), não por seletor de CSS, que é o que quebra primeiro. Login: `cookies.txt` na pasta.
    """
    if not cfg.get("playwright"):
        return []
    try:
        from playwright.sync_api import sync_playwright   # noqa: PLC0415
    except ImportError:
        log("   sem playwright instalado (pip install playwright && playwright install chromium)")
        return []
    url = (f"https://www.tiktok.com/search/video?q={urllib.parse.quote(termo)}" if rede == "tiktok"
           else f"https://www.instagram.com/explore/tags/{re.sub(r'[^0-9a-zA-Z]', '', termo)}/")
    out = []
    try:
        with sync_playwright() as pw:
            nav = pw.chromium.launch(headless=True)
            ctx = nav.new_context(locale="pt-BR", viewport={"width": 1280, "height": 900},
                                  user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                             "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
            ck = Path(cfg.get("cookies") or (raiz_midia() / "cookies.txt"))
            if ck.is_file():
                ctx.add_cookies(_cookies_netscape(ck, rede))
            pg = ctx.new_page()
            pg.goto(url, timeout=45000, wait_until="domcontentloaded")
            pg.wait_for_timeout(3500)
            # os números vêm do JSON que a página embute, não do texto da tela (que é "15,3 mil")
            bruto = pg.content()
            for m in re.finditer(r'"playCount"\s*:\s*(\d+).{0,400}?"uniqueId"\s*:\s*"([^"]+)"', bruto, re.S):
                out.append({"url": f"https://www.tiktok.com/@{m.group(2)}", "titulo": termo, "rede": "tiktok",
                            "perfil": m.group(2), "views": int(m.group(1)), "seguidores": 0, "quando": None,
                            "chave": f"tt:{m.group(2)}:{m.group(1)}"})
            nav.close()
    except Exception as e:   # noqa: BLE001
        log(f"   {rede} pelo navegador não deu ({str(e)[:90]})")
    return out[:quantos]


def _cookies_netscape(arq, rede):
    """o cookies.txt exportado do navegador no formato que o Playwright aceita"""
    dom = ".tiktok.com" if rede == "tiktok" else ".instagram.com"
    out = []
    try:
        for linha in Path(arq).read_text(encoding="utf-8", errors="replace").splitlines():
            if linha.startswith("#") or not linha.strip():
                continue
            p = linha.split("\t")
            if len(p) >= 7 and dom in p[0]:
                out.append({"name": p[5], "value": p[6], "domain": p[0], "path": p[2]})
    except OSError:
        pass
    return out


def Filtrar_Videos(candidatos, cfg, feitos=None):   # noqa: N802
    """A REGRA DE OURO: recente + rápido + perfil pequeno. Devolve os aprovados, o mais urgente primeiro.

    `fator` = views por MINUTO de vida. É ele que separa "15 mil views" de "15 mil views em 29 minutos".
    A janela de 1 h é a nobre; até 24 h ainda entra, mas tem de ter MUITO mais tração (`exigencia`), senão
    todo vídeo de ontem com 50 mil views passaria."""
    feitos = feitos or set()
    aprovados, recusados = [], []
    for v in candidatos:
        if v["chave"] in feitos:
            continue
        if not _relevante(v.get("titulo", ""), v.get("termo") or cfg.get("_termo", ""), cfg.get("_noticia", "")):
            recusados.append((v, "não é sobre o assunto (só coincidiu a palavra)"))
            continue
        motivo = ""
        quando = v.get("quando")
        idade = (dt.datetime.now() - quando).total_seconds() / 60 if quando else None
        # A HORA EXATA NÃO É OBRIGATÓRIA (05/nov): pedir a hora de cada vídeo é uma consulta por candidato,
        # e é justamente a consulta que o YouTube barra sem cookies — TODO candidato era recusado por
        # "não descobri a hora do post". Mas eu JÁ SEI a janela: o vídeo veio do filtro "última hora" do
        # próprio YouTube. Então uso o PIOR CASO da janela (1 h), que é um limite honesto e de graça.
        aproximado = idade is None
        if aproximado:
            idade = float(v.get("janela_max_min") or cfg["janela_folgada_min"])
        if idade < 0.5:
            motivo = "acabou de sair (sem views para medir)"
        elif idade > cfg["janela_folgada_min"]:
            motivo = f"velho ({idade / 60:.0f} h)"
        elif v.get("views", 0) < cfg["min_views"]:
            motivo = f"{v.get('views', 0)} views (mínimo {cfg['min_views']})"
        if motivo:
            recusados.append((v, motivo))
            continue
        # O FILTRO ANTIGIGANTES SÓ VALE COM O NÚMERO NA MÃO (05/nov): a busca não traz os inscritos, e eu
        # estava tratando "não sei" como ZERO — ou seja, um canal de 2 milhões PASSAVA pelo filtro que existe
        # justamente para barrá-lo, que é o contrário do que ele pediu. Agora eu consulto os inscritos só
        # aqui, nos FINALISTAS (poucos, já com views e idade aprovadas), e quem fica sem o número entra
        # MARCADO, para você decidir olhando — nunca como se fosse pequeno.
        if v.get("_precisa_detalhe"):
            _detalha(v, cfg)
            if v.get("quando"):
                idade = max(0.5, (dt.datetime.now() - v["quando"]).total_seconds() / 60)
                aproximado = False
        if v.get("seguidores", 0) > cfg["max_seguidores"]:
            recusados.append((v, f"perfil grande ({v['seguidores']} seguidores): viralizou pelo tamanho dele"))
            continue
        v["perfil_conferido"] = bool(v.get("seguidores"))
        fator = v["views"] / max(1.0, idade)
        # com a hora EXATA, a exigência sobe com a idade (vídeo de 6 h tem de ter muito mais tração).
        # com a idade APROXIMADA eu já usei o pior caso da janela no `fator`, então a exigência fica a base —
        # senão eu puniria duas vezes a mesma incerteza e nada passaria.
        exigencia = cfg["urgencia_minima"] if aproximado else \
            cfg["urgencia_minima"] * (1 if idade <= cfg["janela_min"] else min(6.0, idade / cfg["janela_min"]))
        if fator < exigencia:
            recusados.append((v, f"{fator:.0f} views/min (precisa de {exigencia:.0f} com {idade / 60:.1f} h de vida)"))
            continue
        v["idade_min"] = round(idade, 1)
        v["idade_aprox"] = aproximado
        v["fator"] = round(fator)
        v["faca_agora"] = fator >= cfg["urgencia_faz_agora"]
        aprovados.append(v)
    aprovados.sort(key=lambda x: -x["fator"])
    return aprovados, recusados


# ------------------------------------------------------------------ 4) DOWNLOAD E ALERTA
def Baixar_Video(v, pasta):   # noqa: N802
    """baixa na maior qualidade para `videos_para_react\\`. Devolve o mp4 ou None.

    Reusa o `baixa()` do reels.py de propósito: é lá que estão a hora marcada (um ao vivo não termina
    nunca), o `!is_live` e a cascata de cookies que eu consertei em 05/nov."""
    pasta.mkdir(parents=True, exist_ok=True)
    try:
        from reels import baixa   # noqa: PLC0415
    except ImportError:
        log("   não achei o reels.py: sem download")
        return None
    arq, info = baixa(v["url"], pasta, timeout=600)
    if not arq:
        log(f"   não baixou: {str(info)[:160]}")
        return None
    # o nome diz o que é, para ele achar na pasta sem abrir um por um
    seguro = re.sub(r"[^\w\s\-À-ÿ]", "", v.get("titulo") or v.get("termo") or "viral")[:60].strip() or "viral"
    novo = pasta / f"{dt.datetime.now():%d-%m %Hh%M} - {v['fator']}vmin - {seguro}{arq.suffix}"
    try:
        arq.replace(novo)
        p_info = arq.with_suffix(".info.json")
        if p_info.exists():
            p_info.replace(novo.with_suffix(".info.json"))
        arq = novo
    except OSError:
        pass
    (arq.with_suffix(".txt")).write_text(
        f"{v.get('titulo', '')}\n\n{v['url']}\nperfil: {v.get('perfil', '')} ({v.get('seguidores', 0)} seguidores)\n"
        f"{v.get('views', 0)} views em {v.get('idade_min', 0):.0f} min = {v['fator']} views/min\n"
        f"notícia: {v.get('noticia', '')}\n", encoding="utf-8")
    return arq


def avisa(texto, cfg):
    """o aviso no seu celular: Telegram (TELEGRAM_TOKEN + chat no config) ou Discord (webhook)."""
    try:
        import requests   # noqa: PLC0415
    except ImportError:
        log("   sem a biblioteca requests: não avisei no celular")
        return False
    enviou = False
    tok, chat = os.environ.get("TELEGRAM_TOKEN"), cfg.get("telegram_chat") or os.environ.get("TELEGRAM_CHAT")
    if tok and chat:
        try:
            r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                              json={"chat_id": chat, "text": texto, "parse_mode": "HTML",
                                    "disable_web_page_preview": False}, timeout=25)
            enviou = r.ok
            if not r.ok:
                log(f"   o Telegram recusou: {r.text[:120]}")
        except Exception as e:   # noqa: BLE001
            log(f"   Telegram: {str(e)[:90]}")
    gancho = cfg.get("discord_webhook") or os.environ.get("DISCORD_WEBHOOK")
    if gancho:
        try:
            r = requests.post(gancho, json={"content": re.sub(r"</?b>", "**", texto)[:1900]}, timeout=25)
            enviou = enviou or r.status_code < 300
        except Exception as e:   # noqa: BLE001
            log(f"   Discord: {str(e)[:90]}")
    if not enviou and not (tok and chat) and not gancho:
        log("   (sem Telegram nem Discord configurados: o aviso ficou só no registro)")
    return enviou


def _recado(v):
    """o texto que chega no seu celular"""
    urgencia = "🚨 <b>URGENTE: FAÇA AGORA!</b>" if v.get("faca_agora") else "🔥 viral subindo"
    idade = f"{'no máximo ' if v.get('idade_aprox') else ''}{v.get('idade_min', 0):.0f} min"
    if v.get("perfil_conferido"):
        tamanho = f"{v.get('seguidores', 0):,} seguidores".replace(",", ".")
    else:
        tamanho = "NÃO conferi o tamanho do perfil"
    views = f"{v.get('views', 0):,}".replace(",", ".")
    baixado = "\n📥 já baixado em videos_para_react" if v.get("arquivo") else ""
    return (f"{urgencia}\n<b>{v.get('noticia') or v.get('termo', '')}</b>\n"
            f"{v.get('titulo', '')[:120]}\n\n"
            f"⚡ {v['fator']} views/min — {views} views em {idade}\n"
            f"👤 {v.get('perfil', '')} ({tamanho})\n"
            f"🔗 {v['url']}{baixado}")


# ------------------------------------------------------------------ a rodada
def pauta_para_o_canal(itens, base):
    """o assunto que está explodindo entra como PAUTA do canal de notícias.

    É o elo que ele pediu: o mesmo assunto viral vira (1) vídeo para você reagir e (2) notícia na sua voz.
    O canal.py já lê `pautas.txt`; eu escrevo num arquivo separado e acrescento, para nunca pisar no que
    você digitou na mão."""
    if not itens:
        return
    arq = base / "pautas_virais.txt"
    tinha = set()
    if arq.exists():
        tinha = {norm(l) for l in arq.read_text(encoding="utf-8", errors="replace").splitlines()}
    novas = [i for i in itens if norm(i["termo"]) not in tinha]
    if not novas:
        return
    with arq.open("a", encoding="utf-8") as f:
        for i in novas:
            f.write(f"{i['termo']}\n")
    log(f"   {len(novas)} assunto(s) em {arq.name} (pauta do canal de notícias)")


def rodada(a):
    base = Path(a.pasta) if a.pasta else (raiz_midia() / "viral")
    base.mkdir(parents=True, exist_ok=True)
    cfg = config(base)
    if getattr(a, "sem_baixar", False):
        cfg["baixar"] = False       # só desta vez: não mexe no config.json dele
    hist = le_json(base / "historico.json", {"feitos": [], "termos": {}})
    feitos = set(hist.get("feitos") or [])
    pasta_mp4 = base / "videos_para_react"

    if a.termo:
        assuntos = [{"termo": a.termo, "titulo": f"(busca na mão) {a.termo}", "palavra": "manual",
                     "idade": 0, "fonte": "você", "link": "", "portais": 1,
                     "quando": dt.datetime.now().isoformat(timespec="minutes")}]
        log(f"BUSCA NA MÃO: {a.termo}")
    else:
        # termos usados nas últimas 6 h não voltam (o portal repete a mesma notícia o dia todo)
        corte = time.time() - 6 * 3600
        usados = {k for k, t in (hist.get("termos") or {}).items() if t > corte}
        assuntos = Capturar_Noticias(cfg, usados)
        log(f"notícias quentes: {len(assuntos)} assunto(s)" + (f" — {assuntos[0]['termo']}" if assuntos else ""))
        for x in assuntos[:cfg["quantos_termos"]]:
            log(f"   • {x['termo']}  ({x['palavra']}, {x['portais']} portal(is), {x['idade']:.0f} min) "
                f"← {x['titulo'][:70]}")
        assuntos = assuntos[:cfg["quantos_termos"]]
        if not assuntos:
            log("nenhuma notícia urgente agora (é o normal na maior parte do dia)")

    achou = 0
    for s in assuntos:
        cands = _youtube_api(s["termo"], cfg, cfg["por_termo"])
        if cands is None:
            cands = _youtube_ytdlp(s["termo"], cfg, cfg["por_termo"])
        for rede in ("tiktok", "instagram"):
            cands += _playwright_rede(s["termo"], rede, cfg)
        log(f"   \"{s['termo']}\": {len(cands)} vídeo(s) curto(s) para conferir")
        cfg["_termo"], cfg["_noticia"] = s["termo"], s["titulo"]
        bons, ruins = Filtrar_Videos(cands, cfg, feitos)
        for v, motivo in ruins[:4]:
            log(f"      fora: {v.get('titulo', '')[:45]} — {motivo}")
        for v in bons:
            v["noticia"] = s["titulo"]
            v["termo"] = s["termo"]
            marca = "🚨 FAÇA AGORA" if v["faca_agora"] else "🔥"
            # o "~" avisa que a idade é o PIOR CASO da janela da busca, não a hora exata do post
            til = "no máximo ~" if v.get("idade_aprox") else ""
            log(f"   {marca} {v['fator']} views/min · {v['views']} views em {til}{v['idade_min']:.0f} min · "
                f"{v['perfil']} ({v['seguidores']} seg.) · {v['titulo'][:50]}")
            if cfg.get("baixar"):
                arq = Baixar_Video(v, pasta_mp4)
                if arq:
                    v["arquivo"] = str(arq)
                    log(f"      baixado: {arq.name}")
            avisa(_recado(v), cfg)
            feitos.add(v["chave"])
            achou += 1
        if bons:
            (hist.setdefault("termos", {}))[norm(s["termo"])] = time.time()

    hist["feitos"] = list(feitos)[-800:]
    grava_json(base / "historico.json", hist)
    if cfg.get("pauta_para_o_canal") and not a.termo:
        pauta_para_o_canal(assuntos, base)
    log(f"rodada terminou: {achou} viral(is) para reagir" + (f" em {pasta_mp4}" if achou else ""))
    return achou


def main():
    ap = argparse.ArgumentParser(description="acha notícia quente + vídeo curto explodindo, baixa e avisa")
    ap.add_argument("--termo", help="busca NA MÃO deste termo (pula os portais de notícia)")
    ap.add_argument("--pasta", help="padrão: <DETTO>\\viral")
    ap.add_argument("--vigiar", type=int, metavar="MIN", help="fica em laço, uma rodada a cada MIN minutos")
    ap.add_argument("--sem-baixar", action="store_true", help="só avisa, não baixa")
    a = ap.parse_args()
    base = Path(a.pasta) if a.pasta else (raiz_midia() / "viral")
    base.mkdir(parents=True, exist_ok=True)

    # só UM por vez (o painel e a tarefa do Windows juntos baixariam o mesmo vídeo duas vezes)
    trava = None
    try:
        from reels import trava_rodada   # noqa: PLC0415
        trava = trava_rodada(base, ".viral_rodando")
        if not trava:
            log("NÃO RODEI: outro viral.py já está rodando")
            return
    except ImportError:
        pass

    if not a.vigiar:
        rodada(a)
        return
    log(f"vigiando: uma rodada a cada {a.vigiar} min (Ctrl+C para parar)")
    while True:
        try:
            rodada(a)
        except KeyboardInterrupt:
            log("parei")
            return
        except Exception as e:   # noqa: BLE001
            log(f"erro nesta rodada (sigo vigiando): {str(e)[:140]}")
        time.sleep(max(60, a.vigiar * 60))


if __name__ == "__main__":
    main()
