# -*- coding: utf-8 -*-
"""ALA GALO: reel vertical do jogo com você no estádio, o placar no topo e os jogadores
(recortados, com contorno branco de figurinha) entrando e saindo ao seu lado.

    python tools/galo/galo.py jogo.json

jogo.json (exemplo em tools/galo/jogo.exemplo.json):
{
  "video": "C:/Users/guebe/Videos/edicao ia/gravacao.mp4",
  "saida": "C:/Users/guebe/Videos/edicao ia/galo_final.mp4",
  "placar": {"competicao": "Brasileirão Série A", "quando": "Hoje", "status": "Encerrado",
             "casa": "Atlético-MG", "fora": "Remo", "gols_casa": 3, "gols_fora": 3,
             "escudo_casa": "banco/escudos/atletico.png", "escudo_fora": "banco/escudos/remo.png"},
  "jogadores": [{"nome": "Sampaoli", "foto": "banco/elenco/sampaoli.png"}, {"nome": "Hulk"}],
  "tempos": [],              // opcional: [[entra, sai], ...] em segundos; vazio = automático
  "placar_y": 0.15,          // altura do placar (0 = topo)
  "lado": "alternado",       // "direita", "esquerda" ou "alternado"
  "som": true,               // whoosh na entrada/saída (sem trilha musical)
  "audio_original": true     // mantém o som da gravação
}

Foto sem "foto": procura banco/elenco/<nome>.png|jpg. Foto sem transparência: o fundo é removido
com rembg (pip install rembg) e o recorte fica salvo no banco para os próximos jogos.
Tempos automáticos: os picos de movimento da gravação (seus gestos) viram as entradas;
se não houver gestos claros, divide o vídeo igualmente entre os jogadores.
"""
import json
import subprocess
import sys
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = Path(__file__).resolve().parent
BANCO = AQUI / "banco"
ENTRA, SAI = 0.28, 0.24  # duração do deslize (s)


def slug(s):
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return "".join(c if c.isalnum() else "-" for c in s).strip("-")


