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
import time
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
    "nome_canal": "DETTO GALO NOTÍCIAS",
    # assinatura no fim de toda descrição (canal de torcedor: sem parecer o oficial do clube)
    "assinatura": ("📰 DETTO GALO NOTÍCIAS — o que a imprensa falou do Galo hoje, com a resenha de quem vive o Atlético.\n"
                   "🔔 Inscreva-se e ative o sininho: vídeo novo todo dia.\n📲 Instagram e TikTok: @detto.galo\n"
                   "Canal de torcedor, sem ligação oficial com o Clube Atlético Mineiro. Os vídeos de imprensa são usados em "
                   "trechos curtos, com comentário e crédito a quem produziu."),
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
    "fontes_versao": 6,
    # A LEGENDA DO YOUTUBE ANTES DO WHISPER (06/nov) — o maior gargalo que sobrou na rodada do Galo:
    # transcrever 8 vídeos de 10 a 25 min levava a rodada inteira. O caminho já existia e estava ligado
    # só no GTA. A proteção é a mesma: legenda com menos de 60 palavras ou que cubra menos de 50% do
    # vídeo é RECUSADA e o whisper entra — legenda picada não serve para cortar trecho no fim da frase.
    "legenda_antes_de_transcrever": True,
    "legenda_langs": "pt.*,pt",
    # "qualquer coisa que for notícia": busca do YouTube por data — qualquer canal, se o título fala do Galo (prioridade 4)
    "busca": ["notícias do galo hoje", "atlético mineiro notícias", "galo atlético mg", "corte atlético mineiro programa"],
    "busca_qualquer_canal": True,
    "outras_fontes": ["itatiaia", "globo esporte", "ge globo", "sportv", "band", "cnn", "os donos da bola", "tnt sports",
                      "super fc", "o tempo", "hoje em dia", "rádio 98", "estado de minas", "premiere", "cazé"],
    # 🔴 é a marca de TRANSMISSÃO AO VIVO (e o que travou o canal em 01/nov: "🔴 Grêmio x Atlético-MG" entrou
    # porque não tinha as palavras "ao vivo" nem "live" no título). `fora_sinais` é conferido como SINAL, sem
    # limite de palavra — 🔴 não é palavra e o `\b` do `fora` nunca casaria com ele.
    # "melhores momentos"/"gols" = TRANSMISSÃO DE JOGO = bloqueio no mundo inteiro (conferido na
    # reivindicação de 05/nov, imagem da TNT Sports). Esses nem são baixados.
    "fora": ["react", "reage", "reagindo", "reacao", "reacoes", "ao vivo", "live", "jogo completo", "gameplay",
             "fifa", "efootball", "melhores momentos", "todos os gols", "gols do", "gols da", "highlights",
             "compacto do jogo", "assista aos gols"],
    "recusa_lance": True,   # trecho com GRAMADO na tela não entra (tem_campo)
    "fora_sinais": ["🔴", "🟢 ao vivo", "assista agora", "pre-jogo", "pré-jogo", "pos-jogo", "pós-jogo"],
    "max_horas": 48,  # notícias de hoje e de ontem que ainda não postamos
    "max_videos_rodada": 8,  # quantos vídeos novos baixa/transcreve por rodada (os melhores primeiro; o resto na próxima)
    "trecho_min_s": 15,
    "trecho_max_s": 180,  # a notícia INTEIRA (do começo ao fim do assunto); só corta se passar de 3 min
    "max_trechos_video": 3,
    "buscar_original": True,  # trecho de canal que JUNTA notícias → baixa do vídeo original (crédito para quem fez)
    "original_max_candidatos": 6,
    "parecido_max": 0.35,  # notícia repetida (o mesmo assunto em 2 canais / já postada) fica de fora
    # Assunto JÁ POSTADO HOJE: só volta (como notícia secundária, nunca no título/thumb) quando VOCÊ liga a mesclagem
    # no painel E a notícia traz FATO NOVO de verdade — nota alta e palavras que não estavam no que já foi postado.
    "mesclar_assunto": False,
    "max_repetidas": 1,
    "mesclar_nota_min": 7.0,      # abaixo disso não é fato relevante, é a mesma notícia de novo
    "mesclar_novidade_min": 0.35,  # quanto do assunto precisa ser palavra NOVA
    # OS PRINCIPAIS CAMPEONATOS: em dia de Libertadores, Champions etc., o vídeo também dá a volta pelo mundo.
    # Entram DEPOIS das notícias do Galo e no máximo `max_trechos_campeonato` por vídeo.
    "campeonatos_ligado": True,
    "max_trechos_campeonato": 2,
    "max_videos_campeonato": 3,   # quantos vídeos de campeonato a rodada baixa (pesa transcrever)
    "campeonatos": [
        {"nome": "Libertadores", "termos": ["libertadores"],
         "busca": ["libertadores resultados de hoje", "libertadores classificados jogos"]},
        {"nome": "Champions League", "termos": ["champions", "liga dos campeoes", "liga dos campeões", "uefa"],
         "busca": ["champions league resultados de hoje", "champions league rodada gols"]},
        {"nome": "Brasileirão", "termos": ["brasileirao", "brasileirão", "serie a", "série a"],
         "busca": ["brasileirão rodada resultados hoje", "brasileirão tabela classificação hoje"]},
        {"nome": "Copa do Brasil", "termos": ["copa do brasil"], "busca": ["copa do brasil resultados de hoje"]},
        {"nome": "Sul-Americana", "termos": ["sul-americana", "sul americana", "sudamericana"],
         "busca": ["sul-americana resultados de hoje"]},
        {"nome": "Mundial de Clubes", "termos": ["mundial de clubes", "intercontinental"],
         "busca": ["mundial de clubes resultados hoje"]},
    ],
    "por_fonte": 15,
    "max_min_fonte": 120,
    "duracao_alvo_min": 16,  # MEDIDO nos concorrentes: 16-25 min rende 1,17x; 25+ cai para 0,72x (imprensa + falas)
    "min_trechos": 4,
    "max_videos_dia": 2,
    "horas_entre_posts": 4,
    "privacidade": "public",
    "voz_ref": "voz/minha_voz.wav",
    # VOZ: 1) VoiceStudio aberto no seu PC (open source, de graça) · 2) Fish Audio (FISH_API_KEY) · 3) Chatterbox
    "voicestudio": "",            # endereço; vazio = http://127.0.0.1:3900 (o padrão do VoiceStudio)
    "voz_voicestudio": "",        # nome ou id do perfil de voz clonada lá dentro; vazio = a voz padrão dele
    "velocidade_voz": 1.25,
    "instrucao_voz": "",          # como a voz deve falar; vazio = pt-BR claro, sem sotaque de Portugal
    "sem_voicestudio": False,
    "exagero_voz": 0.6,
    "cor": "#FFD400",
    "auto_postar": False,  # False = monta e espera você aprovar no painel (aba Canais); True = posta sozinho
    "shorts": 2,  # Shorts (9:16) por vídeo: as melhores notícias, cada uma com a sua fala antes
    "horas_entre_shorts": 3,
    "short_max_s": 55,
    "drive": "",  # pasta do Drive com mascara\ e voz\; vazio = <Meu Drive>\DETTO\canal_noticias
}


def log(m):
    # A HORA em cada linha (02/nov): o registro parou às 10:15 e só às 14:03 ele viu que a rodada estava
    # pendurada há 4 h. Sem a hora escrita, "parado" e "demorando" são a mesma coisa no registro.
    print(f"{dt.datetime.now():%H:%M} {m}", flush=True)
    _etapa(m)


# TEMPO POR ETAPA (06/nov): a rodada do GTA levou 78+ min e ninguém sabia ONDE. Cada linha do registro que abre
# uma etapa conhecida fecha a anterior; no fim sai "TEMPOS: baixando 31 min · montando 12 min ..." (uma linha).
_ETAPAS = (("coleta", r"^\s*coleta|na lista, abri|descartados"), ("baixando", r"^\s*baixando"),
           ("transcrevendo", r"^\s*transcrevendo|legenda do youtube"), ("trechos", r"trecho|acha_trechos"),
           ("roteiro", r"roteiro|título|titulo"), ("voz", r"\bvoz\b|falando|fala \d"),
           ("montando", r"monta|render|peça|peca|emenda|vinheta|nivel"), ("thumb", r"thumb"),
           ("enviando", r"enviando|publica|subindo|upload"))
_T = {"nome": "inicio", "t0": None, "soma": {}}


def _etapa(m):
    import re as _re
    import time as _t

    agora = _t.monotonic()
    if _T["t0"] is None:
        _T["t0"] = agora
        import atexit

        atexit.register(lambda: print(f"{dt.datetime.now():%H:%M} TEMPOS: " + _resumo_tempos(), flush=True))
    baixa = str(m).lower()
    for nome, rx in _ETAPAS:
        if _re.search(rx, baixa):
            if nome != _T["nome"]:
                _T["soma"][_T["nome"]] = _T["soma"].get(_T["nome"], 0) + (agora - _T["t0"])
                _T["nome"], _T["t0"] = nome, agora
            break


def _resumo_tempos():
    import time as _t

    soma = dict(_T["soma"])
    if _T["t0"] is not None:
        soma[_T["nome"]] = soma.get(_T["nome"], 0) + (_t.monotonic() - _T["t0"])
    return " · ".join(f"{k} {v / 60:.0f} min" for k, v in sorted(soma.items(), key=lambda kv: -kv[1]) if v >= 30) or "(tudo < 30 s)"


def relogio_da_rodada(minutos):
    """A RODADA TEM HORA PARA ACABAR (02/nov).

    Uma montagem ficou presa das 09:22 às 14:03 segurando a trava: nenhuma rodada seguinte rodou e ele passou
    o dia sem postar. É a mesma lição do download de transmissão ao vivo (01/nov): nada neste sistema pode
    rodar sem prazo. Passado o prazo o processo morre — e a trava, que é do sistema operacional, se solta
    sozinha com ele."""
    import threading

    def bate():
        log(f"NÃO TERMINEI: a rodada passou de {minutos:.0f} min e foi encerrada para não travar o canal. "
            "A última linha acima diz em que peça ela estava.")
        try:
            sys.stdout.flush()
        except Exception:   # noqa: BLE001
            pass
        os._exit(3)

    t = threading.Timer(max(10.0, float(minutos)) * 60, bate)
    t.daemon = True
    t.start()
    return t


def ff(args, limite=900, nome=""):
    """o ffmpeg com HORA MARCADA: uma peça travada não segura mais a rodada inteira"""
    try:
        return subprocess.run(args, timeout=limite)
    except subprocess.TimeoutExpired:
        log(f"   ERRO: {nome or 'o ffmpeg'} passou de {limite}s e foi encerrado (peça pesada demais?)")
        return subprocess.CompletedProcess(args, 1)
    except OSError as e:   # noqa: BLE001
        log(f"   ERRO: não consegui rodar o ffmpeg ({str(e)[:90]})")
        return subprocess.CompletedProcess(args, 1)


def apelidos(cfg):
    """as palavras que dizem que o vídeo é do ASSUNTO do canal (e as que dizem que NÃO é).

    No canal do Galo elas vêm do times.json. Num canal que não é de futebol (GTA 6) não há time nenhum ali:
    a busca voltava vazia, `fala_do_time` reprovava TODO vídeo e a rodada terminava "0 vídeo(s) de hoje"
    mesmo com os canais respondendo. Por isso o preset pode trazer as suas próprias em `"termos"`/`"termos_nao"`."""
    if cfg.get("termos"):
        return [norm(a) for a in cfg["termos"] if a], [norm(a) for a in cfg.get("termos_nao", []) if a], {}
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


def videos_ytdlp(canal, quantos=12, pular=(), max_abrir=3):
    """A HORA de cada vídeo pelo yt-dlp, quando o feed do YouTube não responde.
    Em 29/10 o `feeds/videos.xml` passou a devolver 404/500 até para ID CERTO de canal — e, sem a hora, a rodada
    descartava TODOS os vídeos e terminava "0 vídeo(s) de hoje". Isto custa ~2 s por canal e traz hora, duração,
    tipo (live/short) e descrição."""
    if not canal:
        return []
    pular = set(pular or ())
    # CACHE DE 25 MIN (05/nov): com o feed morto (404 em todos), cada rodada abria os 12 últimos vídeos de CADA
    # canal um por um (`-J` sem flat = uma extração completa por vídeo) — ~100 chamadas ao YouTube por rodada,
    # e rodada repetida a cada clique. Quem pede a lista de novo em menos de 25 min recebe a de antes.
    import tempfile as _tf
    _arq = Path(_tf.gettempdir()) / ("detto_lista_" + re.sub(r"\W+", "_", canal) + ".json")
    try:
        if _arq.exists() and time.time() - _arq.stat().st_mtime < 25 * 60:
            return [{**e, "quando": dt.datetime.fromisoformat(e["quando"])} for e in json.loads(_arq.read_text("utf-8"))]
    except (OSError, ValueError, KeyError):
        pass
    # DUAS ETAPAS (05/nov) — era AQUI que a rodada do GTA levava "uma eternidade": `-J` SEM --flat-playlist
    # ABRE os 8 vídeos INTEIROS de cada canal, um a um (7 canais = 56 extrações completas, cada uma com o
    # desafio "n" do YouTube). A lista em si é de graça; o caro é abrir vídeo. Então:
    #   1) --flat-playlist: a lista (id, título, duração) numa requisição leve;
    #   2) só os vídeos que eu AINDA NÃO VI ganham a extração completa (a hora), e todos numa chamada só.
    # Num dia comum são 0 ou 1 vídeos novos por canal, em vez de 8.
    t0 = time.time()
    r = ytdlp(["--flat-playlist", "--dump-json", "--playlist-end", str(min(quantos, 8)),
               f"https://www.youtube.com/{canal}/videos"])
    lista = []
    for linha in (r.stdout or "").splitlines():
        try:
            e = json.loads(linha)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get("id"):
            lista.append(e)
    if not lista:
        return []

    def _monta(e, ts, nome_canal=""):
        return {"id": e["id"], "titulo": e.get("title") or "",
                "quando": dt.datetime.fromtimestamp(int(ts)),
                "descricao": e.get("description") or "",
                "canal_nome": e.get("channel") or e.get("uploader") or nome_canal,
                "_dur": e.get("duration") or 0,
                "_tipo": "live" if (e.get("live_status") or "") in ("is_live", "was_live", "post_live") else "video"}

    out, abrir = [], []
    for e in lista:
        ts = e.get("timestamp") or e.get("release_timestamp")
        if ts:
            out.append(_monta(e, ts))        # a lista já trouxe a hora: não preciso abrir
        elif e["id"] not in set(pular):
            abrir.append(e)
    abrir = abrir[: int(max_abrir)]
    if abrir:
        r2 = ytdlp(["--dump-json", "--no-playlist", "--skip-download",
                    *[f"https://www.youtube.com/watch?v={e['id']}" for e in abrir]])
        for linha in (r2.stdout or "").splitlines():
            try:
                e = json.loads(linha)
            except ValueError:
                continue
            ts = isinstance(e, dict) and (e.get("timestamp") or e.get("release_timestamp"))
            if ts:
                out.append(_monta(e, ts))
    log(f"   {canal}: {len(lista)} na lista, abri {len(abrir)} ({time.time() - t0:.0f}s)")
    if out:
        try:
            _arq.write_text(json.dumps([{**e, "quando": e["quando"].isoformat()} for e in out], ensure_ascii=False), "utf-8")
        except OSError:
            pass
    return out


_IDS = {}


def acha_channel_id(canal):
    """o ID (UC...) do canal, com UMA requisição leve. É a chave para usar o FEED em vez do yt-dlp.

    POR QUE ISSO EXISTE (05/nov) — era a diferença entre o canal do Galo funcionar e o do GTA 6 morrer:
    as fontes do Galo têm `"id"` no config, então a hora vem do FEED (uma requisição HTTP simples, sem
    yt-dlp nenhum). As do GTA não tinham ID, então TODA rodada fazia uma extração pesada do yt-dlp em 7
    canais — e, com o painel repetindo a rodada a cada 10 min por causa da falha, isso vira centenas de
    chamadas por hora. O YouTube então passa a responder "Sign in to confirm you're not a bot", e aí NEM
    os canais respondem NEM o download funciona. O canal estava envenenando o próprio IP.

    Com o ID em mãos o caminho fica igual ao do Galo: feed, barato, sem yt-dlp."""
    if not canal:
        return ""
    if canal in _IDS:
        return _IDS[canal]
    r = ytdlp(["--flat-playlist", "-J", "--playlist-end", "1", f"https://www.youtube.com/{canal}"], timeout=120)
    cid = ""
    try:
        d = json.loads(r.stdout or "{}")
        if isinstance(d, dict):
            cid = d.get("channel_id") or ((d.get("entries") or [{}]) or [{}])[0].get("channel_id") or ""
    except (ValueError, AttributeError, IndexError):
        cid = ""
    _IDS[canal] = cid
    return cid


