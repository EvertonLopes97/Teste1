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


def tem_audio(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    return bool(r.stdout.strip())


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
    global _atualizou
    if not _atualizou:
        _atualizou = True
        log("atualizando o yt-dlp...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp"], capture_output=True)


def baixa(url, pasta, cookies=None, txt=None):
    """baixa o vídeo + info (título, descrição, tags). Devolve (mp4, info) ou (None, erro)."""
    pasta.mkdir(parents=True, exist_ok=True)
    args = ["-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b", "--merge-output-format", "mp4",
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
    from roteiro_ia import API, _chamar, modelos_disponiveis

    corpo = json.dumps({"contents": [{"parts": partes}], "generationConfig": {"temperature": 0.8, "responseMimeType": "application/json"}}).encode()
    modelos = [os.environ.get("GEMINI_MODEL", "gemini-flash-latest"), "gemini-2.5-flash"]
    for i in range(3):
        if i == 2:
            try:
                modelos.append((modelos_disponiveis() or ["gemini-2.5-flash"])[0])
            except Exception:
                break
        try:
            r = _chamar(f"{API}/models/{modelos[i]}:generateContent", corpo)
            txt = r["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
        except Exception as e:
            log(f"   Gemini ({modelos[i] if i < len(modelos) else '?'}): {str(e)[:160]}")
    return None


def video_pequeno(f, saida, segundos=40, altura=360):
    """cópia leve para o Gemini assistir (cabe na requisição)"""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(f), "-t", str(segundos), "-vf", f"scale=-2:{altura},fps=10", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "34", "-c:a", "aac", "-b:a", "48k", "-ac", "1", str(saida)], check=False)
    return saida if saida.exists() and saida.stat().st_size < 18_000_000 else None


def parte_video(f):
    return {"inline_data": {"mime_type": "video/mp4", "data": base64.b64encode(Path(f).read_bytes()).decode()}}


