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
import unicodedata
from pathlib import Path

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
    "postar": ["instagram:detto.galo", "tiktok:detto.galo"],
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
    c.update(le_json(cfg, {}))
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
def gemini_json(partes):
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    sys.path.insert(0, str(TOOLS))
    from roteiro_ia import gerar

    corpo = json.dumps({"contents": [{"parts": partes}], "generationConfig": {"temperature": 0.8, "responseMimeType": "application/json"}}).encode()
    try:
        r = gerar(corpo, log=log)
        txt = r["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
    except Exception as e:
        log(f"   Gemini: {str(e)[:200]}")
    return None


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
    f = (f"[0:v]trim={i_ini:.3f}:{i_fim:.3f},setpts=PTS-STARTPTS,{cor_sdr(inicio)}{cobre},fps={FPS},setsar=1,format=yuv420p,"
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
    # junta pedaços da mesma linha (acentos, "ç") e fica com o bloco centralizado do topo
    bloco = []
    for l in linhas:
        centro = abs(l[2] - (W - 1 - l[3])) < W * 0.12 and (l[3] - l[2]) > W * 0.12
        if not centro:
            if bloco:
                break
            continue
        if bloco and l[0] - bloco[-1][1] > 3 * max(10, np.median([b[1] - b[0] for b in bloco])):
            break
        bloco.append(l)
    if not bloco:
        return None
    y0, y1 = max(0, bloco[0][0] - 8), min(H, bloco[-1][1] + 8)
    x0, x1 = max(0, min(b[2] for b in bloco) - 10), min(W, max(b[3] for b in bloco) + 10)
    alfa = np.zeros((H, W), np.float32)
    alfa[y0:y1, x0:x1] = np.clip((mn[y0:y1, x0:x1].astype(np.float32) - 60) / 140, 0, 1)
    # sombra escura por baixo (lê na parede branca do seu começo)
    sombra = cv2.GaussianBlur(cv2.dilate(alfa, np.ones((5, 5), np.uint8)), (0, 0), 5) * 0.85
    a_final = np.maximum(alfa, sombra)
    cor = (alfa / np.maximum(a_final, 1e-3) * 255).clip(0, 255).astype(np.uint8)
    rgba = np.dstack([cor, cor, cor, (a_final * 255).astype(np.uint8)])
    cv2.imwrite(str(saida), rgba)
    return saida


def ler_texto(png):
    """o texto do meme em letras (para a legenda): tesseract (português) ou o Gemini lendo a imagem"""
    import cv2

    img = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
    if img is None:
        return ""
    preto = 255 - img[:, :, 3]
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


def troca(inicio, i_ini, i_fim, clip, corte, png, saida):
    """Igual ao original (mesmo texto, música inteira, mesmo lance); só a parte da outra pessoa vira o seu começo."""
    W, H = tamanho(clip)
    W, H = W // 2 * 2, H // 2 * 2
    F = fps_de(clip)
    dc = dur(clip)
    di_total = dur(inicio)
    i_fim = min(di_total, i_fim) if i_fim else di_total
    seu = max(0.3, i_fim - i_ini)
    falta = max(0.0, corte - seu)  # seu começo mais curto que o dele: segura o último quadro
    cobre = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    f = (f"[0:v]trim={i_ini:.3f}:{min(i_fim, i_ini + corte):.3f},setpts=PTS-STARTPTS,{cor_sdr(inicio)}{cobre},fps={F},setsar=1,format=yuv420p"
         f"{f',tpad=stop_mode=clone:stop_duration={falta:.3f}' if falta > 0.01 else ''}[vi0];"
         f"[vi0][2:v]overlay=0:0:format=auto:shortest=1,format=yuv420p[vi];"
         f"[1:v]trim=start={corte:.3f},setpts=PTS-STARTPTS,{cor_sdr(clip)}scale={W}:{H},fps={F},setsar=1,format=yuv420p[vc];"
         f"[vi][vc]concat=n=2:v=1:a=0[v]")
    ac = audio_bom(clip)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(inicio), "-i", str(clip), "-loop", "1", "-i", str(png), "-filter_complex", f, "-map", "[v]"]
    cmd += (["-map", f"1:a:{ac}", "-c:a", "aac", "-b:a", "192k"] if ac is not None else [])
    cmd += ["-t", f"{dc:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
            "-color_trc", "bt709", "-movflags", "+faststart", str(saida)]
    r = subprocess.run(cmd)
    return r.returncode == 0 and saida.exists()


def escolhe_inicio(texto, descr, usos_hoje, hist, por_nome):
    """o seu começo que combina com o texto do meme (Gemini); sem chave: o menos usado"""
    if texto and descr:
        g = gemini_json([{"text": f"Meme de futebol com o texto: {texto!r}. O começo do vídeo mostra uma pessoa reagindo. Qual destes começos "
                                  f"combina mais?\n" + "\n".join(f"- {k}: {d}" for k, d in descr) + "\nJSON {\"inicio\": \"<nome exato>\"}"}])
        if g and g.get("inicio") in por_nome:
            return g["inicio"]
    return sorted(por_nome, key=lambda k: (k in usos_hoje, hist["inicios"].get(k, {}).get("n", 0), random.random()))[0]


def trecho_do_inicio(f):
    """gravação longa de começo: o .txt ao lado pode ter "trecho: 8.0-12.4" (só essa parte entra)"""
    txt = f.with_suffix(".txt")
    if txt.exists():
        m = re.search(r"trecho\s*:?\s*([\d.,]+)\s*[-–]\s*([\d.,]+)", txt.read_text(encoding="utf-8"), re.I)
        if m:
            return float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
    return 0.0, None


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


def main():
    ap = argparse.ArgumentParser(description="reels automáticos: seu começo + viral de futebol + texto")
    ap.add_argument("--pasta", default=str(pasta_padrao()))
    ap.add_argument("--quantos", type=int, default=10)
    ap.add_argument("--so-links", action="store_true", help="só os links do links.txt (não busca virais); o painel usa")
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
    links = [l.strip() for l in (base / "links.txt").read_text(encoding="utf-8").splitlines() if re.match(r"https?://", l.strip())]
    fila = [{"url": u, "chave": None, "seu": True} for u in links]
    if a.so_links:
        if not links:
            log("nenhum link no links.txt")
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
                    _tira_link(base, c["url"], ok=False)
                continue
        chave = c.get("chave") or chave_de(info, c.get("url"))
        if chave in hist["usados"] and not c.get("arquivo"):
            if c.get("seu"):
                _tira_link(base, c["url"], ok=True)
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
        if c.get("seu") and av.get("inicio") and a.modo != "novo":
            png = texto_do_original(clip, av["inicio"] + 0.2, dclip - 0.2, tmp / "texto_original.png")
            if png:
                texto = a.texto or ler_texto(png) or "meme"
                nome_inicio = a.inicio if a.inicio in por_nome else escolhe_inicio(texto, descr, usos_hoje, hist, por_nome)
                i_ini, i_fim = trecho_do_inicio(por_nome[nome_inicio])
                n = feitos_hoje + feitos + 1
                nome = f"{n:02d} - {slug(texto, 40)}"
                saida = destino / f"{nome}.mp4"
                log(f"   TROCA: mesmo texto ({texto}), música inteira; seu começo: {nome_inicio} no lugar dos {av['inicio']:.1f}s da outra pessoa")
                if troca(por_nome[nome_inicio], i_ini, i_fim, clip, av["inicio"], png, saida):
                    dono = {norm(x).replace("_", "").replace(".", "") for x in (info.get("channel"), info.get("uploader"), info.get("uploader_id")) if x}
                    tags = [t for t in tags_originais(info) if norm(t[1:]).replace("_", "") not in dono]
                    tags = list(dict.fromkeys(tags + (a.tags.split() if a.tags else []) + cfg["tags_padrao"]))[:5]
                    desc = re.sub(r"#\S+", "", info.get("description") or "").strip()
                    legenda = a.legenda or (desc if len(desc) > 8 else texto)
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
                        _tira_link(base, c["url"], ok=True)
                    _para_postar(cfg, saida, destino / f"{nome}.txt")
                    feitos += 1
                    log(f"   pronto: {saida}")
                    continue
                log("   a troca falhou; fazendo no modo normal")
            else:
                log("   não achei o texto do original; fazendo no modo normal")
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
            _tira_link(base, c["url"], ok=True)
        _para_postar(cfg, saida, destino / f"{nome}.txt")
        feitos += 1
        log(f"   pronto: {saida}")
    shutil.rmtree(tmp, ignore_errors=True)
    log(f"\n{feitos} reel(s) em {destino}")


def _para_postar(cfg, video, txt):
    """põe o reel na fila de postagem (Instagram / TikTok) — postar.py sobe no horário de cada conta"""
    if not cfg.get("postar"):
        return
    try:
        sys.path.insert(0, str(TOOLS / "postar"))
        from postar import enfileira, pasta_padrao as pasta_postar

        base = Path(cfg.get("pasta_postar") or pasta_postar())
        # nome com a data (o "01 - ..." de amanhã não pisa no de hoje)
        enfileira(base, video, cfg["postar"], txt, nome=f"{dt.date.today().isoformat()} {Path(video).name}")
        log(f"   na fila de postagem: {', '.join(cfg['postar'])}")
    except Exception as e:
        log(f"   não entrou na fila de postagem ({e}); poste manual")


def _tira_link(base, url, ok):
    f = base / "links.txt"
    linhas = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip() != url]
    f.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    with open(base / "links_feitos.txt", "a", encoding="utf-8") as g:
        g.write(f"{dt.date.today()} {'ok' if ok else 'FALHOU'} {url}\n")


if __name__ == "__main__":
    main()
