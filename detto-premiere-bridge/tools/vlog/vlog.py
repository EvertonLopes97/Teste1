# -*- coding: utf-8 -*-
"""EDITOR DE VLOGS (estilo Afreim / Cariani): você joga os clipes do dia numa pasta e sai o vlog editado.

    python tools\\vlog\\vlog.py "G:\\Meu Drive\\DETTO\\vlogs\\viagem rio" --titulo "VLOG RIO" --estilo "dinâmico e engraçado"
    python tools\\vlog\\vlog.py "<pasta>" --formato vertical --legendas 1 --duracao 3
    python tools\\vlog\\vlog.py "<pasta>" --refazer        (usa o plano.json que você ajustou, sem perguntar ao Gemini de novo)

O que faz, em ordem:
  1. clipes em ordem de gravação (data do iPhone); HDR → SDR antes de tudo (tools/sdr.py — a cor certa, sem CapCut)
  2. ouve cada clipe (faster-whisper) e mede movimento/volume; tira algumas fotos de cada um
  3. DIRETOR: o Gemini assiste (fotos + falas) e monta o roteiro: gancho no começo, ordem, o que corta (silêncio,
     tentativa repetida, enrolação), cenas de apoio, textos na tela, efeitos, transições e o CLIMA de cada parte
     (sem Gemini: corta os silêncios e intercala com as melhores cenas). Fica em <saída>\\plano.json (pode ajustar).
  4. monta: cortes secos dentro do mesmo clipe (jump cut), transições entre clipes (chicote, zoom, flash, fade),
     punch-in nas falas fortes, timelapse, texto na tela, legendas (opcional), voz tratada
  5. efeitos sonoros da sua pasta (sons.json) nas transições e destaques; trilha por clima (pasta de músicas),
     abaixando quando você fala; final -14 LUFS → <saída>\\vlog.mp4

Músicas: pasta (padrão E:\\DETTO\\musicas) com subpastas por clima: animado, tranquilo, engracado, emocionante,
tenso, epico (ou o clima no nome do arquivo). Biblioteca de áudio do YouTube = sem atribuição.
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
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
sys.path.insert(0, str(TOOLS))
from sdr import master_sdr, audio_bom, tem_nvenc  # noqa: E402

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv", ".avi"}
CLIMAS = ["animado", "tranquilo", "engracado", "emocionante", "tenso", "epico"]
TRANS = {"whip": "hblur", "zoom": "zoomin", "flash": "fadewhite", "fade": "fade", "slide": "slideleft"}
VOZ = None


def log(m):
    print(m, flush=True)


def le_json(f, padrao):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def grava_json(f, d):
    Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def sonda(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:format_tags=creation_time,com.apple.quicktime.creationdate"
                        ":stream=codec_type,width,height,r_frame_rate:stream_side_data=rotation", "-of", "json", str(f)],
                       capture_output=True, text=True)
    j = json.loads(r.stdout or "{}")
    fmt = j.get("format", {})
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    w, h = int(v.get("width") or 1920), int(v.get("height") or 1080)
    rot = 0
    for sd in v.get("side_data_list") or []:
        if "rotation" in sd:
            rot = abs(int(sd["rotation"]))
    if rot in (90, 270):
        w, h = h, w
    try:
        a_, b_ = (v.get("r_frame_rate") or "30/1").split("/")
        fps = float(a_) / float(b_)
    except Exception:
        fps = 30.0
    tags = fmt.get("tags") or {}
    quando = tags.get("com.apple.quicktime.creationdate") or tags.get("creation_time") or ""
    return {"dur": float(fmt.get("duration") or 0), "w": w, "h": h, "fps": fps, "quando": quando,
            "audio": any(s.get("codec_type") == "audio" for s in j.get("streams", []))}


def ordem_gravacao(f):
    s = sonda(f)
    q = s["quando"]
    try:
        return dt.datetime.fromisoformat(q.replace("Z", "+00:00")).timestamp()
    except Exception:
        return f.stat().st_mtime


# ------------------------------------------------------------------ análise
_MODELO = None


def transcreve(video, saida):
    global _MODELO
    if saida.exists():
        return le_json(saida, [])
    import transcrever as T
    T.dlls_nvidia()
    if _MODELO is None:
        from faster_whisper import WhisperModel
        try:
            _MODELO = WhisperModel(os.environ.get("DETTO_WHISPER", "small"), device="cuda", compute_type="int8_float16")
        except Exception:
            _MODELO = WhisperModel(os.environ.get("DETTO_WHISPER", "small"), device="cpu", compute_type="int8")
    try:
        segs, _ = _MODELO.transcribe(str(video), language="pt", word_timestamps=True, vad_filter=True)
        palavras = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for seg in segs for w in (seg.words or [])]
    except Exception as e:
        log(f"   (sem fala ou erro na transcrição: {str(e)[:80]})")
        palavras = []
    grava_json(saida, palavras)
    return palavras


def frases(palavras, gap=0.7):
    out = []
    for w in palavras:
        if out and w["s"] - out[-1]["e"] <= gap:
            out[-1]["e"] = w["e"]
            out[-1]["t"] += " " + w["w"]
        else:
            out.append({"s": w["s"], "e": w["e"], "t": w["w"]})
    return out


def energia(video, dur):
    """movimento da imagem (0–100) e volume (dB) por segundo"""
    import numpy as np
    W, H = 48, 48
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps=4,scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                       capture_output=True)
    a = np.frombuffer(r.stdout, np.uint8)
    mov = []
    if a.size >= W * H * 2:
        a = a[: a.size // (W * H) * W * H].reshape(-1, H, W).astype(np.float32)
        d = np.concatenate([[0.0], np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))])
        mov = [round(float(d[i:i + 4].mean()), 1) for i in range(0, len(d), 4)]
    k = audio_bom(video)
    vol = []
    if k is not None:
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-map", f"0:a:{k}", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"],
                           capture_output=True)
        s = np.frombuffer(r.stdout, np.float32)
        for i in range(0, len(s), 8000):
            q = s[i:i + 8000]
            vol.append(round(float(20 * np.log10(np.sqrt((q ** 2).mean()) + 1e-6)), 1) if len(q) else -90.0)
    return mov, vol


def fotos(video, dur, pasta, n=6):
    pasta.mkdir(parents=True, exist_ok=True)
    out = []
    n = max(2, min(n, int(dur // 3) + 1))
    for k in range(n):
        t = dur * (k + 0.5) / n
        f = pasta / f"{video.stem}_{k}.jpg"
        if not f.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=320:-2", "-q:v", "6", str(f)])
        if f.exists():
            out.append({"t": round(t, 1), "f": str(f)})
    return out


def analisa(clipes, job):
    """clipes = [{"orig","sdr"}] → lista com duração, falas, movimento, volume e fotos de cada um"""
    out = []
    (job / "analise").mkdir(exist_ok=True)
    for i, c in enumerate(clipes):
        v = Path(c["sdr"])
        cache = job / "analise" / f"{i:03d}.json"
        a = le_json(cache, None)
        if a and a.get("arq") == str(v):
            out.append(a)
            continue
        log(f"   analisando {i + 1}/{len(clipes)}: {Path(c['orig']).name}")
        s = sonda(v)
        pal = transcreve(v, job / "analise" / f"{i:03d}_words.json") if s["audio"] else []
        mov, vol = energia(v, s["dur"])
        a = {"i": i, "arq": str(v), "orig": c["orig"], "dur": s["dur"], "w": s["w"], "h": s["h"], "fps": s["fps"],
             "frases": frases(pal), "palavras": len(pal), "mov": mov, "vol": vol, "fotos": fotos(v, s["dur"], job / "fotos")}
        (job / "analise").mkdir(exist_ok=True)
        grava_json(cache, a)
        out.append(a)
    return out


# ------------------------------------------------------------------ plano (o "diretor")
def prompt_diretor(an, titulo, estilo, alvo_min, formato):
    linhas = []
    for a in an:
        fr = " | ".join(f"[{f['s']:.1f}-{f['e']:.1f}] {f['t']}" for f in a["frases"])[:2500]
        mov = sum(a["mov"]) / max(1, len(a["mov"]))
        linhas.append(f"CLIPE {a['i']} (dura {a['dur']:.1f}s, movimento {mov:.0f}): falas: {fr or '(sem fala)'}")
    return f"""Você é o editor de vlogs do criador @detto.galo (futebol/humor, Belo Horizonte). Edite no estilo de vlogs
