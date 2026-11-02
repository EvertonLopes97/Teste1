# -*- coding: utf-8 -*-
"""GAMEPLAY NARRADA — gravação bruta → vídeo de 15-20 min com a SUA voz narrando + Shorts.

    python tools\\gameplay\\gameplay.py --pasta "E:\\DETTO\\gameplay\\zomboid dia 1" --titulo "..."

MEDIDO nos canais de gameplay narrada (01/nov, últimos 25 vídeos de cada):
  @thegusr  (Project Zomboid, 21 mil views medianos): 15-25 min = **1,30x** · 8-15 min 0,83x
  @Felps    ("[Felps Editado]", 40,5 mil medianos):   15-25 min = **1,33x** · 8-15 min 0,94x
  O melhor de cada um vende uma PREMISSA, não um resumo: "I played Project Zomboid in third
  person!!" (5,6x) e "10 ANOS BEBENDO PETRÓLEO" (3,9x). O pior do @thegusr é o único vídeo FORA do
  formato (comprando jogos, 0,1x) — sair do formato mata.
  → `duracao_alvo_min` 17 e a regra de título pede PREMISSA.

O CAMINHO (cada peça já existia; o que é novo é o `momentos.py`):
  1 analisa cada gravação: duração, MOVIMENTO e VOLUME por segundo (`vlog.energia`) e a sua fala
    (faster-whisper) quando você comentou jogando
  2 `momentos.momentos` escolhe os pedaços que valem — sempre contra o normal DAQUELE vídeo, com a
    subida ANTES do pico (é a tensão que prende) e a reação depois
  3 o Gemini olha UM quadro de cada momento e diz o que aconteceu, para a narração falar do que
    está na tela em vez de encher linguiça
  4 a IA escreve a narração em 1ª pessoa + as REAÇÕES (os dois que você pediu)
  5 a voz sai pela cadeia de sempre: VoiceStudio (a SUA voz clonada) → Fish → neural pt-BR
  6 monta: cada momento cortado, narração por cima com o ÁUDIO DO JOGO ABAIXADO só enquanto você
    fala (sidechain), legenda do que você narra, punch-in nos picos
  7 vinheta depois da chamada, thumb de gameplay, capítulos, conferência do título e os Shorts
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
for p in (TOOLS, TOOLS / "reels", TOOLS / "canal", TOOLS / "vlog", TOOLS / "yt", TOOLS / "thumb", AQUI):
    sys.path.insert(0, str(p))

import momentos as MOM  # noqa: E402
from ffcompat import filtro_complexo  # noqa: E402
from reels import dur, gemini_json, grava_json, le_json, slug, trava_rodada  # noqa: E402

VIDEOS = {".mp4", ".mkv", ".mov", ".m4v", ".avi", ".ts", ".webm"}
W, H, FPS = 1920, 1080, 30


def log(m):
    print(m, flush=True)


CONFIG = {
    "duracao_alvo_min": 17,      # MEDIDO: 15-25 min rende 1,30x (@thegusr) e 1,33x (@Felps)
    "max_momentos": 14,
    "momento_min_s": 8,
    "momento_max_s": 45,
    "shorts": 3,
    "jogo": "",                  # "CS2", "Project Zomboid", "eFootball"... entra no prompt
    "narracao": "primeira+reacao",
    "volume_jogo": 0.35,         # o jogo atrás da sua narração
    "abaixa_db": 11,             # quanto o jogo abaixa enquanto você fala (sidechain)
    "vinheta_canal": "gta6",
    "estilo_thumb": "gameplay",
    "nome_canal": "DETTO PLAY",
    "legendas": True,
    "capitulos": True,
}

REGRAS = """Você narra a SUA PRÓPRIA gameplay, em PRIMEIRA PESSOA e no passado ("eu entrei", "achei que
ia dar certo", "aí eu morri"). Você é o Everton, brasileiro, direto, zoeiro quando cabe, NUNCA formal.
O QUE FAZ ESSE FORMATO FUNCIONAR (medido em @thegusr e @Felps):
- o vídeo vende uma PREMISSA, não um resumo: "eu tentei sobreviver X", "o que acontece se...".
  O título e a abertura são a promessa; o resto é ela se cumprindo.
- a ABERTURA são os 2 primeiros segundos: diga o que vai dar errado, sem "fala galera" e sem vinheta.
- entre os momentos você faz a PONTE ("foi aí que eu tive a pior ideia do vídeo").
- a REAÇÃO é curta e entra DENTRO do momento, no segundo em que a coisa acontece (6 a 15 palavras).
PROIBIDO INVENTAR: fale só do que está descrito no momento. Se o momento diz "morreu para um zumbi",
não diga que foi um grupo. Sem fato, faça a ponte e siga."""


# ------------------------------------------------------------------ 1. gravações
def clipes(pasta):
    vs = [f for f in sorted(pasta.iterdir()) if f.is_file() and f.suffix.lower() in VIDEOS
          and not f.stem.startswith((".", "_")) and "pronto" not in f.stem.lower()]
    return sorted(vs, key=lambda f: (f.stat().st_mtime, f.name))


def analisa(vs, job, cfg):
    """duração + movimento/volume por segundo + a sua fala (quando houver)"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_vl", TOOLS / "vlog" / "vlog.py")
    vl = importlib.util.module_from_spec(spec)
    sys.modules["_vl"] = vl
    spec.loader.exec_module(vl)
    (job / "analise").mkdir(parents=True, exist_ok=True)
    out = []
    for i, v in enumerate(vs):
        cache = job / "analise" / f"{i:03d}.json"
        a = le_json(cache, None)
        if a and a.get("arq") == str(v) and a.get("dur"):
            log(f"   {i + 1}/{len(vs)} {v.name}: já analisado")
            out.append(a)
            continue
        log(f"   {i + 1}/{len(vs)} analisando {v.name}...")
        s = vl.sonda(v)
        mov, vol = vl.energia(v, s["dur"])
        pal = []
        if s.get("audio"):
            try:   # você comentando enquanto jogava é o sinal MAIS confiável de momento forte
                pal = vl.transcreve(v, job / "analise" / f"{i:03d}_words.json")
            except Exception as e:  # noqa: BLE001
                log(f"      não transcrevi ({str(e)[:90]}): sigo pelo volume e movimento")
        a = {"i": i, "arq": str(v), "dur": s["dur"], "w": s["w"], "h": s["h"], "fps": s["fps"],
             "mov": mov, "vol": vol, "palavras": pal, "tem_audio": bool(s.get("audio"))}
        grava_json(cache, a)
        out.append(a)
    return out


