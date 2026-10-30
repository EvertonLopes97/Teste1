# -*- coding: utf-8 -*-
"""REELS AUTOMÁTICOS: o seu começo + um vídeo viral de futebol + o texto "Quando..." no topo.

    python tools\\reels\\reels.py                    → faz 10 reels (padrão) na pasta E:\\DETTO\\reels
    python tools\\reels\\reels.py --quantos 3        → só 3
    python tools\\reels\\reels.py --agendar 07:00    → todo dia às 7h o Windows faz sozinho (PC ligado)
    python tools\\reels\\reels.py --pasta "D:\\reels" → outra pasta

PASTA (criada na primeira vez):
  inicios\\        seus começos (3 a 6 s). O NOME do arquivo diz o que você faz: "cruzando os braços desconfiado.mov",
                  "pegando a mochila e indo embora.mov" (ou um .txt com o mesmo nome explicando). Sem nome que explique,
                  o Gemini assiste e descreve sozinho (uma vez só).
  links.txt       links que VOCÊ achou (TikTok, Instagram, YouTube): um por linha. Vão primeiro, no lugar do SnapTik/
                  SnapInsta. Os usados vão para links_feitos.txt.
  prontos\\AAAA-MM-DD\\   "01 - texto.mp4" + "01 - texto.txt" (legenda + 5 tags) para postar.
  config.json     hashtags de busca, visualizações mínimas, idade máxima do vídeo, duração.
  historico.json  vídeos já usados (nunca repete) e quantas vezes cada começo saiu.

COMO ESCOLHE: links.txt primeiro; depois os Shorts de futebol mais vistos das hashtags do config (só dos últimos
`max_dias` dias, até `max_duracao` s). O Gemini (GEMINI_API_KEY) assiste o viral, escolhe o seu começo que combina e
escreve o texto "Quando...", a legenda e as tags (as do vídeo original primeiro, como você pediu). Sem a chave:
texto pelo título do vídeo e começos em rodízio.

EDIÇÃO (igual aos seus): começo em tela cheia → flash branco → viral (vertical em tela cheia; horizontal ampliado
com faixa preta em cima e embaixo) com o texto no topo do começo ao fim, fonte TikTok Sans, branco com sombra.
Instagram/TikTok pedindo login: coloque um cookies.txt na pasta (extensão "Get cookies.txt LOCALLY" no navegador
logado no Instagram → Export) ou use --cookies firefox (o login do Firefox; Chrome/Edge novos às vezes bloqueiam).
"""
import argparse
import base64
import datetime as dt
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

# os avisos do OpenCV ("Targets are not supported by the new graph engine") enchiam o registro e não dizem nada.
# Tem que ser ANTES do primeiro `import cv2` — por isso fica aqui em cima.
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
os.environ.setdefault("OPENCV_VIDEOIO_PRIORITY_MSMF", "0")

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
FONTE = PONTE / "fonts" / "TikTokSans.ttf"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}

CONFIG_PADRAO = {
    "hashtags": ["futebolengracado", "futebol", "resenhafutebol", "memesdefutebol", "futebolbrasileiro", "lancesbizarros",
                 "footballfunny", "footballmemes", "soccerfunny", "football"],
    "views_minimas": 300000,
    "max_dias": 120,
    "max_duracao": 60,
    "corte_max": 15,
    "tags_padrao": ["#futebol", "#humor", "#resenha", "#viral", "#fy"],
    # cada reel pronto entra na fila de postagem dessas contas (tools/postar/postar.py posta no horário); [] = não posta
    # "todas" = toda conta LIGADA da postagem (Instagram, TikTok, YouTube Shorts, Kwai) que não tem "reels": false
    "postar": ["todas"],
    "pasta_postar": "",
    "exemplos": [
        "Quando é o professor que escolhe as duplas e você vê com quem seu amigo está sentado:",
        "Quando vocês sabem que está rolando uma química mas nenhum dos dois toma iniciativa",
    ],
}


def log(m):
    print(m, flush=True)


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def slug(s, n=48):
    s = re.sub(r"[^\w\s-]", "", norm(s)).strip()
    return re.sub(r"\s+", " ", s)[:n].strip() or "reel"


def pasta_padrao():
    if os.name == "nt" and Path("E:/").exists():
        return Path("E:/DETTO/reels")
    return Path.home() / "DETTO" / "reels"


def le_json(f, padrao):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def grava_json(f, d):
    Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def prepara_pasta(base):
    for p in ("inicios", "prontos", "baixados"):
        (base / p).mkdir(parents=True, exist_ok=True)
    if not (base / "links.txt").exists():
        (base / "links.txt").write_text("# cole aqui links de vídeos (TikTok, Instagram, YouTube), um por linha\n", encoding="utf-8")
    cfg = base / "config.json"
    if not cfg.exists():
        grava_json(cfg, CONFIG_PADRAO)
    c = dict(CONFIG_PADRAO)
    seu = le_json(cfg, {})
    if seu.get("postar") == ["instagram:detto.galo", "tiktok:detto.galo"]:
        seu["postar"] = ["todas"]  # 20/out: reels vão para TODAS as contas ligadas (YouTube Shorts e Kwai também)
        grava_json(cfg, seu)
    c.update(seu)
    return c


def dur(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def tamanho(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:stream_side_data=rotation",
                        "-of", "json", str(f)], capture_output=True, text=True)
    try:
        s = json.loads(r.stdout)["streams"][0]
        w, h = s["width"], s["height"]
        rot = next((abs(int(x.get("rotation", 0))) for x in s.get("side_data_list", []) if "rotation" in x), 0)
        return (h, w) if rot in (90, 270) else (w, h)
    except Exception:
        return 1080, 1920


def audio_bom(f):
    """nº (entre os áudios) do primeiro áudio que o FFmpeg lê. iPhone novo grava 2: o 1º é "áudio espacial" (APAC),
    que o FFmpeg não abre; o 2º é o AAC normal. None = sem áudio"""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    for k, c in enumerate(r.stdout.split()):
        if not c or c in ("unknown", "none") or "apac" in c:
            continue
        # confirma que o FFmpeg deste PC abre esse áudio (o nome do codec muda entre versões do FFmpeg)
        t = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-map", f"0:a:{k}", "-t", "0.2", "-f", "null", "-"],
                           capture_output=True, text=True)
        if t.returncode == 0 and "no decoder" not in (t.stderr or "").lower():
            return k
    return None


SDR_DIR = None  # <pasta reels>/sdr: o começo convertido de HDR para SDR uma vez só


def inicio_sdr(f):
    """o seu começo (iPhone HDR) convertido para SDR UMA vez, pelo master (libplacebo/Dolby Vision = a cor do iPhone).
    Já SDR ou sem conversão possível: o próprio arquivo (aí o filtro do cor.py converte na hora)."""
    try:
        sys.path.insert(0, str(TOOLS))
        from sdr import master_sdr

        d = SDR_DIR or Path(f).parent / "sdr"
        d.mkdir(parents=True, exist_ok=True)
        return master_sdr(f, saida=d / f"{Path(f).stem}.mp4", log=log)
    except Exception as e:
        log(f"   (master SDR do começo falhou: {e}; convertendo na hora)")
        return f


def cor_sdr(f):
    """iPhone grava em HDR (HLG): converte para SDR (cor certa), igual ao editor"""
    try:
        sys.path.insert(0, str(TOOLS))
        from cor import filtro_cor

        x = filtro_cor(str(f))
        return f"{x}," if x else ""
    except Exception:
        return ""