def ultimos(cid, canal="", quantos=12, desde=None, pular=()):
    """os últimos vídeos com a hora: o feed primeiro (leve) e, se ele falhar, o yt-dlp.

    FEED VELHO É PIOR QUE FEED MORTO (05/nov): os 7 canais do GTA diziam "nada novo" na mesma rodada em que a
    busca por data achava 4 vídeos de hoje — inclusive do @SaninPlay, que está na lista. O motivo: o feed do
    YouTube RESPONDE, mas com uma lista atrasada. Como o código só caía no yt-dlp quando o feed vinha VAZIO, a
    lista velha era aceita e o vídeo de hoje nunca aparecia. Agora, se o feed não traz nada depois de `desde`,
    eu confirmo no yt-dlp (que é autoritativo) antes de desistir — custa uma chamada exatamente no caso em que
    eu ia desistir de graça."""
    v = rss(cid) if cid else []
    # SEM ID no config, descubro o ID (1 requisição leve) e uso o FEED — em vez de uma extração pesada do
    # yt-dlp a cada rodada, que é o que marcava o IP e derrubava os downloads do canal de GTA (05/nov).
    if not v and not cid and canal:
        achado = acha_channel_id(canal)
        if achado:
            v = rss(achado)
            if v:
                log(f"   {canal}: achei o id do canal ({achado}) e peguei a hora pelo feed")
    if v and (desde is None or any(x["quando"] >= desde for x in v)):
        return v
    nova = videos_ytdlp(canal, quantos, pular=pular)
    if nova and v:
        tinha = {x["id"] for x in v}
        extras = [x for x in nova if x["id"] not in tinha and (desde is None or x["quando"] >= desde)]
        if extras:
            log(f"   {canal or cid}: o feed estava ATRASADO; o yt-dlp achou {len(extras)} vídeo(s) que faltavam")
            return nova
        return v
    if nova:
        log(f"   {canal or cid}: o feed não respondeu; peguei a hora pelo yt-dlp ({len(nova)} vídeos)")
    return nova or v


def dur_mp4(f):
    """duração de um mp4 em segundos (0 se não der)"""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


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

    _motivos = {}

    def _nao(f, motivo):
        m = _motivos.setdefault(f.get("nome") or f.get("canal") or "?", {})
        m[motivo] = m.get(motivo, 0) + 1

    def considera(v, f, dur_s, tipo="video"):
        if v["id"] in hist["vistos"] or v["id"] in vistos_agora or v["quando"] < limite:
            return
        vistos_agora.add(v["id"])
        # Short não é notícia; live só depois de acabar e dentro do tamanho (o programa do dia da Alterosa é live
        # gravada — entra; jogo/treino ao vivo de horas fica fora pela duração)
        if tipo == "short" or (tipo == "live" and not dur_s):
            return _nao(f, "short/live")
        if f.get("max_videos") and sum(1 for x in novos if x["fonte"] == f.get("nome")) >= f["max_videos"]:
            return _nao(f, "teto do canal")
        durm = (dur_s or 0) / 60
        if dur_s and (durm > f.get("max_min", cfg["max_min_fonte"]) or durm < 0.5):
            return _nao(f, f"duração {durm:.0f} min")
        if f.get("filtro", "titulo") == "gta":
            # canal que fala de GTA o tempo todo (GameplayRJ, SaninPlay): "NOVAS IMAGENS DE GTA" não traz o "6"
            # no título e o filtro de termos recusava (05/nov). Basta a palavra GTA e não ser GTA 5/RP/Online.
            # E a LISTA RÁPIDA não traz descrição (05/nov): num canal que só fala de GTA, "ROCKSTAR MOSTROU
            # LUCIA E JASON" é o vídeo do dia e não tem a palavra GTA em lugar nenhum — por isso os SINAIS.
            _t = f" {norm(v['titulo'])} "
            _td = _t + f" {norm(v.get('descricao', ''))} "
            _sinais = r"\bgta\b|grand theft auto|rockstar|vice city|leonida|lucia caminos|jason duval"
            if not re.search(_sinais, _td) or any(f" {x} " in _t for x in nao):
                log(f"   {f.get('nome')}: fora do assunto: {(v['titulo'] or '')[:70]}")
                return
        elif f.get("filtro", "titulo") == "titulo" and not fala_do_time(f"{v['titulo']} {v.get('descricao', '')}", aps, nao):
            if cfg.get("time") == "GTA":
                log(f"   {f.get('nome')}: fora do assunto: {(v['titulo'] or '')[:70]}")
            return
        if any(re.search(rf"\b{re.escape(norm(x))}\b", norm(v["titulo"])) for x in cfg.get("fora", [])):
            return _nao(f, "título de react/ao vivo")  # não é notícia de imprensa
        if any(s and s.lower() in (v["titulo"] or "").lower() for s in cfg.get("fora_sinais", [])):
            return _nao(f, "transmissão ao vivo")  # o download de um live não terminaria nunca
        if (v.get("_tipo") or "") == "live":
            return _nao(f, "live")
        novos.append({"id": v["id"], "url": f"https://www.youtube.com/watch?v={v['id']}", "titulo": v["titulo"],
                      "fonte": f.get("nome") or v.get("canal_nome") or f.get("canal", ""), "canal": f.get("canal", ""),
                      "dur": dur_s or 0, "publicado": v["quando"].isoformat(timespec="minutes"), "max_trechos": f.get("max_trechos"),
                      "prioridade": f.get("prioridade", 1), "juntador": bool(f.get("juntador"))})

    # OS CANAIS SÃO CONSULTADOS AO MESMO TEMPO (05/nov): eram 7 consultas EM FILA, cada uma esperando a
    # anterior terminar — e é esperar a rede, não trabalhar, então quatro juntas não pesam no PC. A rodada do
    # GTA passou de "uma eternidade" para o tempo do canal mais lento.
    import concurrent.futures as _cf
    _ja_visto = set(hist.get("vistos") or ())
    _listas = {}
    with _cf.ThreadPoolExecutor(max_workers=4) as _ex:
        _pend = {_ex.submit(ultimos, f.get("id") or ids.get(f["canal"]), f.get("canal", ""), 12, limite,
                            _ja_visto): i for i, f in enumerate(cfg["fontes"])}
        for _fut in _cf.as_completed(_pend):
            try:
                _listas[_pend[_fut]] = _fut.result()
            except Exception as _e:             # um canal fora do ar não derruba a rodada inteira
                log(f"   fonte {cfg['fontes'][_pend[_fut]].get('nome')}: {_e}")
                _listas[_pend[_fut]] = []
    for _i, f in enumerate(cfg["fontes"]):
        todos = _listas.get(_i) or []
        lista = [v for v in todos if v["quando"] >= limite]
        _antes = len(lista)
        lista = [v for v in lista if v["id"] not in hist["vistos"]]     # o que já virou trecho não gasta chamada nenhuma
        if _antes and not lista:
            log(f"   {f.get('nome') or f.get('canal')}: {_antes} vídeo(s) na janela, todos JÁ VISTOS em rodadas anteriores")
            continue
        if not lista:
            # DUAS coisas MUITO diferentes diziam a mesma frase (05/nov): um canal que não respondeu (@ errado,
            # 404, bloqueio) e um canal que de fato não postou nada. Agora o registro diz qual é — foi assim que
            # apareceu que o @Voxel estava escrito errado e que o feed vinha atrasado.
            nome = f.get("nome") or f.get("canal")
            if not todos:
                log(f"   {nome}: o canal NÃO RESPONDEU (confira o @ '{f.get('canal')}' — 404, bloqueio ou nome mudado)")
            else:
                novo = max(v["quando"] for v in todos)
                log(f"   {nome}: nada novo (o último é de {novo:%d/%m %H:%M}, fora da janela de {cfg['max_horas']}h)")
            continue
        # quando a lista vem do yt-dlp ela JÁ traz duração e tipo; aí não preciso de uma varredura extra
        durs = {v["id"]: (v["_dur"], v["_tipo"]) for v in lista if v.get("_dur")}
        if not durs and f.get("canal"):
            # o `duracoes` abre TRÊS abas do canal no yt-dlp (videos, shorts, streams). Só cai aqui quando a
            # lista veio do FEED, que não traz duração — e aí é bom aparecer no registro, porque é caro.
            log(f"   {f.get('nome') or f.get('canal')}: a lista não trouxe duração; vou medir (3 chamadas)")
            durs = duracoes(f["canal"])
        for v in lista:
            d_, t_ = durs.get(v["id"], (0, "video"))
            considera(v, f, d_, t_)
    # "entre outras": busca por data; só canais de imprensa da lista, e a hora vem do feed do próprio canal
    ok_nomes = [norm(x) for x in cfg.get("outras_fontes", [])]
    ja = {f.get("id") or ids.get(f["canal"]) for f in cfg["fontes"]}
    feeds = {}
    _fim_busca = time.time() + 60 * float(cfg.get("max_min_busca", 4))
    for q in cfg.get("busca", []):
        if time.time() > _fim_busca:
            log(f"   busca: passei de {cfg.get('max_min_busca', 4)} min, sigo com o que já achei")
            break
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
                if len(feeds) >= int(cfg.get("max_canais_busca", 5)):
                    continue   # cada canal novo = listagem pesada no yt-dlp (o feed RSS morreu): limita por rodada
                feeds[cid] = {x["id"]: x for x in ultimos(cid, v.get("uploader_id") or "")}
            if v.get("id") in feeds[cid]:
                considera(feeds[cid][v["id"]], {"nome": nome, "canal": v.get("uploader_id") or "", "filtro": "titulo",
                                                "prioridade": 1 if imprensa else 4, "juntador": not imprensa}, v.get("duration"))
    # imprensa (1), TV Galo (2), canais de notícias do Galo (3), resto da busca (4); dentro de cada, a mais nova primeiro.
    # Por rodada só os `max_videos_rodada` primeiros (baixar + transcrever pesa); os outros ficam para a próxima.
    novos.sort(key=lambda x: (x["prioridade"], "".join(chr(255 - ord(c)) for c in x["publicado"])))
    novos = novos[: int(cfg.get("max_videos_rodada", 8))]
    # NÃO MARCO COMO "VISTO" AQUI (06/nov). Era o motivo de "0 vídeo(s) de hoje" com vídeo de GTA saindo em
    # todo canal: a coleta marcava os vídeos como vistos ANTES de baixar. Download barrado pelo YouTube (o
    # cookie da noite) = o vídeo queimado para sempre, e toda rodada seguinte via a lista inteira "já vista".
    # Agora quem marca é o laço de download, só depois de o vídeo ter sido de fato processado.
    if _motivos:
        log("   descartados: " + "; ".join(f"{n}: " + ", ".join(f"{k} {c}" for k, c in m.items()) for n, m in _motivos.items()))
    log(f"coleta: {len(novos)} vídeo(s) de hoje sobre o {cfg['time']}: " + "; ".join(f"{x['fonte']} {x['publicado'][11:]}" for x in novos[:8]))
    return novos