# ------------------------------------------------------------------ 2. os momentos
def escolhe(ans, cfg):
    """os melhores momentos de TODAS as gravações, até encher a duração alvo"""
    todos = []
    for a in ans:
        ms = MOM.momentos(a["mov"], a["vol"], a["dur"], a.get("palavras"),
                          quantos=int(cfg["max_momentos"]), min_s=float(cfg["momento_min_s"]),
                          max_s=float(cfg["momento_max_s"]))
        for m in ms:
            m["clipe"] = a["arq"]
            m["ci"] = a["i"]
            m["falou"] = MOM.fala_no_momento(a.get("palavras"), m["ini"], m["fim"])
            todos.append(m)
    # a narração ocupa ~8 s por momento; o alvo é a soma
    alvo = float(cfg["duracao_alvo_min"]) * 60
    todos.sort(key=lambda m: -(m["nota"] + (0.5 if m["pelo"] == "fala" else 0)))
    sel, tot = [], 40.0   # abertura + fechamento
    for m in todos:
        if tot >= alvo or len(sel) >= int(cfg["max_momentos"]):
            break
        sel.append(m)
        tot += (m["fim"] - m["ini"]) + 8
    sel.sort(key=lambda m: (m["ci"], m["ini"]))
    for k, m in enumerate(sel):
        m["n"] = k + 1
    return sel, tot