# ------------------------------------------------------------------ baixar (yt-dlp: YouTube, TikTok, Instagram)
def ytdlp(args, cookies=None):
    base = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--no-playlist"]
    if shutil.which("node"):
        base += ["--js-runtimes", "node"]
    if cookies and Path(cookies).is_file():
        base += ["--cookies", str(cookies)]  # cookies.txt exportado do navegador
    elif cookies:
        base += ["--cookies-from-browser", cookies]
    r = subprocess.run(base + args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 and "no such option" in (r.stderr or "").lower() and "js-runtimes" in (r.stderr or ""):
        base = [x for x in base if x not in ("--js-runtimes", "node")]
        r = subprocess.run(base + args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r


_atualizou = False


def atualiza_ytdlp():
    """atualiza o yt-dlp no máximo uma vez por dia (antes atualizava a cada rodada e demorava)"""
    global _atualizou
    if _atualizou:
        return
    _atualizou = True
    marca = Path.home() / ".detto_ytdlp_atualizado"
    hoje = dt.date.today().isoformat()
    try:
        if marca.exists() and marca.read_text().strip() == hoje:
            return
    except OSError:
        pass
    log("atualizando o yt-dlp (uma vez por dia)...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp"], capture_output=True)
    try:
        marca.write_text(hoje)
    except OSError:
        pass


def baixa(url, pasta, cookies=None, txt=None):
    """baixa o vídeo + info (título, descrição, tags). Devolve (mp4, info) ou (None, erro)."""
    pasta.mkdir(parents=True, exist_ok=True)
    # a MAIOR resolução (até 1920 de altura), qualquer codec; junta em mp4
    args = ["-f", "bv*+ba/b", "-S", "res:1920,fps", "--merge-output-format", "mp4",
            "--write-info-json", "-o", str(pasta / "%(extractor_key)s_%(id)s.%(ext)s"), "--print", "after_move:filepath", url]
    erro = ""
    # sem login → cookies.txt da pasta (extensão "Get cookies.txt LOCALLY") → navegadores (Firefox funciona melhor;
    # Chrome/Edge novos às vezes não deixam ler)
    for k, ck in enumerate([cookies] if cookies else [None] + ([str(txt)] if txt and Path(txt).exists() else []) + ["firefox", "chrome", "edge"]):
        r = ytdlp(args, ck)
        caminho = (r.stdout or "").strip().splitlines()[-1:] or [""]
        f = Path(caminho[0]) if caminho[0] else None
        if f and f.exists() and f.stat().st_size > 50_000:
            info = le_json(f.with_suffix(".info.json"), {})
            return f, info
        erro = ((r.stderr or "").strip().splitlines() or [""])[-1][:200]
        if k == 0:
            atualiza_ytdlp()
    return None, erro


def candidatos_youtube(cfg, usados):
    """Shorts mais vistos das hashtags de futebol (visualizações da busca; idade conferida depois)"""
    tags = list(cfg["hashtags"])
    random.shuffle(tags)
    vistos, out = set(), []
    for tag in tags:
        r = ytdlp(["--flat-playlist", "--dump-json", "--playlist-end", "60", f"https://www.youtube.com/hashtag/{tag}/shorts"])
        if r.returncode != 0 and not r.stdout:
            atualiza_ytdlp()
            r = ytdlp(["--flat-playlist", "--dump-json", "--playlist-end", "60", f"https://www.youtube.com/hashtag/{tag}/shorts"])
        for linha in (r.stdout or "").splitlines():
            try:
                v = json.loads(linha)
            except ValueError:
                continue
            vid = v.get("id")
            if not vid or vid in vistos or f"youtube:{vid}" in usados:
                continue
            vistos.add(vid)
            if (v.get("view_count") or 0) >= cfg["views_minimas"]:
                out.append({"url": f"https://www.youtube.com/shorts/{vid}", "chave": f"youtube:{vid}", "views": v.get("view_count") or 0, "tag": tag})
    out.sort(key=lambda x: -x["views"])
    return out


def recente(info, max_dias):
    d = info.get("upload_date") or ""
    if not re.fullmatch(r"\d{8}", d):
        return True  # sem data (TikTok às vezes): aceita
    return (dt.date.today() - dt.date(int(d[:4]), int(d[4:6]), int(d[6:]))).days <= max_dias


def chave_de(info, url):
    return f"{(info.get('extractor_key') or 'url').lower()}:{info.get('id') or url}"


def tags_originais(info):
    """hashtags do vídeo original (descrição/título/tags), na ordem em que aparecem"""
    txt = f"{info.get('title', '')} {info.get('description', '')}"
    hs = re.findall(r"#([\wÀ-ÿ]{2,40})", txt)
    hs += [t.replace(" ", "") for t in (info.get("tags") or []) if isinstance(t, str) and 2 <= len(t) <= 30]
    out = []
    for h in hs:
        t = "#" + h.lstrip("#").lower()
        if t not in out and not re.fullmatch(r"#(shorts?|reels?|tiktok|fyp|foryou|parati|viral\d*)", t):
            out.append(t)
    return out


# ------------------------------------------------------------------ Gemini (assiste o vídeo e escreve)
GEMINI_FORA = False  # 429 (cota) nesta rodada: vai direto ao Claude, sem tentar o Gemini de novo a cada pergunta


def gemini_json(partes, temperatura=0.8, essencial=True):
    """pergunta ao Gemini (assiste o vídeo). Sem cota/sem chave: pergunta SÓ DE TEXTO → IAs grátis (Cerebras/Groq/
    Mistral/OpenRouter) e depois o Claude; com FOTO/VÍDEO → o Claude só se `essencial` (conferências extras pulam,
    para não gastar o seu Claude)."""
    global GEMINI_FORA
    sys.path.insert(0, str(TOOLS))
    from roteiro_ia import claude_partes_json, gerar, texto_gratis

    if os.environ.get("GEMINI_API_KEY") and not GEMINI_FORA:
        corpo = json.dumps({"contents": [{"parts": partes}], "generationConfig": {"temperature": temperatura, "responseMimeType": "application/json"}}).encode()
        try:
            r = gerar(corpo, log=log)
            txt = r["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
        except Exception as e:
            log(f"   Gemini: {str(e)[:200]}")
            if "429" in str(e) or "nenhum modelo" in str(e):
                GEMINI_FORA = True
    so_texto = all("text" in p_ for p_ in partes)
    if so_texto:
        t = texto_gratis("\n".join(p_["text"] for p_ in partes) + "\n\nResponda SOMENTE com o JSON pedido.", json_mode=True, log=log)
        m = re.search(r"\{.*\}", t or "", re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except ValueError:
                pass
    elif not essencial:
        return None  # conferência extra com imagem: sem Gemini, fica só a dos pixels (não gasta o Claude)
    g = claude_partes_json(partes, log=log)
    if g is not None:
        log("   (respondido pelo Claude da sua assinatura)")
    return g


def video_pequeno(f, saida, segundos=40, altura=360):
    """cópia leve para o Gemini assistir (cabe na requisição)"""
    # iPhone novo: o 1º áudio é o "espacial" (APAC), que o FFmpeg não abre → escolhe o áudio normal
    k = audio_bom(f)
    mapa = ["-map", "0:v:0"] + (["-map", f"0:a:{k}", "-c:a", "aac", "-b:a", "48k", "-ac", "1"] if k is not None else ["-an"])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(f), "-t", str(segundos)] + mapa +
                   ["-vf", f"scale=-2:{altura},fps=10", "-c:v", "libx264", "-preset", "veryfast", "-crf", "34", str(saida)], check=False)
    return saida if saida.exists() and saida.stat().st_size < 18_000_000 else None


def parte_video(f):
    return {"inline_data": {"mime_type": "video/mp4", "data": base64.b64encode(Path(f).read_bytes()).decode()}}


# ------------------------------------------------------------------ começos que você sobe no Google Drive
NOMES_PASTA_INICIOS = {"comeco", "comecos", "inicio", "inicios", "comeco de reel", "comecos de reel"}


def pastas_inicios_drive(cfg):
    """as pastas de começos no Drive: a do config ("pastas_inicios_drive") ou "Começo"/"Começos"/"Inícios" na raiz do
    Meu Drive ou dentro de DETTO (o Google Drive para computador deixa o Drive como uma pasta do PC)"""
    out = [Path(x) for x in cfg.get("pastas_inicios_drive", []) if Path(x).is_dir()]
    raiz = Path(os.environ["DETTO_DRIVE"]) if os.environ.get("DETTO_DRIVE") and Path(os.environ["DETTO_DRIVE"]).is_dir() else None
    if not raiz:
        try:
            sys.path.insert(0, str(TOOLS / "painel"))
            from edicao import drive_raiz

            raiz = drive_raiz()
        except Exception:
            raiz = None
    if raiz:
        for onde in (raiz, raiz / "DETTO"):
            if onde.is_dir():
                out += [d for d in onde.iterdir() if d.is_dir() and norm(d.name.strip()).replace("_", " ") in NOMES_PASTA_INICIOS]
    return list(dict.fromkeys(out))


def nome_valido(t):
    t = re.sub(r"[^\w\s-]", " ", str(t)).replace("_", " ").strip(" .-")
    return re.sub(r"\s+", " ", t)[:70] or "começo"


def sem_repeticao(nome):
    """"pensativo 2 2 2 2 3 2" → "pensativo" (o importador antigo renomeava o mesmo vídeo a cada 10 min)"""
    n = re.sub(r"(\s+\d{1,2}){2,}$", "", nome.strip())
    return n or nome


_ASSIN = {}


def assinatura(f):
    """o vídeo pelo conteúdo: tamanho + começo e fim do arquivo (rápido; o nome e a data podem mudar)"""
    import hashlib
    f = Path(f)
    st = f.stat()
    k = (str(f), st.st_size, st.st_mtime)
    if k not in _ASSIN:
        h = hashlib.md5()
        with open(f, "rb") as a:
            h.update(a.read(1 << 20))
            if st.st_size > 2 << 20:
                a.seek(-(1 << 20), 2)
                h.update(a.read(1 << 20))
        _ASSIN[k] = f"{st.st_size}:{h.hexdigest()[:16]}"
    return _ASSIN[k]


def limpa_inicios_repetidos(base):
    """apaga as cópias repetidas do MESMO começo em inicios\\ (fica a de nome mais curto, com o nome limpo) e os
    masters SDR delas. Erro antigo: o mesmo vídeo do Drive era importado de novo a cada 10 min ("nome 2 2 2...")."""
    pasta = base / "inicios"
    if not pasta.is_dir():
        return 0
    grupos = {}
    for g in pasta.iterdir():
        if g.is_file() and g.suffix.lower() in VIDEO_EXT:
            grupos.setdefault(g.stat().st_size, []).append(g)
    apagados, livre = 0, 0
    for fs in grupos.values():
        por = {}
        for g in fs:
            try:
                por.setdefault(assinatura(g), []).append(g)
            except OSError:
                pass
        for iguais in por.values():
            iguais.sort(key=lambda x: (len(x.stem), x.stem))
            fica = iguais[0]
            for g in iguais[1:]:
                try:
                    if g.with_suffix(".txt").exists() and not fica.with_suffix(".txt").exists():
                        g.with_suffix(".txt").rename(fica.with_suffix(".txt"))  # guarda a descrição/trecho
                    livre += g.stat().st_size
                    g.unlink()
                    for extra in (g.with_suffix(".txt"), (SDR_DIR or pasta / "sdr") / f"{g.stem}.mp4"):
                        if extra.exists():
                            if extra.suffix == ".mp4":
                                livre += extra.stat().st_size
                            extra.unlink()
                    apagados += 1
                except OSError:
                    pass
            limpo = sem_repeticao(fica.stem)
            if limpo != fica.stem and not (pasta / f"{limpo}{fica.suffix}").exists():
                try:
                    txt = fica.with_suffix(".txt")
                    novo = fica.with_name(limpo + fica.suffix)
                    fica.rename(novo)
                    if txt.exists():
                        txt.rename(novo.with_suffix(".txt"))
                except OSError:
                    pass
    if apagados:
        log(f"começos repetidos apagados: {apagados} cópias ({livre / 1e9:.1f} GB liberados)")
    return apagados


def importa_inicios(base, cfg, hist, tmp):
    """Começos que você subiu numa pasta do Drive ("Começo"): o Gemini assiste, dá o NOME do que você faz
    ("cruzando os braços desconfiado") e acha o melhor trecho se a gravação for longa; o arquivo é renomeado no
    Drive e copiado para inicios\\ (já com a cor convertida), pronto para os reels."""
    feitos = hist.setdefault("importados", {})
    novos = 0
    pastas = pastas_inicios_drive(cfg)
    if not pastas:
        return 0
    limpa_inicios_repetidos(base)
    ja = {}  # tamanho → arquivos em inicios\ (para achar o MESMO vídeo, com qualquer nome)
    for g in (base / "inicios").glob("*"):
        if g.is_file() and g.suffix.lower() in VIDEO_EXT:
            ja.setdefault(g.stat().st_size, []).append(g)
    for pasta in pastas:
        for f in sorted(pasta.iterdir()):
            if not f.is_file() or f.suffix.lower() not in VIDEO_EXT or f.name.startswith("~"):
                continue
            try:
                tam = f.stat().st_size
                if time.time() - f.stat().st_mtime < 60:
                    continue  # ainda chegando
                chave = assinatura(f)  # pelo CONTEÚDO: renomear no Drive muda a data e o nome, não o vídeo
            except OSError:
                continue
            limpo = sem_repeticao(f.stem)
            if limpo != f.stem:  # "nome 2 2 2 2" (o erro antigo) → "nome" no Drive também
                novo = f.with_name(limpo + f.suffix)
                try:
                    if not novo.exists():
                        f.rename(novo)
                        f = novo
                except OSError:
                    pass
            if chave in feitos:
                continue
            igual = next((g for g in ja.get(tam, []) if assinatura(g) == chave), None)
            if igual:  # já está em inicios\ (importado antes com outro nome): não copia de novo
                feitos[chave] = {"drive": str(f), "inicio": igual.name, "dia": dt.date.today().isoformat()}
                grava_json(base / "historico.json", hist)
                continue
            log(f"começo novo no Drive: {f.name}")
            d = dur(f)
            nome, descr, trecho = sem_repeticao(f.stem.strip()), "", None
            ja_tem_nome = len(re.findall(r"[a-zA-ZÀ-ÿ]{3,}", nome)) >= 2 and not re.match(r"^(img|vid|mov|dsc|pxl|whatsapp|copy|trim)", nome, re.I) \
                and not re.search(r"[0-9a-f]{16}", nome)
            p = video_pequeno(f, tmp / "comeco_novo.mp4", 90, 240)
            g = gemini_json([{"text": f"""Este é um "começo" de meme de futebol gravado pelo criador @detto.galo ({d:.1f} s): ele faz uma reação
que depois é seguida por um lance. Responda SÓ JSON:
{{"nome": "<o que ele faz, 2 a 6 palavras em português, minúsculas, sem pontuação — ex.: cruzando os braços desconfiado,
rindo e batendo palma, olhando sério para a câmera>",
 "descricao": "<1 frase: o que ele faz e a expressão>",
 "ini": <segundo em que a melhor reação começa>, "fim": <segundo em que termina (2 a 8 s depois)>}}"""}, parte_video(p)],
                            temperatura=0.3) if p else None
            if g and g.get("nome") and not ja_tem_nome:
                nome = nome_valido(g["nome"].lower())
            descr = (g or {}).get("descricao", "")
            try:
                a_, b_ = float(g["ini"]), float(g["fim"])
                if d > 10 and 0 <= a_ < b_ <= d + 0.5 and b_ - a_ >= 1.5:
                    trecho = (round(a_, 2), round(min(b_, d), 2))
            except (TypeError, ValueError, KeyError):
                pass
            alvo = base / "inicios" / f"{nome}{f.suffix.lower()}"
            k = 2
            while alvo.exists():
                alvo = base / "inicios" / f"{nome} {k}{f.suffix.lower()}"
                k += 1
            shutil.copyfile(f, alvo)
            linhas = [descr] if descr else []
            if trecho:
                linhas.append(f"trecho: {trecho[0]}-{trecho[1]}")
            if linhas:
                alvo.with_suffix(".txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")
            # o nome novo também no Drive (você vê o que é cada um) — o nome LIMPO, sem o " 2" de inicios\
            if nome != f.stem:
                novo = f.with_name(nome + f.suffix)
                try:
                    if not novo.exists():
                        f.rename(novo)
                        f = novo
                except OSError as e:
                    log(f"   (não renomeei no Drive: {e})")
            feitos[chave] = {"drive": str(f), "inicio": alvo.name, "dia": dt.date.today().isoformat()}
            ja.setdefault(alvo.stat().st_size, []).append(alvo)
            grava_json(base / "historico.json", hist)
            try:
                inicio_sdr(alvo)  # já deixa a cor convertida (o 1º reel com ele sai mais rápido)
            except Exception:
                pass
            log(f"   → inicios\\{alvo.name}" + (f"  (trecho {trecho[0]}–{trecho[1]} s)" if trecho else ""))
            novos += 1
    return novos


def descricao_inicio(f, cache, tmp):
    """o que você faz no começo: .txt ao lado, nome do arquivo, ou o Gemini assiste (uma vez)"""
    txt = f.with_suffix(".txt")
    if txt.exists():
        d = re.sub(r"(?im)^\s*trecho\s*:?.*$", "", txt.read_text(encoding="utf-8")).strip()
        if d:
            return d
    nome = f.stem.strip()
    if len(re.findall(r"[a-zA-ZÀ-ÿ]{3,}", nome)) >= 2 and not re.match(r"^(img|vid|mov|dsc|pxl|whatsapp)", nome, re.I):
        return nome
    if nome in cache:
        return cache[nome]
    p = video_pequeno(f, tmp / "inicio.mp4", 8, 240)
    r = gemini_json([{"text": "Descreva em uma frase curta, em português, o que o homem faz e a expressão dele neste vídeo curto "
                               "(é o começo de um meme). Responda JSON {\"descricao\": \"...\"}."}, parte_video(p)]) if p else None
    d = (r or {}).get("descricao") or nome
    cache[nome] = d
    return d


def escreve(clip_peq, info, inicios, cfg, usos_hoje):
    """Gemini: começo que combina + texto da tela + legenda + tags + melhor trecho"""
    lista = "\n".join(f"- {k}: {d}" for k, d in inicios)
    orig = tags_originais(info)
    prompt = f"""Você é o @detto.galo, criador de memes de futebol no Reels/TikTok (humor brasileiro, linguagem de torcedor).
Formato do seu reel: primeiro aparece VOCÊ fazendo uma reação (um dos seus "começos" abaixo) e depois o vídeo viral.
O TEXTO NA TELA fica no topo o tempo todo e liga a sua reação ao vídeo, no estilo "Quando..." (situação do dia a dia
que todo mundo vive, comparada ao que acontece no vídeo). Exemplos seus:
{chr(10).join('- ' + e for e in cfg['exemplos'])}

Seus começos (nome: o que você faz):
{lista}

Vídeo viral (anexo). Título original: {info.get('title', '')!r}. Descrição: {str(info.get('description', ''))[:400]!r}

Responda SÓ JSON:
{{"inicio": "<nome exato de um começo da lista que combina com a piada>",
 "texto": "<texto da tela, 6 a 22 palavras, sem hashtag, sem emoji>",
 "legenda": "<legenda do post, 1 ou 2 frases curtas, pode ter 1 emoji e uma pergunta para comentarem>",
 "tags": ["#...", "#...", "#...", "#...", "#..."],
 "inicio_corte": <segundo do vídeo viral onde começa a parte boa>,
 "fim_corte": <segundo onde termina; no máximo {cfg['corte_max']} s depois do início>,
 "enquadramento": "<aberto se o vídeo é horizontal em plano aberto e a jogada acontece perto das bordas (não pode cortar as laterais); senão fechado>"}}"""
    if orig:
        prompt += f"\nAs tags do vídeo original são {' '.join(orig[:12])}: use as que servem primeiro."
    if usos_hoje:
        prompt += f"\nEvite os começos já usados hoje: {', '.join(usos_hoje)}."
    return gemini_json([{"text": prompt}, parte_video(clip_peq)])


# ------------------------------------------------------------------ edição
def texto_png(texto, saida, W=1080, H=1920):
    """texto no topo: TikTok Sans, branco, sombra suave, centralizado (como os seus reels)"""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    tam = 72 if len(texto) < 70 else 62 if len(texto) < 110 else 54
    fonte = ImageFont.truetype(str(FONTE), tam)
    try:
        # eixos da TikTok Sans: tamanho óptico, largura, peso, inclinação → SemiBold normal
        vals = {"Optical size": 36, "Width": 100, "Weight": 560, "Slant": 0}
        fonte.set_variation_by_axes([vals.get(e["name"].decode() if isinstance(e["name"], bytes) else e["name"], e["default"]) for e in fonte.get_variation_axes()])
    except Exception:
        pass
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    linhas, atual = [], ""
    for p in texto.split():
        t = f"{atual} {p}".strip()
        if d0.textlength(t, font=fonte) > W * 0.72 and atual:
            linhas.append(atual)
            atual = p
        else:
            atual = t
    if atual:
        linhas.append(atual)
    alt = int(tam * 1.18)
    y0 = int(H * 0.165)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds, dt_ = ImageDraw.Draw(sombra), ImageDraw.Draw(img)
    for i, l in enumerate(linhas):
        x = (W - d0.textlength(l, font=fonte)) / 2
        y = y0 + i * alt
        # sombra larga e escura: lê em parede branca e no gramado
        ds.text((x, y + 4), l, font=fonte, fill=(0, 0, 0, 235), stroke_width=7, stroke_fill=(0, 0, 0, 235))
        dt_.text((x, y), l, font=fonte, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(15, 15, 15, 255))
    sombra = sombra.filter(ImageFilter.GaussianBlur(6))
    texto_png.fim = y0 + len(linhas) * alt + 10  # onde o texto termina (o vídeo pode ir logo abaixo)
    Image.alpha_composite(sombra, img).save(saida)


def _quadro(f, t):
    import cv2
    import numpy as np

    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(f), "-frames:v", "1", "-vf", "scale=-2:640", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_GRAYSCALE) if r.stdout else None


