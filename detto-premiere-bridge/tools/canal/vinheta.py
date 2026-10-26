# -*- coding: utf-8 -*-
"""VINHETA DE ABERTURA dos vídeos horizontais — faz uma vez por canal e emenda no começo do vídeo.

    python tools\\canal\\vinheta.py --canal noticias            → faz/refaz a vinheta do canal de notícias
    python tools\\canal\\vinheta.py --canal vlog --dur 2.5      → a do EVERTON LOPES, mais curta
    python tools\\canal\\vinheta.py --ver <video.mp4>           → emenda a vinheta nesse vídeo (teste)

A vinheta fica guardada em `<DETTO>\\marca\\vinheta_<canal>_<LxA>_<fps>.mp4` e só é refeita quando o nome do canal
muda (ou com `--refazer`): montar custa alguns segundos de Chromium, e o vídeo de todo dia só emenda o arquivo.

`abre(video, saida, canal, nome, cfg)` é o que o editar.py / canal.py / canal_vlog.py chamam: ela faz a vinheta no
mesmo tamanho e fps do vídeo e devolve o vídeo com a abertura na frente (sem re-render do seu vídeo quando dá).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent

CANAIS = {
    # o canal de notícias: cara de telejornal, com o selo PLANTÃO
    "noticias": {"nome": "DETTO GALO NOTÍCIAS", "dur": 3.0, "estilo": "noticias", "selo": "@", "sub": "@"},
    # o canal principal (@detto.galo): mesma cara amarelo-e-preto, sem plantão, com a resenha
    "galo": {"nome": "DETTO GALO", "dur": 2.4, "estilo": "noticias", "selo": "", "sub": "RESENHA DO GALO"},
    # vlogs e gameplays
    "vlog": {"nome": "EVERTON LOPES", "dur": 2.6, "estilo": "vlog", "selo": "@", "sub": "@"},
}


def log(m):
    print(m, flush=True)


def pasta_marca():
    if os.name == "nt" and Path("E:/").exists():
        return Path("E:/DETTO/marca")
    return Path.home() / "DETTO" / "marca"


def _ff(args):
    return subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, text=True)


def formato(video):
    """(largura, altura, fps, tem_audio) do vídeo"""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate", "-of", "csv=p=0", str(video)], capture_output=True, text=True)
    p = (r.stdout or "").strip().split(",")
    try:
        w, h = int(p[0]), int(p[1])
        n, d = (p[2].split("/") + ["1"])[:2]
        fps = round(float(n) / float(d or 1))
    except (IndexError, ValueError):
        return 1920, 1080, 30, True
    a = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                        "-of", "csv=p=0", str(video)], capture_output=True, text=True)
    return w, h, max(1, fps), bool((a.stdout or "").strip())


def faz(canal="noticias", nome="", dur=0.0, w=1920, h=1080, fps=30, pasta=None, refazer=False, log=log):
    """a vinheta do canal nesse tamanho/fps (guardada; só refaz quando precisa)"""
    c = CANAIS.get(canal, CANAIS["noticias"])
    nome = (nome or c["nome"]).strip()
    dur = float(dur or c["dur"])
    base = Path(pasta or pasta_marca()).resolve()   # o node roda noutra pasta: o caminho tem que ser absoluto
    base.mkdir(parents=True, exist_ok=True)
    arq = base / f"vinheta_{canal}_{w}x{h}_{fps}.mp4"
    marca = arq.with_suffix(".json")
    igual = marca.exists() and arq.exists()
    if igual and not refazer:
        try:
            d = json.loads(marca.read_text(encoding="utf-8"))
            if d.get("nome") == nome and abs(float(d.get("dur", 0)) - dur) < 0.01 and d.get("v") == 2:
                return arq
        except (OSError, ValueError):
            pass
    log(f"vinheta: montando a do canal {canal} ({nome}, {dur:.1f}s, {w}x{h}, {fps} fps)")
    r = subprocess.run(["node", str(AQUI / "vinheta.js"), "--canal", c.get("estilo", canal), "--nome", nome,
                        "--out", str(arq), "--dur", f"{dur:.2f}", "--fps", str(fps), "--largura", str(w),
                        "--altura", str(h), "--selo", c.get("selo", "@"), "--sub", c.get("sub", "@")],
                       cwd=str(PONTE), capture_output=True, text=True)
    if r.returncode != 0 or not arq.exists():
        log(f"vinheta: não consegui montar ({(r.stderr or r.stdout or '')[-200:]})")
        return None
    marca.write_text(json.dumps({"nome": nome, "dur": dur, "v": 2}, ensure_ascii=False), encoding="utf-8")
    return arq


def duracao(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def emenda(vinheta, video, saida, log=log, em=0.0):
    """põe a vinheta no vídeo. `em` = em que segundo ela entra (0 = na frente).
    VINHETA NO SEGUNDO 0 QUEBRA A RETENÇÃO (26/out): quem abre o vídeo tem que ouvir a chamada primeiro; a
    abertura do canal entra DEPOIS dela. Os pedaços são padronizados (tamanho, fps, áudio) para o concat não falhar."""
    vinheta, video, saida = Path(vinheta).resolve(), Path(video).resolve(), Path(saida).resolve()
    if not (vinheta.exists() and video.exists()):
        return None
    w, h, fps, tem_audio = formato(video)
    total = duracao(video)
    em = float(em or 0)
    if em < 0.3 or (total and em > total - 0.5):
        em = 0.0   # não dá para partir aqui: volta para a frente do vídeo
    sys.path.insert(0, str(TOOLS))
    from ffcompat import filtro_complexo

    def norm_v(i, rot):
        if rot == "vin":
            return f"[{i}:v]scale={w}:{h},setsar=1,fps={fps},format=yuv420p[v{i}];"
        return (f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p[v{i}];")

    def norm_a(i, rot):
        if rot == "vin" or tem_audio:
            return f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}];"
        return f"anullsrc=r=48000:cl=stereo,atrim=0:3600[a{i}];"   # vídeo sem áudio: silêncio no lugar

    if em:
        # [vídeo até `em`] + [vinheta] + [resto do vídeo]
        entradas = ["-t", f"{em:.3f}", "-i", str(video), "-i", str(vinheta), "-ss", f"{em:.3f}", "-i", str(video)]
        tipos = ["vid", "vin", "vid"]
    else:
        entradas = ["-i", str(vinheta), "-i", str(video)]
        tipos = ["vin", "vid"]
    grafo = "".join(norm_v(i, t) for i, t in enumerate(tipos)) + "".join(norm_a(i, t) for i, t in enumerate(tipos))
    grafo += "".join(f"[v{i}][a{i}]" for i in range(len(tipos))) + f"concat=n={len(tipos)}:v=1:a=1[v][a]"
    g = saida.parent / "_vinheta_grafo.txt"
    g.parent.mkdir(parents=True, exist_ok=True)
    g.write_text(grafo, encoding="utf-8")
    r = _ff([*entradas, *filtro_complexo(str(g)), "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(saida)])
    g.unlink(missing_ok=True)
    if r.returncode != 0 or not saida.exists():
        log(f"vinheta: não emendei ({(r.stderr or '')[-200:]})")
        return None
    return saida


def abre(video, canal="noticias", nome="", cfg=None, saida=None, log=log, em=0.0):
    """O QUE OS PROGRAMAS CHAMAM: devolve o vídeo com a vinheta (ou o original, se algo falhar).
    `em` = o segundo em que ela entra. A abertura NÃO vai mais no segundo 0: isso quebrava a retenção — quem abre
    o vídeo tem que ouvir a chamada/resumo com o CTA primeiro, e só então vem a vinheta (`"vinheta_em"` no config
    força um segundo fixo; 0 = na frente, como era).
    `cfg` é o config do canal: `"vinheta": false` desliga, `"vinheta_s"` muda a duração."""
    cfg = cfg or {}
    if cfg.get("vinheta") is False:
        return Path(video)
    video = Path(video)
    w, h, fps, _ = formato(video)
    if h > w:   # a vinheta é da abertura do YouTube (horizontal); no 9:16 ela não entra
        return video
    v = faz(canal, nome or cfg.get("nome_canal", ""), float(cfg.get("vinheta_s", 0) or 0), w, h, fps, log=log)
    if not v:
        return video
    if cfg.get("vinheta_em") is not None:
        em = float(cfg["vinheta_em"] or 0)
    alvo = Path(saida) if saida else video.with_name(video.stem + "_vinheta.mp4")
    if not emenda(v, video, alvo, log, em=em):
        return video
    if not saida:   # troca o vídeo pelo que tem a vinheta (o nome que o resto do sistema espera)
        video.unlink(missing_ok=True)
        alvo.replace(video)
        alvo = video
    log(f"vinheta: abertura do canal {canal} em {alvo.name} " + (f"aos {em:.1f}s (depois da chamada)" if em >= 0.3 else "na frente"))
    return alvo


def main():
    ap = argparse.ArgumentParser(description="vinheta de abertura dos vídeos horizontais")
    ap.add_argument("--canal", default="noticias", choices=list(CANAIS))
    ap.add_argument("--nome", default="", help="nome do canal na vinheta (padrão: o do canal)")
    ap.add_argument("--dur", type=float, default=0.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--largura", type=int, default=1920)
    ap.add_argument("--altura", type=int, default=1080)
    ap.add_argument("--pasta", default="")
    ap.add_argument("--refazer", action="store_true")
    ap.add_argument("--ver", default="", help="emenda a vinheta neste vídeo e salva ao lado (teste)")
    ap.add_argument("--em", type=float, default=0.0, help="segundo em que a vinheta entra (0 = na frente)")
    a = ap.parse_args()
    v = faz(a.canal, a.nome, a.dur, a.largura, a.altura, a.fps, a.pasta or None, a.refazer)
    if not v:
        return
    log(f"pronto: {v}")
    if a.ver:
        s = Path(a.ver).with_name(Path(a.ver).stem + "_com_vinheta.mp4")
        log(f"com a vinheta: {emenda(v, a.ver, s, em=a.em)}")


if __name__ == "__main__":
    main()