def rotula(sel, job, cfg):
    """o Gemini olha UM quadro de cada momento e diz o que aconteceu (sem ele, o momento fica sem nome)"""
    (job / "quadros").mkdir(parents=True, exist_ok=True)
    partes = [{"text": f"""Estes são quadros de uma gameplay de {cfg.get('jogo') or 'videogame'}, um por MOMENTO.
Para CADA um, diga em português o que está acontecendo, em até 12 palavras, concreto (o que dá para VER).
Responda SÓ JSON: {{"momentos": [{{"n": 1, "oque": "..."}}]}}"""}]
    for m in sel:
        f = job / "quadros" / f"m{m['n']:02d}.jpg"
        if not f.exists():
            t = m["ini"] + (m["fim"] - m["ini"]) * 0.7   # 70% do momento: já é o resultado, não a subida
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", m["clipe"],
                            "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "6", str(f)])
        if f.exists():
            partes.append({"text": f"MOMENTO {m['n']}:"})
            partes.append({"inline_data": {"mime_type": "image/jpeg",
                                           "data": base64.b64encode(f.read_bytes()).decode()}})
    g = gemini_json(partes) or {}
    por_n = {int(x.get("n", 0)): str(x.get("oque", ""))[:120] for x in (g.get("momentos") or []) if x.get("n")}
    for m in sel:
        m["oque"] = por_n.get(m["n"], "")
    achou = sum(1 for m in sel if m["oque"])
    log(f"   o que acontece em cada momento: {achou}/{len(sel)}" if achou else
        "   a IA não descreveu os momentos (sem Gemini?): a narração vai pela sua fala e pela ordem")
    return sel


# ------------------------------------------------------------------ 3. a narração
def roteiro(sel, cfg, titulo_pedido="", titulos_antes=()):
    lista = "\n".join(
        f"MOMENTO {m['n']} ({m['fim'] - m['ini']:.0f}s)"
        + (f" — na tela: {m['oque']}" if m.get("oque") else "")
        + (f" — você falou: \"{m['falou'][:180]}\"" if m.get("falou") else "")
        for m in sel)
    proibido = ""
    if titulos_antes:
        proibido = ("\nTÍTULOS QUE JÁ SAÍRAM NESTE CANAL:\n" + "\n".join(f"- {t}" for t in list(titulos_antes)[:8])
                    + "\nO título de hoje NÃO pode ser sobre a mesma premissa desses.")
    g = gemini_json([{"text": f"""{REGRAS}

Jogo: {cfg.get('jogo') or 'não informado'}. {"Ideia do vídeo: " + titulo_pedido if titulo_pedido else ""}
Os momentos da gravação, em ordem:
{lista}
{proibido}

Responda SÓ JSON:
{{"titulo": "<título em MAIÚSCULAS, até 60 letras, vendendo a PREMISSA. Tendo NÚMERO na premissa (7 dias, 100 zumbis, 1 vida), o número VAI no título — é o conserto que mais funciona. Nada de 'melhores momentos'>",
 "premissa": "<a promessa do vídeo em 1 frase>",
 "thumb_texto": "<2 a 4 palavras da premissa>", "thumb_destaque": "<1 palavra dela>",
 "descricao": "<2 a 3 frases>", "tags": ["<10 a 15 tags>"],
 "abertura": {{"texto": "<2 a 3 frases: a promessa + o que vai dar errado, até 45 palavras>", "clima": "atencao"}},
 "pontes": [{{"antes_do": <nº do momento>, "texto": "<1 a 2 frases ligando ao momento, até 35 palavras>", "clima": "..."}}],
 "reacoes": [{{"momento": <nº>, "em": <segundo DENTRO do momento, nunca nos 2 primeiros nem nos 2 últimos>,
               "texto": "<sua reação, 6 a 15 palavras>", "clima": "..."}}],
 "fechamento": {{"texto": "<fecho + like/inscrição, até 40 palavras>", "clima": "comemorando"}}}}
Uma PONTE antes de cada momento. REAÇÃO só nos momentos de 12 s ou mais (1 por momento).
climas: falando, atencao, comemorando, bravo, pensativo, surpreso"""}])
    if not g or not g.get("abertura"):
        log("   a IA não escreveu o roteiro: faço um simples pela ordem dos momentos")
        g = {"titulo": (titulo_pedido or f"GAMEPLAY DE {cfg.get('jogo') or 'HOJE'}").upper()[:85],
             "premissa": titulo_pedido or "", "thumb_texto": (cfg.get("jogo") or "GAMEPLAY")[:18],
             "thumb_destaque": "", "descricao": "", "tags": [],
             "abertura": {"texto": "Olha o que aconteceu nessa partida.", "clima": "atencao"},
             "pontes": [{"antes_do": m["n"], "texto": f"Momento {m['n']}.", "clima": "falando"} for m in sel],
             "reacoes": [], "fechamento": {"texto": "Deixa o like e se inscreve.", "clima": "comemorando"}}
    return g