def descricao_inicio(f, cache, tmp):
    """o que você faz no começo: .txt ao lado, nome do arquivo, ou o Gemini assiste (uma vez)"""
    txt = f.with_suffix(".txt")
    if txt.exists():
        return txt.read_text(encoding="utf-8").strip()
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
 "fim_corte": <segundo onde termina; no máximo {cfg['corte_max']} s depois do início>}}"""
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
        ds.text((x + 2, y + 3), l, font=fonte, fill=(0, 0, 0, 200))
        dt_.text((x, y), l, font=fonte, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(30, 30, 30, 160))
    sombra = sombra.filter(ImageFilter.GaussianBlur(4))
    Image.alpha_composite(sombra, img).save(saida)


def monta(inicio, clip, ini, fim, texto, saida, tmp):
    """começo (tela cheia) → flash → viral (vertical cheio; horizontal ampliado com faixa preta) + texto no topo"""
    W, H, FPS = 1080, 1920, 30
    di = dur(inicio)
    dc = max(1.0, fim - ini)
    cw, ch = tamanho(clip)
    ar = cw / max(1, ch)
    png = tmp / "texto.png"
    texto_png(texto, png, W, H)
    cobre = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    if ar <= 0.8:
        vclip = cobre
    else:
        # horizontal: largura cheia ampliada até 1,33x (no máximo 67% da altura), faixa preta em cima/embaixo
        z = min(1.33, (H * 0.67) / (W / ar))
        sw, sh = int(W * z) // 2 * 2, int(W * z / ar) // 2 * 2
        vclip = f"scale={sw}:{sh},crop={W}:{sh},pad={W}:{H}:0:(oh-ih)/2:black"
    fl = 0.12
    f = (f"[0:v]{cobre},fps={FPS},setsar=1,fade=t=out:st={max(0, di - fl):.3f}:d={fl}:color=white[v0];"
         f"[1:v]trim={ini:.3f}:{fim:.3f},setpts=PTS-STARTPTS,{vclip},fps={FPS},setsar=1,fade=t=in:st=0:d={fl * 1.5:.3f}:color=white[v1];")
    a0 = "[0:a]aresample=48000,loudnorm=I=-16:TP=-2[a0];" if tem_audio(inicio) else f"anullsrc=r=48000:cl=stereo,atrim=0:{di:.3f}[a0];"
    a1 = (f"[1:a]atrim={ini:.3f}:{fim:.3f},asetpts=PTS-STARTPTS,aresample=48000,loudnorm=I=-16:TP=-2[a1];" if tem_audio(clip)
          else f"anullsrc=r=48000:cl=stereo,atrim=0:{dc:.3f}[a1];")
    f += a0 + a1 + "[v0][a0][v1][a1]concat=n=2:v=1:a=1[vc][ac];[vc][2:v]overlay=0:0[v];[ac]loudnorm=I=-14:TP=-1[a]"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(inicio), "-i", str(clip), "-loop", "1", "-i", str(png), "-filter_complex", f,
                        "-map", "[v]", "-map", "[a]", "-t", f"{di + dc:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                        "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(saida)])
    return r.returncode == 0 and saida.exists()


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
    ap.add_argument("--cookies", default=None, help="chrome, edge ou firefox (Instagram/TikTok/YouTube pedindo login)")
    ap.add_argument("--agendar", metavar="HH:MM", help="cria a tarefa diária no Windows")
    ap.add_argument("--clip", help="(teste) usa este vídeo como viral em vez de buscar")
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
    if a.clip:
        fila = [{"arquivo": a.clip, "chave": f"arquivo:{Path(a.clip).name}", "seu": True}]
    buscou = False
    feitos = 0
    while feitos < a.quantos:
        if not fila:
            if buscou or a.clip:
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
        # Gemini: começo + texto + legenda + tags + trecho
        peq = video_pequeno(clip, tmp / "viral.mp4")
        g = escreve(peq, info, descr, cfg, usos_hoje) if peq else None
        nome_inicio = (g or {}).get("inicio") if g and (g.get("inicio") in por_nome) else None
        if not nome_inicio:
            # sem Gemini: rodízio pelo começo menos usado (e não usado hoje)
            nome_inicio = sorted(por_nome, key=lambda k: (k in usos_hoje, hist["inicios"].get(k, {}).get("n", 0), random.random()))[0]
        texto = re.sub(r"\s+", " ", (g or {}).get("texto") or re.sub(r"#\S+|[^\w\sÀ-ÿ?!,.:]", "", info.get("title", "")).strip() or "Quando o futebol é assim")
        orig = tags_originais(info)
        tags = (orig + [t if t.startswith("#") else "#" + t for t in (g or {}).get("tags", [])] + cfg["tags_padrao"])
        tags = list(dict.fromkeys(t.lower().replace(" ", "") for t in tags))[:5]
        legenda = ((g or {}).get("legenda") or texto).strip()
        ini = float((g or {}).get("inicio_corte") or 0)
        fim = float((g or {}).get("fim_corte") or 0)
        if not (0 <= ini < dclip) or fim <= ini:
            ini, fim = 0.0, dclip
        fim = min(fim, dclip, ini + cfg["corte_max"])
        if fim - ini < 3:
            ini, fim = 0.0, min(dclip, cfg["corte_max"])
        n = feitos_hoje + feitos + 1
        nome = f"{n:02d} - {slug(texto, 40)}"
        saida = destino / f"{nome}.mp4"
        log(f"   começo: {nome_inicio} | texto: {texto}")
        if not monta(por_nome[nome_inicio], clip, ini, fim, texto, saida, tmp):
            log("   falhou a edição, próximo")
            continue
        fonte_txt = c.get("url") or str(clip)
        (destino / f"{nome}.txt").write_text(f"{legenda}\n\n{' '.join(tags)}\n\n---\nTexto na tela: {texto}\nOriginal: {fonte_txt}"
                                             f"{' (@' + info['uploader_id'] + ')' if info.get('uploader_id') else ''}\n", encoding="utf-8")
        hist["usados"][chave] = {"dia": hoje, "arquivo": saida.name, "url": fonte_txt}
        i = hist["inicios"].setdefault(nome_inicio, {"n": 0})
        i["n"] += 1
        i["ultimo"] = hoje
        usos_hoje.append(nome_inicio)
        grava_json(base / "historico.json", hist)
        if c.get("seu") and c.get("url"):
            _tira_link(base, c["url"], ok=True)
        feitos += 1
        log(f"   pronto: {saida}")
    shutil.rmtree(tmp, ignore_errors=True)
    log(f"\n{feitos} reel(s) em {destino}")


def _tira_link(base, url, ok):
    f = base / "links.txt"
    linhas = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip() != url]
    f.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    with open(base / "links_feitos.txt", "a", encoding="utf-8") as g:
        g.write(f"{dt.date.today()} {'ok' if ok else 'FALHOU'} {url}\n")


if __name__ == "__main__":
    main()