def _faixa(f, t0, t1):
    """faixa (y0, y1 em fração da altura) onde está o vídeo de verdade: linhas cheias e com movimento.
    Fora dela: barra preta com o texto gravado do outro criador (texto = linha com pouco pixel aceso)."""
    import numpy as np

    fr = [q for q in (_quadro(f, t0 + (t1 - t0) * k / 5) for k in range(1, 5)) if q is not None]
    if len(fr) < 2:
        return None
    a = np.array(fr, np.float32)
    cheia = ((a > 14).mean(axis=2)).mean(axis=0) > 0.6
    mexe = a.std(axis=0).mean(axis=1) > 6
    ok = cheia & mexe
    melhor, ini = (0, 0, 0), None
    for y, v in enumerate(list(ok) + [False]):
        if v and ini is None:
            ini = y
        elif not v and ini is not None:
            if y - ini > melhor[0]:
                melhor = (y - ini, ini, y)
            ini = None
    h = a.shape[1]
    if melhor[0] < h * 0.2:
        return None
    # barra de verdade = fora da faixa quase tudo PRETO (só o texto aceso); parede/gramado parado não conta
    luz = ((a > 14).mean(axis=2)).mean(axis=0)
    fora = np.concatenate([luz[: melhor[1]], luz[melhor[2]:]])
    if len(fora) > h * 0.1 and float(np.median(fora)) > 0.25:
        return 0.0, 1.0
    return melhor[1] / h, melhor[2] / h


def analisa_viral(f):
    """Repost no formato meme (outro criador no começo + o lance com faixa preta e texto gravado):
    acha onde começa o lance (corte de cena em que aparece a faixa) e a faixa do vídeo (sem o texto dele).
    Devolve {"inicio": s, "faixa": (y0, y1)} — vazio se o vídeo é "limpo"."""
    d = dur(f)
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(f), "-vf", "select='gt(scene,0.25)',showinfo", "-f", "null", "-"], capture_output=True, text=True)
    cortes = [0.0] + [float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stderr or "") if 0.8 < float(x) < d - 1]
    cortes = sorted(set(cortes)) + [d]
    partes = []
    for a_, b_ in zip(cortes[:-1], cortes[1:]):
        if b_ - a_ >= 0.6:
            partes.append((a_, b_, _faixa(f, a_, b_)))
    out = {}
    tem_barra = [p for p in partes if p[2] and (p[2][1] - p[2][0]) < 0.85]
    if not tem_barra:
        return out
    primeira = tem_barra[0]
    # antes dela, tela cheia (o criador original) → o lance começa no corte
    if primeira[0] > 0.5 and all(not p[2] or (p[2][1] - p[2][0]) >= 0.85 for p in partes if p[1] <= primeira[0] + 0.01):
        out["inicio"] = round(primeira[0] + 0.05, 2)
    fx = _faixa(f, primeira[0], d)
    if fx and (fx[1] - fx[0]) < 0.9:
        # margem para dentro: corta a borda (às vezes sobra 1 linha do texto ou da barra)
        # (em cima mais: a última linha do texto do outro criador costuma encostar no vídeo)
        out["faixa"] = (round(fx[0] + 0.03, 4), round(fx[1] - 0.006, 4))
    return out


def monta(inicio, clip, ini, fim, texto, saida, tmp, i_ini=0.0, i_fim=None, zoom=None, foco=0.5, faixa=None):
    """começo (tela cheia) → flash → viral (vertical cheio; horizontal ampliado com faixa preta) + texto no topo.
    i_ini/i_fim: trecho do começo (gravação longa); zoom: ampliação do viral horizontal (1 = largura toda, sem cortar;
    padrão até 1,33); foco: onde fica o corte lateral (0 = esquerda, 0,5 = meio, 1 = direita)."""
    inicio = inicio_sdr(inicio)
    W, H, FPS = 1080, 1920, 30
    di_total = dur(inicio)
    i_fim = min(di_total, i_fim) if i_fim else di_total
    di = max(0.5, i_fim - i_ini)
    dc = max(1.0, fim - ini)
    cw, ch = tamanho(clip)
    corta = ""
    if faixa:
        # só a faixa do lance (sem a barra preta e o texto do outro criador)
        y0, y1 = int(ch * faixa[0]) // 2 * 2, int(ch * faixa[1]) // 2 * 2
        corta = f"crop={cw}:{y1 - y0}:0:{y0},"
        ch = y1 - y0
    ar = cw / max(1, ch)
    png = tmp / "texto.png"
    texto_png(texto, png, W, H)
    cobre = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    if ar <= 0.8:
        vclip = cobre
    else:
        # horizontal: largura cheia ampliada até 1,33x (no máximo 67% da altura), faixa preta em cima/embaixo
        z = zoom if zoom else min(1.33, (H * 0.67) / (W / ar))
        sw, sh = int(W * z) // 2 * 2, int(W * z / ar) // 2 * 2
        x = int((sw - W) * max(0.0, min(1.0, foco)))
        # abaixo do texto quando cabe (texto no preto, como nos seus); senão no meio
        fim_txt = getattr(texto_png, "fim", int(H * 0.3))
        y = max((H - sh) // 2, min(fim_txt + 24, H - sh)) // 2 * 2
        vclip = f"scale={sw}:{sh},crop={W}:{sh}:{x}:0,pad={W}:{H}:0:{y}:black"
    fl = 0.12
    quadro_seu = enquadra(inicio, W, H, i_ini, i_fim, getattr(texto_png, "fim", None))
    f = (f"[0:v]trim={i_ini:.3f}:{i_fim:.3f},setpts=PTS-STARTPTS,{cor_sdr(inicio)}{quadro_seu},fps={FPS},setsar=1,format=yuv420p,"
         f"fade=t=out:st={max(0, di - fl):.3f}:d={fl}:color=white[v0];"
         f"[1:v]trim={ini:.3f}:{fim:.3f},setpts=PTS-STARTPTS,{cor_sdr(clip)}{corta}{vclip},fps={FPS},setsar=1,format=yuv420p,"
         f"fade=t=in:st=0:d={fl * 1.5:.3f}:color=white[v1];")
    ai, ac = audio_bom(inicio), audio_bom(clip)
    a0 = (f"[0:a:{ai}]atrim={i_ini:.3f}:{i_fim:.3f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-2[a0];" if ai is not None
          else f"anullsrc=r=48000:cl=stereo,atrim=0:{di:.3f}[a0];")
    a1 = (f"[1:a:{ac}]atrim={ini:.3f}:{fim:.3f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-2[a1];" if ac is not None
          else f"anullsrc=r=48000:cl=stereo,atrim=0:{dc:.3f}[a1];")
    f += a0 + a1 + "[v0][a0][v1][a1]concat=n=2:v=1:a=1[vc][ac];[vc][2:v]overlay=0:0:shortest=1[v];[ac]loudnorm=I=-14:TP=-1[a]"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(inicio), "-i", str(clip), "-loop", "1", "-i", str(png), "-filter_complex", f,
                        "-map", "[v]", "-map", "[a]", "-t", f"{di + dc:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                        "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(saida)])
    return r.returncode == 0 and saida.exists()


# ------------------------------------------------------------------ modo TROCA (link de meme: só troca a pessoa)
def fps_de(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    try:
        a_, b_ = r.stdout.strip().split("/")
        return round(float(a_) / float(b_), 3) or 30
    except Exception:
        return 30


def _quadros_cor(clip, t0, t1, n):
    import cv2
    import numpy as np

    fr = []
    for k in range(n):
        t = t0 + (t1 - t0) * (k + 0.5) / n
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                           capture_output=True)
        q = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR) if r.stdout else None
        if q is not None:
            fr.append(q)
    return fr


def _copia_texto(fr, letra, caixa, saida, raio_max=10):
    """recorta o texto do original PIXEL A PIXEL (mesma fonte, cor, contorno e sombra): mediana dos quadros, só onde a
    imagem fica parada perto das letras e é letra ou contorno (claro ou escuro) — o fundo que mexe fica de fora."""
    import cv2
    import numpy as np

    a = np.array(fr)
    med = np.median(a, axis=0).astype(np.uint8)
    cinza = a.astype(np.float32).mean(axis=3)
    desvio = cinza.std(axis=0)
    gm = cinza.mean(axis=0)
    H, W = letra.shape
    x0, y0, x1, y1 = caixa
    n, _, st, _ = cv2.connectedComponentsWithStats(letra, 8)
    alt = float(np.median([st[i, 3] for i in range(1, n)])) if n > 1 else 20.0
    raio = int(max(2, min(raio_max, round(alt * 0.14))))
    perto = cv2.dilate(letra, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * raio + 1, 2 * raio + 1))).astype(bool)
    colado = cv2.dilate(letra, np.ones((3, 3), np.uint8)).astype(bool)  # borda antisserrilhada da própria letra
    parado = desvio < 16
    tom = (gm < 95) | (gm > 165) | colado
    m = np.zeros((H, W), np.float32)
    sel = perto & parado & tom
    m[y0:y1, x0:x1] = sel[y0:y1, x0:x1]
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    m = np.minimum(m, cv2.GaussianBlur(m, (0, 0), 0.7) * 1.4).clip(0, 1)
    cv2.imwrite(str(saida), np.dstack([med, (m * 255).astype(np.uint8)]))
    return saida


def texto_do_original(clip, t0, t1, saida):
    """O texto do meme EXATAMENTE como no original (mesma fonte, tamanho e lugar): ele fica parado sobre o lance
    que se mexe, então o mínimo de vários quadros guarda só o que é fixo. Ficam as linhas centralizadas do topo
    (o placar da TV, também fixo, fica de fora). Devolve o PNG transparente do tamanho do vídeo, ou None."""
    import cv2
    import numpy as np

    fr = []
    for k in range(8):
        t = t0 + (t1 - t0) * (k + 0.5) / 8
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
        q = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_GRAYSCALE) if r.stdout else None
        if q is not None:
            fr.append(q)
    if len(fr) < 3:
        return None
    mn = np.array(fr).min(axis=0)
    H, W = mn.shape
    claro = mn > 150
    linhas, ini = [], None
    for y in range(int(H * 0.6)):
        v = claro[y].sum() > 2
        if v and ini is None:
            ini = y
        elif not v and ini is not None:
            if y - ini >= 6:
                xs = np.where(claro[ini:y].any(axis=0))[0]
                linhas.append((ini, y, xs.min(), xs.max()))
            ini = None
    # junta pedaços da mesma linha (acentos, "ç") e fica com o bloco centralizado do topo.
    # Uma linha CURTA no meio do texto ("1 mês isolados") não encerra o bloco — antes ela cortava a legenda pela
    # metade; o bloco só termina quando há um buraco de verdade entre as linhas.
    bloco = []
    for l in linhas:
        larg = l[3] - l[2]
        centrada_ = abs(l[2] - (W - 1 - l[3])) < W * 0.14
        if not centrada_ or larg <= W * (0.07 if bloco else 0.12):
            continue   # ruído (sombra, acento solto, placar fora do centro): pula, não encerra
        if bloco and l[0] - bloco[-1][1] > 3 * max(10, np.median([b[1] - b[0] for b in bloco])):
            break      # buraco grande: o que vem depois é outro texto (legenda de baixo, @ do perfil)
        bloco.append(l)
    if not bloco:
        return None
    y0, y1 = max(0, bloco[0][0] - 16), min(H, bloco[-1][1] + 16)   # folga: o topo das letras saía cortado
    x0, x1 = max(0, min(b[2] for b in bloco) - 16), min(W, max(b[3] for b in bloco) + 16)
    cores = _quadros_cor(clip, t0, t1, 8)
    if len(cores) >= 3:
        letra = np.zeros((H, W), np.uint8)
        letra[y0:y1, x0:x1] = claro[y0:y1, x0:x1]
        # faixa preta do original: a letra sai do preto sem perder nada (borda suave igual à original, cor de cada
        # letra mantida) + sombra suave embaixo, como o texto do TikTok/CapCut — lê na parede clara do seu começo,
        # sem o contorno serrilhado (que deixava o texto "borrado")
        med = np.median(np.array(cores), axis=0).astype(np.float32)
        g = med.mean(axis=2)
        alfa = np.zeros((H, W), np.float32)
        perto = cv2.dilate(letra, np.ones((7, 7), np.uint8)).astype(bool)
        alfa[y0:y1, x0:x1] = np.clip((g[y0:y1, x0:x1] - 35) / 165, 0, 1)
        alfa *= perto
        cor = np.clip(med / np.maximum(alfa, 0.25)[..., None], 0, 255)
        sombra = cv2.GaussianBlur(cv2.dilate(alfa, np.ones((3, 3), np.uint8)), (0, 0), 2.2)
        sombra = np.roll(sombra, (2, 1), axis=(0, 1)) * 0.75
        a_final = alfa + sombra * (1 - alfa)
        rgb = cor * (alfa / np.maximum(a_final, 1e-3))[..., None]  # sombra preta: só a letra tem cor
        cv2.imwrite(str(saida), np.dstack([rgb.astype(np.uint8), (a_final * 255).astype(np.uint8)]))
        return saida
    alfa = np.zeros((H, W), np.float32)
    alfa[y0:y1, x0:x1] = np.clip((mn[y0:y1, x0:x1].astype(np.float32) - 60) / 140, 0, 1)
    sombra = cv2.GaussianBlur(cv2.dilate(alfa, np.ones((5, 5), np.uint8)), (0, 0), 5) * 0.85
    a_final = np.maximum(alfa, sombra)
    cor = (alfa / np.maximum(a_final, 1e-3) * 255).clip(0, 255).astype(np.uint8)
    cv2.imwrite(str(saida), np.dstack([cor, cor, cor, (a_final * 255).astype(np.uint8)]))
    return saida