def voz(falas, job, cfg, pasta):
    """a cadeia de sempre: VoiceStudio (a SUA voz) → Fish → neural pt-BR. O clima manda na emoção."""
    fj = job / "falas.json"
    grava_json(fj, falas)
    ref = Path(cfg.get("voz_ref") or "")
    if not ref.is_file():
        for c in ("canal_galo", "canal_gta6"):
            q = pasta.parent.parent / c / "voz" / "minha_voz.wav"
            if q.is_file():
                ref = q
                break
    cmd = [sys.executable, str(TOOLS / "canal" / "voz.py"), str(fj), str(job / "voz")]
    if ref.is_file():
        cmd += ["--ref", str(ref)]
    if cfg.get("voicestudio"):
        cmd += ["--voicestudio", cfg["voicestudio"]]
    if cfg.get("voz_voicestudio"):
        cmd += ["--voz-vs", cfg["voz_voicestudio"]]
    r = subprocess.run(cmd)
    if r.returncode:
        raise RuntimeError("a voz não ficou pronta — o motivo está nas linhas acima (quase sempre: abra o "
                           "VoiceStudio com a sua voz clonada, ou conserte a chave do Fish)")
    return json.loads(fj.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ 4. montagem
_NVENC = None


def enc():
    """NVENC s\u00f3 se ele REALMENTE codifica. Listar em `-encoders` n\u00e3o prova nada: a placa pode estar
    sem driver/CUDA e o render morre com "Cannot load libcuda.so.1" DEPOIS de montar meia pe\u00e7a."""
    global _NVENC
    if _NVENC is None:
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
                            "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True, timeout=90)
        _NVENC = r.returncode == 0
    if _NVENC:
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "20", "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]


_NF = [0]


def ff(filtro, job):
    """O FILTRO VAI PARA UM ARQUIVO (regra do projeto): `-filter_complex_script` saiu no FFmpeg 8 e o
    `ffcompat.filtro_complexo` recebe o CAMINHO do arquivo, n\u00e3o o texto do filtro. Passar o texto faz
    toda pe\u00e7a morrer em "Failed to set value ... for option 'filter_complex_script'"."""
    _NF[0] += 1
    f = Path(job) / "tmp" / f"filtro_{_NF[0]:04d}.txt"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(filtro, encoding="utf-8")
    return filtro_complexo(f)


def _esc(s):
    return str(s).replace("\\", "/").replace(":", r"\:").replace("'", "\u2019").replace("%", r"\%")


def quebra(texto, largura=42, max_linhas=4):
    """O DRAWTEXT NÃO QUEBRA LINHA SOZINHO: uma narração de 40 palavras saía numa linha só, estourando
    os dois lados da tela (metade do texto fora do quadro). Aqui eu quebro na mão."""
    palavras = re.sub(r"\s+", " ", str(texto or "").strip()).split(" ")
    linhas, atual = [], ""
    for w in palavras:
        if atual and len(atual) + 1 + len(w) > largura:
            linhas.append(atual)
            atual = w
        else:
            atual = f"{atual} {w}".strip()
    if atual:
        linhas.append(atual)
    if len(linhas) > max_linhas:            # não cabe: corta e avisa com reticências
        linhas = linhas[:max_linhas]
        linhas[-1] = linhas[-1][:largura - 1] + "…"
    return "\n".join(_esc(l) for l in linhas)


def peca_narracao(wav, quadro, texto, saida, cfg, job):
    """a PONTE/abertura: um quadro do jogo parado com a sua narração por cima (barato e não enche o disco)"""
    da = dur(wav) + 0.25
    # zoom lento no quadro parado, SEM zoompan (ver peca_momento): scale com eval=frame + crop fixo
    ex = f"(1+0.06*min(t/{max(0.1, da):.2f},1))"
    f = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
         f"scale=w='{W}*{ex}':h='{H}*{ex}':eval=frame,crop={W}:{H}:'(iw-{W})/2':'(ih-{H})/2'[v0];")
    ult = "v0"
    if cfg.get("legendas") and texto:
        t = quebra(texto, 42, 4)
        n_l = t.count(chr(10)) + 1
        f += (f"[{ult}]drawtext=text='{t}':fontsize=44:fontcolor=white:borderw=5:bordercolor=black@0.9:"
              f"x=(w-text_w)/2:y=h-{150 + 56 * n_l}:line_spacing=10[vt];")
        ult = "vt"
    f += f"[{ult}]format=yuv420p[vo];[1:a]loudnorm=I=-16:TP=-1.5,aresample=48000,apad=pad_dur=0.25[ao]"
    cmd = ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(quadro), "-i", str(wav),
           *ff(f, job), "-map", "[vo]", "-map", "[ao]", "-t", f"{da:.2f}", *enc(), str(saida)]
    return subprocess.run(cmd).returncode == 0 and Path(saida).exists()