def coleta_campeonatos(cfg, hist, ja_vistos):
    """A VOLTA PELO MUNDO: em dia de Libertadores, Champions, Copa do Brasil (ou rodada do Brasileirão), traz também
    um ou dois vídeos da imprensa sobre o campeonato. Não force nada: se não teve jogo, a busca por data não devolve
    vídeo novo e o bloco simplesmente não existe naquele dia."""
    if not cfg.get("campeonatos_ligado", True):
        return []
    import urllib.parse

    limite = dt.datetime.now() - dt.timedelta(hours=min(30, cfg.get("max_horas", 30)))
    ok_nomes = [norm(x) for x in cfg.get("outras_fontes", [])]
    fora = [norm(x) for x in cfg.get("fora", [])]
    novos, feeds = [], {}
    for camp in cfg.get("campeonatos", []):
        termos = [norm(t) for t in camp.get("termos", [])]
        achou = 0
        for q in camp.get("busca", []):
            if achou:
                break
            r = ytdlp(["--flat-playlist", "--dump-json", "--playlist-end", "12", "--extractor-args", "youtube:lang=pt",
                       "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q) + "&sp=CAI%253D"])
            for linha in (r.stdout or "").splitlines():
                try:
                    v = json.loads(linha)
                except ValueError:
                    continue
                cid, nome = v.get("channel_id"), v.get("channel") or ""
                if not cid or v.get("id") in hist["vistos"] or v.get("id") in ja_vistos:
                    continue
                imprensa = any(o in norm(nome) for o in ok_nomes)
                if not (imprensa or cfg.get("busca_qualquer_canal")):
                    continue
                tit = norm(v.get("title", ""))
                if not any(t in tit for t in termos) or any(re.search(rf"\b{re.escape(x)}\b", tit) for x in fora):
                    continue
                dur_s = v.get("duration") or 0
                if dur_s and not (0.5 <= dur_s / 60 <= cfg.get("max_min_fonte", 120)):
                    continue
                if cid not in feeds:
                    feeds[cid] = {x["id"]: x for x in ultimos(cid, v.get("uploader_id") or v.get("channel") or "")}
                f = feeds[cid].get(v["id"])
                if not f or f["quando"] < limite:
                    continue  # sem a hora do feed não dá para saber se é de hoje
                ja_vistos.add(v["id"])
                novos.append({"id": v["id"], "url": f"https://www.youtube.com/watch?v={v['id']}", "titulo": f["titulo"],
                              "fonte": nome, "canal": v.get("uploader_id") or "", "dur": dur_s,
                              "publicado": f["quando"].isoformat(timespec="minutes"), "max_trechos": 1,
                              "prioridade": 5, "juntador": not imprensa, "campeonato": camp["nome"],
                              "assunto": f"{camp['nome']}: os jogos, os gols e como ficou a situação dos times"})
                achou += 1
                break
    novos.sort(key=lambda x: "".join(chr(255 - ord(c)) for c in x["publicado"]))
    novos = novos[: int(cfg.get("max_videos_campeonato", 3))]
    if novos:
        log("campeonatos: " + "; ".join(f"{x['campeonato']} ({x['fonte']})" for x in novos))
    return novos


# ------------------------------------------------------------------ 2. trechos sobre o time
def transcreve(video, idioma="pt"):
    """as palavras com tempo. idioma=None = o whisper DESCOBRE a língua (canal gringo no canal de GTA).
    Devolve (palavras, idioma_achado)."""
    cache = Path(video).with_suffix(".words.json")
    if cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            return d.get("palavras") or [], d.get("idioma") or "pt"
        if idioma is not None:
            return d, "pt"   # cache antigo (lista pura): o canal só tem fonte em português, serve
        # canal que aceita fonte gringa: o cache antigo foi feito com "pt" na marra e pode ser texto sem
        # sentido de uma fala em inglês — refaz com o idioma descoberto
    from transcrever import dlls_nvidia, transcrever

    dlls_nvidia()
    try:
        w, lin = transcrever(str(video), "small", "cuda", idioma, com_idioma=True)
    except Exception:
        w, lin = transcrever(str(video), "small", "cpu", idioma, com_idioma=True)
    print()
    cache.write_text(json.dumps({"palavras": w, "idioma": lin}, ensure_ascii=False), encoding="utf-8")
    return w, lin


def palavras_do_cache(arquivo):
    """as palavras do .words.json, no formato novo ({"palavras": [...], "idioma": "en"}) ou no antigo (lista).
    Ler o dicionário como se fosse lista dava `TypeError: string indices must be integers`."""
    d = json.loads(Path(arquivo).with_suffix(".words.json").read_text(encoding="utf-8"))
    return (d.get("palavras") or []) if isinstance(d, dict) else d


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


# MEDIDO em 150 vídeos dos 6 canais concorrentes do Galo (30/10/2026): o ÂNGULO do trecho muda o resultado do
# vídeo inteiro, porque é dele que sai o título e a thumb. Por isso a nota não é só "é novidade?".
REGRA_NOTA = """A NOTA decide o que vira título e thumb do vídeo, então pese o ÂNGULO (isto foi medido nos canais
concorrentes, não é opinião): SOME 2 pontos se a fala é de um JORNALISTA CONHECIDO elogiando, se rendendo ou mudando
de opinião sobre o Galo (Renata Fan, Denílson, Neto, Mauro Cezar, Benjamin Back, Casagrande, PVC, Vampeta) — é o
trecho que mais rende. SOME 1,5 se é REFORÇO/CONTRATAÇÃO/MERCADO com nome de jogador. SOME 1 se dá para citar o
PROGRAMA de onde saiu (Globo Esporte MG, Jogo Aberto, ESPN, Itatiaia, Alterosa). TIRE 1 se o assunto é só
ARBITRAGEM/ROUBO/VAR (rende 0,89x nesses canais). Nota máxima 10."""


def acha_trechos(words, info, cfg, assunto=None):
    """trechos que falam do time (ou do ASSUNTO de uma pauta sua): Gemini (começo/fim certos, manchete, clima);
    sem chave: janelas pela palavra (pauta sem chave: o começo do vídeo)"""
    _, _, t = apelidos(cfg)
    # O ASSUNTO DO CANAL manda. Antes o "(o Galo)" era FIXO: o canal de GTA pedia à IA "trechos em que falam do
    # GTA (o Galo)" e ela, com razão, não achava nada — a rodada terminava "0 trecho(s)" em TODO vídeo.
    if assunto:
        alvo = f"em que falam de: {assunto}" if assunto != "*" else "com a notícia/assunto principal deste vídeo"
    elif cfg.get("assunto"):
        alvo = f"em que falam de {cfg['assunto']}: notícia, novidade, análise, opinião, entrevista"
    else:
        alvo = f"em que falam do {t.get('nome', cfg['time'])} (o Galo): análise, elogio, crítica, polêmica, notícia, entrevista"
    regra_canal = ("Este canal JUNTA notícias de vários programas: marque SÓ as partes em que fala a IMPRENSA (apresentador/jornalista "
                   "de TV, rádio, entrevista, coletiva). IGNORE a narração do dono do canal ('fala galera', 'se inscreve', leitura de "
                   "manchete, opinião do youtuber) e anúncios." if info.get("juntador") else
                   "Ignore vinheta, intervalo, propaganda e conversa sem notícia.")
    regra_nota = cfg.get("regra_nota") or REGRA_NOTA
    g = gemini_json([{"text": f"""Transcrição (segundos entre colchetes) de "{info['titulo']}" ({info['fonte']}).
Marque os trechos {alvo}.
Cada trecho é UMA notícia INTEIRA: do começo ao fim do assunto (a informação + a análise/opinião sobre ela), começo e fim
NATURAIS (frase completa, nunca cortar no meio), entre {cfg.get("trecho_min_s", 15)} e {cfg.get("trecho_max_s", 180)} segundos — o tamanho que a notícia precisar.
{regra_canal}
{"Ignore o resto." if assunto else "Ignore trechos sobre outros times."}
A transcrição pode estar em OUTRA LÍNGUA (canal gringo). Nesse caso entenda normalmente, mas escreva a "manchete" e
o "resumo" SEMPRE EM PORTUGUÊS DO BRASIL.
{regra_nota}
Responda SÓ JSON:
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


def novidade(tx, postados):
    """0..1: quanto do assunto é FATO NOVO — palavras que não apareceram em nada que já foi postado hoje.
    É o que separa "a mesma notícia de novo" de "a notícia andou"."""
    A = _palavras_chave(tx)
    if not A:
        return 0.0
    velhas = set()
    for p in postados:
        velhas |= _palavras_chave(p)
    return len(A - velhas) / len(A)


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


# ------------------------------------------------------------------ 2b. o vídeo ORIGINAL (canal que só junta → a fonte)
def _tokens(txt):
    return re.findall(r"\w+", norm(txt))


def _janela(alvo, ws):
    """onde o texto `alvo` (lista de palavras) foi dito em `ws` ([{w,s,e}]): (ini, fim, nota 0..1) ou None"""
    import difflib
    from collections import Counter
    toks = [re.sub(r"\W+", "", norm(w["w"])) for w in ws]
    n = len(alvo)
    if n < 12 or len(toks) < n // 2:
        return None
    A = Counter(alvo)
    passo = max(1, n // 10)
    melhor, nm = None, 0.0
    for i in range(0, max(1, len(toks) - n // 2), passo):
        B = Counter(toks[i: i + n])
        nota = sum((A & B).values()) / n
        if nota > nm:
            melhor, nm = i, nota
    if melhor is None or nm < 0.45:
        return None

    def refina(pedaco, lo, hi, esperado, do_fim=False):
        # o pedaço mais parecido; empate (frase repetida) = o mais perto de onde devia estar
        k = len(pedaco)
        best, bn, br = None, -1.0, 0.0
        for j in range(max(0, lo), min(len(toks) - k, hi) + 1):
            r = difflib.SequenceMatcher(None, pedaco, toks[j: j + k], autojunk=False).ratio()
            sc = r - 0.004 * abs(j - esperado)
            if sc > bn:
                best, bn, br = j, sc, r
        if best is None or br < 0.5:
            return None
        return best + k - 1 if do_fim else best

    k = min(12, n // 3)
    i0 = refina(alvo[:k], melhor - n // 2, melhor + n // 2, melhor)
    i1 = refina(alvo[-k:], melhor + n // 2, melhor + n + n // 2, melhor + n - k, do_fim=True)
    i0 = melhor if i0 is None else i0
    i1 = min(len(ws) - 1, melhor + n - 1) if i1 is None or i1 <= i0 else i1
    return ws[i0]["s"], ws[i1]["e"], nm


def legenda_youtube(vid, pasta, langs="pt.*,pt"):
    """as palavras com tempo pela legenda do YouTube (automática serve) — sem baixar nem transcrever o vídeo.
    `langs` aceita outras línguas (o canal de GTA pega canal gringo: "pt.*,pt,en.*,en")."""
    pasta.mkdir(parents=True, exist_ok=True)
    cache = pasta / f"{vid}.leg2.json"
    if cache.exists():
        return le_json(cache, [])
    ytdlp(["--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", langs, "--sub-format", "json3",
           "-o", str(pasta / f"{vid}.%(ext)s"), f"https://www.youtube.com/watch?v={vid}"])
    ws, lin = [], ""
    def _prio(f):
        # a faixa ORIGINAL primeiro ("pt-orig"/"en-orig"); depois português; as TRADUZIDAS pelo YouTube por último.
        # Antes valia a ordem alfabética: "en" vinha antes de "pt" e um vídeo em PORTUGUÊS entrava pela tradução em
        # inglês — o canal achava que era gringo, traduzia e dublava.
        l = f.name.split(".")[-2].lower() if f.name.count(".") >= 2 else ""
        return (0 if "orig" in l else (1 if l.startswith("pt") else 2), f.name)

    for f in sorted(pasta.glob(f"{vid}*.json3"), key=_prio):
        lin = (f.name.split(".")[-2] if f.name.count(".") >= 2 else "")[:2].lower()
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for ev in d.get("events", []):
            t0 = ev.get("tStartMs", 0) / 1000
            fim_ev = t0 + ev.get("dDurationMs", 0) / 1000
            segs = [x for x in ev.get("segs") or [] if (x.get("utf8") or "").strip()]
            for k, sg in enumerate(segs):
                s0 = t0 + sg.get("tOffsetMs", 0) / 1000
                s1 = t0 + segs[k + 1].get("tOffsetMs", 0) / 1000 if k + 1 < len(segs) else fim_ev
                pal = sg["utf8"].split()
                passo = max(0.1, (s1 - s0) / len(pal))  # legenda por frase: espalha as palavras no tempo dela
                for q, w in enumerate(pal):
                    ws.append({"w": w, "s": round(s0 + q * passo, 2), "e": round(s0 + (q + 1) * passo, 2)})
        f.unlink(missing_ok=True)
        if ws:
            break
    grava_json(cache, ws)
    if ws and lin:
        grava_json(pasta / f"{vid}.leg2.idioma.json", {"idioma": lin})
    return ws


def palavras_rapidas(v, cfg, pasta, log=log):
    """ANTES de transcrever: tenta a LEGENDA do YouTube, que é instantânea.
    Transcrever 8 vídeos de 10-25 min no whisper levava a rodada inteira; a legenda automática já serve para
    achar os trechos e para traduzir. Devolve (palavras, idioma) ou (None, "") quando não dá para confiar."""
    if not cfg.get("legenda_antes_de_transcrever") or not v.get("id"):
        return None, ""
    try:
        ws = legenda_youtube(v["id"], pasta / "legendas", cfg.get("legenda_langs", "pt.*,pt,en.*,en"))
    except Exception as e:   # noqa: BLE001
        log(f"   legenda do YouTube: {str(e)[:90]}")
        return None, ""
    if not ws:
        return None, ""
    d = dur(v.get("arquivo") or "") or float(v.get("dur") or 0)
    cobre = (ws[-1]["e"] - ws[0]["s"]) / d if d else 1.0
    if len(ws) < 60 or cobre < 0.5:   # legenda picada/parcial não serve para cortar o trecho
        log(f"   legenda do YouTube só cobre {cobre * 100:.0f}% do vídeo: vou transcrever")
        return None, ""
    idi = (le_json(pasta / "legendas" / f"{v['id']}.leg2.idioma.json", {}) or {}).get("idioma") or "pt"
    log(f"   peguei a legenda do YouTube ({len(ws)} palavras, {idi.upper()}) — sem transcrever, muito mais rápido")
    return ws, idi


def candidatos_originais(x, v, cfg, descricao=""):
    """vídeos que podem ser o ORIGINAL do trecho: links na descrição do canal que juntou + busca pelo programa e
    pelas palavras do assunto (por data). Nunca o próprio canal que juntou nem outro "juntador"."""
    import urllib.parse
    juntadores = {norm(f.get("nome", "")) for f in cfg["fontes"] if f.get("juntador")} | {norm(v.get("fonte", ""))}
    out, vistos = [], {v.get("id")}
    for vid in re.findall(r"(?:youtu\.be/|watch\?v=|/live/|/shorts/)([\w-]{11})", descricao or ""):
        if vid not in vistos:
            vistos.add(vid)
            out.append({"id": vid, "canal_nome": "", "titulo": "", "dur": 0, "da_descricao": True})
    chave = sorted(_palavras_chave(x.get("texto", "")), key=lambda w: -len(w))[:5]
    prog = (x.get("programa") or "").strip()
    buscas = ([f"{prog} atlético"] if prog else []) + ([" ".join(chave[:4]) + " atlético"] if chave else [])
    for q in buscas:
        r = ytdlp(["--flat-playlist", "--dump-json", "--playlist-end", "10", "--extractor-args", "youtube:lang=pt",
                   "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q) + "&sp=CAI%253D"])
        for linha in (r.stdout or "").splitlines():
            try:
                c = json.loads(linha)
            except ValueError:
                continue
            nome = c.get("channel") or c.get("uploader") or ""
            if not c.get("id") or c["id"] in vistos or norm(nome) in juntadores or "/shorts/" in str(c.get("url", "")):
                continue
            vistos.add(c["id"])
            out.append({"id": c["id"], "canal_nome": nome, "canal": c.get("uploader_id") or "", "titulo": c.get("title") or "",
                        "dur": c.get("duration") or 0})
    # o canal com o nome do programa (ou de imprensa da lista) primeiro
    ok_nomes = [norm(o) for o in cfg.get("outras_fontes", [])] + ([norm(prog)] if prog else [])

    def peso(c):
        n = norm(c["canal_nome"] + " " + c["titulo"])
        return (0 if c.get("da_descricao") else 1, 0 if any(o and o in n for o in ok_nomes) else 1)
    return sorted(out, key=peso)[: int(cfg.get("original_max_candidatos", 6))]


def busca_original(x, v, cfg, pasta, descricao=""):
    """o trecho veio de um canal que só JUNTA notícias (ex. Galotícias mostrando a Band Minas): acha o vídeo ORIGINAL,
    o mesmo pedaço nele (pela legenda do YouTube) e baixa SÓ esse pedaço na melhor qualidade. Devolve o trecho trocado
    (arquivo/ini/fim/fonte = o original; o crédito vai para quem fez) ou None (fica o do canal que juntou)."""
    alvo = _tokens(x.get("texto", ""))
    if len(alvo) < 25:
        return None
    for c in candidatos_originais(x, v, cfg, descricao):
        ws = legenda_youtube(c["id"], pasta / "legendas")
        j = _janela(alvo, ws) if ws else None
        if not j:
            continue
        a, b, nota = j
        info = {}
        r = ytdlp(["--skip-download", "--dump-json", f"https://www.youtube.com/watch?v={c['id']}"])
        try:
            info = json.loads((r.stdout or "").strip().splitlines()[-1])
        except (ValueError, IndexError):
            pass
        nome = info.get("channel") or info.get("uploader") or c["canal_nome"]
        if norm(nome) in {norm(f.get("nome", "")) for f in cfg["fontes"] if f.get("juntador")}:
            continue
        m0 = max(0.0, a - 4)
        saida = pasta / "fontes" / f"orig_{c['id']}_{int(a)}.mp4"
        saida.parent.mkdir(parents=True, exist_ok=True)
        if not saida.exists():
            rr = ytdlp(["-f", "bv*[height<=1080]+ba/b[height<=1080]", "-S", "res:1080,fps", "--merge-output-format", "mp4",
                        "--download-sections", f"*{m0:.1f}-{b + 4:.1f}", "--force-keyframes-at-cuts", "-o", str(saida),
                        f"https://www.youtube.com/watch?v={c['id']}"])
            if rr.returncode != 0 or not saida.exists():
                log(f"   original achado ({nome}) mas não baixou: {((rr.stderr or '').strip().splitlines() or [''])[-1][:120]}")
                continue
        # tempo exato dentro do pedaço baixado (transcreve o pedaço — curto)
        ini, fim = a - m0, b - m0
        try:
            wp, _ = transcreve(saida)
            jj = _janela(alvo, wp)
            if jj:
                ini, fim = max(0.0, jj[0] - 0.1), jj[1] + 0.15
        except Exception:
            pass
        d = dur(saida) or fim
        fim = min(fim, d - 0.1)
        if fim - ini < 8:
            continue
        log(f"   ORIGINAL: {nome} — {(info.get('title') or c['titulo'])[:60]} ({nota:.0%} igual) → crédito para {nome}")
        return {**x, "arquivo": str(saida), "ini": round(ini, 2), "fim": round(fim, 2), "fonte": nome,
                "canal": info.get("uploader_id") or c.get("canal") or "", "video": c["id"],
                "url_original": f"https://www.youtube.com/watch?v={c['id']}", "juntado_por": v.get("fonte", ""),
                "programa": x.get("programa") or "", "prioridade": 1}
    return None


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
        words = palavras_do_cache(x["arquivo"])
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
        words = palavras_do_cache(x["arquivo"])
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


def roteiro(sel, cfg, titulos_antes=()):
    # o nome do BLOCO SECUNDÁRIO vem do canal: no Galo é "a volta pelo mundo" (os outros campeonatos), no
    # canal de games é "o resto dos games" (05/nov). O mecanismo é o mesmo; só a redação muda.
    bloco = cfg.get("bloco_extra_nome") or "a volta pelo mundo"
    fora_do_tema = (cfg.get("bloco_extra_aviso") or "NÃO É DO GALO")
    lista = "\n".join(f"{i + 1}. [ORIGEM: {origem(x)}]"
                      + (f" [{fora_do_tema} — {x['campeonato']}, {bloco} no fim do vídeo]" if x.get("campeonato") else "")
                      + (" [ESTE ASSUNTO JÁ SAIU NUM VÍDEO SEU HOJE: trate como notícia secundária, com um ângulo "
                         "novo, e NUNCA como a manchete]" if x.get("repetida") else "")
                      + (f" [TRECHO EM {x['idioma'].upper()} — vai LEGENDADO em português; avise na sua fala que é "
                         "de um canal de fora]" if (x.get("idioma") or "pt") != "pt" else "")
                      + f" {x['manchete']} — {x.get('resumo', '')} (clima: {x['clima']}; {x['fim'] - x['ini']:.0f} s)"
                      for i, x in enumerate(sel))
    longos = "\n\n".join(f"TRECHO {i + 1} ({x['fim'] - x['ini']:.0f} s) — o que é dito:\n{falas_do_trecho(x)}"
                          for i, x in enumerate(sel) if x["fim"] - x["ini"] >= cfg.get("comentario_min_s", 45))
    # QUEM FALA E SOBRE O QUÊ vem do config: é o que deixa o mesmo canal.py servir ao Galo e ao GTA 6
    # (o preset gta6 troca persona, assunto e as regras). Sem config, continua o canal do Galo de sempre.
    persona = cfg.get("persona") or ('como um torcedor apaixonado e engraçado de BH (gírias leves, "Massa", "Galo doido"), '
                                     "opinando sobre o que a imprensa falou (alguns trechos podem ser de OUTROS assuntos do "
                                     "futebol que você escolheu comentar: fale deles com o mesmo jeito, sempre como torcedor "
                                     "do Galo)")
    assunto = cfg.get("assunto") or "notícias do Atlético-MG (o Galo)"
    regras_extra = cfg.get("regras_roteiro") or ""
    if cfg.get("lancamento"):   # contagem regressiva de verdade, calculada na hora (nada de data inventada)
        try:
            falta = (dt.date.fromisoformat(cfg["lancamento"]) - dt.date.today()).days
            regras_extra += (f"\n- HOJE FALTAM {falta} DIA(S) para o lançamento ({cfg['lancamento']})."
                             if falta > 0 else "\n- O JOGO JÁ LANÇOU: fale no passado e foque em gameplay e análise.")
        except ValueError:
            pass
    # OS TÍTULOS QUE JÁ SAÍRAM (01/nov): no canal de GTA 6 cinco vídeos seguidos vieram com "210 GB", "mapa" e
    # "south park" no título. A IA não tinha como saber — ela só via os trechos de HOJE e, com razão, titulava no
    # fato mais forte, que é o mesmo da véspera. Agora ela recebe a lista e a PROIBIÇÃO explícita.
    proibido_repetir = ""
    if titulos_antes:
        proibido_repetir = ("\nTÍTULOS QUE JÁ SAÍRAM NESTE CANAL NOS ÚLTIMOS DIAS (do mais novo para o mais velho):\n"
                            + "\n".join(f"- {t}" for t in list(titulos_antes)[:8])
                            + "\nO título de HOJE **NÃO PODE** ser sobre o mesmo fato desses, nem repetir o número/nome que "
                              "era o gancho deles. Se o fato principal de hoje JÁ FOI título antes, titule no ÂNGULO NOVO "
                              "(o que mudou, quem falou agora, o detalhe que ainda não tinha saído) e, não havendo ângulo "
                              "novo, titule na SEGUNDA notícia mais forte. A thumb_texto segue a mesma regra.")
    regra_titulo = cfg.get("regra_titulo") or (
        'O TÍTULO e a THUMB saem SEMPRE da notícia do GALO mais forte (nunca de um trecho marcado como "a volta pelo '
        'mundo" nem de um que já saiu hoje). Se houver trechos de campeonato, a fala antes do primeiro deles avisa que '
        'agora é a volta pelo mundo ("e pra fechar, como é que ficou a Libertadores ontem") e o fechamento volta a ser '
        "sobre o Galo.\n"
        # o que segue foi MEDIDO em 150 vídeos dos 6 canais concorrentes (30/10/2026); o número é quantas vezes o
        # vídeo rende a mais que a mediana DAQUELE canal, então não é opinião minha nem deles
        "COMO ESCOLHER O TÍTULO (medido nos canais concorrentes, do que mais rende para o que menos):\n"
        "1. NOME DE JORNALISTA FAMOSO que falou do Galo no trecho (Renata Fan, Denílson, Neto, Mauro Cezar, "
        "Benjamin Back, Casagrande, PVC, Vampeta): 1,36x. Use o nome dele no título quando a fala principal for dele "
        "— \"RENATA FAN SE RENDE AO GALO E ELOGIA FRED\".\n"
        "2. REFORÇO / CONTRATAÇÃO / MERCADO: 1,22x. Se tiver nome de jogador chegando, é esse o título.\n"
        "3. NOME DO PROGRAMA no começo (GLOBO ESPORTE MG, JOGO ABERTO, ESPN, ITATIAIA, ALTEROSA): 1,18x — quem "
        "procura o programa acha o vídeo.\n"
        "4. PERGUNTA no título: 1,14x.  5. Duas partes separadas por \" / \": 1,11x.\n"
        "NÃO construa o título em cima de ARBITRAGEM/ROUBO/VAR: rende 0,89x (MENOS que a média) nesses canais.\n"
        "O 🚨 não muda nada (1,02x): pode usar, mas não conta como gancho.\n"
        "Título em CAIXA ALTA, até 100 caracteres, terminando com \" / NOTÍCIAS DO GALO\".")
    g = gemini_json([{"text": f"""Você narra o canal "{cfg['nome_canal']}", de {assunto}, {persona}. Os trechos, em ordem:
{lista}

Escreva a narração que liga os trechos. Responda SÓ JSON:
{{"titulo": "<título do YouTube em MAIÚSCULAS, chamativo, até 95 letras, com o principal nome/placar>",
 "thumb_texto": "<2 a 4 palavras da NOTÍCIA PRINCIPAL que dão vontade de clicar (nome do jogador/técnico/assunto; sem mentir)>", "thumb_destaque": "<1 palavra do thumb_texto para destacar>",
 "descricao": "<2 a 3 frases sobre o vídeo>", "tags": ["<10 a 15 tags>"],
 "abertura": {{"texto": "<gancho de 2 a 3 frases, até 45 palavras>", "clima": "<{'|'.join(CLIMAS)}>"}},
 "falas": [{{"antes_do": <número do trecho>, "texto": "<sua opinião/ponte para o trecho, 1 a 3 frases, até 40 palavras>", "clima": "..."}}],
 "comentarios": [{{"trecho": <número>, "depois_de": <segundo do trecho, logo DEPOIS de uma frase forte>, "texto": "<sua reação curta ao que ACABOU de ser dito, 6 a 20 palavras>", "clima": "..."}}],
 "fechamento": {{"texto": "<opinião final + pedir like, inscrição e comentário, até 40 palavras>", "clima": "..."}}}}
COMENTÁRIOS NO MEIO: nos trechos longos abaixo, entre UMA reação sua no meio da reportagem (2 se passar de 2 min), como
quem pausa e comenta o que acabou de ouvir ("Olha isso, Massa!", "Concordo demais com ele", "Aí não, né?") — só onde
combina, nunca nos primeiros 10 s nem nos últimos 10 s do trecho.
{longos}

{regra_titulo}
{proibido_repetir}
{regras_extra}

Uma fala antes de CADA trecho (antes_do = 1, 2, 3...). CADA fala DIZ DE ONDE VEM o trecho seguinte, pelo nome do programa/emissora
da ORIGEM (ex.: "olha o que falaram no Globo Esporte Minas", "o pessoal do Jogo Aberto, da Band, comentou"; se for "via" um canal,
cite o programa e o canal). No fechamento, diga que os créditos de tudo que foi usado estão nos comentários e na descrição."""}])
    if not g:
        nomes = ", ".join(x["fonte"] for x in sel[:3])
        g = {"titulo": f"IMPRENSA FALA DO GALO! {sel[0]['manchete']}"[:95], "thumb_texto": "", "thumb_destaque": "",
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


def faixa_png(texto, sub, saida, cor, hud=None):
    """manchete na faixa de baixo + crédito da fonte (transparente, por cima do molde).

    `hud=(n, total, canal)` liga a BARRA DE CAPÍTULO do formato Dulebio (05/nov): no topo "NOME ▸ 03 / 07 ▸
    MANCHETE", em cima de TODA notícia. Foi o traço que mais se repete no vídeo que fez 21,6x a mediana do canal
    (@Dulebio, 1,87 mil inscritos): cada trecho com a barra do capítulo no alto e a fonte escrita embaixo —
    parece documentário, não colagem, e diz ao espectador em que ponto do vídeo ele está."""
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
    if hud:
        n, total, canal = hud
        barra = f"{canal}   \u00b7   {n:02d} / {total:02d}   \u00b7   {texto}"
        t = 24
        fb = fonte_pil(t, "Inter-Bold.otf")
        while d.textlength(barra.upper(), font=fb) > W - 120 and t > 14:
            t -= 2
            fb = fonte_pil(t, "Inter-Bold.otf")
        d.rectangle((0, 0, W, 78), fill=(0, 0, 0, 150))
        d.text((40, 39), barra.upper(), font=fb, fill="#ffffff", anchor="lm")
        d.rectangle((40, 74, 40 + int((W - 80) * n / max(total, 1)), 78), fill=cor)   # a barrinha de progresso
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
        # gravações com o nome "ouvindo"/"escutando" são feitas para isso; senão as de pouco gesto
        calmas = ([p for p in vs if re.search(r"ouvindo|escutando|calmo|assistindo", norm(p.stem))]
                  or [p for p in vs if av[p.stem].get("nivel") == "pouco"] or [p for p in vs if av[p.stem].get("nivel") == "médio"])
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


def comando_voz(cfg, pasta, fj):
    """a linha de comando do voz.py com os ajustes do canal (a MESMA cadeia: VoiceStudio → Fish → neural)"""
    ref = pasta / cfg.get("voz_ref", "voz/minha_voz.wav")
    cmd = [sys.executable, str(AQUI / "voz.py"), str(fj), str(pasta / "voz" / "cache"), "--ref", str(ref),
           "--exagero", str(cfg["exagero_voz"])]
    for chave, bandeira in (("voicestudio", "--voicestudio"), ("voz_voicestudio", "--voz-vs"),
                            ("velocidade_voz", "--velocidade-vs"), ("instrucao_voz", "--instrucao-vs"),
                            ("voz_neural", "--voz-edge")):
        if cfg.get(chave):
            cmd += [bandeira, str(cfg[chave])]
    if cfg.get("sem_voicestudio"):
        cmd.append("--sem-voicestudio")
    if cfg.get("sem_voz_neural"):
        cmd.append("--sem-edge")
    return cmd


def dublagem(trad, clima, cfg, pasta, tmp, idx, log=log):
    """A SUA VOZ traduzindo o trecho gringo, por cima do áudio original (legenda sozinha dá trabalho de ler
    enquanto o vídeo corre). Cada frase entra no SEGUNDO em que ela é dita no original; frase que não cabe no
    espaço dela é acelerada um pouco (até 1,35x) para não atropelar a seguinte."""
    if not trad:
        return None
    tmp.mkdir(parents=True, exist_ok=True)
    fj = tmp / f"dub_{idx}.json"
    falas = [{"id": f"d{idx}_{k}", "texto": f["texto"], "clima": clima or "falando"} for k, f in enumerate(trad)]
    grava_json(fj, falas)
    r = subprocess.run(comando_voz(cfg, pasta, fj))
    if r.returncode:
        log("      dublagem: a voz não saiu; o trecho fica só com a legenda")
        return None
    falas = json.loads(fj.read_text(encoding="utf-8"))
    ins, mix, n = [], [], 0
    for k, (f, tr) in enumerate(zip(falas, trad)):
        arq = f.get("arquivo")
        if not arq or not Path(arq).exists():
            continue
        da = dur_mp4(arq) or 0
        if da <= 0:
            continue
        espaco = (trad[k + 1]["ini"] - tr["ini"]) if k + 1 < len(trad) else da
        rapido = min(1.35, max(1.0, da / espaco)) if espaco > 0.4 else 1.0
        ins += ["-i", str(arq)]
        at = f",atempo={rapido:.3f}" if rapido > 1.01 else ""
        mix.append(f"[{n}:a]aresample=48000{at},adelay={int(max(0.0, tr['ini']) * 1000)}:all=1[d{n}]")
        n += 1
    if not n:
        return None
    saida = tmp / f"dub_{idx}.wav"
    filtro = ";".join(mix) + ";" + "".join(f"[d{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0[o]"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", filtro, "-map", "[o]",
                        "-ar", "48000", "-ac", "1", str(saida)])
    if r.returncode or not saida.exists():
        log("      dublagem: não consegui montar a faixa de voz; fica só a legenda")
        return None
    log(f"      dublagem: {n} fala(s) na sua voz por cima do original")
    return saida


def tem_campo(clip, ini, fim, amostras=6, limite=0.42):
    """O trecho mostra IMAGEM DE JOGO (gramado)? Se mostra, NÃO PODE ENTRAR no vídeo.

    POR QUE ISSO EXISTE (05/nov) — os vídeos do canal estavam sendo DERRUBADOS depois de postados, e o
    print da reivindicação mostrou de onde: um lance de **Atlético de Madrid x Bayern pela Champions,
    imagem da TNT Sports**, que entrou pelo bloco "a volta pelo mundo". Transmissão de jogo é a coisa mais
    protegida que existe: o Content ID bloqueia NO MUNDO INTEIRO, em segundos, e não adianta crédito,
    comentário nem trecho curto. O único vídeo que NÃO foi bloqueado naquele dia foi justamente o que não
    tinha imagem de jogo nenhuma.

    Fala de estúdio (o que o canal quer) e lance de jogo (o que derruba o canal) são fáceis de separar:
    a transmissão de futebol é um plano aberto do GRAMADO, e gramado é uma mancha verde que ocupa metade
    da tela. Estúdio, mesa de debate e entrevista não têm isso. Então eu meço o verde.

    `limite` 0,42 = 42% da tela verde. Medido em quadros reais: transmissão aberta fica em 0,55-0,75;
    estúdio de esporte com fundo colorido fica abaixo de 0,15."""
    import cv2
    import numpy as np

    os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
    verdes, olhados = 0, 0
    for k in range(amostras):
        t_ = ini + (fim - ini) * (k + 0.5) / amostras
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t_:.2f}", "-i", str(clip), "-frames:v", "1",
                            "-vf", "scale=320:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
        if not r.stdout:
            continue
        img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        olhados += 1
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # verde de grama: matiz 35-85, com saturação e brilho de campo iluminado
        campo = cv2.inRange(hsv, np.array([35, 60, 40]), np.array([85, 255, 255]))
        if float(campo.mean()) / 255.0 >= limite:
            verdes += 1
    if not olhados:
        return False
    # metade dos quadros com gramado = é transmissão de jogo
    return verdes >= max(1, olhados // 2)


def so_imagens(clip, ini, fim, amostras=5):
    """O trecho é só IMAGEM (gameplay, lance, fotos do jogo) ou tem alguém FALANDO na tela?
    Quando não tem ninguém, o vídeo merece a TELA CHEIA — pôr a cara dele num canto ao lado de uma gameplay
    só rouba espaço. Tendo uma pessoa falando, o layout normal (janela + você no canto) continua."""
    import cv2
    import numpy as np

    os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
    modelo = TOOLS.parent / "yunet.onnx"
    com_rosto, olhados = 0, 0
    for k in range(amostras):
        t_ = ini + (fim - ini) * (k + 0.5) / amostras
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t_:.2f}", "-i", str(clip), "-frames:v", "1",
                            "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
        if not r.stdout:
            continue
        img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        olhados += 1
        try:
            h, w = img.shape[:2]
            if modelo.exists():
                d = cv2.FaceDetectorYN.create(str(modelo), "", (w, h), 0.7)
                _, f = d.detect(img)
                # rosto PEQUENO (torcida, jogador no campo) não é alguém falando com a câmera
                if f is not None and any(x[2] * x[3] > w * h * 0.012 for x in f):
                    com_rosto += 1
        except Exception:   # noqa: BLE001
            return False    # na dúvida, o layout de sempre
    if olhados < 2:
        return False
    return com_rosto <= olhados * 0.34      # rosto em pouquíssimos quadros = é imagem de jogo


def mascara_longa(clima, pasta, tmp, dur, durante_reportagem=False, log=log):
    """Uma gravação de 6 s repetida num trecho de 90 s dá 15 voltas: é isso que deixa o GESTO com cara de robô.
    Aqui eu EMENDO gravações DIFERENTES até cobrir o trecho, então o loop (se sobrar) é muito mais longo e variado."""
    um = mascara_de(clima, pasta, durante_reportagem)
    if not um:
        return None
    d1 = dur_mp4(um)
    if not d1 or d1 >= dur * 0.9:
        return um
    partes, total, vistos = [um], d1, {um}
    for _ in range(7):
        if total >= dur:
            break
        nova = mascara_de(clima, pasta, durante_reportagem)
        if not nova:
            break
        if nova in vistos and len(vistos) > 2:   # acabaram as gravações diferentes
            break
        vistos.add(nova)
        partes.append(nova)
        total += dur_mp4(nova) or 0
    if len(partes) < 2:
        return um
    tmp.mkdir(parents=True, exist_ok=True)
    saida = tmp / f"masc_{abs(hash(tuple(str(x) for x in partes))) % 10**8}.mp4"
    if saida.exists():
        return saida
    lista = tmp / (saida.stem + ".txt")
    lista.write_text("".join(f"file '{Path(x).as_posix()}'\n" for x in partes), encoding="utf-8")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
                        "-an", "-c", "copy", str(saida)])
    if r.returncode != 0:   # parâmetros diferentes: emenda reencodando
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
                            "-an", *enc(), str(saida)])
    if r.returncode != 0 or not saida.exists():
        return um
    log(f"      máscara: {len(partes)} gravações emendadas ({total:.0f}s) para não repetir o gesto")
    return saida


def cobre(w, h):
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"


_ENC = None


def enc():
    """O ENCODER: a PLACA DE VÍDEO quando ela realmente funciona, senão a CPU.

    POR QUE ISSO IMPORTA (02/nov): o canal montava TUDO no libx264 — 20 min de 1080p com desfoque e três
    sobreposições, na CPU de um notebook, com a RTX 3050 parada do lado. Uma rodada levava HORAS e ele passou
    um dia sem postar. O NVENC faz a mesma peça em uma fração do tempo e não disputa a CPU com a voz.

    Testar com `-encoders` NÃO prova nada (a placa pode estar sem driver e o render morre no meio com
    "Cannot load libcuda.so.1" — já aconteceu na gameplay): eu CODIFICO 1 quadro de verdade, uma vez por
    rodada, e guardo a resposta. `DETTO_SEM_NVENC=1` força a CPU."""
    global _ENC
    if _ENC is None:
        _ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
        if os.environ.get("DETTO_SEM_NVENC") == "1":
            log("   render na CPU (DETTO_SEM_NVENC=1)")
        else:
            try:
                r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                                    "-i", "color=c=black:s=256x256:d=0.1", "-c:v", "h264_nvenc",
                                    "-f", "null", "-"], capture_output=True, timeout=120)
                if r.returncode == 0:
                    # cq 23 ≈ crf 20 do x264 no olho, e o arquivo sai parecido
                    _ENC = ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23", "-b:v", "0"]
                    log("   render na PLACA DE VÍDEO (NVENC)")
                else:
                    log("   render na CPU (a placa recusou o NVENC)")
            except (OSError, subprocess.SubprocessError):
                log("   render na CPU (não consegui testar a placa)")
    # as peças são emendadas com `-c copy`, então TODAS precisam sair do mesmo encoder e com o mesmo fps
    return [*_ENC, "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]


def traduz_frases(frases, de_idioma, log=log):
    """as falas do trecho em PORTUGUÊS (Gemini → IAs grátis → Claude). Falhou, devolve o original."""
    if not frases:
        return []
    g = gemini_json([{"text": "Traduza para PORTUGUÊS DO BRASIL, falado e natural (é legenda de vídeo sobre games), "
                              f"estas {len(frases)} falas em {de_idioma}. Mantenha nomes próprios, números e siglas. "
                              "NÃO explique, NÃO junte nem divida: devolva exatamente a mesma quantidade, na ordem.\n"
                              "Responda SÓ JSON: {\"frases\": [\"<tradução 1>\", ...]}\n\n"
                              + json.dumps(frases, ensure_ascii=False)}])
    out = (g or {}).get("frases") or []
    if len(out) != len(frases):
        log(f"   tradução: a IA devolveu {len(out)} de {len(frases)} falas; fica o original onde faltou")
        out = (out + frases[len(out):])[:len(frases)]
    return [str(x) for x in out]


def frases_do_trecho(words, ini, fim, por_frase=9):
    """as palavras do trecho em pedaços de legenda, cada um com começo e fim"""
    ws = [w for w in words if w.get("s") is not None and ini - 0.2 <= w["s"] <= fim]
    out = []
    for i in range(0, len(ws), por_frase):
        g = ws[i:i + por_frase]
        if not g:
            continue
        out.append({"texto": " ".join(x["w"] for x in g).strip(),
                    "ini": max(0.0, g[0]["s"] - ini), "fim": min(fim - ini, g[-1].get("e", g[-1]["s"]) - ini)})
    return [f for f in out if f["texto"] and f["fim"] > f["ini"]]


def legenda_pngs(frases, pasta, idx):
    """PNG por frase, na parte de baixo da JANELA do vídeo (legenda de tradução, não a faixa dele)"""
    from PIL import Image, ImageDraw

    x, y, w, h = JANELA
    out = []
    for k, f in enumerate(frases):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        txt = f["texto"].strip()
        linhas, atual = [], ""
        for pal in txt.split():
            if len(atual) + len(pal) + 1 > 46:
                linhas.append(atual)
                atual = pal
            else:
                atual = (atual + " " + pal).strip()
        if atual:
            linhas.append(atual)
        linhas = linhas[-2:]
        fon = fonte_pil(46)
        alt = 56 * len(linhas) + 24
        topo = y + h - alt - 28
        larg = max(dr.textlength(l, font=fon) for l in linhas) + 48
        dr.rounded_rectangle((x + w // 2 - larg // 2, topo, x + w // 2 + larg // 2, topo + alt), radius=14,
                             fill=(0, 0, 0, 190))
        for n, l in enumerate(linhas):
            dr.text((x + w // 2, topo + 14 + 28 + n * 56), l, font=fon, fill="#FFFFFF", anchor="mm",
                    stroke_width=2, stroke_fill="#000000")
        arq = pasta / f"trad_{idx}_{k}.png"
        img.save(arq)
        out.append((arq, f["ini"], f["fim"]))
    return out


def peca_trecho(base, clip, ini, fim, masc, faixa, saida, legenda=None, cheia=False, dub=None, dub_vol=0.16):
    """o trecho da imprensa na janela grande; você de máscara (sem som) no canto.
    `cheia`: o vídeo ocupa a TELA INTEIRA e a máscara não entra (trecho só de imagem/gameplay).
    `dub`: wav com a SUA voz traduzindo por cima — o áudio original abaixa para `dub_vol`."""
    d = fim - ini
    ins = ["-loop", "1", "-i", str(base), "-ss", f"{ini:.2f}", "-t", f"{d:.2f}", "-i", str(clip), "-loop", "1", "-i", str(faixa)]
    x, y, w, h = (0, 0, W, H) if cheia else JANELA
    cx, cy, cw, ch = CANTO
    vw, vh = tamanho(clip)
    if vw and vh and vw / vh < 1.4:
        # vídeo vertical/quadrado (TikTok, Reels): o próprio vídeo desfocado preenche as laterais, sem barra preta
        f = (f"[1:v]{cor_sdr(clip)}split[v1][v2];[v1]{cobre(w // 4, h // 4)},boxblur=8:2,scale={w}:{h},eq=brightness=-0.08[fundo];"
             f"[v2]scale={w}:{h}:force_original_aspect_ratio=decrease,setsar=1[fr];[fundo][fr]overlay=(W-w)/2:(H-h)/2,setsar=1[v];"
             f"[0:v][v]overlay={x}:{y}[a0];")
    elif cheia:
        f = f"[1:v]{cor_sdr(clip)}{cobre(w, h)},setsar=1[v];[0:v][v]overlay=0:0[a0];"
    else:
        f = (f"[1:v]{cor_sdr(clip)}scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1[v];"
             f"[0:v][v]overlay={x}:{y}[a0];")
    if masc and not cheia:
        ins += ["-stream_loop", "-1", "-i", str(masc)]
        f += f"[3:v]{cor_sdr(masc)}{cobre(cw, ch)},setsar=1[m];[a0][m]overlay={cx}:{cy}[a1];"
    else:
        f += "[a0]null[a1];"
    f += "[a1][2:v]overlay=0:0[a2];"
    # LEGENDA DA TRADUÇÃO: o canal gringo entra LEGENDADO em português (cada PNG no tempo da fala dele)
    atual = "a2"
    for k, (arq, la, lb) in enumerate(legenda or []):
        if lb <= 0 or la >= d:
            continue
        ins += ["-loop", "1", "-i", str(arq)]
        n = ins.count("-i") - 1          # o índice desta entrada no ffmpeg
        prox = f"L{k}"
        f += (f"[{atual}][{n}:v]overlay=0:0:enable='between(t,{max(0.0, la):.2f},{min(d, lb + 0.25):.2f})'[{prox}];")
        atual = prox
    f += f"[{atual}]fps={FPS},format=yuv420p[vo]"
    ac = audio_bom(clip)
    if dub and Path(dub).exists() and ac is not None:
        # DUBLAGEM: a sua voz por cima, o original bem baixinho atrás (dá para ouvir que é gringo, mas entende tudo)
        ins += ["-i", str(dub)]
        nd = ins.count("-i") - 1
        f += (f";[1:a:{ac}]volume={dub_vol:.2f},aresample=48000[orig];"
              f"[{nd}:a]aresample=48000,volume=1.0[fala];"
              f"[orig][fala]amix=inputs=2:duration=first:dropout_transition=0,"
              f"loudnorm=I=-16:TP=-1.5[ao]")
        af = ["-map", "[ao]"]
    elif ac is not None:
        af = ["-map", f"1:a:{ac}", "-af", "loudnorm=I=-16:TP=-1.5,aresample=48000"]
    else:
        af = []
    r = ff(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", f, "-map", "[vo]", *af, "-t", f"{d:.2f}", *enc(), str(saida)],
           limite=int(max(600, d * 12)), nome="a peça do trecho")
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


def peca_fala(base, wav, masc, texto, pasta, idx, saida, logo, apoio=None):
    """você falando (narração clonada): sua gravação de máscara GRANDE na janela, legenda na faixa.

    `apoio`: (arquivo, segundo) para mostrar IMAGEM DO JOGO na janela grande enquanto você fala, com a sua
    máscara no canto. É o que faltava num canal de games (05/nov, pedido dele: "deve mostrar imagens/vídeos
    do GTA"): durante a narração a janela mostrava SÓ a sua cara, e o espectador ficava minutos sem ver jogo
    nenhum. O trecho usado é o da PRÓPRIA notícia que a fala está apresentando — já está baixado, não custa
    nada e cai certo: você diz "a Rockstar liberou novas imagens" e as imagens estão na tela."""
    da = dur(wav) + 0.25
    x, y, w, h = JANELA
    cx, cy, cw, ch = CANTO
    legs = legendas(texto, da - 0.25, pasta, idx)
    ins = ["-loop", "1", "-i", str(base), "-i", str(wav)]
    if apoio and Path(apoio[0]).exists():
        # a imagem do jogo ocupa a janela (MUDA, em loop se o pedaço for curto); você vai para o canto
        ins += ["-stream_loop", "-1", "-ss", f"{float(apoio[1]):.2f}", "-i", str(apoio[0])]
        f = f"[2:v]{cor_sdr(apoio[0])}{cobre(w, h)},setsar=1[ap];[0:v][ap]overlay={x}:{y}[b0];"
        if masc:
            ins += ["-stream_loop", "-1", "-i", str(masc)]
            f += f"[3:v]{cor_sdr(masc)}{cobre(cw, ch)},setsar=1[m];[b0][m]overlay={cx}:{cy}[b1];"
        else:
            ins += ["-loop", "1", "-i", str(logo)]
            f += f"[3:v]{cobre(cw, ch)}[lg];[b0][lg]overlay={cx}:{cy}[b1];"
        ult = "b1"
        proxima = 4
    elif masc:
        ins += ["-stream_loop", "-1", "-i", str(masc)]
        f = f"[2:v]{cor_sdr(masc)}{cobre(w, h)},setsar=1[m];[0:v][m]overlay={x}:{y}[b0];"
    else:
        ins += ["-f", "lavfi", "-i", f"color=c=0x111111:s={w}x{h}:r={FPS}"]
        f = f"[0:v][2:v]overlay={x}:{y}[b0];"
    if not (apoio and Path(apoio[0]).exists()):
        ins += ["-loop", "1", "-i", str(logo)]
        f += f"[3:v]{cobre(cw, ch)}[lg];[b0][lg]overlay={cx}:{cy}[b1];"
        ult = "b1"
        proxima = 4
    for k, (png, a, b) in enumerate(legs):
        ins += ["-loop", "1", "-i", str(png)]
        f += f"[{ult}][{proxima + k}:v]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[c{k}];"
        ult = f"c{k}"
    f += f"[{ult}]fps={FPS},format=yuv420p[vo];[1:a]atempo=1.05,loudnorm=I=-16:TP=-1.5,aresample=48000,apad=pad_dur=0.2[ao]"
    r = ff(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", f, "-map", "[vo]", "-map", "[ao]", "-t", f"{da / 1.05 + 0.2:.2f}", *enc(), str(saida)],
           limite=int(max(600, da * 12)), nome="a peça da sua fala")
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
    ref = pasta / cfg.get("voz_ref", "voz/minha_voz.wav")
    cmd_voz = [sys.executable, str(AQUI / "voz.py"), str(fj), str(pasta / "voz" / "cache"), "--ref", str(ref),
               "--exagero", str(cfg["exagero_voz"])]
    if cfg.get("voicestudio"):
        cmd_voz += ["--voicestudio", cfg["voicestudio"]]
    if cfg.get("voz_voicestudio"):
        cmd_voz += ["--voz-vs", cfg["voz_voicestudio"]]
    if cfg.get("velocidade_voz"):
        cmd_voz += ["--velocidade-vs", str(cfg["velocidade_voz"])]
    if cfg.get("instrucao_voz"):
        cmd_voz += ["--instrucao-vs", cfg["instrucao_voz"]]
    if cfg.get("sem_voicestudio"):
        cmd_voz.append("--sem-voicestudio")
    if cfg.get("voz_neural"):          # qual voz neural pt-BR usar quando o VoiceStudio estiver fechado
        cmd_voz += ["--voz-edge", cfg["voz_neural"]]
    if cfg.get("sem_voz_neural"):
        cmd_voz.append("--sem-edge")
    # a voz PARA de propósito quando só sobrou o Chatterbox (ver voz.py): mostre o MOTIVO, não um traceback
    r = subprocess.run(cmd_voz)
    if r.returncode:
        raise SemVoz("a voz não ficou pronta — o motivo está nas linhas acima do registro (quase sempre: abra o "
                     "VoiceStudio no PC com a sua voz clonada, ou conserte a chave do Fish)")
    falas = json.loads(fj.read_text(encoding="utf-8"))
    fala_antes = {f["antes"]: f for f in falas if "antes" in f}
    comenta = {}
    for f in falas:
        if "comenta" in f:
            comenta.setdefault(f["comenta"], []).append(f)
    # 2) peças: abertura → (fala → trecho [→ comentário → resto do trecho])… → fechamento
    pecas = []
    # CAPÍTULOS: as peças são emendadas em ORDEM com -c copy, então somando a duração das anteriores eu
    # sei o segundo EXATO em que cada notícia começa no vídeo final — e a manchete dela já é o título.
    marcas = []

    medidas = {}

    def onde_estou():
        # a duração de cada peça é medida UMA vez: isto era chamado por notícia e remedia TODAS as peças
        # anteriores (uns 300 ffprobe num vídeo de 20 min)
        return sum(medidas.setdefault(p, dur_mp4(p)) for p in pecas)

    # IMAGEM DO JOGO ATRÁS DA SUA FALA (05/nov): a fala que apresenta a notícia i mostra o trecho DELA na
    # janela, em vez de só a sua cara. Ligado por canal (`apoio_na_fala`), para não mudar o visual do Galo.
    quer_apoio = bool(cfg.get("apoio_na_fala"))

    def add_fala(f, apoio=None):
        p = tmp / f"p{len(pecas):03d}.mp4"
        t0 = time.time()
        if peca_fala(base, f["arquivo"], mascara_de(f["clima"], pasta), f["texto"], tmp, len(pecas), p, logo,
                     apoio=apoio if quer_apoio else None):
            pecas.append(p)
            log(f"      peça {len(pecas)} (sua fala{' + imagem do jogo' if (apoio and quer_apoio) else ''}) "
                f"pronta em {time.time() - t0:.0f}s")

    add_fala(falas[0], apoio=(sel[0]["arquivo"], sel[0]["ini"]) if sel else None)
    # onde termina a CHAMADA de abertura (resumo + CTA): é aí que a vinheta entra, não no segundo 0
    abertura_s = dur_mp4(pecas[0]) if pecas else 0.0
    for i, x in enumerate(sel):
        # o capítulo começa na FALA que apresenta a notícia (é ali que o assunto começa), não no trecho
        marcas.append((onde_estou(), x.get("manchete") or ""))
        if i in fala_antes:
            # o apoio é o trecho desta notícia, que é justamente a que a fala está apresentando
            add_fala(fala_antes[i], apoio=(x["arquivo"], x["ini"]))
        p = tmp / f"p{len(pecas):03d}.mp4"
        fx = faixa_png(x["manchete"], f"Imagens: {origem(x)}", tmp / f"faixa_{i}.png", cfg["cor"],
                       hud=(i + 1, len(sel), (cfg.get("nome_canal") or "DETTO").split()[0]) if cfg.get("barra_capitulo") else None)
        log(f"   trecho {i + 1}/{len(sel)}: {x['manchete']} ({x['fim'] - x['ini']:.0f}s, {x['fonte']})")
        cortes = sorted({round(c["em"], 2) for c in comenta.get(i, [])})
        partes = list(zip([x["ini"]] + cortes, cortes + [x["fim"]]))
        coms = sorted(comenta.get(i, []), key=lambda c: c["em"])
        # TRECHO EM OUTRA LÍNGUA (canal gringo no canal de GTA): traduz uma vez e legenda em português
        trad = []
        if (x.get("idioma") or "pt") != "pt":
            try:
                wds, _ = transcreve(x["arquivo"], None)
                fr = frases_do_trecho(wds, x["ini"], x["fim"])
                pt = traduz_frases([f["texto"] for f in fr], x["idioma"], log)
                trad = [{**f, "texto": p_} for f, p_ in zip(fr, pt)]
                log(f"      em {x['idioma'].upper()}: {len(trad)} legenda(s) em português")
            except Exception as e:   # noqa: BLE001
                log(f"      não consegui traduzir ({str(e)[:90]}): o trecho entra sem legenda")
        for n, (a0, b0) in enumerate(partes):
            p = tmp / f"p{len(pecas):03d}.mp4"
            # as legendas desta PARTE, com o tempo contado do começo dela
            leg = legenda_pngs([{**f, "ini": f["ini"] - (a0 - x["ini"]), "fim": f["fim"] - (a0 - x["ini"])}
                                for f in trad if f["fim"] > (a0 - x["ini"]) and f["ini"] < (b0 - x["ini"])],
                               tmp, f"{i}_{n}") if trad else None
            # TELA CHEIA quando é só imagem de jogo/gameplay (ninguém falando na tela): a sua cara num canto
            # ao lado de uma gameplay só rouba espaço. Com alguém falando, o layout de sempre.
            cheia = bool(cfg.get("tela_cheia_sem_rosto", True)) and so_imagens(x["arquivo"], a0, b0)
            masc = None if cheia else mascara_longa(x["clima"], pasta, tmp / "masc", b0 - a0,
                                                    durante_reportagem=True, log=log)
            if cheia:
                log("      só imagem (ninguém falando na tela): vai em TELA CHEIA")
            # a parte da dublagem que cai nesta peça, com o tempo contado do começo dela
            dub = None
            if trad and cfg.get("dublar", True):
                aqui = [{**f, "ini": f["ini"] - (a0 - x["ini"]), "fim": f["fim"] - (a0 - x["ini"])}
                        for f in trad if f["fim"] > (a0 - x["ini"]) and f["ini"] < (b0 - x["ini"])]
                dub = dublagem(aqui, x.get("clima"), cfg, pasta, tmp / "dub", f"{i}_{n}", log=log)
            t0 = time.time()
            if peca_trecho(base, x["arquivo"], a0, b0, masc, fx, p, leg, cheia=cheia, dub=dub,
                           dub_vol=float(cfg.get("volume_original_dublado", 0.16))):
                pecas.append(p)
                log(f"      peça {len(pecas)} ({b0 - a0:.0f}s de imprensa) pronta em {time.time() - t0:.0f}s")
            else:
                log(f"      peça {len(pecas) + 1} NÃO saiu ({b0 - a0:.0f}s de imprensa)")
            if n < len(coms):
                log(f"      comentário seu no meio: {coms[n]['texto'][:60]}")
                add_fala(coms[n])
    add_fala(falas[-1])
    lista = tmp / "pecas.txt"
    lista.write_text("".join(f"file '{p.as_posix()}'\n" for p in pecas), encoding="utf-8")
    bruto = tmp / "bruto.mp4"
    log(f"   emendando as {len(pecas)} peças...")
    t0 = time.time()
    if ff(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(bruto)],
          limite=1800, nome="a emenda das peças").returncode != 0:
        raise RuntimeError("não consegui emendar as peças (veja o erro do ffmpeg acima)")
    log(f"   nivelando o som ({time.time() - t0:.0f}s na emenda)...")
    if ff(["ffmpeg", "-v", "error", "-y", "-i", str(bruto), "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(saida)],
          limite=1800, nome="o nivelamento do som").returncode != 0:
        raise RuntimeError("não consegui nivelar o som do vídeo")
    log(f"   vídeo montado: {dur_mp4(saida) / 60:.1f} min")
    return saida, abertura_s, marcas


# ------------------------------------------------------------------ 5. thumb
THUMB_VARIANTE = {"v": ""}  # a variante usada na última thumb (vai para o post.json)


def escolhe_variante_thumb(cfg):
    """teste A/B das capas: rosto (controle, com a sua foto) | gancho (manchete + quadro claro, sem rosto) | tema (foto da
    pessoa do assunto, sem o seu rosto). 'auto' faz rodízio pela quantidade de prontos já feitos."""
    v = str(cfg.get("thumb_variante", "auto")).lower()
    if v in ("rosto", "gancho", "tema"):
        return v
    n = len(list((Path(cfg.get("_pasta", "")) / "prontos").glob("*/post.json"))) if cfg.get("_pasta") else 0
    return ("gancho", "tema", "rosto")[n % 3]


def foto_do_tema(rot, destino, log=print):
    """foto de quem é o assunto (jornalista/jogador), 1 rosto, da internet — nunca o seu"""
    nome = (rot.get("thumb_destaque") or "").strip()
    if len(nome) < 3:
        return None
    try:
        sys.path.insert(0, str(TOOLS))
        import busca_imagem as BI
        r = BI.buscar(nome, exige=[nome.split()[0]], rosto=True, destino=str(destino), log=log, prazo=40)
        return r["file"] if r else None
    except Exception as e:
        log(f"   foto do tema falhou ({e})")
        return None


def thumb(video, rot, cfg, pasta_saida, sel=None):
    """thumb viral: VOCÊ (a melhor reação das suas gravações de máscara — surpreso/bravo/rindo primeiro) + UM QUADRO da
    notícia principal (o vídeo original da imprensa, no trecho usado) + o ASSUNTO (thumb_texto do roteiro) + escudo"""
    try:
        sys.path.insert(0, str(TOOLS / "thumb"))
        from viral import thumb_viral

        pasta = Path(pasta_saida)
        pm = Path(cfg.get("_pasta", "")) / "mascara" / "sdr"
        masc = [p for p in pm.glob("*.mp4") if not p.stem.endswith("__inteiro")] if pm.exists() else []
        masc.sort(key=lambda p: 0 if re.search(r"surpres|brav|rind|comemor|choc|assust", norm(p.stem)) else 1)
        principal = (sel or [None])[0]
        quadro, faixas = (principal["arquivo"], [(float(principal["ini"]) + 2, float(principal["fim"]) - 1)]) if principal and \
            Path(principal.get("arquivo", "")).exists() else (video, None)
        assunto = rot.get("titulo", "") + " — " + "; ".join(x.get("manchete", "") for x in (sel or [])[:4])
        esc = TOOLS / "banco" / "escudos" / f"{cfg['time']}.png"
        var = escolhe_variante_thumb(cfg)
        pessoa = None
        if var == "tema":
            (pasta / "thumbs").mkdir(parents=True, exist_ok=True)
            pessoa = foto_do_tema(rot, pasta / "thumbs", log)
            if not pessoa:
                var = "gancho"
        THUMB_VARIANTE["v"] = var
        log(f"   thumb: variante {var}")
        feitas = thumb_viral(pasta / "thumbs", assunto, rot.get("thumb_texto", ""), rot.get("thumb_destaque", ""), None,
                             masc[:6], quadro, faixas, [esc] if esc.exists() else [],
                             cfg.get("estilo_thumb", "noticia"), cfg.get("nome_canal", ""), log=log, variante=var, pessoa=pessoa)
        if not feitas:
            return None
        shutil.copyfile(feitas[0], pasta / "thumb_1.jpg")
        return pasta / "thumb_1.jpg"
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
            words, lin = transcreve(arq, cfg.get("idioma_fontes", "pt"))
            v["idioma"] = lin
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
        f += f"[{ult}]fps={FPS},format=yuv420p[vo];[0:a]atempo=1.05,loudnorm=I=-16:TP=-1.5,aresample=48000,apad=pad_dur=0.2[ao]"
        p = tmp / f"sv_{idx}_a.mp4"
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", f, "-map", "[vo]", "-map", "[ao]", "-t", f"{da / 1.05 + 0.2:.2f}",
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
    r = ff(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", f, "-map", "[vo]", *af, "-t", f"{fim - ini:.2f}", *enc(), str(p)],
           limite=int(max(600, (fim - ini) * 12)), nome="a peça do short")
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
        # ANTES ISSO ERA MUDO: a máscara/voz nunca chegava e ninguém sabia por quê (o painel só dizia
        # "nenhuma gravação"). Agora o registro diz onde eu procurei.
        d_ = raiz_drive()
        log(f"Drive: não achei a pasta do canal ({raiz if raiz else 'nenhum Google Drive no PC'}). "
            + (f"O Drive está em {d_}: crie lá DETTO\\canal_noticias com as pastas mascara e voz."
               if d_ else "Abra o Google Drive para computador, ou ponha o caminho em \"drive\" no config/painel."))
        return
    m = raiz / "mascara"
    if not m.is_dir():
        log(f"Drive: a pasta {m} não existe (é de lá que vêm as gravações de máscara)")
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
    if not v.is_dir():
        log(f"Drive: a pasta {v} não existe (é de lá que vem a sua voz de referência)")
    if v.is_dir():
        auds = [f for f in v.iterdir() if f.is_file() and f.suffix.lower() in AUDIO_EXT]
        if auds:
            f = max(auds, key=lambda x: x.stat().st_mtime)
            marca = f"{f.name}|{f.stat().st_size}|{int(f.stat().st_mtime)}"
            reg = pasta / "voz" / "origem_drive.txt"
            if not reg.exists() or reg.read_text(encoding="utf-8").strip() != marca:
                ref = pasta / cfg.get("voz_ref", "voz/minha_voz.wav")
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



# ====================================================================== PRESETS DE CANAL
# O MESMO canal.py serve a mais de um canal: o que muda é o config (fontes, persona, regras do roteiro).
# `python tools\canal\canal.py --pasta <pasta> --preset gta6` escreve o config do canal de GTA 6.
GTA6 = {
    "preset": "gta6",
    # O NOME NÃO PODE SER "GTA 6": o canal morre no dia que o jogo sai e não segura outra gameplay. Os grandes do
    # nicho fazem assim (SanInPlay, GameplayRJ, NobertoGamer): nome próprio no canal, GTA 6 no conteúdo e na capa.
    "nome_canal": "DETTO PLAY",
    "assinatura": ("🎮 DETTO PLAY — tudo sobre o Grand Theft Auto VI até o lançamento: notícias, trailers e gameplay "
                   "comentada.\n🔔 Inscreva-se e ative o sininho: vídeo novo todo dia.\n📲 Instagram e TikTok: @detto.galo\n"
                   "Canal de fã, sem ligação oficial com a Rockstar Games ou a Take-Two. Os vídeos são usados em trechos "
                   "curtos, com comentário e crédito a quem produziu."),
    "assunto": "tudo sobre o GTA 6 (Grand Theft Auto VI) — notícias, trailers e gameplay comentada, até o lançamento",
    "persona": ("como um jogador brasileiro que acompanha o GTA 6 de perto: animado, direto, sem forçar gíria. Você "
                "REAGE e COMENTA o que acabou de aparecer na tela (react/review): diz o que achou bom, o que achou "
                "estranho, e compara com o GTA 5 quando ajuda a entender"),
    "regra_titulo": ("O TÍTULO e a THUMB saem da novidade mais forte do GTA 6 que aparece nos trechos. NUNCA prometa no "
                     "título algo que não está no vídeo (nada de \"GTA 6 ADIADO\" se ninguém disse isso) — título mentiroso "
                     "derruba o canal.\n"
                     # medido em 96 vídeos de SanInPlay, GameplayRJ, NobertoGamer e Will Mac (30/10/2026)
                     "MEDIDO nos canais concorrentes: no GTA 6 o título quase não muda o resultado — 🚨 (1,00x), número "
                     "no título (1,00x), parênteses (1,00x). DUAS coisas pioram: \"VAZOU/VAZAMENTO\" no título (0,90x) e "
                     "terminar com \"...\" (0,90x). Então: diga o FATO NOVO em palavras concretas e diretas, sem "
                     "reticências e sem a palavra vazamento no título (no corpo do vídeo, vazamento continua sendo "
                     "chamado de vazamento). O que decide neste nicho é a THUMB e sair TODO DIA, não o título.\n"
                     # medido em 05/11 nos canais que ELE mandou de referência
                     "MEDIDO nos canais de referência dele (05/11): num canal PEQUENO, NÚMERO no título rende 2,00x (Dulebio, 1,8 mil inscritos) e terminar com \"!!\" rende 0,05x — ou seja, ponha o número concreto (GB, dias, quantidade) e NUNCA termine em \"!!\". Num canal grande isso se inverte, mas o seu é pequeno.\n"
                     "O TÍTULO E A THUMB SAEM SEMPRE DO GTA 6, nunca de um trecho marcado como \"o resto dos games\" — esse bloco é o fim do vídeo. A fala antes do primeiro trecho dele avisa que agora é o resto dos games (\"e pra fechar, o que mais rolou nos games hoje\") e o fechamento volta a ser sobre o GTA 6."),
    # no GTA a alavanca não é o ângulo (como no Galo) e sim ser NOVO e CONCRETO — medido: título quase não muda nada
    "regra_nota": ("A NOTA é o quanto aquilo é NOVIDADE DE VERDADE e CONCRETA sobre o GTA 6: imagem ou gameplay "
                   "oficial nova, data, preço, tamanho do jogo, mecânica mostrada, declaração da Rockstar = nota alta. "
                   "Opinião, especulação, 'teoria de fã', recap do que já se sabia e reação a vazamento velho = nota "
                   "baixa. Trecho que repete o que o canal já falou nos últimos dias também cai."),
    "regras_roteiro": (
        "REGRAS DESTE CANAL (o que mais importa):\n"
        "- PROIBIDO INVENTAR qualquer coisa sobre o jogo: data, preço, mapa, personagem, mecânica ou tamanho. Só vale o "
        "que foi DITO ou MOSTRADO no trecho.\n"
        "- Vazamento e rumor você CHAMA de vazamento/rumor, sempre: \"saiu um vazamento, e vale lembrar que a Rockstar não "
        "confirmou\". Nunca trate rumor como oficial.\n"
        "- O que é OFICIAL hoje: lançamento em 19 de novembro de 2026, pré-download em 12 de novembro, PlayStation 5 e "
        "Xbox Series X e S (a versão de PC não tem data), preço no Brasil de quatrocentos e quarenta e nove reais e "
        "noventa (padrão) e quinhentos e quarenta e nove e noventa (Ultimate), protagonistas Lucia Caminos e Jason "
        "Duval, em Leonida/Vice City.\n"
        "- Números por extenso na narração (a voz LÊ o que você escrever) e nada de siglas soletradas erradas: escreva "
        "\"gê tê á seis\" como \"GTA seis\" e o narrador fala certo.\n"
        "- Na abertura, diga quantos dias faltam para o lançamento quando essa informação for dada abaixo."),
    "time": "GTA",
    # os canais que ELE acompanha (29/out, pedido dele). Canal que não existir/404 é pulado sozinho, e a BUSCA
    # POR DATA continua trazendo o resto — então acrescentar canal aqui nunca derruba a rodada.
    # O "id" NÃO É ENFEITE (05/nov): com ele a hora vem do FEED (uma requisição HTTP simples). Sem ele, toda
    # rodada fazia uma extração PESADA do yt-dlp em 7 canais — e era por isso que o canal de GTA 6 morria
    # enquanto o do Galo (que tem os ids) funcionava: o GTA marcava o próprio IP e o YouTube passava a
    # responder "not a bot" até no download. Os 7 ids abaixo foram conferidos um por um em 05/11, e cada
    # feed devolveu 15 vídeos.
    "fontes": [
        {"canal": "@SaninPlay", "id": "UCiQotbmKsXF1n3xp3MYvoiw", "nome": "Sanin Play", "filtro": "gta"},
        {"canal": "@GameplayRJ", "id": "UCJAbkIY17zAmCTNQHH0bQoQ", "nome": "GameplayRJ", "filtro": "gta"},
        {"canal": "@RockstarGames", "id": "UC6VcWc1rAoWdBCM0JxrRQ3A", "nome": "Rockstar Games",
         "filtro": "tudo", "prioridade": 1},
        {"canal": "@BRKsEDU", "id": "UCWKtHaeXVzUscYGcm0hEunw", "nome": "BRKsEDU", "filtro": "titulo", "prioridade": 3},
        # @Voxel não existe ("This channel does not have a videos tab"): o canal é @VOXELOFICIAL (conferido 05/nov)
        {"canal": "@VOXELOFICIAL", "id": "UCupqHNRTEHjNtq9X8djWyaQ", "nome": "Voxel", "filtro": "titulo", "prioridade": 3},
        {"canal": "@TecMundo", "id": "UCdmGjywrxeOPfC7vDllmSgQ", "nome": "TecMundo", "filtro": "titulo", "prioridade": 3},
        {"canal": "@IGNBrasil", "id": "UCfg4PAgKIurlvYJRhhukv_g", "nome": "IGN Brasil", "filtro": "titulo", "prioridade": 3},
        # CANAIS GRINGOS (06/nov, "sempre tem vídeo de GTA inclusive em canal gringo"): o id é descoberto na
        # primeira rodada (acha_channel_id) e o trecho em inglês sai dublado/legendado em português.
        {"canal": "@IGN", "nome": "IGN", "filtro": "gta", "prioridade": 3},
        {"canal": "@GameSpot", "nome": "GameSpot", "filtro": "gta", "prioridade": 3},
    ],
    "formato": "auto",   # "auto" = rodízio (1 de cada por dia) ou noticias / documentario / cartoes
    "formatos_ativos": ["noticias", "documentario", "cartoes"],
    "max_canais_busca": 5,
    "fontes_versao": 8,   # 06/nov: canais e buscas em inglês; 05/nov: filtro "gta" nos 2 canais de GTA; ids; barra de capítulo dos canais (feed em vez de yt-dlp) + bloco de outros games
    "busca": ["gta 6 notícias", "gta 6 gameplay", "gta 6 trailer análise", "gta 6 novidades hoje",
              "grand theft auto 6 notícia", "gta 6 vazamento",
              "gta 6 news today", "gta 6 trailer 3", "gta 6 gameplay leak", "gta 6 rockstar new screenshots"],
    "busca_qualquer_canal": True,
    "outras_fontes": [],
    "fora": ["ao vivo", "live", "podcast completo", "sorteio", "gta 5 rp", "gta rp", "roleplay"],
    "max_horas": 48,
    "trecho_min_s": 15,
    "trecho_max_s": 120,      # pedaço de gameplay/notícia; o comentário dele entra entre os trechos
    "max_trechos_video": 3,
    # MEDIDO em 3 nichos e 5 canais: 12-18 min ganha em TODOS (GTA 1,30x · Gigaton Games 1,29x ·
    # Dulebio 2,73x · Nerds de Negócios 2,23x) e 8-12 min PERDE em todos. 14 cai no meio da faixa
    # mesmo depois da vinheta.
    "duracao_alvo_min": 14,
    "comentario_min_s": 40,
    "buscar_original": False,  # aqui não existe "canal que junta": o vídeo achado já é a fonte
    # NOTÍCIA DE OUTROS GAMES (05/nov, pedido dele) — o mesmo mecanismo da "volta pelo mundo" do Galo, que
    # já existia e está testado: um BLOCO SECUNDÁRIO no fim do vídeo, com busca própria, que simplesmente
    # NÃO EXISTE no dia em que não há notícia (nada é forçado).
    # Era preciso: o canal descartava "ZELDA OCARINA OF TIME REMAKE" do BRKsEDU e o remake da IGN, porque
    # os `termos` só aceitam palavras de GTA — justamente a notícia de games que ele quer dar.
    "campeonatos_ligado": True,
    "bloco_extra_nome": "o resto dos games",
    "bloco_extra_aviso": "NÃO É DO GTA 6",
    "max_trechos_campeonato": 2,
    "max_videos_campeonato": 2,
    "campeonatos": [
        {"nome": "lançamentos e novidades dos games",
         "termos": ["gameplay", "trailer", "review", "análise", "lançamento", "remake", "remaster", "dlc",
                    "atualização", "update", "beta", "anúncio"],
         "busca": ["notícias de games hoje", "lançamento de jogo trailer hoje", "gameplay novidade jogo hoje"]},
        {"nome": "o que saiu nos consoles e na PC gaming",
         "termos": ["playstation", "ps5", "xbox", "game pass", "nintendo", "switch", "steam", "epic games",
                    "pc gamer", "placa de vídeo"],
         "busca": ["playstation xbox notícia hoje", "nintendo switch notícia hoje", "steam notícia jogo hoje"]},
    ],
    "mesclar_assunto": True,   # GTA 6 é UM assunto só: sem isso a rodada ficaria sem material
    # num canal de assunto único TUDO parece repetido: o limite do Galo (0,35) barraria todas as notícias
    "parecido_max": 0.6,
    # ENTRAR no vídeo é frouxo (0,8, senão um canal de assunto único fica sem material); ser a NOTÍCIA
    # PRINCIPAL/título é apertado — foi o que deixou 5 vídeos seguidos com "210 GB" e "mapa" no título
    "titulo_parecido_max": 0.3,
    "dias_ja_postado": 7,   # num canal de assunto único o mesmo fato volta a semana toda
    "max_min_busca": 4,
    "mesclar_nota_min": 5,
    "mesclar_novidade_min": 0.2,
    "max_repetidas": 3,
    "lancamento": "2026-11-19",
    # canal gringo entra: deixa o whisper DESCOBRIR a língua e o trecho sai LEGENDADO em português
    "idioma_fontes": None,
    # VELOCIDADE: a legenda do YouTube evita transcrever vídeo de 10-25 min (era isso que fazia a rodada demorar)
    "dublar": True,                  # trecho gringo sai com a SUA voz traduzindo por cima (+ a legenda)
    "tela_cheia_sem_rosto": True,    # gameplay/imagem sem ninguém falando ocupa a tela inteira
    # MEDIDO em 3 canais que ele mandou (05/nov): num canal de games o espectador tem de ver JOGO na tela.
    # Durante a narração a janela mostrava só a máscara dele — minutos sem jogo nenhum.
    "apoio_na_fala": True,
    "legenda_antes_de_transcrever": True,
    "legenda_langs": "pt.*,pt,en.*,en",
    "max_videos_rodada": 4,   # com 13 min de alvo não precisa de 8 vídeos por rodada; o resto fica para a próxima
    "termos": ["gta 6", "gta6", "gta vi", "grand theft auto 6", "grand theft auto vi", "vice city", "rockstar games",
               "lucia caminos", "jason duval", "leonida"],
    "termos_nao": ["gta 5", "gta v", "gta san andreas", "gta rp", "gta online", "gta 4", "gta iv"],
    "vinheta_canal": "gta6",
    "estilo_thumb": "gta6",
}

# cada preset é o CONFIG_PADRAO COM AS TROCAS dele: assim nenhuma chave some (foi o KeyError 'voz_ref' do
# canal de GTA 6, que morreu no traz_do_drive na primeira rodada)
PRESETS = {"galo": CONFIG_PADRAO, "gta6": {**CONFIG_PADRAO, **GTA6}}

class SemVoz(Exception):
    """A voz boa não está disponível: a rodada para com o motivo, sem traceback e sem moer o Chatterbox a noite toda."""


FORMATOS = {
    "noticias": {"barra_capitulo": False},
    # estilo Dulebio: barra de capítulo no topo, imagem oficial em tela cheia, trechos curtos e mais cortes
    "documentario": {"barra_capitulo": True, "tela_cheia_sem_rosto": True, "trecho_max_s": 45, "max_trechos_video": 5},
    # estilo Gigaton: ritmo calmo, trechos curtos de b-roll com a manchete em destaque
    "cartoes": {"barra_capitulo": True, "tela_cheia_sem_rosto": True, "trecho_max_s": 25, "max_trechos_video": 6},
}


def escolhe_formato(pasta, cfg):
    """`formato`: nome fixo, ou "auto" = rodízio: pelo menos um de CADA formato ativo por dia
    (o primeiro ativo sem vídeo de hoje; todos feitos = o que está há mais tempo sem sair)."""
    ativos = [f for f in (cfg.get("formatos_ativos") or list(FORMATOS)) if f in FORMATOS] or ["noticias"]
    f = cfg.get("formato", "noticias")
    if f != "auto":
        return f if f in FORMATOS else "noticias"
    import comum
    hoje = dt.date.today().isoformat()
    ult = {}
    for _, d in comum.prontos(pasta):
        ult.setdefault(d.get("formato") or "noticias", d.get("criado", ""))
    for k in ativos:
        if not str(ult.get(k, "")).startswith(hoje):
            return k
    return min(ativos, key=lambda k: ult.get(k, ""))


def prepara(pasta, preset=""):
    for p in ("mascara", "voz", "fontes", "prontos"):
        (pasta / p).mkdir(parents=True, exist_ok=True)
    cfg_f = pasta / "config.json"
    seu = le_json(cfg_f, {})
    # qual canal é este: o preset gravado no config manda (o --preset só vale na primeira vez ou para trocar)
    nome_preset = (seu.get("preset") or preset or "galo").lower()
    base = PRESETS.get(nome_preset) or CONFIG_PADRAO
    if not cfg_f.exists() or (preset and preset != seu.get("preset")):
        seu = {**base, **{k: v for k, v in seu.items() if k not in base}} if seu else dict(base)
        grava_json(cfg_f, seu)
        log(f"config do canal \"{seu.get('nome_canal')}\" gravado em {cfg_f}")
    cfg = dict(base)
    if nome_preset != "galo":      # canal que não é o do Galo não recebe as migrações das fontes do Galo
        # MAS PRECISA DAS SUAS PRÓPRIAS (05/nov): o config do GTA 6 já existe no PC dele, então nada que eu
        # mude no preset chegava lá — o @Voxel errado ficaria errado para sempre e o bloco de outros games
        # nunca apareceria. Cada preset tem o seu `fontes_versao` e traz as chaves novas quando ele sobe.
        if base is not CONFIG_PADRAO and seu.get("fontes_versao", 1) < base.get("fontes_versao", 1):
            for k_ in ("fontes", "fontes_versao", "busca", "fora", "campeonatos", "campeonatos_ligado",
                       "max_trechos_campeonato", "max_videos_campeonato", "bloco_extra_nome",
                       "bloco_extra_aviso", "regra_titulo", "termos", "termos_nao", "barra_capitulo", "formato", "formatos_ativos", "max_canais_busca", "parecido_max", "titulo_parecido_max", "dias_ja_postado", "max_min_busca"):
                if k_ in base:
                    seu[k_] = base[k_]
            grava_json(cfg_f, seu)
            log(f"config: atualizei as fontes do preset {nome_preset} (canal certo do Voxel + bloco de "
                f"notícias de outros games no fim do vídeo)")
        cfg.update(seu)
        leia_ = pasta / "LEIA-ME.txt"
        if not leia_.exists():
            shutil.copyfile(AQUI / "LEIA-ME.txt", leia_)
        return cfg
    if seu.get("fontes_versao", 1) < CONFIG_PADRAO["fontes_versao"]:
        # 20/out: imprensa (Jogo Aberto, Alterosa, ESPN, TNT), TV Galo às vezes, canais de notícias do Galo e busca;
        # notícia INTEIRA; hoje e ontem; sem repetir notícia
        for k_ in ("fontes", "fontes_versao", "busca", "busca_qualquer_canal", "outras_fontes", "fora", "max_horas", "max_videos_rodada",
                   "trecho_min_s", "trecho_max_s", "max_trechos_video", "parecido_max",
                   "legenda_antes_de_transcrever", "legenda_langs"):
            seu[k_] = CONFIG_PADRAO[k_]
        if seu.get("duracao_alvo_min", 12) < 16:
            seu["duracao_alvo_min"] = CONFIG_PADRAO["duracao_alvo_min"]
        grava_json(cfg_f, seu)
        log("config: fontes novas (imprensa + TV Galo + canais de notícias do Galo + busca), notícias inteiras de hoje e ontem")
    if seu.get("nome_canal") in (None, "", "GALO NOTÍCIAS"):
        seu["nome_canal"] = CONFIG_PADRAO["nome_canal"]  # 20/out: o canal se chama DETTO GALO NOTÍCIAS
        seu.setdefault("assinatura", CONFIG_PADRAO["assinatura"])
        grava_json(cfg_f, seu)
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
    ap = argparse.ArgumentParser(description="canal automático (Galo, GTA 6...)")
    ap.add_argument("--pasta", default=str(pasta_padrao()))
    ap.add_argument("--preset", default="", choices=["", "galo", "gta6"],
                    help="que canal é este (gta6 = canal de GTA 6; grava o config na pasta)")
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
    cfg = prepara(pasta, a.preset)
    if cfg.get("formato") is not None or cfg.get("formatos_ativos"):
        cfg["_formato"] = escolhe_formato(pasta, cfg)
        cfg.update(FORMATOS[cfg["_formato"]])
        log(f"formato desta rodada: {cfg['_formato']}")
    traz_do_drive(pasta, cfg)
    # SEM MATERIAL DE BASE A RODADA NÃO TEM COMO TERMINAR: a máscara (você na tela) e a voz de referência (a voz
    # clonada) são obrigatórias. Antes a rodada ia até o fim, gastava download/IA e acabava sem entregar nada —
    # e o painel só dizia "rodada terminou (ok)".
    if not os.environ.get("DETTO_VOZ_FALSA"):
        faltando = []
        masc = [f for f in (pasta / "mascara").glob("*") if f.is_file() and f.suffix.lower() in VIDEO_EXT]
        if not masc:
            faltando.append(f"MÁSCARA: nenhuma gravação em {pasta / 'mascara'} (5–10 s de você, o nome diz o clima: "
                            "rindo.mov, bravo.mov, comemorando.mov...)")
        ref = pasta / cfg.get("voz_ref", "voz/minha_voz.wav")
        if not ref.exists():
            faltando.append(f"VOZ DE REFERÊNCIA: falta {ref} (20–30 s da sua voz falando normal, sem música)")
        if faltando:
            d_ = raiz_drive()
            onde = (Path(cfg["drive"]) if cfg.get("drive") else (d_ / "DETTO" / "canal_noticias" if d_ else None))
            log("NÃO RODEI — falta o material de base deste canal:")
            for x in faltando:
                log(f"   - {x}")
            if onde:
                log(f"   Suba pelo celular em {onde}, nas pastas mascara e voz (qualquer áudio serve) — a próxima "
                    "rodada copia sozinha.")
            else:
                log("   Ponha os arquivos nas pastas acima (ou configure a pasta do Drive no painel).")
            return
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
    from reels import trava_rodada, dono_da_trava
    TRAVA = trava_rodada(pasta, ".canal_rodando")
    if not TRAVA:
        quem, pid = dono_da_trava(pasta, ".canal_rodando")
        # ANTES esta mensagem não dizia nada e o painel mostrava "rodada terminou (ok)": um canal.py que travou e
        # ficou vivo (aconteceu: preso desde 20/10) matava TODAS as rodadas seguintes em silêncio.
        log(f"NÃO RODEI: outro canal.py está com a trava ({quem or 'sem pid anotado'}). Se ele estiver travado há "
            f"horas, encerre no painel (botão Destravar) ou feche o processo {pid or 'python.exe'} e rode de novo.")
        return
    # a rodada tem HORA PARA ACABAR: passando disso ela morre e solta a trava (02/nov, 4 h presa e nenhum
    # vídeo no dia). `"max_minutos_rodada": 0` no config desliga.
    _lim = float(cfg.get("max_minutos_rodada", 110) or 0)
    if _lim > 0:
        relogio_da_rodada(_lim)
    hist = le_json(pasta / "historico.json", {"vistos": {}, "trechos": [], "postados": []})
    hoje = dt.date.today().isoformat()
    # VÍDEOS QUEIMADOS (06/nov): até hoje a coleta marcava "visto" ANTES de baixar. Download barrado = vídeo
    # perdido. Uma vez só, devolvo os vistos dos últimos 3 dias que NUNCA viraram trecho (sem trecho no
    # histórico = nunca foram aproveitados) para a fila de coleta.
    if not hist.get("vistos_v2"):
        _com_trecho = {t.get("video") for t in hist.get("trechos", [])}
        _corte = (dt.date.today() - dt.timedelta(days=3)).isoformat()
        _devolvi = [i for i, d in hist.get("vistos", {}).items()
                    if isinstance(d, str) and d >= _corte and i not in _com_trecho and not str(i).startswith("local_")]
        for i in _devolvi:
            hist["vistos"].pop(i, None)
        hist["vistos_v2"] = hoje
        if _devolvi:
            log(f"   devolvi {len(_devolvi)} vídeo(s) que tinham sido marcados como vistos sem nunca virar trecho")

    # 1-2) coleta → baixa → transcreve → trechos
    def local(v):
        """arquivo da imprensa no PC; o .info.json do yt-dlp ao lado (se tiver) dá o título e a fonte"""
        d = le_json(Path(v).with_suffix(".info.json"), {})
        fonte = d.get("uploader") or d.get("channel") or "teste"
        fonte = {"atletico": "TV Galo", "espnbrasil": "ESPN Brasil"}.get(str(fonte).lower(), fonte)
        return {"id": "local_" + hashlib.sha1(v.encode()).hexdigest()[:8], "arquivo": v, "fonte": fonte, "canal": "",
                "titulo": re.sub(r"\s+", " ", d.get("description") or d.get("title") or Path(v).stem)[:200]}
    novos = [local(v) for v in a.video] if a.video else ([] if a.sem_coleta else coleta(cfg, hist))
    if not a.video and not a.sem_coleta:
        try:  # a volta pelo mundo: Libertadores, Champions, Copa do Brasil... no dia em que teve
            novos += coleta_campeonatos(cfg, hist, {x["id"] for x in novos})
        except Exception as e:
            log(f"campeonatos: {str(e)[:140]}")
    grava_json(pasta / "historico.json", hist)
    try:
        pautas(pasta, cfg, hist)
    except Exception as e:
        log(f"pautas: {e}")
    nao_baixou = []
    for v in novos:
        if not v.get("arquivo"):
            log(f"\nbaixando: {v['titulo']} ({v['fonte']})")
            arq, info = baixa(v["url"], pasta / "fontes")
            if not arq:
                log(f"   não baixou: {info}")
                nao_baixou.append(str(info))
                # só desisto do vídeo na 3ª falha; antes disso ele volta na próxima rodada
                _t = hist.setdefault("tentativas", {})
                _t[v["id"]] = _t.get(v["id"], 0) + 1
                if _t[v["id"]] >= 3:
                    hist["vistos"][v["id"]] = hoje
                    log("   3 falhas neste vídeo: deixo de tentar")
                grava_json(pasta / "historico.json", hist)
                from reels import precisa_login as _pl
                if len(nao_baixou) >= 2 and all(_pl(m) for m in nao_baixou):
                    # cada tentativa a mais só piora o bloqueio do IP; não adianta insistir sem cookie
                    log("   o YouTube barrou 2 vezes seguidas: PARO de tentar os outros vídeos para não piorar o bloqueio")
                    break
                continue
            v["arquivo"] = str(arq)
            v["descricao"] = (info or {}).get("description") or ""
        words, lin = palavras_rapidas(v, cfg, pasta, log)      # a legenda do YouTube, quando serve
        if words is None:
            log(f"transcrevendo: {Path(v['arquivo']).name}")
            words, lin = transcreve(v["arquivo"], cfg.get("idioma_fontes", "pt"))
        v["idioma"] = lin
        if lin != "pt":
            log(f"   esse vídeo está em {lin.upper()}: vou traduzir e LEGENDAR o trecho em português")
        tr = acha_trechos(words, v, cfg, assunto=v.get("assunto"))
        if v.get("id") and not str(v["id"]).startswith("local_"):
            hist["vistos"][v["id"]] = hoje      # agora sim: foi baixado e lido
        do_que = v["campeonato"] if v.get("campeonato") else (cfg.get("assunto", "")[:40] or "o Galo")
        log(f"   {len(tr)} trecho(s) sobre {do_que}")
        dv = dur(v["arquivo"]) or 1e9
        tr = [{**x, "fim": min(x["fim"], dv - 0.2)} for x in tr if min(x["fim"], dv - 0.2) - x["ini"] >= 8]  # nunca além do fim do vídeo
        for x in tr:
            t = {**x, "video": v["id"], "arquivo": v["arquivo"], "fonte": v["fonte"], "canal": v.get("canal", ""), "data": hoje,
                 "idioma": v.get("idioma", "pt"),
                 "publicado": v.get("publicado") or dt.datetime.now().isoformat(timespec="minutes"), "usado": False,
                 "prioridade": v.get("prioridade", 1),
                 **({"campeonato": v["campeonato"]} if v.get("campeonato") else {})}
            if v.get("juntador") and cfg.get("buscar_original", True):
                # canal que só junta: vai até o vídeo ORIGINAL (melhor qualidade, crédito para quem fez)
                try:
                    o = busca_original(t, v, cfg, pasta, v.get("descricao", ""))
                except Exception as e:
                    log(f"   original: {str(e)[:120]}")
                    o = None
                if o:
                    t = o
                    hist["vistos"][o["video"]] = hoje
                else:
                    log(f"   original não achado: fica o de {v['fonte']}" + (f" (programa: {x['programa']})" if x.get("programa") else ""))
            hist["trechos"].append(t)
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
        # POR QUE não há trecho (05/nov): "sem trechos para montar" era a última linha de uma rodada em que
        # NENHUM dos 4 vídeos tinha baixado — o painel mostrava "(ok)" e ele não sabia que o problema era o
        # YouTube pedindo login. Agora a rodada termina dizendo o MOTIVO, que é o que o painel exibe.
        if nao_baixou and len(nao_baixou) >= max(1, len(novos)):
            from reels import precisa_login
            quanto = len(nao_baixou)
            if any(precisa_login(m) for m in nao_baixou):
                log(f"NÃO RODEI: o YouTube pediu login/robô em TODOS os {quanto} vídeos, então não baixou nada. "
                    "Exporte um cookies.txt (extensão \"Get cookies.txt LOCALLY\" no navegador logado no YouTube) "
                    "e salve em E:\\DETTO\\cookies.txt — ou instale o Firefox e faça login no YouTube nele uma vez.")
            else:
                log(f"NÃO RODEI: nenhum dos {quanto} vídeos baixou. Último motivo: {nao_baixou[-1][:160]}")
            return
        log("sem trechos para montar")
        return
    # os melhores (nota) até o tamanho do vídeo, sem repetir muito a mesma fonte seguida
    alvo = cfg["duracao_alvo_min"] * 60
    sel, tot = [], 0.0

    def total_estimado():
        # imprensa + suas falas (~12 s antes de cada notícia) + abertura e fechamento (~30 s)
        return tot + 12 * len(sel) + 30
    por_video = {}
    lim_p = float(cfg.get("parecido_max", 0.35))
    # o que já saiu HOJE pode voltar como notícia secundária (com outro foco); o de ontem/anteontem fica fora de vez
    hoje_txt = [u["texto"] for u in hist.get("ja_postado", []) if u.get("data") == hoje]
    antes_txt = [u["texto"] for u in hist.get("ja_postado", []) if u.get("data") != hoje]
    n_rep, n_camp, adiadas = 0, 0, []
    # pautas primeiro; depois as melhores notas, desempate pela mais nova (notícia do dia na frente)
    for x in sorted(recentes, key=lambda x: (not x.get("pauta"), -round(float(x.get("nota", 5))), int(x.get("prioridade", 1)),
                                             "".join(chr(255 - ord(c)) for c in x.get("publicado", "")))):
        if total_estimado() >= alvo:
            break
        if por_video.get(x["video"], 0) >= int(cfg.get("max_trechos_video", 3)):
            continue
        tx = x.get("texto") or x.get("manchete", "")
        if any(parecido(tx, y.get("texto") or y.get("manchete", "")) >= lim_p for y in sel):
            continue  # a mesma notícia já entrou por outro canal
        if any(parecido(tx, t) >= lim_p for t in antes_txt):
            x["usado"] = True  # já saiu num vídeo de ontem: notícia velha, não volta
            continue
        # IMAGEM DE JOGO DERRUBA O VÍDEO (05/nov) — conferido na reivindicação que ele recebeu: era um lance
        # de Atlético de Madrid x Bayern da TNT Sports, bloqueado no mundo inteiro. Transmissão de futebol é
        # o conteúdo mais protegido que existe; crédito e comentário não protegem. Então o trecho com
        # GRAMADO na tela simplesmente NÃO ENTRA. `"recusa_lance": false` desliga.
        if cfg.get("recusa_lance", True):
            try:
                if tem_campo(x["arquivo"], x["ini"], x["fim"]):
                    x["usado"] = True   # não adianta guardar para a próxima rodada: continua sendo lance
                    log(f"   FORA (imagem de jogo, o YouTube bloqueia no mundo inteiro): "
                        f"\"{(x.get('manchete') or '')[:50]}\" — {x.get('fonte', '')}")
                    continue
            except Exception as e:   # noqa: BLE001
                log(f"   não consegui conferir se tem lance ({str(e)[:70]}); deixo passar")
        if x.get("campeonato"):  # a volta pelo mundo entra em dose pequena
            if n_camp >= int(cfg.get("max_trechos_campeonato", 2)):
                continue
            n_camp += 1
        elif any(parecido(tx, t) >= lim_p for t in hoje_txt):
            adiadas.append(x)  # assunto do vídeo de hoje: decide no fim, quando já houver uma manchete nova
            continue
        por_video[x["video"]] = por_video.get(x["video"], 0) + 1
        sel.append(x)
        tot += x["fim"] - x["ini"]
    # QUEM PODE SER A NOTÍCIA PRINCIPAL (01/nov) — era isso que fazia o canal de GTA 6 sair com quase o MESMO
    # TÍTULO cinco vídeos seguidos ("210 GB", "mapa", "south park"). Um único `parecido_max` decidia DUAS coisas
    # diferentes, e no GTA ele é 0,8 de propósito (frouxo, senão um canal de assunto único fica sem material):
    # então a notícia de ontem voltava, vinha com a nota mais alta, caía em PRIMEIRO e virava o título de novo.
    # Agora são dois limites: ENTRAR no vídeo continua frouxo; ser a PRIMEIRA (o título) é apertado.
    lim_t = float(cfg.get("titulo_parecido_max", min(0.5, lim_p)))
    titulos_antes = [u["titulo"] for u in sorted(hist.get("titulos", []), key=lambda u: u.get("quando", ""), reverse=True)][:8]
    textos_dos_titulos = [u.get("texto") or u.get("titulo", "") for u in
                          sorted(hist.get("titulos", []), key=lambda u: u.get("quando", ""), reverse=True)][:8]
    if sel and textos_dos_titulos:
        def ja_foi_titulo(x):
            tx = x.get("texto") or x.get("manchete", "")
            return max((parecido(tx, t) for t in textos_dos_titulos), default=0.0)

        novo = next((i for i, x in enumerate(sel) if ja_foi_titulo(x) < lim_t), None)
        if novo is None:
            log(f"   ATENÇÃO: todas as {len(sel)} notícias de hoje já foram título nos últimos dias — o roteiro vai "
                "receber a ordem de titular no ÂNGULO NOVO (veja os títulos anteriores no prompt)")
        elif novo > 0:
            x = sel.pop(novo)
            log(f"   a notícia mais forte de hoje JÁ FOI título antes ({ja_foi_titulo(sel[0]):.2f} de semelhança): "
                f"quem vai em PRIMEIRO é \"{x.get('manchete', '')[:60]}\"")
            sel.insert(0, x)
    # o assunto que já saiu hoje só volta se VOCÊ ligou a mesclagem no painel E a notícia trouxe FATO NOVO
    if adiadas and not cfg.get("mesclar_assunto"):
        log(f"   {len(adiadas)} trecho(s) do assunto que já saiu hoje ficaram de fora "
            "(ligue \"Mesclar assunto do dia\" no painel para eles voltarem como notícia secundária)")
        adiadas = []
    for x in adiadas:
        if not sel or n_rep >= int(cfg.get("max_repetidas", 1)) or total_estimado() >= alvo:
            break
        tx = x.get("texto") or x.get("manchete", "")
        if any(parecido(tx, y.get("texto") or y.get("manchete", "")) >= lim_p for y in sel):
            continue
        nota = float(x.get("nota", 5))
        nov = novidade(tx, hoje_txt)
        if nota < float(cfg.get("mesclar_nota_min", 7)) or nov < float(cfg.get("mesclar_novidade_min", 0.35)):
            log(f"   mesclagem recusada ({x.get('manchete', '')[:40]}): nota {nota:.0f}, fato novo {nov * 100:.0f}% "
                "— é a mesma notícia, não entra")
            continue
        x["repetida"] = True
        n_rep += 1
        sel.append(x)
        tot += x["fim"] - x["ini"]
        log(f"   mesclado: \"{x.get('manchete', '')[:46]}\" ({nov * 100:.0f}% de fato novo)")
    # ordem no vídeo: pautas → notícias novas do Galo (da mais nova para a mais antiga) → o assunto que já saiu hoje
    # → a volta pelo mundo (campeonatos). O FOCO (título e thumb) é sempre o primeiro, nunca um assunto repetido.
    def grupo(x):
        return 3 if x.get("campeonato") else 2 if x.get("repetida") else 0 if x.get("pauta") else 1
    sel = sorted(sel, key=lambda x: (grupo(x), "".join(chr(255 - ord(c)) for c in x.get("publicado", ""))))
    if n_rep:
        log(f"   {n_rep} assunto que já saiu hoje volta como notícia secundária (o foco é outro)")
    if n_camp:
        log(f"   {n_camp} trecho(s) de campeonato: " + ", ".join(sorted({x["campeonato"] for x in sel if x.get("campeonato")})))
    # PISO QUE O --forcar NÃO FURA (05/nov): hoje saiu um vídeo do canal de notícias com SÓ A ABERTURA E O
    # FECHAMENTO. O motivo: `monta()` sempre põe a 1ª e a última fala, e o laço do meio é sobre `sel` — com
    # `sel` vazio sobram as duas falas e nada no meio. O `--forcar` (que é o que o botão "Rodar agora" manda)
    # passava direto pela única guarda que existia, que era a de DURAÇÃO. Vídeo sem notícia não é vídeo:
    # `--forcar` serve para não esperar mais material, não para montar sem material nenhum.
    minimo = max(1, int(cfg.get("min_trechos_video", 1)))
    if len(sel) < minimo:
        log(f"NÃO RODEI: {len(sel)} trecho(s) de imprensa — um vídeo só com a abertura e o fechamento não serve. "
            + ("Os vídeos de hoje não baixaram (veja acima o motivo)." if nao_baixou
               else "Não achei notícia nova sobre o assunto do canal hoje."))
        return
    if tot < float(cfg.get("min_imprensa_s", 45)):
        log(f"NÃO RODEI: só {tot:.0f}s de imprensa no total — isso não dá um vídeo, dá uma chamada. "
            "Espero a próxima rodada.")
        return
    if total_estimado() < alvo:
        if not a.forcar:
            log(f"ainda não dá {cfg['duracao_alvo_min']} min (tem ~{total_estimado() / 60:.1f} min de notícia nova); espera a próxima rodada")
            return
        log(f"AVISO: só tem ~{total_estimado() / 60:.1f} min de notícia nova (menos de {cfg['duracao_alvo_min']}); monto assim porque você mandou")
    log(f"\nmontando: {len(sel)} trechos, {tot / 60:.1f} min de imprensa (~{total_estimado() / 60:.1f} min de vídeo)")
    rot = roteiro(sel, cfg, titulos_antes)
    tmp = pasta / "tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    pronto = pasta / "prontos" / f"{dt.datetime.now():%Y-%m-%d_%H%M} - {slug(rot['titulo'], 50)}"
    pronto.mkdir(parents=True, exist_ok=True)
    video, abertura_s, marcas = monta(sel, rot, cfg, pasta, tmp, pronto / "video.mp4")
    antes_da_vinheta = dur_mp4(video)
    try:   # vinheta do canal DEPOIS da chamada de abertura (no segundo 0 ela quebrava a retenção)
        import vinheta as VIN

        video = VIN.abre(video, cfg.get("vinheta_canal", "noticias"), cfg.get("nome_canal", ""), cfg, log=log, em=abertura_s)
    except Exception as e:
        log(f"vinheta: não entrou ({str(e)[:120]})")
    # a vinheta entrou NO MEIO (depois da chamada) e empurrou tudo que vem depois: os capítulos têm que
    # andar junto, senão cada um cai no fim da notícia anterior
    caps, bloco_caps = [], ""
    if cfg.get("capitulos", True):
        try:
            sys.path.insert(0, str(TOOLS / "yt"))
            import capitulos as CAP

            dur_final = dur_mp4(video)
            marcas = CAP.desloca(marcas, abertura_s, max(0.0, dur_final - (antes_da_vinheta or dur_final)))
            caps = CAP.de_marcas(marcas, dur_final, cfg.get("capitulo_abertura") or "Os destaques de hoje")
            # os capítulos vão ALTO na descrição: o YouTube só lê como capítulo a lista que começa em 0:00
            bloco_caps = f"\n\nCapítulos:\n{CAP.texto(caps)}" if caps else ""
            log(f"capítulos: {len(caps)}" if caps else "capítulos: não deu 3 válidos (o YouTube exige 3, "
                                                       "com 10 s cada) — o vídeo sai sem a barrinha")
        except Exception as e:  # noqa: BLE001
            log(f"capítulos: não saíram ({str(e)[:120]})")
    th = thumb(video, rot, {**cfg, "_pasta": str(pasta)}, pronto, sel)
    creditos = sorted({origem(x) + (f" — youtube.com/{x['canal']}" if x.get("canal") else "") for x in sel})
    tags = [t.strip("#") for t in rot.get("tags", [])][:15]
    hashtags = " ".join("#" + re.sub(r"\W", "", t) for t in tags[:3])
    descricao = (f"{rot.get('descricao', '')}{bloco_caps}\n\n{hashtags}\n\nCréditos das imagens:\n"
                 + "\n".join(f"• {c}" for c in creditos) + "\n\nNarração com voz gerada por inteligência artificial."
                 + (f"\n\n{cfg['assinatura']}" if cfg.get("assinatura") else ""))
    (pronto / "post.txt").write_text(f"{rot['titulo']}\n\n{descricao}\n\nTags: {', '.join(tags)}\n", encoding="utf-8")
    # TÍTULO + THUMB conferidos com as regras MEDIDAS do nicho (30/out). Isto AVISA, nunca barra: título
    # fraco ainda é melhor que vídeo não postado — mas aparecendo no registro, ele vê e corrige a próxima.
    lint = None
    try:
        sys.path.insert(0, str(TOOLS / "yt"))
        import titulo as TIT

        lint = TIT.confere(rot["titulo"], rot.get("thumb_texto", ""), cfg.get("preset", "galo"),
                           dur_mp4(video) / 60 if video else None)
        log(f"título: nota {lint['nota']}/100" + (f" · alavanca medida {lint['alavanca']:.2f}x" if lint["alavanca"] != 1 else ""))
        for p in sorted(lint["problemas"], key=lambda x: -x["peso"])[:4]:
            log(f"   ✗ {p['diz']}")
    except Exception as e:  # noqa: BLE001
        log(f"título: não consegui conferir ({str(e)[:100]})")
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
    # guarda o TÍTULO de hoje (7 dias): é o que impede o próximo vídeo de sair com o mesmo gancho
    hist["titulos"] = ([u for u in hist.get("titulos", [])
                        if (dt.date.today() - dt.date.fromisoformat((u.get("quando") or hoje)[:10])).days <= 7]
                       + [{"quando": dt.datetime.now().isoformat(timespec="minutes"), "titulo": rot["titulo"],
                           "texto": (sel[0].get("texto") or sel[0].get("manchete", ""))[:1500] if sel else rot["titulo"]}])[-20:]
    _dias_jp = int(cfg.get("dias_ja_postado", 3))
    hist["ja_postado"] = [u for u in hist.get("ja_postado", []) if (dt.date.today() - dt.date.fromisoformat(u["data"])).days <= _dias_jp] + \
        [{"data": hoje, "texto": (x.get("texto") or x.get("manchete", ""))[:1500]} for x in sel]
    # crédito também num COMENTÁRIO no vídeo (o sistema comenta logo depois de postar)
    comentario = ("📺 Créditos — trechos de TV/rádio/canais usados neste vídeo (comentados pelo canal):\n"
                  + "\n".join(f"• {c}" for c in creditos) + "\n\nTodos os direitos dos trechos são dos seus donos. Narração com voz gerada por IA.")
    post = {"titulo": rot["titulo"], "descricao": descricao, "tags": tags, "video": "video.mp4", "thumb": th.name if th else "", "thumb_variante": THUMB_VARIANTE["v"],
            "comentario": comentario, "capitulos": caps, "lint_titulo": lint,
            "shorts": shorts, "formato": cfg.get("_formato", "noticias"), "status": "aguardando", "criado": dt.datetime.now().isoformat(timespec="seconds"),
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
    try:
        main()
    except SemVoz as e:   # motivo em UMA linha, sem traceback (o painel mostra essa linha)
        try:
            log(f"NÃO RODEI: {e}")
        except Exception:
            print(f"NÃO RODEI: {e}", flush=True)
        os._exit(3)
    os._exit(0)