# ------------------------------------------------------------------ meme do link dele: onde está a OUTRA PESSOA
FPS_ANALISE = 30


def cenas_do_video(f):
    """divide o vídeo em cenas: corte seco (a imagem troca de uma vez) ou passagem pelo preto (fade).
    Devolve (cenas, quadros): cenas = [{"a", "b", "fade_in", "fade_out"}] em segundos; quadros = miniaturas BGR."""
    import numpy as np

    W, H = 72, 128
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-vf", f"fps={FPS_ANALISE},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                       capture_output=True)
    a = np.frombuffer(r.stdout, np.uint8)
    n = a.size // (W * H * 3)
    if n < FPS_ANALISE:
        return [], None
    a = a[: n * W * H * 3].reshape(n, H, W, 3)
    g = a.astype(np.float32).mean(axis=3)
    luz = g.mean(axis=(1, 2))
    dif = np.concatenate([[0.0], np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))])
    med = float(np.median(dif[1:])) + 1e-3
    marcas = []  # (início, fim) em quadros de cada troca de cena
    # passagens pelo preto: quadros bem mais escuros que o segundo anterior
    i = 1
    while i < n:
        base = float(np.median(luz[max(0, i - FPS_ANALISE):i])) if i > 3 else float(luz[0])
        if base > 25 and luz[i] < 0.55 * base:
            j = i
            while j < n and luz[j] < 0.75 * base:
                j += 1
            k = i
            while k > 1 and luz[k - 1] < 0.92 * base and luz[k - 1] < luz[k - 2] + 2:
                k -= 1  # começo do escurecimento
            if j - k <= FPS_ANALISE * 1.5:
                marcas.append((k, j))
            i = j + 1
        else:
            i += 1
    # cortes secos
    for i in range(1, n):
        if dif[i] > max(28.0, 5 * med) and not any(m0 - 2 <= i <= m1 + 2 for m0, m1 in marcas):
            marcas.append((i, i))
    marcas.sort()
    cenas, ini, fade_in = [], 0, False
    for m0, m1 in marcas:
        if m0 - ini >= max(3, FPS_ANALISE // 6):
            cenas.append({"a": ini / FPS_ANALISE, "b": m0 / FPS_ANALISE, "fade_in": fade_in, "fade_out": m1 > m0, "q": (ini, m0)})
        elif cenas and m1 > m0:
            cenas[-1]["fade_out"] = True
        ini, fade_in = m1, m1 > m0
    if n - ini >= 3:
        cenas.append({"a": ini / FPS_ANALISE, "b": n / FPS_ANALISE, "fade_in": fade_in, "fade_out": False, "q": (ini, n)})
    # cena colada em outra (corte sem fade): o fim de uma é o começo da outra
    for c0, c1 in zip(cenas[:-1], cenas[1:]):
        if not c0["fade_out"] and not c1["fade_in"]:
            c0["b"] = c1["a"]
    return cenas, a


def _hist_sem_preto(img):
    """histograma de cor SEM as faixas pretas/escuras (memes com barra preta pareciam todos iguais)"""
    import cv2
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = (hsv[:, :, 2] > 40).astype("uint8")
    if m.sum() < m.size * 0.03:
        m = None
    return cv2.calcHist([hsv], [0, 1], m, [18, 8], [0, 180, 0, 256])


def _parecida(a, c0, c1):
    """quanto a cena c1 parece com a c0 (mesmo lugar / mesma pessoa): histograma de cor"""
    import cv2

    def hist(c):
        q0, q1 = c["q"]
        h = sum(_hist_sem_preto(x) for x in a[q0:q1:max(1, (q1 - q0) // 6)])
        return cv2.normalize(h, h).flatten()
    return float(cv2.compareHist(hist(c0), hist(c1), cv2.HISTCMP_CORREL))


def partes_da_pessoa(clip, tmp, inicio=0.0):
    """Meme do link dele (outra pessoa + lance, podendo voltar a pessoa no meio): marca cada cena como "pessoa"
    (a parte que vira o seu começo) ou "lance". Gemini olhando uma foto de cada cena; sem Gemini: a 1ª cena é a
    pessoa e as cenas parecidas com ela (mesmo lugar) também."""
    import cv2

    cenas, a = cenas_do_video(clip)
    if len(cenas) < 2:
        # SEM CORTE DE CENA ACHADO (corte suave, zoom, crossfade): era aqui que o link dele morria com "não achei
        # onde está a pessoa e onde está o lance". Mas o analisa_viral JÁ mediu onde o lance começa — parto ali.
        d = dur(clip)
        if inicio and 0.6 < inicio < d - 0.8:
            log(f"   sem corte de cena no vídeo: parto no começo do lance ({inicio:.1f}s)")
            return [{"a": 0.0, "b": inicio, "tipo": "pessoa"}, {"a": inicio, "b": d, "tipo": "lance"}]
        return cenas
    tipos = None
    if os.environ.get("GEMINI_API_KEY"):
        partes = [{"text": "Este vídeo é um MEME de futebol: uma pessoa se grava (selfie/celular, situação do dia a dia, "
                           "com legenda tipo 'eu quando...') e depois entra o LANCE (jogo de futebol, transmissão, jogador, "
                           "torcida, outro vídeo viral). Às vezes a pessoa volta no meio ou no fim. Abaixo vai uma foto de "
                           "cada cena, em ordem. Para cada cena responda \"pessoa\" (a parte gravada pela pessoa do meme) ou "
                           "\"lance\" (o resto). Responda JSON {\"cenas\": [\"pessoa\", \"lance\", ...]} com "
                           f"exatamente {len(cenas)} itens."}]
        for k, c in enumerate(cenas):
            ok, jpg = cv2.imencode(".jpg", cv2.resize(_quadro_cor(clip, (c["a"] + c["b"]) / 2), (216, 384)))
            partes.append({"text": f"cena {k + 1} ({c['a']:.1f}s a {c['b']:.1f}s):"})
            partes.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(jpg.tobytes()).decode()}})
        g = gemini_json(partes, temperatura=0)
        t = (g or {}).get("cenas")
        if isinstance(t, list) and len(t) == len(cenas) and all(str(x).lower() in ("pessoa", "lance") for x in t):
            tipos = [str(x).lower() for x in t]
            log("   cenas (Gemini): " + ", ".join(f"{c['a']:.1f}-{c['b']:.1f}s {x}" for c, x in zip(cenas, tipos)))
    if tipos is None:
        tipos = ["pessoa"] + ["pessoa" if _parecida(a, cenas[0], c) > 0.8 else "lance" for c in cenas[1:]]
        log("   cenas: " + ", ".join(f"{c['a']:.1f}-{c['b']:.1f}s {x}" for c, x in zip(cenas, tipos)))
    for c, x in zip(cenas, tipos):
        c["tipo"] = x
    return cenas


def _quadro_cor(f, t):
    import cv2
    import numpy as np

    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(f), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True)
    q = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR) if r.stdout else None
    return q if q is not None else np.zeros((384, 216, 3), np.uint8)


def troca_partes(inicio, i_ini, i_fim, clip, cenas, pngs, saida):
    """Igual ao original (texto, música inteira, lances); TODA cena da outra pessoa (no começo, no meio ou no fim)
    vira um pedaço do seu começo, com a legenda que estava nela. Fade da cena original = fade no seu pedaço."""
    inicio = inicio_sdr(inicio)
    W, H = tamanho(clip)
    W, H = W // 2 * 2, H // 2 * 2
    F = fps_de(clip)
    dc = dur(clip)
    di_total = dur(inicio)
    i_fim = min(di_total, i_fim) if i_fim else di_total
    cobre = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    # cada cena vai até a fronteira com a próxima; a transição do original (fade pelo preto) fica do lado da pessoa,
    # para o rosto dela nunca aparecer escurecendo
    fronteiras = []
    for c0, c1 in zip(cenas[:-1], cenas[1:]):
        fronteiras.append(c0["b"] if (c1["tipo"] == "pessoa" and c0["tipo"] != "pessoa") else c1["a"])
    limites = [0.0] + fronteiras + [dc]
    blocos = []
    for k, c in enumerate(cenas):
        a_, b = limites[k], limites[k + 1]
        if blocos and blocos[-1]["tipo"] == c["tipo"] and c["tipo"] == "lance":
            blocos[-1]["b"] = b
            continue
        blocos.append({"tipo": c["tipo"], "a": a_, "b": b, "k": k,
                       "fade_in": c["fade_in"] and k > 0, "fade_out": c["fade_out"] and k < len(cenas) - 1})
    blocos = [x for x in blocos if x["b"] - x["a"] > 0.02]
    png0 = next((pngs.get(bl["k"]) for bl in blocos if bl["tipo"] == "pessoa" and pngs.get(bl["k"])), None)
    cobre = enquadra(inicio, W, H, i_ini, i_fim, fim_do_texto(png0, H) if png0 else None)
    entradas = ["-i", str(inicio), "-i", str(clip)]
    f, nomes, cursor, ip = [], [], i_ini, 2
    seu_total = max(0.3, i_fim - i_ini)
    for j, bl in enumerate(blocos):
        d = bl["b"] - bl["a"]
        if bl["tipo"] == "pessoa":
            if cursor + d > i_fim and d <= seu_total:
                cursor = i_ini  # acabou o seu começo: volta para o início dele
            fim_seu = min(i_fim, cursor + d)
            falta = max(0.0, d - (fim_seu - cursor))
            fades = ""
            if bl["fade_in"]:
                fades += f",fade=t=in:st=0:d={min(0.35, d / 3):.3f}"
            if bl["fade_out"]:
                fades += f",fade=t=out:st={max(0.0, d - min(0.35, d / 3)):.3f}:d={min(0.35, d / 3):.3f}"
            f.append(f"[0:v]trim={cursor:.3f}:{fim_seu:.3f},setpts=PTS-STARTPTS,{cobre},fps={F},setsar=1,format=yuv420p"
                     f"{f',tpad=stop_mode=clone:stop_duration={falta:.3f}' if falta > 0.01 else ''},trim=duration={d:.3f}[pv{j}]")
            png = pngs.get(bl["k"])
            if png:
                entradas += ["-loop", "1", "-i", str(png)]
                f.append(f"[pv{j}][{ip}:v]overlay=0:0:format=auto:shortest=1{fades},format=yuv420p[s{j}]")
                ip += 1
            else:
                f.append(f"[pv{j}]null{fades}[s{j}]")
            cursor = fim_seu
        else:
            f.append(f"[1:v]trim={bl['a']:.3f}:{bl['b']:.3f},setpts=PTS-STARTPTS,{cor_sdr(clip)}scale={W}:{H},fps={F},setsar=1,format=yuv420p[s{j}]")
        nomes.append(f"[s{j}]")
    f.append(f"{''.join(nomes)}concat=n={len(nomes)}:v=1:a=0[v]")
    ac = audio_bom(clip)
    cmd = ["ffmpeg", "-v", "error", "-y"] + entradas + ["-filter_complex", ";".join(f), "-map", "[v]"]
    cmd += (["-map", f"1:a:{ac}", "-c:a", "aac", "-b:a", "192k"] if ac is not None else [])
    cmd += ["-t", f"{dc:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
            "-color_trc", "bt709", "-movflags", "+faststart", str(saida)]
    r = subprocess.run(cmd)
    return r.returncode == 0 and saida.exists()


def _palavras(png):
    import unicodedata
    t = unicodedata.normalize("NFKD", ler_texto(Path(png)) or "").encode("ascii", "ignore").decode().lower()
    return [w for w in re.findall(r"[a-z0-9]+", t) if len(w) >= 2]


def melhor_legenda(pg, barra):
    """legenda achada na cena da pessoa × texto da barra do lance (meme de barra = o MESMO texto).
    Se a da cena saiu pela metade (só a última linha, letra branca em parede clara), fica a da barra, inteira."""
    if not pg or not barra:
        return pg or barra
    try:
        a, b = _palavras(pg), _palavras(barra)
    except Exception:
        return pg
    if not b:
        return pg
    if not a:
        return barra
    dentro = sum(1 for w in a if any(w in x or x in w for x in b)) / len(a)
    if dentro >= 0.6 and sum(map(len, a)) < 0.8 * sum(map(len, b)):
        log(f"   legenda da cena pela metade ({len(a)} de {len(b)} palavras) → texto inteiro do lance")
        return barra
    return pg