def peca_momento(clipe, ini, fim, saida, cfg, job, reacao=None, zoom_em=None):
    """o pedaço da gameplay. Com reação: a sua voz entra NO SEGUNDO em que a coisa acontece e o
    áudio do JOGO abaixa só ali (sidechain), em vez de ficar baixo o vídeo todo."""
    d = fim - ini
    ins = ["-ss", f"{ini:.2f}", "-t", f"{d:.2f}", "-i", str(clipe)]
    v = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}"
    if zoom_em is not None:
        # PUNCH-IN no pico. `crop` NÃO aceita `enable` ("Timeline not supported with filter 'crop'"),
        # e `zoompan` é proibido no projeto (reescala a imagem inteira a cada quadro: ~57 s por cena).
        # O jeito certo é o mesmo do shop: scale com eval=frame numa EXPRESSÃO de t, e crop fixo.
        z = max(0.5, min(d - 0.5, zoom_em))
        ex = f"(1+0.12*between(t,{z - 0.6:.2f},{z + 1.4:.2f}))"
        v += (f",scale=w='{W}*{ex}':h='{H}*{ex}':eval=frame,"
              f"crop={W}:{H}:'(iw-{W})/2':'(ih-{H})/2'")
    v += "[v0];"
    ult, nf = "v0", 1
    if reacao and Path(reacao["arquivo"]).exists():
        ins += ["-i", str(reacao["arquivo"])]
        em = max(0.3, min(d - 0.5, float(reacao.get("em", d / 2))))
        if cfg.get("legendas") and reacao.get("texto"):
            t = quebra(reacao["texto"], 34, 3)
            n_l = t.count(chr(10)) + 1
            dr = dur(reacao["arquivo"]) + 0.3
            v += (f"[{ult}]drawtext=text='{t}':fontsize=52:fontcolor=yellow:borderw=6:bordercolor=black@0.9:"
                  f"x=(w-text_w)/2:y=h-{140 + 64 * n_l}:line_spacing=12:"
                  f"enable='between(t,{em:.2f},{em + dr:.2f})'[vr];")
            ult = "vr"
        nf = 2
    v += f"[{ult}]format=yuv420p[vo];"
    if nf == 2:
        em = max(0.3, min(d - 0.5, float(reacao.get("em", d / 2))))
        # o jogo abaixa SÓ enquanto você fala: sidechaincompress com a sua voz como gatilho
        v += (f"[1:a]adelay={int(em * 1000)}|{int(em * 1000)},apad,atrim=0:{d:.2f},"
              f"loudnorm=I=-15:TP=-1.5,asplit[vz][gat];"
              f"[0:a]volume=1.0,asplit[jg][x];[x]anullsink;"
              f"[jg][gat]sidechaincompress=threshold=0.03:ratio=12:attack=20:release=300"
              f":makeup=1[jogo];[jogo][vz]amix=inputs=2:duration=first:weights=1 1.6,"
              f"loudnorm=I=-14:TP=-1[ao]")
        mapa = ["-map", "[vo]", "-map", "[ao]"]
    else:
        v += f"[0:a]volume={float(cfg.get('volume_jogo', 0.35)) + 0.45:.2f},loudnorm=I=-15:TP=-1.5[ao]"
        mapa = ["-map", "[vo]", "-map", "[ao]"]
    cmd = ["ffmpeg", "-v", "error", "-y", *ins, *ff(v, job), *mapa, "-t", f"{d:.2f}", *enc(), str(saida)]
    if subprocess.run(cmd).returncode == 0 and Path(saida).exists():
        return True
    # sem áudio no clipe (gravação só de imagem): refaz com silêncio
    cmd2 = ["ffmpeg", "-v", "error", "-y", *ins, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p",
            "-map", "0:v", "-map", f"{nf}:a", "-t", f"{d:.2f}", *enc(), "-c:a", "aac", str(saida)]
    return subprocess.run(cmd2).returncode == 0 and Path(saida).exists()