brasileiros como Afreim e Renato Cariani: ritmo rápido, jump cuts tirando silêncio e enrolação, gancho forte nos
primeiros segundos, cenas de apoio curtas entre as falas, textos na tela situando (lugar/momento), efeitos sonoros
pontuais, trilha que muda de clima conforme a parte. Estilo pedido: {estilo or 'dinâmico, divertido, verdadeiro'}.
Título: {titulo or '(você sugere)'}. Formato: {formato}. Duração alvo: ~{alvo_min} min (pode ser menos se o material for curto).

Material (os clipes estão na ordem em que foram gravados; as fotos de cada clipe vêm em seguida, com o tempo):
{chr(10).join(linhas)}

Regras:
- "trechos" em ORDEM de exibição. Comece com um GANCHO de 3–8 s (o momento mais forte/engraçado de qualquer clipe),
  depois siga a ordem cronológica.
- Trecho de fala: comece e termine nos limites das frases indicadas (não corte palavra); tire repetições,
  "é... é...", tentativas refeitas e silêncios. Trecho de cena (sem fala): 1,5–4 s, só o melhor.
- tipo: "fala" | "cena" | "timelapse" (cena longa acelerada 3x, 2–4 s no vídeo final).
- zoom: "punch" em frases de impacto/piada (no máx. 1 a cada ~20 s), senão "nada".
- texto: texto CURTO na tela (ex.: "DIA 1 • BH", "06:30 TREINO") só quando ajuda a situar; senão "".
- transicao (antes do trecho): "corte" (padrão, mesmo clipe), "whip", "zoom", "flash" ou "fade" (troca de lugar/momento).
- sfx: "whoosh" | "boom" | "risada" | "ding" | "pop" | "fail" | "nenhum" (pouco: 1 a cada ~15 s).
- secoes: agrupe os trechos em partes de 30–120 s, cada uma com um clima de trilha: {", ".join(CLIMAS)}.