def sonda(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:format=duration", "-of", "json", str(video)],
                       capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


def fonte(tam, negrito=False):
    nomes = (["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"] if negrito
             else ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"])
    for n in nomes:
        for base in ["", "C:/Windows/Fonts/", "/usr/share/fonts/truetype/dejavu/",
                     "/usr/share/fonts/truetype/liberation/"]:
            try:
                return ImageFont.truetype(base + n, tam)
            except OSError:
                pass
    return ImageFont.load_default()


# ------------------------------------------------------------------ recorte do jogador

def achar_foto(j):
    if j.get("foto"):
        p = Path(j["foto"])
        return p if p.is_absolute() else (AQUI / p if (AQUI / p).exists() else p)
    for ext in ("png", "webp", "jpg", "jpeg"):
        p = BANCO / "elenco" / f"{slug(j['nome'])}.{ext}"
        if p.exists():
            return p
    raise SystemExit(f"Sem foto para {j['nome']}: coloque em {BANCO / 'elenco'} ou informe \"foto\"")


def recorte(j, altura):
    """PNG com transparência + contorno branco (estilo figurinha), recortado justo."""
    pronto = BANCO / "recortes" / f"{slug(j['nome'])}.png"
    foto = achar_foto(j)
    if pronto.exists() and pronto.stat().st_mtime >= foto.stat().st_mtime:
        img = Image.open(pronto).convert("RGBA")
    else:
        img = Image.open(foto).convert("RGBA")
        if np.asarray(img)[..., 3].min() == 255:  # sem transparência: tira o fundo
            try:
                from rembg import remove
            except ImportError:
                raise SystemExit("Foto sem fundo transparente e rembg não instalado: pip install rembg")
            img = remove(img)
        img = img.crop(img.getbbox())
        a = np.asarray(img)[..., 3]
        borda = max(4, img.height // 90)
        img = img.crop((-borda * 2, -borda * 2, img.width + borda * 2, img.height + borda * 2))
        a = np.asarray(img)[..., 3]
        dil = Image.fromarray(a).filter(ImageFilter.MaxFilter(borda * 2 + 1)).filter(ImageFilter.GaussianBlur(1))
        fundo = Image.new("RGBA", img.size, (255, 255, 255, 0))
        fundo.putalpha(dil)
        sombra = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sombra.putalpha(dil.filter(ImageFilter.GaussianBlur(borda * 2)).point(lambda v: v * 0.45))
        img = Image.alpha_composite(Image.alpha_composite(sombra, fundo), img)
        pronto.parent.mkdir(parents=True, exist_ok=True)
        img.save(pronto)
    esc = altura / img.height
    return img.resize((max(1, round(img.width * esc)), round(altura)), Image.LANCZOS)


# ------------------------------------------------------------------ placar (estilo card do Google)

def escudo(caminho, nome, tam):
    p = Path(caminho) if caminho else BANCO / "escudos" / f"{slug(nome)}.png"
    if not p.is_absolute() and not p.exists():
        p = AQUI / p
    if p.exists():
        e = Image.open(p).convert("RGBA")
        e.thumbnail((tam, tam), Image.LANCZOS)
        return e
    e = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    d = ImageDraw.Draw(e)
    d.ellipse((0, 0, tam - 1, tam - 1), fill=(40, 40, 40, 255))
    sig = "".join(w[0] for w in nome.split()[:2]).upper()
    f = fonte(tam // 3, True)
    d.text((tam / 2, tam / 2), sig, font=f, fill="white", anchor="mm")
    return e


def placar_png(pl, W):
    w = int(W * 0.62)
    h = int(w * 0.36)
    k = w / 450
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=int(10 * k), fill=(236, 237, 240, 245))
    pequena, media, grande = fonte(int(11 * k)), fonte(int(12 * k), True), fonte(int(30 * k))
    cinza, preto = (95, 99, 104), (32, 33, 36)
    d.text((18 * k, 16 * k), f"{pl.get('competicao', '')} · {pl.get('quando', 'Hoje')}", font=pequena, fill=cinza)
    d.text((w - 18 * k, 16 * k), pl.get("status", "Encerrado"), font=media, fill=preto, anchor="ra")
    cy, tam = h * 0.56, int(34 * k)
    for lado, x in (("casa", 40 * k), ("fora", w - 40 * k)):
        e = escudo(pl.get(f"escudo_{lado}"), pl.get(lado, ""), tam)
        img.alpha_composite(e, (int(x - e.width / 2), int(cy - e.height / 2)))
        d.text((x, h - 12 * k), pl.get(lado, ""), font=pequena, fill=cinza, anchor="md")
    d.text((w * 0.34, cy), str(pl.get("gols_casa", "")), font=grande, fill=preto, anchor="mm")
    d.text((w * 0.66, cy), str(pl.get("gols_fora", "")), font=grande, fill=preto, anchor="mm")
    d.text((w * 0.5, cy), "×", font=pequena, fill=cinza, anchor="mm")
    return img


# ------------------------------------------------------------------ quando cada jogador entra

def picos_de_movimento(video, n, dur):
    """Gestos = picos de diferença entre quadros (baixa resolução, 10 amostras/s)."""
    try:
        import cv2
    except ImportError:
        return None
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    passo = max(1, round(fps / 10))
    energia, ant, i = [], None, 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % passo == 0:
            g = cv2.cvtColor(cv2.resize(f, (90, 160)), cv2.COLOR_BGR2GRAY).astype(np.float32)
            energia.append(0 if ant is None else float(np.abs(g - ant).mean()))
            ant = g
        i += 1
    cap.release()
    e = np.convolve(np.array(energia), np.ones(5) / 5, mode="same")
    if len(e) < 20 or e.max() < 1.5:
        return None
    vaga = dur / n
    picos = []
    for k in range(n):  # um gesto por fatia do vídeo
        a, b = int(k * vaga * 10), int(min(len(e), (k + 1) * vaga * 10 - 15))
        if b <= a:
            return None
        picos.append((a + int(np.argmax(e[a:b]))) / 10)
    return picos


def calcular_tempos(cfg, n, dur):
    if cfg.get("tempos"):
        return [tuple(t) for t in cfg["tempos"]][:n]
    vaga = dur / n
    ini = picos_de_movimento(cfg["video"], n, dur) or [k * vaga + min(1.0, vaga * 0.2) for k in range(n)]
    tempos = []
    for k, t in enumerate(ini):
        fim = (ini[k + 1] - 0.15) if k + 1 < n else dur - 0.3
        tempos.append((max(0.05, t), max(t + 1.2, min(fim, t + vaga * 0.9))))
    return tempos


# ------------------------------------------------------------------ montagem (ffmpeg)

def whoosh(destino, dur):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"anoisesrc=d={dur}:c=pink:a=0.6", "-af",
                    f"highpass=f=400,lowpass=f=5000,afade=t=in:d={dur * 0.5},afade=t=out:st={dur * 0.5}:d={dur * 0.5},volume=0.5",
                    str(destino)], check=True)


def filtro_complexo(arq):
    """FFmpeg 7+ trocou -filter_complex_script por -/filter_complex."""
    import re as _re
    r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    m = _re.search(r"ffmpeg version n?(\d+)", r.stdout or "")
    return ["-/filter_complex", str(arq)] if (int(m.group(1)) if m else 7) >= 7 else ["-filter_complex_script", str(arq)]


def main():
    cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    video = Path(cfg["video"])
    W, H, dur = sonda(video)
    trab = Path(cfg.get("trabalho") or video.with_name("galo_tmp"))
    trab.mkdir(parents=True, exist_ok=True)

    entradas, filtros = ["-i", str(video)], []
    atual = "[0:v]"
    sys.path.insert(0, str(AQUI.parent))
    from cor import filtro_cor
    fc = filtro_cor(video)  # iPhone em HDR → SDR com a cor certa
    if fc:
        filtros.append(f"[0:v]{fc}[v0]")
        atual = "[v0]"
    if cfg.get("placar"):
        placar_png(cfg["placar"], W).save(trab / "placar.png")
        entradas += ["-loop", "1", "-i", str(trab / "placar.png")]
        filtros.append(f"{atual}[1:v]overlay=x=(W-w)/2:y=H*{float(cfg.get('placar_y', 0.15)):.3f}:shortest=1[v1]")
        atual = "[v1]"

    jogs = cfg["jogadores"]
    tempos = calcular_tempos(cfg, len(jogs), dur)
    lado_cfg = cfg.get("lado", "alternado")
    sons = []
    for k, (j, (t0, t1)) in enumerate(zip(jogs, tempos)):
        img = recorte(j, H * float(j.get("altura", 0.36)))
        arq = trab / f"j{k}.png"
        img.save(arq)
        idx = len([x for x in entradas if x == "-i"])
        entradas += ["-loop", "1", "-i", str(arq)]
        dir_ = (k % 2 == 0) if lado_cfg == "alternado" else (lado_cfg == "direita")
        alvo = W * (0.70 if dir_ else 0.30)       # ao seu lado
        X = f"({alvo:.0f}-w/2)"
        fora = "W" if dir_ else "(-w)"            # entra e sai pelo mesmo lado
        y = f"H-h-H*{float(j.get('base', 0.0)):.3f}"
        a = f"(t-{t0:.3f})/{ENTRA}"
        b = f"(t-{t1 - SAI:.3f})/{SAI}"
        x = (f"if(lt(t,{t0 + ENTRA:.3f}),{fora}+({X}-{fora})*(1-pow(1-{a},3))*(1+0.08*sin(PI*{a})),"
             f"if(gt(t,{t1 - SAI:.3f}),{X}+({fora}-{X})*pow({b},2),{X}))")
        filtros.append(f"{atual}[{idx}:v]overlay=x='{x}':y='{y}':enable='between(t,{t0:.3f},{t1:.3f})':shortest=1[v{k + 2}]")
        atual = f"[v{k + 2}]"
        sons += [t0, t1 - SAI]

    audio = []
    if cfg.get("som", True) and sons:
        whoosh(trab / "whoosh.wav", 0.35)
        base = len([x for x in entradas if x == "-i"])
        entradas += ["-i", str(trab / "whoosh.wav")]
        partes = [f"[{base}:a]asplit={len(sons)}" + "".join(f"[w{i}]" for i in range(len(sons)))]
        for i, t in enumerate(sons):
            partes.append(f"[w{i}]adelay={int(t * 1000)}:all=1[d{i}]")
        mix = "".join(f"[d{i}]" for i in range(len(sons)))
        if cfg.get("audio_original", True):
            partes.append(f"[0:a]{mix}amix=inputs={len(sons) + 1}:duration=first:normalize=0[a]")
        else:
            partes.append(f"anullsrc=r=48000:cl=stereo:d={dur}[sil];[sil]{mix}amix=inputs={len(sons) + 1}:duration=first:normalize=0[a]")
        filtros += partes
        audio = ["-map", "[a]"]
    elif cfg.get("audio_original", True):
        audio = ["-map", "0:a?"]

    script = trab / "filtro.txt"
    script.write_text(";\n".join(filtros), encoding="utf-8")
    saida = cfg.get("saida") or str(video.with_name("galo_final.mp4"))
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats", *entradas, *filtro_complexo(script),
           "-map", atual, *audio, "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", saida]
    subprocess.run(cmd, check=True)
    print("\nTempos usados (cole em \"tempos\" para ajustar):")
    print(json.dumps([[round(a, 2), round(b, 2)] for a, b in tempos]))
    print(f"Pronto: {saida}")


if __name__ == "__main__":
    main()