def monta(sel, rot, falas, job, saida, cfg):
    por_id = {f["id"]: f for f in falas}
    pontes = {int(p.get("antes_do", 0)): p for p in (rot.get("pontes") or [])}
    reacoes = {}
    for r in (rot.get("reacoes") or []):
        try:
            reacoes[int(r.get("momento", 0))] = r
        except (TypeError, ValueError):
            pass
    tmp = job / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    pecas, marcas = [], []
    quadro = job / "quadros" / "capa.jpg"
    if not quadro.exists() and sel:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{sel[0]['ini']:.2f}", "-i", sel[0]["clipe"],
                        "-frames:v", "1", str(quadro)])

    def agora():
        return sum(dur(p) for p in pecas)

    def narra(fid, texto):
        f = por_id.get(fid)
        if not f or not Path(f.get("arquivo", "")).exists():
            return
        p = tmp / f"p{len(pecas):03d}.mp4"
        if peca_narracao(f["arquivo"], quadro, texto, p, cfg, job):
            pecas.append(p)

    narra("abertura", rot["abertura"]["texto"])
    abertura_s = agora()
    for m in sel:
        marcas.append((agora(), (m.get("oque") or f"Momento {m['n']}")[:90]))
        if m["n"] in pontes:
            narra(f"ponte{m['n']:02d}", pontes[m["n"]]["texto"])
        r = reacoes.get(m["n"])
        rf = por_id.get(f"reacao{m['n']:02d}") if r else None
        reac = None
        if r and rf and Path(rf.get("arquivo", "")).exists():
            reac = {"arquivo": rf["arquivo"], "texto": r.get("texto", ""),
                    "em": float(r.get("em", (m["fim"] - m["ini"]) / 2))}
        p = tmp / f"p{len(pecas):03d}.mp4"
        log(f"   momento {m['n']}/{len(sel)}: {m['fim'] - m['ini']:.0f}s"
            + (f" — {m['oque']}" if m.get("oque") else "") + ("  (com reação)" if reac else ""))
        if peca_momento(m["clipe"], m["ini"], m["fim"], p, cfg, job, reac,
                        zoom_em=(m["fim"] - m["ini"]) * 0.72):
            pecas.append(p)
    narra("fechamento", rot["fechamento"]["texto"])
    if not pecas:
        raise RuntimeError("nenhuma peça foi montada (veja os erros do ffmpeg acima)")
    lista = tmp / "pecas.txt"
    lista.write_text("".join(f"file '{p.as_posix()}'\n" for p in pecas), encoding="utf-8")
    bruto = tmp / "bruto.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
                    "-c", "copy", str(bruto)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(bruto), "-c:v", "copy",
                    "-af", "loudnorm=I=-14:TP=-1", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", str(saida)], check=True)
    return saida, abertura_s, marcas