Responda SÓ JSON:
{{"titulo": "...", "secoes": [{{"clima": "animado", "trechos": [{{"clip": 0, "ini": 1.2, "fim": 6.8, "tipo": "fala",
"zoom": "nada", "texto": "", "transicao": "corte", "sfx": "nenhum"}}]}}]}}"""


def diretor_gemini(an, titulo, estilo, alvo_min, formato):
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    from roteiro_ia import gerar
    partes = [{"text": prompt_diretor(an, titulo, estilo, alvo_min, formato)}]
    total = 0
    for a in an:
        for f in a["fotos"][:5]:
            if total >= 120:
                break
            try:
                partes.append({"text": f"clipe {a['i']} t={f['t']}s:"})
                partes.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(Path(f["f"]).read_bytes()).decode()}})
                total += 1
            except OSError:
                pass
    corpo = json.dumps({"contents": [{"parts": partes}], "generationConfig": {"temperature": 0.6, "responseMimeType": "application/json"}}).encode()
    try:
        r = gerar(corpo, log=log)
        txt = r["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
    except Exception as e:
        log(f"   Gemini não montou o plano ({str(e)[:150]}); sigo com o automático")
        return None


def diretor_simples(an, titulo, alvo_min):
    """sem Gemini: falas sem silêncio, na ordem; clipe sem fala vira cena curta (o melhor movimento)"""
    trechos = []
    melhor = None
    for a in an:
        ini_clip = True
        if a["frases"]:
            for f in a["frases"]:
                if f["e"] - f["s"] < 0.6:
                    continue
                trechos.append({"clip": a["i"], "ini": max(0, f["s"] - 0.12), "fim": min(a["dur"], f["e"] + 0.2), "tipo": "fala",
                                "zoom": "nada", "texto": "", "transicao": "whip" if ini_clip and trechos else "corte",
                                "sfx": "whoosh" if ini_clip and trechos else "nenhum"})
                ini_clip = False
                vol = max(a["vol"][int(f["s"]):int(f["e"]) + 1] or [-90])
                if 3 <= f["e"] - f["s"] <= 9 and (melhor is None or vol > melhor[0]):
                    melhor = (vol, a["i"], f)
        else:
            mov = a["mov"] or [0]
            if a["dur"] >= 8:
                trechos.append({"clip": a["i"], "ini": 0.5, "fim": min(a["dur"] - 0.2, 0.5 + 9), "tipo": "timelapse", "zoom": "nada", "texto": "",
                                "transicao": "fade" if trechos else "corte", "sfx": "nenhum"})
            else:
                k = max(range(len(mov)), key=lambda i: mov[i]) if mov else 0
                ini = max(0.0, min(a["dur"] - 3.0, k - 1.0))
                trechos.append({"clip": a["i"], "ini": ini, "fim": min(a["dur"], ini + 3.0), "tipo": "cena", "zoom": "nada", "texto": "",
                                "transicao": "zoom" if trechos else "corte", "sfx": "whoosh" if trechos else "nenhum"})
    if melhor:  # gancho: a fala mais forte
        _, ci, f = melhor
        trechos.insert(0, {"clip": ci, "ini": max(0, f["s"] - 0.1), "fim": f["e"] + 0.2, "tipo": "fala", "zoom": "punch",
                           "texto": "", "transicao": "corte", "sfx": "boom"})
        if len(trechos) > 1:
            trechos[1]["transicao"], trechos[1]["sfx"] = "flash", "whoosh"
    # partes de ~75 s alternando o clima
    secoes, atual, acum, k = [], [], 0.0, 0
    for t in trechos:
        atual.append(t)
        acum += (t["fim"] - t["ini"]) / (3 if t["tipo"] == "timelapse" else 1)
        if acum >= 75:
            secoes.append({"clima": ["animado", "tranquilo", "engracado"][k % 3], "trechos": atual})
            atual, acum, k = [], 0.0, k + 1
    if atual:
        secoes.append({"clima": ["animado", "tranquilo", "engracado"][k % 3], "trechos": atual})
    return {"titulo": titulo, "secoes": secoes}


def limpa_plano(plano, an):
    """confere o que veio do Gemini: clipe existe, tempos dentro do clipe e nos limites das falas"""
    por_i = {a["i"]: a for a in an}
    for s in plano.get("secoes", []):
        if s.get("clima") not in CLIMAS:
            s["clima"] = "animado"
        ok = []
        for t in s.get("trechos", []):
            a = por_i.get(int(t.get("clip", -1)) if str(t.get("clip", "")).lstrip("-").isdigit() else -1)
            if not a:
                continue
            ini, fim = float(t.get("ini", 0)), float(t.get("fim", 0))
            ini, fim = max(0.0, ini), min(a["dur"] - 0.05, fim)
            if t.get("tipo") == "fala":
                # não cortar palavra: puxa para a frase que contém o ponto
                for f in a["frases"]:
                    if f["s"] - 0.3 <= ini <= f["e"]:
                        ini = min(ini, max(0.0, f["s"] - 0.1))
                    if f["s"] <= fim <= f["e"] + 0.3:
                        fim = max(fim, min(a["dur"] - 0.05, f["e"] + 0.15))
            if fim - ini < 0.5:
                continue
            t.update(clip=a["i"], ini=round(ini, 2), fim=round(fim, 2))
            t["tipo"] = t.get("tipo") if t.get("tipo") in ("fala", "cena", "timelapse") else "fala"
            t["transicao"] = t.get("transicao") if t.get("transicao") in ("corte", *TRANS) else "corte"
            t["zoom"] = "punch" if t.get("zoom") == "punch" else "nada"
            t["texto"] = str(t.get("texto") or "")[:40]
            t["sfx"] = t.get("sfx") or "nenhum"
            ok.append(t)
        s["trechos"] = ok
    plano["secoes"] = [s for s in plano.get("secoes", []) if s["trechos"]]
    return plano


# ------------------------------------------------------------------ render
def cadeia_voz():
    modelo = TOOLS / "motion" / "rnnoise_sh.rnnn"
    ruido = "afftdn=nf=-25"
    if modelo.exists() and modelo.stat().st_size > 1000:
        ruido = "arnndn=m=rnnoise.rnnn:mix=0.85"  # cópia no job (caminho sem ":" do Windows)
    return ",".join(["highpass=f=75", ruido, "equalizer=f=250:width_type=o:width=1:g=-2", "equalizer=f=3500:width_type=o:width=1.5:g=3",
                     "deesser=i=0.4", "acompressor=threshold=-20dB:ratio=3:attack=5:release=120:makeup=2"])


def enc_video(rapido=True):
    if tem_nvenc():
        return ["-c:v", "h264_nvenc", "-preset", "p5" if rapido else "p6", "-rc", "vbr", "-cq", "19" if rapido else "18", "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "veryfast" if rapido else "medium", "-crf", "18"]


def esc_txt(s):
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019").replace("%", "\\%")


def render_trecho(t, a, W, H, fps, saida, job):
    """um trecho pronto no tamanho final: enquadrado (vertical num vlog horizontal = fundo desfocado), punch-in,
    timelapse, texto na tela; voz tratada. Mesmo formato em todos (para emendar com transição)."""
    ini, fim = t["ini"], t["fim"]
    vel = 3.0 if t["tipo"] == "timelapse" else 1.0
    sw, sh = a["w"], a["h"]
    mesmo_formato = (sw >= sh) == (W >= H)
    z = 1.12 if t.get("zoom") == "punch" else 1.0
    if mesmo_formato:
        vf = f"scale={int(W * z)}:{int(H * z)}:force_original_aspect_ratio=increase,crop={W}:{H}"
    else:
        vf = (f"split[ca][cb];[ca]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.08[fundo];"
              f"[cb]scale={int(W * z)}:{int(H * z)}:force_original_aspect_ratio=decrease[frente];[fundo][frente]overlay=(W-w)/2:(H-h)/2")
    vf += f",setpts=(PTS-STARTPTS)/{vel},fps={fps},setsar=1,format=yuv420p"
    if t.get("texto"):
        txt = esc_txt(t["texto"].upper())
        tam = int(H * (0.055 if W >= H else 0.04))
        vf += (f",drawtext=fontfile=fonte.ttf:text='{txt}':fontsize={tam}:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw={tam // 3}"
               f":x=w*0.05:y=h*0.08:enable='lt(t,3.2)':alpha='if(lt(t,0.25),t/0.25,if(gt(t,2.9),(3.2-t)/0.3,1))'")
    dur_saida = (fim - ini) / vel
    k = audio_bom(a["arq"])
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{ini:.3f}", "-to", f"{fim:.3f}", "-i", a["arq"]]
    if k is not None and vel == 1.0:
        cmd += ["-filter_complex", f"[0:v]{vf}[v];[0:a:{k}]{VOZ},aresample=48000,aformat=channel_layouts=stereo[a]", "-map", "[v]", "-map", "[a]"]
    else:
        # timelapse/sem áudio: silêncio (a trilha cobre)
        cmd += ["-f", "lavfi", "-t", f"{dur_saida:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
                "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-map", "1:a"]
    cmd += ["-t", f"{dur_saida:.3f}"] + enc_video(True) + ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(saida)]
    r = subprocess.run(cmd, cwd=str(job), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"trecho {saida.name}: {r.stderr[-400:]}")
    return dur_saida


def legendas_ass(itens, W, H, saida):
    """legenda das falas (2–4 palavras por vez), estilo vlog: branca, contorno preto, embaixo"""
    def ts(x):
        x = max(0.0, x)
        return f"{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}"
    tam = int(H * (0.05 if W < H else 0.06))
    y = int(H * (0.28 if W < H else 0.1))
    linhas = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "", "[V4+ Styles]",
              "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
              "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
              f"Style: L,Inter ExtraBold,{tam},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,{max(3, tam // 14)},2,2,40,40,{y},1",
              "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for s, e, txt in itens:
        linhas.append(f"Dialogue: 0,{ts(s)},{ts(e)},L,,0,0,0,,{txt.upper()}")
    Path(saida).write_text("\n".join(linhas) + "\n", encoding="utf-8")


def monta(plano, an, job, W, H, fps, legendas, log=log):
    """renderiza os trechos e emenda: corte seco = concat; transição = xfade (+ cruzamento do áudio)"""
    global VOZ
    VOZ = cadeia_voz()
    rn = TOOLS / "motion" / "rnnoise_sh.rnnn"
    if rn.exists():
        shutil.copyfile(rn, job / "rnnoise.rnnn")
    shutil.copyfile(PONTE / "fonts" / "Inter-ExtraBold.otf", job / "fonte.ttf")
    por_i = {a["i"]: a for a in an}
    pasta = job / "partes"
    pasta.mkdir(exist_ok=True)
    itens = []
    n = sum(len(s["trechos"]) for s in plano["secoes"])
    k = 0
    for si, s in enumerate(plano["secoes"]):
        for t in s["trechos"]:
            k += 1
            f = pasta / f"{k:04d}.mp4"
            chave = json.dumps([t, W, H, fps], sort_keys=True)
            marca = f.with_suffix(".json")
            if f.exists() and marca.exists() and marca.read_text(encoding="utf-8") == chave:
                d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                         capture_output=True, text=True).stdout or 0)
            else:
                log(f"   trecho {k}/{n} (clipe {t['clip']} {t['ini']:.1f}–{t['fim']:.1f}s, {t['tipo']})")
                d = render_trecho(t, por_i[t["clip"]], W, H, fps, f, job)
                marca.write_text(chave, encoding="utf-8")
            itens.append({"f": f, "d": d, "t": t, "secao": si})
    # emenda: blocos de cortes secos (concat) ligados por transições (xfade)
    TD = 0.3
    entradas, filtros = [], []
    pos = 0.0  # tempo no vídeo final
    marcas = []  # (tempo, sfx) e início de cada seção
    inicio_secao = {}
    falas = []
    cur_v, cur_a = None, None
    for idx, it in enumerate(itens):
        entradas += ["-i", str(it["f"])]
        # mesma base de tempo em tudo (o xfade recusa misturar a do concat com a do arquivo)
        filtros.append(f"[{idx}:v]setpts=PTS-STARTPTS,fps={fps},settb=1/{fps},format=yuv420p[iv{idx}];"
                       f"[{idx}:a]asettb=AVTB,asetpts=PTS-STARTPTS,aresample=48000[ia{idx}]")
        v, a_ = f"[iv{idx}]", f"[ia{idx}]"
        tr = it["t"]["transicao"] if idx else "corte"
        if cur_v is None:
            cur_v, cur_a, pos = v, a_, it["d"]
            ini_item = 0.0
        elif tr == "corte" or it["d"] < TD * 3 or pos < TD * 3:
            filtros.append(f"{cur_v}{cur_a}{v}{a_}concat=n=2:v=1:a=1[cv{idx}][a{idx}];[cv{idx}]settb=1/{fps}[v{idx}]")
            ini_item = pos
            pos += it["d"]
            cur_v, cur_a = f"[v{idx}]", f"[a{idx}]"
        else:
            off = pos - TD
            filtros.append(f"{cur_v}{v}xfade=transition={TRANS[tr]}:duration={TD}:offset={off:.3f}[v{idx}]")
            filtros.append(f"{cur_a}{a_}acrossfade=d={TD}:c1=tri:c2=tri[a{idx}]")
            ini_item = off
            pos = off + it["d"]
            cur_v, cur_a = f"[v{idx}]", f"[a{idx}]"
        inicio_secao.setdefault(it["secao"], ini_item)
        sfx = it["t"].get("sfx")
        if sfx and sfx != "nenhum":
            marcas.append((max(0.0, ini_item - (0.12 if tr != "corte" else 0.0)), sfx))
        # legendas: falas do trecho no tempo do vídeo final
        if legendas and it["t"]["tipo"] == "fala":
            pal = le_json(job / "analise" / f"{it['t']['clip']:03d}_words.json", [])
            sel = [w for w in pal if it["t"]["ini"] <= w["s"] < it["t"]["fim"]]
            for g in range(0, len(sel), 3):
                bloco = sel[g:g + 3]
                s0 = ini_item + bloco[0]["s"] - it["t"]["ini"]
                e0 = ini_item + min(bloco[-1]["e"], it["t"]["fim"]) - it["t"]["ini"]
                falas.append((s0, max(e0, s0 + 0.3), " ".join(w["w"] for w in bloco).replace("{", "").replace("}", "")))
    filtros.append(f"{cur_v}null[vfim];{cur_a}anull[afim]" if filtros else f"{cur_v}null[vfim];{cur_a}anull[afim]")
    # legendas por cima
    vf_final = "[vfim]"
    if legendas and falas:
        legendas_ass(falas, W, H, job / "legendas.ass")
        filtros.append("[vfim]ass=legendas.ass:fontsdir=.[vleg]")
        vf_final = "[vleg]"
    grafo = ";".join(filtros)
    (job / "grafo.txt").write_text(grafo, encoding="utf-8")
    sem = job / "vlog_sem_trilha.mp4"
    log(f"   emendando {len(itens)} trechos ({pos / 60:.1f} min)...")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y"] + entradas + ["-filter_complex_script", "grafo.txt", "-map", vf_final, "-map", "[afim]"]
                       + enc_video(False) + ["-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", sem.name],
                       cwd=str(job), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"emenda: {r.stderr[-600:]}")
    return sem, pos, marcas, inicio_secao


def efeitos(video, marcas, saida, job):
    """efeitos sonoros (sua pasta, sons.json) nos tempos marcados, ~12 dB abaixo da voz"""
    from biblioteca_sons import arquivo
    mapa = {"whoosh": "whoosh", "boom": "boom", "risada": "risada", "ding": "ding", "pop": "pop", "fail": "fail"}
    entradas, partes, n = [], [], 0
    usados = {}
    for t, nome in marcas:
        cat = mapa.get(nome)
        if not cat:
            continue
        f = arquivo(cat, usados.get(cat, 0))
        usados[cat] = usados.get(cat, 0) + 1
        if not f:
            continue
        n += 1
        entradas += ["-i", f]
        partes.append(f"[{n}:a]atrim=0:1.6,afade=t=out:st=1.2:d=0.4,aresample=48000,aformat=channel_layouts=stereo,"
                      f"loudnorm=I=-28:TP=-6,adelay={int(t * 1000)}|{int(t * 1000)}[s{n}]")
    if not n:
        shutil.copyfile(video, saida)
        return saida
    mix = "".join(f"[s{i}]" for i in range(1, n + 1))
    grafo = ";".join(partes) + f";[0:a]{mix}amix=inputs={n + 1}:normalize=0:duration=first[a]"
    (job / "grafo_sfx.txt").write_text(grafo, encoding="utf-8")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video)] + entradas + ["-filter_complex_script", "grafo_sfx.txt", "-map", "0:v",
                       "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(saida)], cwd=str(job), capture_output=True, text=True)
    if r.returncode != 0:
        log(f"   (efeitos sonoros não entraram: {r.stderr[-200:]})")
        shutil.copyfile(video, saida)
    return saida


def acha_musica(pasta, clima, usadas):
    pasta = Path(pasta)
    if not pasta.exists():
        return None
    aud = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
    todas = [p for p in pasta.rglob("*") if p.suffix.lower() in aud]
    if not todas:
        return None
    def norm(s):
        import unicodedata
        return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()
    do_clima = [p for p in todas if clima in norm(str(p.relative_to(pasta)))]
    lista = do_clima or todas
    nao = [p for p in lista if str(p) not in usadas] or lista
    escolha = random.choice(nao)
    usadas.add(str(escolha))
    return escolha


def trilha(video, plano, inicio_secao, musicas, saida):
    usadas = set()
    args = []
    for si, s in enumerate(plano["secoes"]):
        m = acha_musica(musicas, s["clima"], usadas)
        if not m:
            continue
        t = inicio_secao.get(si, 0.0)
        args.append(f"{int(t // 60)}:{t % 60:05.2f}={m}")
    if not args:
        log(f"   sem músicas em {musicas} (crie as pastas animado, tranquilo, engracado...): o vlog sai sem trilha")
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1", "-c:a", "aac",
                            "-b:a", "192k", str(saida)])
        return saida if r.returncode == 0 else video
    log(f"   trilha: {len(args)} música(s) por clima")
    r = subprocess.run([sys.executable, str(TOOLS / "trilha.py"), str(video)] + args + ["--saida", str(saida)])
    return saida if r.returncode == 0 and Path(saida).exists() else video


def folha(video, saida):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "fps=1/6,scale=320:-2,tile=6x4", "-frames:v", "1", str(saida)])


# ------------------------------------------------------------------ principal
def main():
    ap = argparse.ArgumentParser(description="editor de vlogs")
    ap.add_argument("pasta", help="pasta com os clipes (pode ser a do Google Drive)")
    ap.add_argument("--saida", help="pasta do trabalho (padrão: <pasta> vlog)")
    ap.add_argument("--titulo", default="")
    ap.add_argument("--estilo", default="", help='ex.: "dinâmico e engraçado, estilo Afreim"')
    ap.add_argument("--formato", choices=["horizontal", "vertical"], default="horizontal")
    ap.add_argument("--duracao", type=float, default=10, help="duração alvo em minutos")
    ap.add_argument("--legendas", type=int, default=None, help="1 = legenda das falas (padrão: só no vertical)")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--musicas", default=os.environ.get("DETTO_MUSICAS") or ("E:/DETTO/musicas" if os.name == "nt" else str(Path.home() / "DETTO" / "musicas")))
    ap.add_argument("--refazer", action="store_true", help="usa o plano.json existente (ajustado por você)")
    ap.add_argument("--sem-gemini", action="store_true")
    a = ap.parse_args()
    pasta = Path(a.pasta)
    clipes_orig = sorted((p for p in pasta.iterdir() if p.suffix.lower() in VIDEO_EXT and not p.stem.endswith(" SDR")), key=ordem_gravacao) \
        if pasta.is_dir() else []
    if not clipes_orig:
        sys.exit(f"Nenhum vídeo em {pasta}")
    job = Path(a.saida) if a.saida else pasta.with_name(pasta.name + " vlog")
    job.mkdir(parents=True, exist_ok=True)
    W, H = (1920, 1080) if a.formato == "horizontal" else (1080, 1920)
    legendas = (a.formato == "vertical") if a.legendas is None else bool(a.legendas)
    log(f"VLOG: {len(clipes_orig)} clipes de {pasta} → {job}")

    log("1/5 cor: HDR → SDR (uma vez por clipe)")
    (job / "clipes").mkdir(exist_ok=True)
    clipes = []
    for p in clipes_orig:
        try:
            s = master_sdr(p, saida=job / "clipes" / f"{p.stem}.mp4", log=log)
        except Exception as e:
            log(f"   {p.name}: {e} — uso o original")
            s = p
        clipes.append({"orig": str(p), "sdr": str(s)})

    log("2/5 ouvindo e olhando os clipes")
    an = analisa(clipes, job)

    log("3/5 roteiro do vlog")
    plano = le_json(job / "plano.json", None) if a.refazer else None
    if not plano:
        plano = None if a.sem_gemini else diretor_gemini(an, a.titulo, a.estilo, a.duracao, a.formato)
        plano = plano or diretor_simples(an, a.titulo, a.duracao)
    plano = limpa_plano(plano, an)
    if not plano["secoes"]:
        sys.exit("O plano ficou vazio (nada para mostrar).")
    grava_json(job / "plano.json", plano)
    n = sum(len(s["trechos"]) for s in plano["secoes"])
    log(f"   {n} trechos em {len(plano['secoes'])} partes: {', '.join(s['clima'] for s in plano['secoes'])}  (ajuste em {job / 'plano.json'})")

    log("4/5 montando (cortes, transições, textos, voz)")
    sem, dur, marcas, inicio_secao = monta(plano, an, job, W, H, a.fps, legendas)
    com_sfx = efeitos(sem, marcas, job / "vlog_sfx.mp4", job)

    log("5/5 trilha por clima")
    final = trilha(com_sfx, plano, inicio_secao, a.musicas, job / "vlog.mp4")
    folha(final, job / "vlog_conferir.jpg")
    for f in ("vlog_sem_trilha.mp4", "vlog_sfx.mp4"):
        if (job / f) != Path(final):
            (job / f).unlink(missing_ok=True)
    # disco: os trechos renderizados saem (o --refazer refaz rápido a partir dos clipes SDR, que ficam)
    if Path(final) == job / "vlog.mp4":
        shutil.rmtree(job / "partes", ignore_errors=True)
    log(f"\nPronto: {final}  ({dur / 60:.1f} min)\nPlano (para ajustar e rodar com --refazer): {job / 'plano.json'}")


if __name__ == "__main__":
    main()