def legenda_parada(clip, t0, t1, saida):
    """A legenda da parte da pessoa EXATAMENTE como no original, em qualquer altura da tela: letras claras em todos
    os quadros (mínimo) E com borda forte (parede lisa e lâmpada não entram). PNG transparente do tamanho do vídeo."""
    import cv2
    import numpy as np

    fr = []
    for k in range(10):
        t = t0 + (t1 - t0) * (k + 0.5) / 10
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                           capture_output=True)
        q = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR) if r.stdout else None
        if q is not None:
            fr.append(q.max(axis=2))  # o canal mais forte: letra branca, amarela, laranja ou verde conta igual
    if len(fr) < 4:
        return None
    mn = np.array(fr).min(axis=0)
    mx = np.array(fr).max(axis=0)
    H, W = mn.shape
    claro = (mn > 185).astype(np.uint8)
    borda = cv2.dilate((cv2.morphologyEx(mn, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 60).astype(np.uint8), np.ones((3, 3), np.uint8))
    # contorno escuro parado (o traço preto da legenda): pega letra branca em cima de parede branca
    contorno = cv2.dilate((mx < 100).astype(np.uint8), np.ones((9, 9), np.uint8))

    def centrada(l):
        """legenda de meme: linha centralizada, letras de altura parecida (parede/grade/placar não passam)"""
        xs0 = min(c[0] for c in l["c"])
        xs1 = max(c[0] + c[2] for c in l["c"])
        hs = np.array([c[3] for c in l["c"]], np.float32)
        return (abs((xs0 + xs1) / 2 - W / 2) < W * 0.15 and xs1 - xs0 > W * 0.12
                and float(hs.std() / max(1.0, hs.mean())) < 0.45)

    def melhor_bloco(letra):
        n, _, st, _ = cv2.connectedComponentsWithStats(letra, 8)
        comps = [st[i] for i in range(1, n) if 3 <= st[i, 3] <= H * 0.05 and st[i, 2] <= W * 0.08 and st[i, 4] >= 6]
        if len(comps) < 6:
            return None
        # linhas de texto: centro das letras agrupado; fica o bloco (linhas vizinhas) com mais letras
        alt = float(np.median([c[3] for c in comps]))
        comps.sort(key=lambda c: c[1] + c[3] / 2)
        linhas = []
        for c in comps:
            yc = c[1] + c[3] / 2
            if linhas and yc - linhas[-1]["y"] < alt * 0.8:
                linhas[-1]["c"].append(c)
                linhas[-1]["y"] = np.mean([x[1] + x[3] / 2 for x in linhas[-1]["c"]])
            else:
                linhas.append({"y": yc, "c": [c]})
        linhas = [l for l in linhas if len(l["c"]) >= 4 and centrada(l)]
        if not linhas:
            return None
        blocos = [[linhas[0]]]
        for l in linhas[1:]:
            if l["y"] - blocos[-1][-1]["y"] < alt * 3.6:
                blocos[-1].append(l)
            else:
                blocos.append([l])
        return max(blocos, key=lambda b: sum(len(l["c"]) for l in b))

    # duas leituras (letra com borda / letra com contorno escuro): fica a que achou MAIS texto (mais linhas e letras)
    opcoes = []
    for letra in (claro & borda, claro & contorno, claro & (borda | contorno)):
        b = melhor_bloco(letra)
        if b:
            opcoes.append((len(b), sum(len(l["c"]) for l in b), b, letra))
    if not opcoes:
        return None
    _, _, bloco, letra = max(opcoes, key=lambda o: (o[0], o[1]))
    cs = [c for l in bloco for c in l["c"]]
    x0, x1 = max(0, min(c[0] for c in cs) - 12), min(W, max(c[0] + c[2] for c in cs) + 12)
    y0, y1 = max(0, min(c[1] for c in cs) - 12), min(H, max(c[1] + c[3] for c in cs) + 12)
    cores = _quadros_cor(clip, t0, t1, 10)
    if len(cores) >= 4:
        return _copia_texto(cores, letra, (x0, y0, x1, y1), saida)
    alfa = np.zeros((H, W), np.float32)
    perto = cv2.dilate(letra, np.ones((7, 7), np.uint8)).astype(bool)
    reg = np.clip((mn.astype(np.float32) - 150) / 70, 0, 1)
    alfa[y0:y1, x0:x1] = np.where(perto[y0:y1, x0:x1], reg[y0:y1, x0:x1], 0)
    sombra = cv2.GaussianBlur(cv2.dilate(alfa, np.ones((3, 3), np.uint8)), (0, 0), 3) * 0.6
    a_final = np.maximum(alfa, sombra)
    cor = (alfa / np.maximum(a_final, 1e-3) * 255).clip(0, 255).astype(np.uint8)
    cv2.imwrite(str(saida), np.dstack([cor, cor, cor, (a_final * 255).astype(np.uint8)]))
    return saida


def png_vazio(clip, saida):
    import cv2
    import numpy as np

    W, H = tamanho(clip)
    cv2.imwrite(str(saida), np.zeros((H, W, 4), np.uint8))
    return saida


def ler_texto(png):
    """o texto do meme em letras (para a legenda): tesseract (português) ou o Gemini lendo a imagem"""
    import cv2

    img = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
    if img is None:
        return ""
    import numpy as np

    cinza = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    preto = np.where(img[:, :, 3] > 128, 255 - cinza, 255).astype(np.uint8)  # letra clara → preta no branco (contorno some)
    tmp = Path(png).with_name("ocr.png")
    cv2.imwrite(str(tmp), preto)
    if shutil.which("tesseract"):
        langs = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
        r = subprocess.run(["tesseract", str(tmp), "-", "-l", "por" if "por" in langs else "eng", "--psm", "6"], capture_output=True, text=True)
        txt = re.sub(r"\s+", " ", r.stdout).strip()
        if len(txt) > 5:
            return txt
    g = gemini_json([{"text": "Transcreva exatamente o texto desta imagem (português, mantenha abreviações como 'q' e 'ent'). JSON {\"texto\": \"...\"}"},
                     {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(tmp.read_bytes()).decode()}}])
    return (g or {}).get("texto", "")


# ------------------------------------------------------------------ conferências (antes e depois do render)
def _palavras_txt(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return [w for w in re.findall(r"[a-z0-9]+", t) if len(w) >= 2]


def _bate(a, b):
    """quanto do texto b aparece em a (0..1), palavra a palavra"""
    pa, pb = _palavras_txt(a), _palavras_txt(b)
    if not pb:
        return 1.0 if not pa else 0.0
    return sum(1 for w in pb if any(w == x or (len(w) > 3 and (w in x or x in w)) for x in pa)) / len(pb)


def _jpg64(img, w=432):
    import cv2
    h = int(img.shape[0] * w / img.shape[1])
    ok, jpg = cv2.imencode(".jpg", cv2.resize(img, (w, h)), [cv2.IMWRITE_JPEG_QUALITY, 88])
    return {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(jpg.tobytes()).decode()}}


def le_tela(clip, t):
    """o texto do meme escrito na tela nesse instante (Gemini). Vazio quando não dá para ler."""
    q = _quadro_cor(clip, t)
    if q is None:
        return ""
    g = gemini_json([{"text": "Transcreva EXATAMENTE o texto de legenda/meme escrito nesta imagem (o texto grande, normalmente no "
                              "topo; ignore placar, marca d'água e @ de perfil). Mantenha abreviações e pontuação. "
                              "JSON {\"texto\": \"...\"} (vazio se não tiver texto)."}, _jpg64(q, 540)], temperatura=0)
    return re.sub(r"\s+", " ", (g or {}).get("texto", "")).strip()


def le_texto_duplo(png, quadro_original=None):
    """CONFERÊNCIA DE LETRA (2 leituras): o PNG do texto pelo tesseract/Gemini + o Gemini lendo o quadro ORIGINAL
    (o texto como está na tela). Devolve (texto, ok): ok = as duas leituras batem (≥ 85%)."""
    l1 = ler_texto(png) if png else ""
    l2 = ""
    if quadro_original is not None:
        g = gemini_json([{"text": "Transcreva EXATAMENTE o texto de legenda/meme escrito nesta imagem (o texto grande, normalmente no "
                                  "topo; ignore placar, marca d'água e @ de perfil). Mantenha abreviações e pontuação. "
                                  "JSON {\"texto\": \"...\"} (vazio se não tiver texto)."}, _jpg64(quadro_original, 540)],
                        temperatura=0)
        l2 = re.sub(r"\s+", " ", (g or {}).get("texto", "")).strip()
    if l1 and l2:
        ok = min(_bate(l1, l2), _bate(l2, l1)) >= 0.85
        if not ok:
            # o PNG ser o COMEÇO do texto da tela = o recorte cortou o resto (é o caso que estraga o vídeo).
            # Palavras trocadas, sem faltar o fim, costuma ser só o OCR lendo mal — o PNG está inteiro.
            n1 = re.sub(r"\s+", " ", l1).strip().lower()
            n2 = re.sub(r"\s+", " ", l2).strip().lower()
            if len(n2) > len(n1) * 1.25 and n2.startswith(n1[: max(8, int(len(n1) * 0.7))]):
                log(f"   conferência de letra: o recorte pegou SÓ O COMEÇO do texto — falta {n2[len(n1):].strip()!r}")
            else:
                log(f"   conferência de letra: leituras diferentes (pode ser o OCR) — PNG: {l1!r} × tela: {l2!r}")
        return (l2 if len(l2) >= len(l1) * 0.8 else l1), ok
    return (l1 or l2), bool(l1 or l2)


def _cala_opencv():
    """tira os avisos "Targets are not supported by the new graph engine" do YuNet, que enchiam o registro"""
    try:
        import cv2

        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        pass