def shorts(sel, job, pronto, cfg, quantos):
    """os melhores momentos viram 9:16 pelo vertical916 (o mesmo dos outros canais)"""
    feitos = []
    melhores = sorted(sel, key=lambda m: -(m["nota"] + (0.5 if m["pelo"] == "fala" else 0)))[:quantos]
    for k, m in enumerate(melhores):
        corte = job / "tmp" / f"short_bruto_{k}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{m['ini']:.2f}", "-t",
                        f"{min(58.0, m['fim'] - m['ini']):.2f}", "-i", m["clipe"], *enc(),
                        "-c:a", "aac", str(corte)])
        if not corte.exists():
            continue
        sv = pronto / f"short_{k + 1}.mp4"
        r = subprocess.run([sys.executable, str(TOOLS / "vertical916.py"), str(corte), str(sv)])
        if r.returncode == 0 and sv.exists():
            feitos.append({"arquivo": sv.name, "titulo": (m.get("oque") or f"Momento {m['n']}")[:90]})
            log(f"   short {k + 1}: {m.get('oque') or m['n']}")
    return feitos


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="gameplay bruta → vídeo narrado na sua voz + Shorts")
    ap.add_argument("--pasta", required=True, help=r"pasta com a gravação (ex.: E:\DETTO\gameplay\zomboid dia 1)")
    ap.add_argument("--titulo", default="", help="a ideia/premissa do vídeo (ajuda muito a IA)")
    ap.add_argument("--jogo", default="", help="CS2, Project Zomboid, eFootball, GTA 6...")
    ap.add_argument("--minutos", type=float, default=None, help="duração alvo (padrão 17: a faixa medida)")
    ap.add_argument("--shorts", type=int, default=None)
    ap.add_argument("--sem-voz", action="store_true", help="só acha os momentos e escreve o roteiro")
    ap.add_argument("--so-momentos", action="store_true", help="só lista os momentos e para (confere antes de gastar voz)")
    a = ap.parse_args()

    pasta = Path(a.pasta)
    if not pasta.is_dir():
        log(f"não achei a pasta {pasta}")
        return 1
    cfg = {**CONFIG, **le_json(pasta / "config.json", {})}
    if a.jogo:
        cfg["jogo"] = a.jogo
    if a.minutos:
        cfg["duracao_alvo_min"] = a.minutos
    if a.shorts is not None:
        cfg["shorts"] = a.shorts
    grava_json(pasta / "config.json", cfg)

    trava = trava_rodada(pasta, ".gameplay_rodando")
    if not trava:
        log("NÃO RODEI: outro gameplay.py está trabalhando nesta pasta")
        return 1
    try:
        vs = clipes(pasta)
        if not vs:
            log(f"nenhuma gravação em {pasta} (ponha o mp4 da gameplay aí dentro)")
            return 1
        job = pasta / "job"
        job.mkdir(exist_ok=True)
        log(f"\n{len(vs)} gravação(ões), alvo de {cfg['duracao_alvo_min']:.0f} min"
            + (f" · jogo: {cfg['jogo']}" if cfg.get("jogo") else ""))
        ans = analisa(vs, job, cfg)
        total = sum(x["dur"] for x in ans) / 60
        sel, est = escolhe(ans, cfg)
        if not sel:
            log("não achei momento nenhum — a gravação é curta demais ou totalmente parada")
            return 1
        log(f"\n{len(sel)} momento(s) escolhido(s) de {total:.0f} min de gravação "
            f"(~{est / 60:.0f} min de vídeo):")
        for m in sel:
            log(f"   #{m['n']:2} {m['ini'] / 60:5.1f}min  {m['fim'] - m['ini']:4.0f}s  nota {m['nota']:.2f}"
                f"  ({m['pelo']})" + (f'  você falou: "{m["falou"][:60]}"' if m.get("falou") else ""))
        grava_json(job / "momentos.json", sel)
        if a.so_momentos:
            log(f"\nos momentos estão em {job / 'momentos.json'} — conferi e paro aqui (--so-momentos)")
            return 0

        sel = rotula(sel, job, cfg)
        hist = le_json(pasta / "historico.json", {"titulos": []})
        rot = roteiro(sel, cfg, a.titulo, [u.get("titulo", "") for u in hist.get("titulos", [])][-8:])
        grava_json(job / "roteiro.json", rot)
        log(f"\ntítulo: {rot['titulo']}")
        if rot.get("premissa"):
            log(f"premissa: {rot['premissa']}")
        if a.sem_voz:
            log(f"\nroteiro em {job / 'roteiro.json'} (--sem-voz: não montei)")
            return 0

        falas = [{"id": "abertura", "texto": rot["abertura"]["texto"], "clima": rot["abertura"].get("clima", "atencao")}]
        for p in (rot.get("pontes") or []):
            try:
                n = int(p.get("antes_do", 0))
            except (TypeError, ValueError):
                continue
            if p.get("texto"):
                falas.append({"id": f"ponte{n:02d}", "texto": p["texto"], "clima": p.get("clima", "falando")})
        for r in (rot.get("reacoes") or []):
            try:
                n = int(r.get("momento", 0))
            except (TypeError, ValueError):
                continue
            if r.get("texto"):
                falas.append({"id": f"reacao{n:02d}", "texto": r["texto"], "clima": r.get("clima", "surpreso")})
        falas.append({"id": "fechamento", "texto": rot["fechamento"]["texto"],
                      "clima": rot["fechamento"].get("clima", "comemorando")})
        log(f"\nvoz: {len(falas)} fala(s)")
        falas = voz(falas, job, cfg, pasta)

        pronto = pasta / "prontos" / f"{dt.datetime.now():%Y-%m-%d_%H%M} - {slug(rot['titulo'], 50)}"
        pronto.mkdir(parents=True, exist_ok=True)
        log("\nmontando:")
        video, abertura_s, marcas = monta(sel, rot, falas, job, pronto / "video.mp4", cfg)
        antes_vinheta = dur(video)

        if cfg.get("vinheta_canal"):
            try:
                import vinheta as VIN

                video = VIN.abre(video, cfg["vinheta_canal"], cfg.get("nome_canal", ""), cfg,
                                 log=log, em=abertura_s)
            except Exception as e:  # noqa: BLE001
                log(f"vinheta: não entrou ({str(e)[:110]})")

        caps, bloco = [], ""
        if cfg.get("capitulos", True):
            try:
                import capitulos as CAP

                df = dur(video)
                marcas = CAP.desloca(marcas, abertura_s, max(0.0, df - (antes_vinheta or df)))
                caps = CAP.de_marcas(marcas, df, "A ideia do vídeo")
                bloco = f"\n\nCapítulos:\n{CAP.texto(caps)}" if caps else ""
                log(f"capítulos: {len(caps)}" if caps else "capítulos: não deu 3 válidos")
            except Exception as e:  # noqa: BLE001
                log(f"capítulos: não saíram ({str(e)[:110]})")

        th = None
        try:
            from viral import thumb_viral

            assunto = f"{rot['titulo']} — {cfg.get('jogo', '')}"
            feitas = thumb_viral(pronto / "thumbs", assunto, rot.get("thumb_texto", ""),
                                 rot.get("thumb_destaque", ""), None, [], video, None, [],
                                 cfg.get("estilo_thumb", "gameplay"), cfg.get("nome_canal", ""), log=log)
            if feitas:
                th = pronto / "thumb_1.jpg"
                shutil.copyfile(feitas[0], th)
        except Exception as e:  # noqa: BLE001
            log(f"thumb: não saiu ({str(e)[:110]})")

        try:
            import titulo as TIT

            lint = TIT.confere(rot["titulo"], rot.get("thumb_texto", ""), "gta6", dur(video) / 60)
            log(f"título: nota {lint['nota']}/100")
            for p in sorted(lint["problemas"], key=lambda x: -x["peso"])[:3]:
                log(f"   ✗ {p['diz']}")
        except Exception as e:  # noqa: BLE001
            lint = None
            log(f"título: não conferi ({str(e)[:90]})")

        sh = shorts(sel, job, pronto, cfg, int(cfg.get("shorts", 3))) if cfg.get("shorts") else []
        tags = [t.strip("#") for t in (rot.get("tags") or [])][:15]
        descricao = f"{rot.get('descricao', '')}{bloco}\n\n" + " ".join("#" + re.sub(r"\W", "", t) for t in tags[:3])
        (pronto / "post.txt").write_text(f"{rot['titulo']}\n\n{descricao}\n\nTags: {', '.join(tags)}\n",
                                         encoding="utf-8")
        grava_json(pronto / "post.json", {
            "titulo": rot["titulo"], "descricao": descricao, "tags": tags, "video": "video.mp4",
            "thumb": th.name if th else "", "capitulos": caps, "lint_titulo": lint, "shorts": sh,
            "premissa": rot.get("premissa", ""), "status": "aguardando",
            "criado": dt.datetime.now().isoformat(timespec="seconds"),
            "momentos": [{"n": m["n"], "oque": m.get("oque", ""), "pelo": m["pelo"]} for m in sel]})
        hist["titulos"] = (hist.get("titulos", []) + [{"quando": dt.datetime.now().isoformat(timespec="minutes"),
                                                       "titulo": rot["titulo"]}])[-20:]
        grava_json(pasta / "historico.json", hist)
        shutil.rmtree(job / "tmp", ignore_errors=True)   # o disco dele é apertado
        log(f"\nPRONTO: {pronto}")
        log(f"   vídeo de {dur(video) / 60:.0f} min · {len(sh)} short(s)")
        return 0
    finally:
        try:
            trava.close()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    sys.exit(main())