def _rosto(img):
    """tem rosto de gente na imagem? (YuNet; sem o modelo: Haar do OpenCV)"""
    import cv2

    _cala_opencv()
    modelo = TOOLS.parent / "yunet.onnx"
    try:
        if modelo.exists():
            h, w = img.shape[:2]
            d = cv2.FaceDetectorYN.create(str(modelo), "", (w, h), 0.7)
            _, f = d.detect(img)
            return f is not None and len(f) > 0 and any(x[2] * x[3] > w * h * 0.004 for x in f)
        c = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return len(c.detectMultiScale(g, 1.1, 6, minSize=(max(24, img.shape[1] // 14),) * 2)) > 0
    except Exception:
        return False


def confere_cenas(clip, cenas):
    """2ª CONFERÊNCIA das cenas (antes de montar): a mesma pessoa que aparece no começo e VOLTA no meio/fim também
    tem que ser coberta pelo seu começo. Cena marcada "lance" que é o mesmo lugar/pessoa de uma cena "pessoa" (cor
    parecida + rosto) → o Gemini compara as duas fotos; se for a mesma pessoa, vira "pessoa"."""
    import cv2
    import numpy as np
    pessoas = [c for c in cenas if c.get("tipo") == "pessoa"]
    if not pessoas:
        return cenas
    fotos = {id(c): _quadro_cor(clip, (c["a"] + c["b"]) / 2) for c in cenas}

    def hist(img):
        h = _hist_sem_preto(cv2.resize(img, (108, 192)))
        return cv2.normalize(h, h).flatten()

    def mesma(c, ref):
        g = gemini_json([{"text": "Foto 1: a pessoa de um meme (gravação dela). Foto 2: outra cena do MESMO vídeo. A foto 2 mostra a "
                                  "MESMA pessoa/gravação da foto 1 (mesmo lugar, mesma pessoa) ou é outra coisa (jogo de "
                                  "futebol, desenho, filme, outra pessoa, outro vídeo)? JSON {\"mesma_pessoa\": true|false}"},
                         _jpg64(ref), _jpg64(fotos[id(c)])], temperatura=0)
        return (g or {}).get("mesma_pessoa") if g else None
    ref = fotos[id(pessoas[0])]
    h0 = hist(ref)
    # cena marcada "pessoa" que não parece nada com a 1ª (outro lugar, sem rosto): confere — desenho/lance escuro
    # não pode virar o seu começo
    for c in pessoas[1:]:
        sim = float(cv2.compareHist(hist(fotos[id(c)]), h0, cv2.HISTCMP_CORREL))
        if sim < 0.5 and not _rosto(fotos[id(c)]):
            r = mesma(c, ref)
            if r is not True:
                c["tipo"] = "lance"
                log(f"   conferência das cenas: {c['a']:.1f}-{c['b']:.1f}s não é a pessoa (fica o original)")
    pessoas = [c for c in cenas if c.get("tipo") == "pessoa"]
    hp = [hist(fotos[id(c)]) for c in pessoas]
    for c in cenas:
        if c.get("tipo") != "lance" or c["b"] - c["a"] < 0.4:
            continue
        sim = max(float(cv2.compareHist(hist(fotos[id(c)]), h, cv2.HISTCMP_CORREL)) for h in hp)
        if sim < 0.75 or not _rosto(fotos[id(c)]):
            continue
        r = mesma(c, ref)
        if r is True or (r is None and sim > 0.9):
            c["tipo"] = "pessoa"
            log(f"   conferência das cenas: {c['a']:.1f}-{c['b']:.1f}s é a MESMA pessoa do começo → o seu começo entra aí também")
    _ = np
    return cenas


def confere_troca(saida, clip, cenas, texto_ref):
    """CONFERÊNCIA DO VÍDEO PRONTO (2 checagens) antes de ir para a fila:
    1) pixels: em cada cena da pessoa a outra pessoa SUMIU (o quadro é bem diferente do original) e cada lance ficou
       IGUAL ao original; o texto que fica na sua parte é o mesmo que continua na tela (leitura do quadro).
    2) Gemini olhando um quadro de cada cena: ninguém além de você nas partes trocadas, texto inteiro e igual.
    Devolve a lista de problemas (vazia = perfeito)."""
    import cv2
    import numpy as np
    probs = []

    def mini(img):
        g = cv2.cvtColor(cv2.resize(img, (54, 96), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
        return (g - g.mean()) / (g.std() + 1e-3)
    quadros = []
    for c in cenas:
        if c["b"] - c["a"] < 0.3:
            continue
        t = (c["a"] + c["b"]) / 2
        q_out, q_ori = _quadro_cor(saida, t), _quadro_cor(clip, t)
        q_ori = cv2.resize(q_ori, (q_out.shape[1], q_out.shape[0]))
        corr = float((mini(q_out) * mini(q_ori)).mean())
        if c["tipo"] == "pessoa" and corr > 0.8:
            probs.append(f"{c['a']:.1f}-{c['b']:.1f}s: a outra pessoa ainda aparece (quadro igual ao original)")
        if c["tipo"] == "lance" and corr < 0.6:
            probs.append(f"{c['a']:.1f}-{c['b']:.1f}s: o lance não ficou igual ao original")
        quadros.append((c, q_out))
    # letra pelos PIXELS (sem internet): as letras do texto no lance têm que estar inteiras (claras) na sua parte
    lances_ = sorted((c for c in cenas if c["tipo"] == "lance" and c["b"] - c["a"] >= 0.8), key=lambda c: c["b"] - c["a"], reverse=True)
    if lances_ and any(c["tipo"] == "pessoa" for c, _ in quadros):
        L = lances_[0]
        tmpd = Path(saida).with_suffix(".conf.png")
        try:
            png = texto_do_original(saida, L["a"] + 0.15, L["b"] - 0.15, tmpd)
            if png:
                alfa = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)[:, :, 3]
                letra = alfa > 230
                if letra.sum() > 200:
                    for c, q in quadros:
                        if c["tipo"] != "pessoa":
                            continue
                        g = cv2.cvtColor(cv2.resize(q, (alfa.shape[1], alfa.shape[0])), cv2.COLOR_BGR2GRAY)
                        cob = float((g[letra] > 170).mean())
                        if cob < 0.85:
                            probs.append(f"{c['a']:.1f}-{c['b']:.1f}s: texto incompleto na sua parte ({cob:.0%} das letras)")
        finally:
            tmpd.unlink(missing_ok=True)
    if texto_ref:
        for c, q in quadros:
            if c["tipo"] != "pessoa":
                continue
            g = gemini_json([{"text": "Transcreva EXATAMENTE o texto de legenda/meme escrito nesta imagem (ignore marca d'água e @). "
                                      "JSON {\"texto\": \"...\"}"}, _jpg64(q, 540)], temperatura=0, essencial=False)
            lido = (g or {}).get("texto") if g else None
            if lido is not None and _bate(lido, texto_ref) < 0.8:
                probs.append(f"{c['a']:.1f}-{c['b']:.1f}s: texto diferente do que continua na tela ({lido!r})")
    if quadros and os.environ.get("GEMINI_API_KEY"):
        partes = [{"text": "Conferência de um reel antes de postar. As fotos são um quadro de cada cena, em ordem; as marcadas "
                           "\"SUA PARTE\" deveriam mostrar SÓ o criador (homem de barba, @detto.galo) — nenhuma outra pessoa "
                           "gravando selfie; as marcadas \"LANCE\" são o vídeo original e ficam como estão. "
                           + (f"O texto do meme deve aparecer inteiro e igual em TODAS: {texto_ref!r}. " if texto_ref else "")
                           + "Aponte só problemas reais (texto cortado, embaralhado, faltando palavra, borrado; outra pessoa na "
                             "parte dele; imagem estourada/branca demais). JSON {\"ok\": true|false, \"problemas\": [\"...\"]}"}]
        for c, q in quadros:
            partes += [{"text": ("SUA PARTE" if c["tipo"] == "pessoa" else "LANCE") + f" ({c['a']:.1f}s):"}, _jpg64(q)]
        g = gemini_json(partes, temperatura=0, essencial=False)
        if g and g.get("ok") is False:
            probs += [f"Gemini: {x}" for x in (g.get("problemas") or ["não aprovou"])][:4]
    return probs


def legenda_viral(texto, info, peq, cfg):
    """legenda do POST (não o texto da tela): viral e ligada ao vídeo — nunca "meme"."""
    desc = re.sub(r"#\S+|@\S+", "", info.get("description") or "").strip()
    g = None
    if os.environ.get("GEMINI_API_KEY"):
        ex = "\n".join("- " + e for e in cfg.get("exemplos_legenda", [])[:6])
        partes = [{"text": f"""Você é o @detto.galo (memes de futebol, humor brasileiro). Escreva a LEGENDA DO POST deste reel.
Texto na tela: {texto!r}. Legenda original: {desc[:300]!r}.
Regras: 1 ou 2 frases curtas, com gancho, ligada à piada do vídeo, linguagem de torcedor, pode ter 1 emoji e uma pergunta
que faça comentar/marcar alguém. NÃO repita o texto da tela, não escreva "meme", sem hashtags.
{('Exemplos dele:' + chr(10) + ex) if ex else ''}
Responda JSON {{"legenda": "...", "tags": ["#...", "#...", "#..."]}}"""}]
        if peq:
            partes.append(parte_video(peq))
        g = gemini_json(partes, temperatura=0.9)
    leg = ((g or {}).get("legenda") or "").strip()
    if not leg or _palavras_txt(leg) == ["meme"]:
        if len(desc) > 8:
            leg = desc
        elif texto and texto.lower() != "meme":
            leg = random.choice(["Quem nunca? 😂 Marca aquele amigo", "Me diz que eu não sou o único 😂", "Fala a verdade, já foi você 😂",
                                 "Comenta aí se já passou por isso 😂"])
        else:
            leg = "Comenta aí o que você faria 😂"
    return leg, [t if t.startswith("#") else "#" + t for t in (g or {}).get("tags", []) if t]


def escolhe_inicio(texto, descr, usos_hoje, hist, por_nome):
    """o seu começo que combina com o texto do meme (Gemini); sem chave: o menos usado"""
    if texto and descr:
        g = gemini_json([{"text": f"Meme de futebol com o texto: {texto!r}. O começo do vídeo mostra uma pessoa reagindo. Qual destes começos "
                                  f"combina mais?\n" + "\n".join(f"- {k}: {d}" for k, d in descr) + "\nJSON {\"inicio\": \"<nome exato>\"}"}])
        if g and g.get("inicio") in por_nome:
            return g["inicio"]
    return sorted(por_nome, key=lambda k: (k in usos_hoje, hist["inicios"].get(k, {}).get("n", 0), random.random()))[0]


def _movimento(video, fps=10):
    """quanto cada quadro muda (0..255): o toque no botão de gravar faz TUDO tremer"""
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


def cortes_pontas(mv, fps=10, ini_min=1.0, fim_min=1.2):
    """(ini, fim) sem o botão: no começo, o tremor do toque; no FIM, a mão indo para o botão aparece ANTES do tremor
    (o movimento sobe e não desce mais) — corta antes disso. Mínimos: ini_min / fim_min."""
    import numpy as np
    n = len(mv)
    total = n / fps
    if n < fps * 3:
        return 0.0, total
    meio = mv[int(n * 0.25): int(n * 0.75)] if n > fps * 4 else mv
    base = float(np.median(meio))
    lim = max(base * 3.0, float(np.percentile(meio, 90)) * 1.5, 2.0)
    ini, fim = ini_min, total - fim_min
    for k in range(min(n, fps * 3)):
        if mv[k] > lim:
            ini = max(ini, (k + 1) / fps + 0.25)
    for k in range(n - 1, max(-1, n - fps * 3 - 1), -1):
        if mv[k] > lim:
            fim = min(fim, k / fps - 0.25)
    # mão chegando: nos últimos 4 s, o ponto a partir do qual o movimento fica acima de 1,6x o normal até o fim
    sobe = max(base * 1.6, 1.2)
    k0 = None
    for k in range(n - 1, max(-1, n - fps * 4 - 1), -1):
        janela = mv[max(0, k - 2): k + 1]
        if float(np.mean(janela)) > sobe:
            k0 = k
        else:
            if k0 is not None:
                break
    if k0 is not None and k0 / fps < fim:
        fim = min(fim, k0 / fps - 0.3)
    if fim - ini < 1.5:
        return (0.3, max(0.8, total - 0.3)) if total > 1.5 else (0.0, total)
    return round(ini, 2), round(fim, 2)


def cortes_botao(video):
    """onde a gravação começa e termina SEM o botão (mão chegando/celular tremendo): corta o tremor das pontas
    (até 3 s) e um mínimo fixo (0,8 s; 0,3 s em gravação curta). Guarda em inicios/.cortes.json."""
    import numpy as np
    video = Path(video)
    cache_f = video.parent / ".cortes.json"
    cache = le_json(cache_f, {})
    chave = f"v2|{video.name}|{video.stat().st_size}|{int(video.stat().st_mtime)}"
    if chave in cache:
        return tuple(cache[chave])
    mv, fps = _movimento(video), 10
    n = len(mv)
    total = n / fps if n else dur(video)
    if n < fps * 2:
        res = (0.0, total)
    else:
        curto = total < 5
        res = cortes_pontas(mv, fps, 0.3 if curto else 0.8, 0.5 if curto else 1.2)
    cache[chave] = list(res)
    grava_json(cache_f, cache)
    return res


def trecho_do_inicio(f):
    """o trecho do começo que entra: o .txt ao lado pode ter "trecho: 8.0-12.4"; SEMPRE sem o toque no botão de gravar
    do começo/fim (antes entrava você clicando na câmera)"""
    try:
        b0, b1 = cortes_botao(f)
    except Exception:
        b0, b1 = 0.0, None
    txt = f.with_suffix(".txt")
    if txt.exists():
        m = re.search(r"trecho\s*:?\s*([\d.,]+)\s*[-–]\s*([\d.,]+)", txt.read_text(encoding="utf-8"), re.I)
        if m:
            a_, b_ = float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
            a2, b2 = max(a_, b0), min(b_, b1) if b1 else b_
            return (a2, b2) if b2 - a2 >= 1.0 else (a_, b_)
    return b0, b1


def _rosto_caixa(img):
    """o maior rosto da imagem: (cx, cy, h) em fração do quadro, ou None"""
    import cv2
    h, w = img.shape[:2]
    modelo = TOOLS.parent / "yunet.onnx"
    try:
        if modelo.exists():
            d = cv2.FaceDetectorYN.create(str(modelo), "", (w, h), 0.7)
            _, f = d.detect(img)
            fs = [(x[0], x[1], x[2], x[3]) for x in (f if f is not None else [])]
        else:
            c = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            fs = list(c.detectMultiScale(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 1.1, 6, minSize=(max(24, w // 14),) * 2))
    except Exception:
        return None
    fs = [x for x in fs if x[2] * x[3] > w * h * 0.003]
    if not fs:
        return None
    x, y, fw, fh = max(fs, key=lambda q: q[2] * q[3])
    return ((x + fw / 2) / w, (y + fh / 2) / h, fh / h)


def fim_do_texto(png, H):
    """até onde vai o texto do topo (px) no PNG transparente; None se não tem texto"""
    try:
        from PIL import Image
        im = Image.open(png).convert("RGBA")
        a = im.split()[-1].crop((0, 0, im.width, int(im.height * 0.6)))
        bb = a.point(lambda v: 255 if v > 40 else 0).getbbox()
        return int(bb[3] * H / im.height) if bb else None
    except Exception:
        return None


def enquadra(inicio, W, H, i_ini, i_fim, fim_txt=None):
    """o seu começo no quadro W×H: rosto NO MEIO (na horizontal) e ABAIXO do texto do topo — com zoom quando precisa
    (até 1,6x). Antes era só "preencher o quadro" pelo centro: rosto de lado ou debaixo da escrita."""
    import numpy as np
    w0, h0 = tamanho(inicio)
    padrao = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    if not w0 or not h0:
        return padrao
    fim = i_fim if i_fim else dur(inicio)
    caixas = [c for c in (_rosto_caixa(q) for q in _quadros_cor(inicio, i_ini, max(i_ini + 0.2, fim), 6)) if c]
    if not caixas:
        return padrao
    cx, cy, fh = (float(np.median([c[k] for c in caixas])) for k in range(3))
    s0 = max(W / w0, H / h0)
    # onde o centro do rosto deve ficar: abaixo do texto (com folga de meio rosto), nunca acima de 38% da altura
    alvo_y = max(H * 0.38, (fim_txt or 0) + 0.65 * fh * h0 * s0 + 20)
    melhor = None
    for z in (1.0, 1.1, 1.2, 1.3, 1.45, 1.6):
        s = s0 * z
        sw, sh = int(round(w0 * s / 2)) * 2, int(round(h0 * s / 2)) * 2
        if fh * sh > H * 0.42 and z > 1.0:
            break  # rosto grande demais
        x = int(min(max(cx * sw - W / 2, 0), sw - W))
        y = int(min(max(cy * sh - alvo_y, 0), sh - H))
        erro_x = abs((cx * sw - x) - W / 2) / W
        topo_rosto = (cy * sh - y) - fh * sh / 2
        erro_y = max(0.0, ((fim_txt or 0) + 10 - topo_rosto) / H)
        nota = erro_x + erro_y * 2 + (z - 1) * 0.05
        if melhor is None or nota < melhor[0]:
            melhor = (nota, sw, sh, x // 2 * 2, y // 2 * 2)
        if erro_x < 0.04 and erro_y < 0.01:
            break
    nota, sw, sh, x, y = melhor
    if nota < 0.06:
        return f"scale={sw}:{sh},crop={W}:{H}:{x}:{y}"
    # rosto muito no canto/no topo da gravação: nem o zoom resolve → estende a borda (espelhada) para dar para
    # centralizar e descer o rosto para baixo do texto
    z = 1.25
    s = s0 * z
    sw, sh = int(round(w0 * s / 2)) * 2, int(round(h0 * s / 2)) * 2
    xi, yi = int(cx * sw - W / 2), int(cy * sh - alvo_y)
    pl, pt = max(0, -xi), max(0, -yi)
    pr, pb = max(0, xi + W - sw), max(0, yi + H - sh)
    pl, pr = min(pl, W // 3) // 2 * 2, min(pr, W // 3) // 2 * 2
    pt, pb = min(pt, H // 3) // 2 * 2, min(pb, H // 3) // 2 * 2
    x = min(max(xi + pl, 0), sw + pl + pr - W) // 2 * 2
    y = min(max(yi + pt, 0), sh + pt + pb - H) // 2 * 2
    return (f"scale={sw}:{sh},pad={sw + pl + pr}:{sh + pt + pb}:{pl}:{pt},"
            f"fillborders=left={pl}:right={pr}:top={pt}:bottom={pb}:mode=mirror,crop={W}:{H}:{x}:{y}")


# ------------------------------------------------------------------ principal
def agendar(hora, base, quantos):
    if os.name != "nt":
        sys.exit("O agendamento é do Windows (Agendador de Tarefas). Aqui rode com cron.")
    py = Path(sys.executable)
    bat = base / "fazer_reels.bat"
    bat.write_text(f'@echo off\ncd /d "{PONTE}"\n"{py}" "{Path(__file__).resolve()}" --pasta "{base}" --quantos {quantos} >> "{base / "reels.log"}" 2>&1\n', encoding="utf-8")
    r = subprocess.run(["schtasks", "/Create", "/F", "/SC", "DAILY", "/TN", "DETTO reels", "/ST", hora, "/TR", f'"{bat}"'], capture_output=True, text=True)
    print(r.stdout or r.stderr)
    if r.returncode == 0:
        print(f"Agendado: todo dia às {hora} ({quantos} reels). O PC precisa estar ligado. Log: {base / 'reels.log'}")
        print("Para tirar: schtasks /Delete /TN \"DETTO reels\" /F")


TRAVA = None


def trava_rodada(base, nome=".reels_rodando"):
    """só UM por vez: o painel e a tarefa do Windows rodando juntos faziam o mesmo trabalho 2 vezes. A trava é do
    sistema: some sozinha quando o processo acaba (até se ele travar/fechar).

    QUEM ESTÁ COM ELA (29/out): o arquivo guarda PID e hora de quem pegou. Um processo que trava e fica vivo (foi o
    que aconteceu com o canal.py: preso desde 20/10) deixava todas as rodadas seguintes morrerem caladas — agora dá
    para dizer no registro e no painel quem é, e o painel tem botão para encerrar."""
    f = open(Path(base) / nome, "a+")
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    try:   # deixa escrito quem pegou (a trava do sistema é no 1º byte; escrevo depois dele)
        f.seek(1)
        f.truncate(1)
        f.write(f" pid={os.getpid()} desde={dt.datetime.now():%d/%m %H:%M}\n")
        f.flush()
    except OSError:
        pass
    return f


def dono_da_trava(base, nome=".reels_rodando"):
    """quem está com a trava: (texto, pid) — para o registro e para o painel. Sem ninguém, ("", 0)."""
    f = Path(base) / nome
    if not f.exists():
        return "", 0
    try:
        txt = f.read_text(encoding="utf-8", errors="replace")[:200].strip()
    except OSError:
        txt = ""
    txt = txt.replace("\x00", "").strip()
    m = re.search(r"pid=(\d+)", txt)
    # SEM pid anotado não dá para saber desde quando: a data do ARQUIVO é de quando ele foi criado (podem ser
    # semanas), e dizer "rodada antiga desde 20/10" mandou a gente caçar um zumbi que não existia.
    return (txt if m else ""), (int(m.group(1)) if m else 0)


def main():
    ap = argparse.ArgumentParser(description="reels automáticos: seu começo + viral de futebol + texto")
    ap.add_argument("--pasta", default=str(pasta_padrao()))
    ap.add_argument("--quantos", type=int, default=10)
    ap.add_argument("--refazer-links", action="store_true", help="refaz mesmo os links que já viraram reels")
    ap.add_argument("--so-links", action="store_true", help="só os links do links.txt (não busca virais); o painel usa")
    ap.add_argument("--importar", action="store_true", help="só puxa os começos novos da pasta do Drive (Começo) e sai")
    ap.add_argument("--cookies", default=None, help="chrome, edge ou firefox (Instagram/TikTok/YouTube pedindo login)")
    ap.add_argument("--agendar", metavar="HH:MM", help="cria a tarefa diária no Windows")
    ap.add_argument("--clip", help="usa este vídeo (arquivo ou link) como viral em vez de buscar")
    ap.add_argument("--inicio", help="nome do começo (arquivo da pasta inicios, sem extensão) em vez de o Gemini escolher")
    ap.add_argument("--texto", help="texto da tela (senão o Gemini escreve)")
    ap.add_argument("--legenda", help="legenda do post")
    ap.add_argument("--tags", help="as 5 tags, separadas por espaço")
    ap.add_argument("--corte", help="trecho do viral, ex.: 9.5-21")
    ap.add_argument("--zoom", type=float, help="ampliação do viral horizontal (1 = largura toda; padrão até 1,33)")
    ap.add_argument("--modo", choices=["troca", "novo"], default="troca",
                    help="link de meme (outra pessoa + lance): troca = igual ao original só trocando a pessoa (padrão); novo = texto novo")
    ap.add_argument("--foco", type=float, default=0.5, help="onde cortar a lateral do viral ampliado (0 esq., 0,5 meio, 1 dir.)")
    a = ap.parse_args()
    base = Path(a.pasta)
    cfg = prepara_pasta(base)
    if a.agendar:
        return agendar(a.agendar, base, a.quantos)
    global TRAVA
    TRAVA = trava_rodada(base)
    if not TRAVA:
        log("outro reels.py já está rodando (painel ou tarefa do Windows) — saio para não fazer o mesmo link duas vezes")
        return
    global SDR_DIR
    SDR_DIR = base / "sdr"
    (base / "tmp").mkdir(exist_ok=True)
    h_ = le_json(base / "historico.json", {"usados": {}, "inicios": {}, "descricoes": {}})
    try:
        n_ = importa_inicios(base, cfg, h_, base / "tmp")
        if n_:
            log(f"{n_} começo(s) novo(s) do Drive prontos em inicios\\")
    except Exception as e:
        log(f"começos do Drive: {e}")
    if a.importar:
        return
    inicios = sorted(p for p in (base / "inicios").iterdir() if p.suffix.lower() in VIDEO_EXT)
    if not inicios:
        sys.exit(f"Grave seus começos e coloque em {base / 'inicios'} (o nome do arquivo diz o que você faz).")
    hist = le_json(base / "historico.json", {"usados": {}, "inicios": {}, "descricoes": {}})
    hoje = dt.date.today().isoformat()
    destino = base / "prontos" / hoje
    destino.mkdir(parents=True, exist_ok=True)
    tmp = base / "tmp"
    tmp.mkdir(exist_ok=True)
    feitos_hoje = len([p for p in destino.glob("*.mp4")])
    descr = [(p.stem, descricao_inicio(p, hist["descricoes"], tmp)) for p in inicios]
    grava_json(base / "historico.json", hist)
    por_nome = {p.stem: p for p in inicios}
    usos_hoje = [k for k, v in hist["inicios"].items() if v.get("ultimo") == hoje]

    # fila: links seus primeiro, depois os virais das hashtags
    links = list(dict.fromkeys(l.strip() for l in (base / "links.txt").read_text(encoding="utf-8").splitlines() if re.match(r"https?://", l.strip())))
    # link que JÁ virou reels (mesmo colado de outro jeito) não é refeito: sai do links.txt e segue para o próximo
    ja = links_ja_feitos(base, hist)
    if not a.refazer_links:
        repetidos = [u for u in links if chave_link(u) in ja]
        for u in repetidos:
            _tira_link(base, u, ok=True, hist=hist)
        if repetidos:
            log(f"{len(repetidos)} link(s) já viraram reels antes; pulei: " + ", ".join(u[:60] for u in repetidos[:4]))
            links = [u for u in links if chave_link(u) not in ja]
            grava_json(base / "historico.json", hist)
    fila = [{"url": u, "chave": None, "seu": True} for u in links]
    if a.so_links:
        if not links:
            log("nenhum link novo no links.txt")
            return
        a.quantos = max(a.quantos, len(links))
    if a.clip:
        fila = [{"url": a.clip, "chave": None, "seu": True}] if re.match(r"https?://", a.clip) else [{"arquivo": a.clip, "chave": f"arquivo:{Path(a.clip).name}", "seu": True}]
    buscou = False
    feitos = 0
    while feitos < a.quantos:
        if not fila:
            if buscou or a.clip or a.so_links:
                break
            log("procurando virais de futebol (Shorts mais vistos)...")
            fila = candidatos_youtube(cfg, hist["usados"])
            buscou = True
            log(f"   {len(fila)} candidatos")
            continue
        c = fila.pop(0)
        if c.get("chave") and c["chave"] in hist["usados"]:
            continue
        if c.get("arquivo"):
            clip, info = Path(c["arquivo"]), {"title": Path(c["arquivo"]).stem}
        else:
            log(f"\nbaixando {c['url']}")
            clip, info = baixa(c["url"], base / "baixados", a.cookies, base / "cookies.txt")
            if not clip:
                log(f"   não baixou: {info}")
                if c.get("seu"):
                    _tira_link(base, c["url"], ok=False, motivo=f"não baixou: {str(info)[:160]}")
                continue
        chave = c.get("chave") or chave_de(info, c.get("url"))
        if chave in hist["usados"] and not c.get("arquivo"):
            if c.get("seu"):
                _tira_link(base, c["url"], ok=True, hist=hist)
            continue
        if not c.get("seu") and not recente(info, cfg["max_dias"]):
            log("   velho demais, próximo")
            hist["usados"][chave] = {"pulado": "velho"}
            continue
        dclip = dur(clip)
        if not c.get("seu") and dclip > cfg["max_duracao"] + 1:
            log("   longo demais, próximo")
            hist["usados"][chave] = {"pulado": "longo"}
            continue
        # repost em formato meme: tira o começo do outro criador e a barra com o texto dele
        av = analisa_viral(clip)
        if av.get("inicio"):
            log(f"   o lance começa em {av['inicio']:.1f}s (antes é o outro criador: sai)")
        if av.get("faixa"):
            log(f"   faixa do vídeo {av['faixa'][0]:.2f}–{av['faixa'][1]:.2f} da altura (texto gravado do original fica de fora)")
        # LINK SEU no formato meme (outra pessoa + lance): fica IGUAL ao original — mesmo texto, música inteira,
        # mesmo lance —, só troca a parte da pessoa pelo seu começo
        if c.get("seu") and a.modo != "novo":
            # cada cena: pessoa (vira o seu começo, com a legenda dela) ou lance (fica igual). Link SEU nunca vira
            # o modo normal: se não der, avisa e não posta nada errado.
            cenas = confere_cenas(clip, partes_da_pessoa(clip, tmp, av.get("inicio") or 0.0))
            pessoas = [k for k, x in enumerate(cenas) if x.get("tipo") == "pessoa"]
            if (not pessoas or len(pessoas) == len(cenas)) and (av.get("inicio") or 0) > 0.6:
                # as cenas não separaram (tudo "pessoa" ou tudo "lance"), mas sabemos onde o lance começa
                ini_l = float(av["inicio"])
                if ini_l < dclip - 0.8:
                    log(f"   as cenas não separaram: uso o começo do lance ({ini_l:.1f}s) para partir")
                    cenas = [{"a": 0.0, "b": ini_l, "tipo": "pessoa"}, {"a": ini_l, "b": dclip, "tipo": "lance"}]
                    pessoas = [0]
            if not pessoas or len(pessoas) == len(cenas):
                log("   NÃO FIZ: não achei onde está a outra pessoa e onde está o lance neste vídeo"
                    " (para usar só o lance com texto novo: modo novo)")
                if c.get("url"):
                    _tira_link(base, c["url"], ok=False,
                               motivo="não achei onde está a outra pessoa e onde está o lance (para usar só o lance"
                                      " com texto novo, cole o link com modo novo)")
                continue
            # o texto que continua na tela no LANCE (mais longo): é o texto do meme, inteiro e limpo
            lances_ = sorted((x for x in cenas if x.get("tipo") == "lance" and x["b"] - x["a"] >= 0.8),
                             key=lambda x: x["b"] - x["a"], reverse=True)
            L = lances_[0] if lances_ else None
            texto_barra = texto_do_original(clip, L["a"] + 0.15, L["b"] - 0.15, tmp / "texto_original.png") if L else None
            def monta_pngs(usar_barra):
                out = {}
                for k in pessoas:
                    x = cenas[k]
                    m = min(0.15, (x["b"] - x["a"]) / 5)
                    pg = None
                    if not (usar_barra and texto_barra) and x["b"] - x["a"] >= 0.6:
                        pg = legenda_parada(clip, x["a"] + m, x["b"] - m, tmp / f"legenda_{k}.png")
                    # meme de barra: o texto da barra é o do meme (inteiro e limpo); a legenda achada na cena da
                    # pessoa sai pela metade/borrada quando a letra branca fica em cima de parede clara
                    out[k] = (texto_barra if usar_barra else None) or pg or texto_barra
                return out
            # O TEXTO MUDA NO MEIO DO VÍDEO? Tem meme em que a parte da pessoa diz uma coisa ("eu no primeiro dia de
            # aula...") e o lance diz outra ("O resto é história"). Aí o texto do lance NÃO serve para a sua parte:
            # cada cena fica com o texto DELA. (Quando os dois são o mesmo, o da barra continua melhor: sai limpo.)
            t_pessoa = (cenas[pessoas[0]]["a"] + cenas[pessoas[0]]["b"]) / 2
            lido_pessoa = le_tela(clip, t_pessoa)
            usar_barra = bool(texto_barra)
            if texto_barra and lido_pessoa:
                lido_lance = le_tela(clip, (L["a"] + L["b"]) / 2)
                if lido_lance and min(_bate(lido_pessoa, lido_lance), _bate(lido_lance, lido_pessoa)) < 0.7:
                    usar_barra = False
                    log(f"   o texto muda no meio do vídeo (sua parte: {lido_pessoa[:48]!r} × lance: {lido_lance[:48]!r})"
                        " — cada cena fica com o texto dela")
            pngs = monta_pngs(usar_barra)
            # CONFERÊNCIA DE LETRA: o texto recortado × o texto lido no quadro original (onde ele continua na tela)
            t_ref = (L["a"] + L["b"]) / 2 if (texto_barra and usar_barra) else t_pessoa
            png0 = next((pngs[k] for k in pessoas if pngs[k]), None)
            lido, letra_ok = le_texto_duplo(png0, _quadro_cor(clip, t_ref))
            if not letra_ok and lido:
                # 2ª tentativa de letra: o outro jeito de recortar; fica o que bate com o texto lido na tela
                alt = monta_pngs(not texto_barra or png0 != texto_barra)
                png1 = next((alt[k] for k in pessoas if alt[k]), None)
                if png1 and png1 != png0 and _bate(ler_texto(png1), lido) > _bate(ler_texto(png0), lido):
                    pngs = alt
                    log("   conferência de letra: usei o outro recorte (bate com o texto da tela)")
            texto = a.texto or lido or slug(info.get("title") or "", 60) or "meme"
            nome_inicio = a.inicio if a.inicio in por_nome else escolhe_inicio(texto, descr, usos_hoje, hist, por_nome)
            i_ini, i_fim = trecho_do_inicio(por_nome[nome_inicio])
            n = feitos_hoje + feitos + 1
            nome = f"{n:02d} - {slug(texto, 40)}"
            saida = destino / f"{nome}.mp4"
            trechos = ", ".join(f"{cenas[k]['a']:.1f}-{cenas[k]['b']:.1f}s" for k in pessoas)
            log(f"   TROCA: mesmo texto ({texto}), música inteira; seu começo ({nome_inicio}) no lugar da outra pessoa em {trechos}")
            feito = troca_partes(por_nome[nome_inicio], i_ini, i_fim, clip, cenas, pngs, saida)
            # CONFERÊNCIA DO VÍDEO (2 checagens; se achar problema, refaz uma vez pelo outro jeito e confere de novo)
            probs = confere_troca(saida, clip, cenas, lido) if feito else ["a montagem falhou"]
            if probs and feito:
                log("   conferência 1 achou: " + " | ".join(probs))
                if any("texto" in x.lower() for x in probs):
                    pngs = monta_pngs(not texto_barra or pngs.get(pessoas[0]) != texto_barra)
                feito = troca_partes(por_nome[nome_inicio], i_ini, i_fim, clip, cenas, pngs, saida)
                probs = confere_troca(saida, clip, cenas, lido) if feito else ["a montagem falhou"]
                log("   conferência 2: " + ("OK" if not probs else " | ".join(probs)))
            else:
                log("   conferência: OK (cenas, texto e imagem)")
            if feito and probs:
                conferir = destino / "conferir"
                conferir.mkdir(exist_ok=True)
                shutil.move(str(saida), str(conferir / saida.name))
                (conferir / f"{nome}.txt").write_text("NÃO FOI PARA A FILA — a conferência achou:\n- " + "\n- ".join(probs)
                                                      + f"\n\nOriginal: {c.get('url') or clip}\n", encoding="utf-8")
                log(f"   NÃO POSTEI: ficou em {conferir.name}\\{saida.name} para você olhar (a conferência não aprovou)")
                if c.get("url"):
                    _tira_link(base, c["url"], ok=False, motivo="FEITO, mas a conferência não aprovou: está em prontos\\"
                               + f"{hoje}\\conferir\\{saida.name} — " + "; ".join(probs)[:200])
                continue
            if feito:
                dono = {norm(x).replace("_", "").replace(".", "") for x in (info.get("channel"), info.get("uploader"), info.get("uploader_id")) if x}
                tags = [t for t in tags_originais(info) if norm(t[1:]).replace("_", "") not in dono]
                tags = list(dict.fromkeys(tags + (a.tags.split() if a.tags else []) + cfg["tags_padrao"]))[:5]
                leg_g, tags_g = legenda_viral(texto, info, video_pequeno(clip, tmp / "viral.mp4"), cfg) if not a.legenda else (a.legenda, [])
                legenda = a.legenda or leg_g
                tags = list(dict.fromkeys(tags[:3] + [t.lower() for t in tags_g] + tags))[:5]
                fonte_txt = c.get("url") or str(clip)
                (destino / f"{nome}.txt").write_text(f"{legenda}\n\n{' '.join(tags)}\n\n---\nTexto na tela (o do original): {texto}\nOriginal: {fonte_txt}"
                                                     f"{' (@' + str(info.get('channel')) + ')' if info.get('channel') else ''}\n", encoding="utf-8")
                hist["usados"][chave] = {"dia": hoje, "arquivo": saida.name, "url": fonte_txt, "modo": "troca"}
                h_ = hist["inicios"].setdefault(nome_inicio, {"n": 0})
                h_["n"] += 1
                h_["ultimo"] = hoje
                usos_hoje.append(nome_inicio)
                grava_json(base / "historico.json", hist)
                if c.get("url"):
                    _tira_link(base, c["url"], ok=True, hist=hist)
                _para_postar(cfg, saida, destino / f"{nome}.txt")
                feitos += 1
                log(f"   pronto: {saida}")
            else:
                log("   NÃO FIZ: a troca falhou (veja o erro acima)")
                if c.get("url"):
                    _tira_link(base, c["url"], ok=False, motivo="a troca falhou (não achei a parte da pessoa ou o lance)")
            continue
        # Gemini: começo + texto + legenda + tags + trecho
        peq = video_pequeno(clip, tmp / "viral.mp4")
        g = escreve(peq, info, descr, cfg, usos_hoje) if peq and not (a.texto and a.inicio) else None
        g = dict(g or {})
        if a.inicio:
            g["inicio"] = a.inicio
        if a.texto:
            g["texto"] = a.texto
        if a.legenda:
            g["legenda"] = a.legenda
        if a.tags:
            g["tags"] = a.tags.split()
        if a.corte:
            x, y = a.corte.replace(",", ".").split("-")
            g["inicio_corte"], g["fim_corte"] = float(x), float(y)
        nome_inicio = (g or {}).get("inicio") if g and (g.get("inicio") in por_nome) else None
        if not nome_inicio:
            # sem Gemini: rodízio pelo começo menos usado (e não usado hoje)
            nome_inicio = sorted(por_nome, key=lambda k: (k in usos_hoje, hist["inicios"].get(k, {}).get("n", 0), random.random()))[0]
        texto = re.sub(r"\s+", " ", (g or {}).get("texto") or re.sub(r"#\S+|[^\w\sÀ-ÿ?!,.:]", "", info.get("title", "")).strip() or "Quando o futebol é assim")
        dono = {norm(x).replace("_", "").replace(".", "") for x in (info.get("channel"), info.get("uploader"), info.get("uploader_id")) if x}
        orig = [t for t in tags_originais(info) if norm(t[1:]).replace("_", "") not in dono]
        tags = (orig + [t if t.startswith("#") else "#" + t for t in (g or {}).get("tags", [])] + cfg["tags_padrao"])
        tags = list(dict.fromkeys(t.lower().replace(" ", "") for t in tags))[:5]
        legenda = ((g or {}).get("legenda") or texto).strip()
        ini = float((g or {}).get("inicio_corte") or 0)
        fim = float((g or {}).get("fim_corte") or 0)
        if not a.corte and av.get("inicio") and ini < av["inicio"]:
            ini = av["inicio"]
            fim = max(fim, dclip) if fim <= ini else fim
        if not (0 <= ini < dclip) or fim <= ini:
            ini, fim = av.get("inicio", 0.0), dclip
        fim = min(fim, dclip, ini + cfg["corte_max"])
        if fim - ini < 3:
            ini = av.get("inicio", 0.0)
            fim = min(dclip, ini + cfg["corte_max"])
        n = feitos_hoje + feitos + 1
        nome = f"{n:02d} - {slug(texto, 40)}"
        saida = destino / f"{nome}.mp4"
        log(f"   começo: {nome_inicio} | texto: {texto}")
        i_ini, i_fim = trecho_do_inicio(por_nome[nome_inicio])
        zoom = a.zoom or ({"aberto": 1.0}.get(str(g.get("enquadramento", "")).lower()))
        if not monta(por_nome[nome_inicio], clip, ini, fim, texto, saida, tmp, i_ini, i_fim, zoom, a.foco, av.get("faixa")):
            log("   falhou a edição, próximo")
            continue
        fonte_txt = c.get("url") or str(clip)
        (destino / f"{nome}.txt").write_text(f"{legenda}\n\n{' '.join(tags)}\n\n---\nTexto na tela: {texto}\nOriginal: {fonte_txt}"
                                             f"{' (@' + str(info.get('channel') or info.get('uploader_id')) + ')' if info.get('channel') or info.get('uploader_id') else ''}\n", encoding="utf-8")
        hist["usados"][chave] = {"dia": hoje, "arquivo": saida.name, "url": fonte_txt}
        i = hist["inicios"].setdefault(nome_inicio, {"n": 0})
        i["n"] += 1
        i["ultimo"] = hoje
        usos_hoje.append(nome_inicio)
        grava_json(base / "historico.json", hist)
        if c.get("seu") and c.get("url"):
            _tira_link(base, c["url"], ok=True, hist=hist)
        _para_postar(cfg, saida, destino / f"{nome}.txt")
        feitos += 1
        log(f"   pronto: {saida}")
    shutil.rmtree(tmp, ignore_errors=True)
    log(f"\n{feitos} reel(s) em {destino}")


def destinos_reels(cfg, base):
    """para onde vai cada reel: a lista do config; "todas" = toda conta ligada da postagem (Instagram, TikTok, YouTube
    Shorts e Kwai), menos as marcadas com "reels": false"""
    lista = list(cfg.get("postar") or [])
    if "todas" not in lista:
        return lista
    try:
        from postar import prepara as prep_postar
        contas = prep_postar(base)["contas"]
    except Exception:
        contas = []
    # @detto.tv é a conta de OUTRO tipo de vídeo: só recebe reels se marcar "reels": true nela
    todas = [f"{c['plataforma']}:{c['conta']}" for c in contas
             if c.get("ativo", True) and c.get("reels", c["conta"] != "detto.tv") is not False]
    return list(dict.fromkeys([x for x in lista if x != "todas"] + todas))


def _para_postar(cfg, video, txt):
    """põe o reel na fila de postagem (Instagram / TikTok) — postar.py sobe no horário de cada conta"""
    if not cfg.get("postar"):
        return
    try:
        sys.path.insert(0, str(TOOLS / "postar"))
        from postar import enfileira, pasta_padrao as pasta_postar

        base = Path(cfg.get("pasta_postar") or pasta_postar())
        destinos = destinos_reels(cfg, base)
        if not destinos:
            log("   nenhuma conta ligada para receber os reels (painel → Configurações)")
            return
        # nome com a data (o "01 - ..." de amanhã não pisa no de hoje)
        enfileira(base, video, destinos, txt, nome=f"{dt.date.today().isoformat()} {Path(video).name}")
        log(f"   na fila de postagem: {', '.join(destinos)}")
    except Exception as e:
        log(f"   não entrou na fila de postagem ({e}); poste manual")


def chave_link(url):
    """a IDENTIDADE do vídeo no link: é por ela que dá para saber se esse link JÁ virou reels, mesmo que você cole
    o endereço de outro jeito (com ?si=..., com /shorts/, sem a barra do fim, com www ou sem)."""
    u = str(url or "").strip()
    m = re.search(r"(?:youtu\.be/|youtube\.com/(?:shorts/|live/|embed/|watch\?(?:.*&)?v=))([\w-]{6,})", u, re.I)
    if m:
        return f"yt:{m.group(1)}"
    m = re.search(r"instagram\.com/(?:[\w.]+/)?(?:reels?|p|tv)/([\w-]+)", u, re.I)
    if m:
        return f"ig:{m.group(1)}"
    m = re.search(r"tiktok\.com/.*?/video/(\d+)", u, re.I)
    if m:
        return f"tt:{m.group(1)}"
    m = re.search(r"(?:vm|vt)\.tiktok\.com/([\w-]+)", u, re.I)
    if m:
        return f"tt:{m.group(1)}"
    u = re.sub(r"[?#].*$", "", u).rstrip("/").lower()
    return re.sub(r"^https?://(www\.)?", "", u)


def links_ja_feitos(base, hist):
    """as chaves dos links que já viraram reels — do historico.json e do links_feitos.txt (o registro antigo)"""
    feitos = set(hist.get("links", {}))
    f = base / "links_feitos.txt"
    if f.exists():
        for linha in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.search(r"(https?://\S+)", linha)
            if m and " ok " in linha:
                feitos.add(chave_link(m.group(1)))
    return feitos


def _tira_link(base, url, ok, hist=None, motivo=""):
    f = base / "links.txt"
    linhas = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip() != url]
    f.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    with open(base / "links_feitos.txt", "a", encoding="utf-8") as g:
        g.write(f"{dt.date.today()} {'ok' if ok else 'FALHOU'} {url}" + (f" — {motivo}" if motivo else "") + "\n")
    if not ok:
        # o link saía da lista calado e você não via POR QUE não virou reels (26/out). Agora fica aqui, e o
        # painel mostra na aba Reels automáticos.
        with open(base / "links_falhos.txt", "a", encoding="utf-8") as g:
            g.write(f"{dt.datetime.now():%d/%m %H:%M}\t{url}\t{motivo or 'veja o registro'}\n")
    if ok and hist is not None:  # guarda a identidade do vídeo: se você colar esse link de novo, não refaz
        hist.setdefault("links", {})[chave_link(url)] = {"dia": dt.date.today().isoformat(), "url": url}


if __name__ == "__main__":
    main()
