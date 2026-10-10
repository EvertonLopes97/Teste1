# -*- coding: utf-8 -*-
"""DETTO REAGE — edição automática de vídeos de react.

    python tools/react/react.py react.json

Você entrega 3 arquivos:
  "camera":  sua gravação (webcam/câmera, com o seu microfone)
  "tela":    a gravação da tela durante o react (mostra quando você pausou)
  "original": o vídeo que você reagiu, bruto (qualidade cheia, áudio limpo)

O sistema:
  1. sincroniza câmera ↔ tela pelo áudio (bata uma palma no começo para ficar perfeito);
  2. acha as PAUSAS na gravação da tela (imagem parada) e liga cada trecho tocado ao vídeo original;
  3. monta: vídeo tocando  → layout DETTO REAGE (vídeo grande na moldura, você no quadro, painéis);
            você pausou     → transição de zoom na sua câmera e só você falando na tela;
            voltou a tocar  → zoom de volta para o layout;
  4. áudio: o original limpo por baixo (abaixa sozinho quando você fala) + a sua voz tratada.
O que ele entendeu fica em <camera>.react.json (trechos tocados e pausas): corrija ali e rode de novo.

react.json:
{
  "camera": "C:/.../eu.mp4", "tela": "C:/.../tela.mp4", "original": "C:/.../video.mp4",
  "titulo": "REAGINDO: ...",            // faixa embaixo do vídeo
  "mascote": "C:/.../caricatura.png",   // opcional (PNG sem fundo), canto inferior esquerdo
  "patrocinio": "C:/.../logo.png",      // opcional, painel do canto superior direito
  "formato": "horizontal",              // ou "vertical" (TikTok/Reels)
  "offset_camera": null,                // segundos (câmera = tela + offset) se o áudio não bater
  "saida": "C:/.../react.mp4"
}
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = Path(__file__).resolve().parent
PONTE = AQUI.parents[1]
FONTES = PONTE / "fonts"
SR = 16000
AMARELO = (232, 255, 58)       # neon da marca (RGB)
BRANCO = (255, 255, 255)
PRETO = (8, 8, 10)


# ================================================================== utilidades

def sonda(v):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(v)],
                       capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    n, d = j["streams"][0]["r_frame_rate"].split("/")
    return j["streams"][0]["width"], j["streams"][0]["height"], float(n) / float(d), float(j["format"]["duration"])


def audio(v, sr=SR, filtro=None):
    cmd = ["ffmpeg", "-v", "error", "-i", str(v), "-vn", "-ac", "1", "-ar", str(sr)]
    if filtro:
        cmd += ["-af", filtro]
    r = subprocess.run(cmd + ["-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def envelope(a, sr=SR, hop=0.01):
    n = int(sr * hop)
    m = len(a) // n
    e = np.sqrt((a[: m * n].reshape(m, n) ** 2).mean(axis=1) + 1e-9)
    e = np.log(e)
    d = np.diff(e, prepend=e[0])
    return np.maximum(d, 0)


def atraso(a, b, max_s=600, hop=0.01):
    """Quanto b está atrasado em relação a a (segundos), por correlação dos envelopes."""
    ea, eb = envelope(a), envelope(b)
    n = 1 << int(np.ceil(np.log2(len(ea) + len(eb))))
    c = np.fft.irfft(np.fft.rfft(eb, n) * np.conj(np.fft.rfft(ea, n)), n)
    lags = np.concatenate([np.arange(0, n // 2), np.arange(-n // 2, 0)])
    ok = np.abs(lags * hop) <= max_s
    k = int(np.argmax(np.where(ok, c, -np.inf)))
    conf = c[k] / (np.std(c[ok]) + 1e-9)
    return float(lags[k] * hop), float(conf)


def fonte(nome, tam):
    for f in (FONTES / nome, Path("C:/Windows/Fonts") / nome):
        if f.exists():
            return ImageFont.truetype(str(f), tam)
    return ImageFont.load_default()


# ================================================================== leitura do react (sincronia + pausas)

def miniaturas(video, fps=10, tam=(96, 54), crop=None):
    cap = cv2.VideoCapture(str(video))
    vf = cap.get(cv2.CAP_PROP_FPS) or 30
    passo = max(1, round(vf / fps))
    out, i = [], 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % passo == 0:
            if crop:
                x0, y0, x1, y1 = crop
                f = f[y0:y1, x0:x1]
            g = cv2.cvtColor(cv2.resize(f, tam, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
            out.append(g)
        i += 1
    cap.release()
    return np.array(out), vf / passo


def area_do_video(tela):
    """Onde o vídeo está na gravação da tela (a região que mais muda)."""
    W, H, _, _ = sonda(tela)
    mini, _ = miniaturas(tela, fps=2, tam=(192, 108))
    var = mini.std(axis=0)
    m = var > max(4.0, np.percentile(var, 60))
    cols = np.where(m.mean(axis=0) > 0.3)[0]
    rows = np.where(m.mean(axis=1) > 0.3)[0]
    if len(cols) < 20 or len(rows) < 20:
        return (0, 0, W, H)
    return (int(cols[0] / 192 * W), int(rows[0] / 108 * H), int((cols[-1] + 1) / 192 * W), int((rows[-1] + 1) / 108 * H))


def ler_react(cfg):
    tela, orig, cam = Path(cfg["tela"]), Path(cfg["original"]), Path(cfg["camera"])
    crop = area_do_video(tela)
    mt, fps_m = miniaturas(tela, crop=crop)
    mo, fps_o = miniaturas(orig)
    # 1) pausas: a imagem do vídeo na tela fica parada
    mov = np.r_[0, np.abs(np.diff(mt, axis=0)).mean(axis=(1, 2))]
    parado = mov < 0.6
    parado[0] = False  # 1º quadro não tem diferença
    for k in range(1, len(parado) - 1):  # tapa buraco de 1 quadro (compressão)
        if not parado[k] and parado[k - 1] and parado[k + 1]:
            parado[k] = True
    trechos, k = [], 0
    while k < len(parado):
        j = k
        while j + 1 < len(parado) and parado[j + 1] == parado[k]:
            j += 1
        t0, t1 = k / fps_m, (j + 1) / fps_m
        trechos.append(["pausa" if parado[k] else "toca", round(t0, 2), round(t1, 2)])
        k = j + 1
    # pausas curtas (< 0,7 s) são o próprio vídeo parado, não pausa sua
    limp = []
    for tr in trechos:
        if tr[0] == "pausa" and tr[2] - tr[1] < 0.7:
            tr[0] = "toca"
        if limp and limp[-1][0] == tr[0]:
            limp[-1][2] = tr[2]
        else:
            limp.append(tr)
    # 2) cada trecho tocado → onde está no original (casando as imagens)
    mo_n = (mo - mo.mean(axis=(1, 2), keepdims=True)) / (mo.std(axis=(1, 2), keepdims=True) + 1e-6)
    ultimo = 0.0
    for tr in limp:
        if tr[0] != "toca":
            continue
        a, b = int(tr[1] * fps_m), max(int(tr[1] * fps_m) + 1, int(tr[2] * fps_m))
        idx = np.linspace(a, b - 1, min(8, b - a)).astype(int)
        votos = []
        for i in idx:
            q = mt[i]
            q = (q - q.mean()) / (q.std() + 1e-6)
            sc = (mo_n * q).mean(axis=(1, 2))
            j = int(np.argmax(sc))
            if sc[j] > 0.5:
                votos.append(j / fps_o - i / fps_m)
        off = float(np.median(votos)) if votos else ultimo
        tr.append(round(off, 2))  # original = tela + off
        ultimo = off + (tr[2] - tr[1]) * 0 + 0
    # 2b) pausa de verdade = o vídeo volta de onde parou (o deslocamento muda o tamanho da pausa);
    #     se o deslocamento não mudou, era só uma cena parada do próprio vídeo
    final = []
    for tr in limp:
        if final and tr[0] == "toca" and len(final) >= 2 and final[-1][0] == "pausa" and final[-2][0] == "toca" \
                and abs(tr[3] - final[-2][3]) < 0.4:
            final.pop()
            final[-1][2] = tr[2]
            continue
        if final and tr[0] == "toca" and final[-1][0] == "toca":
            final[-1][2] = tr[2]
            continue
        final.append(tr)
    limp = final
    # 3) câmera ↔ tela pelo áudio
    if cfg.get("offset_camera") is not None:
        off_cam, conf = float(cfg["offset_camera"]), 99.0
    else:
        off_cam, conf = atraso(audio(tela), audio(cam))
    return {"area_tela": crop, "offset_camera": round(off_cam, 3), "confianca_sincronia": round(conf, 1),
            "trechos": limp}


# ================================================================== visual (storyboard DETTO REAGE)

def layout(formato):
    if formato == "vertical":
        return {"W": 1080, "H": 1920,
                "video": (40, 300, 1040, 862),       # 16:9 grande em cima
                "cam": (40, 990, 1040, 1553),        # você embaixo (16:9, largura toda)
                "faixa": (40, 880, 1040, 950),
                "painel": (40, 1620, 1040, 1840),
                "mascote": None}
    return {"W": 1920, "H": 1080,
            "video": (60, 60, 1300, 757),            # 1240x697 (16:9)
            "cam": (1250, 640, 1860, 983),           # 610x343 (16:9)
            "faixa": (60, 790, 1200, 860),
            "painel": (1360, 60, 1860, 560),
            "mascote": (30, 690, 330, 1080)}


def fundo(cfg, L):
    W, H = L["W"], L["H"]
    img = Image.new("RGB", (W, H), PRETO)
    d = ImageDraw.Draw(img, "RGBA")
    # listras diagonais do Galo, bem sutis
    for x in range(-H, W + H, 120):
        d.polygon([(x, 0), (x + 60, 0), (x + 60 + H, H), (x + H, H)], fill=(255, 255, 255, 9))
    # brilho neon atrás do vídeo
    glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow)
    x0, y0, x1, y1 = L["video"]
    gd.rectangle((x0 - 30, y0 - 30, x1 + 30, y1 + 30), fill=110)
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    img = Image.composite(Image.new("RGB", (W, H), (70, 80, 10)), img, glow)
    d = ImageDraw.Draw(img, "RGBA")
    # moldura do vídeo: branco → amarelo
    for k in range(12):
        c = tuple(int(BRANCO[i] + (AMARELO[i] - BRANCO[i]) * k / 11) for i in range(3))
        d.rectangle((x0 - 12 + k, y0 - 12 + k, x1 + 12 - k, y1 + 12 - k), outline=c, width=1)
    # faixa do título (estilo telejornal)
    fx0, fy0, fx1, fy1 = L["faixa"]
    d.rectangle((fx0, fy0, fx1, fy1), fill=AMARELO)
    d.rectangle((fx0, fy0, fx0 + 230, fy1), fill=PRETO)
    f1, f2 = fonte("Anton-Regular.ttf", int((fy1 - fy0) * 0.62)), fonte("Anton-Regular.ttf", int((fy1 - fy0) * 0.55))
    d.text((fx0 + 115, (fy0 + fy1) / 2), "DETTO REAGE", font=f1, fill=AMARELO, anchor="mm")
    d.text((fx0 + 250, (fy0 + fy1) / 2), cfg.get("titulo", "").upper()[:60], font=f2, fill=PRETO, anchor="lm")
    if L["W"] < L["H"]:  # vertical: cabeçalho no alto
        d.text((W / 2, 140), "DETTO REAGE", font=fonte("Anton-Regular.ttf", 120), fill=AMARELO, anchor="mm")
        d.text((W / 2, 235), "@detto.galo", font=fonte("Inter-ExtraBold.otf", 40), fill=BRANCO, anchor="mm")
    # painel: @ e chamada (ou patrocinador)
    px0, py0, px1, py1 = L["painel"]
    d.rounded_rectangle((px0, py0, px1, py1), 26, fill=(18, 18, 22, 235), outline=(255, 255, 255, 40), width=2)
    cx = (px0 + px1) / 2
    if cfg.get("patrocinio") and Path(cfg["patrocinio"]).exists():
        p = Image.open(cfg["patrocinio"]).convert("RGBA")
        p.thumbnail((px1 - px0 - 80, (py1 - py0) * 0.5))
        img.paste(p, (int(cx - p.width / 2), py0 + 40), p)
        topo_txt = py0 + 60 + p.height
    else:
        topo_txt = py0 + 40
    fa, fb, fc = fonte("Anton-Regular.ttf", 74), fonte("Inter-ExtraBold.otf", 34), fonte("Inter-Bold.otf", 28)
    if L["W"] < L["H"]:
        d.text((cx, (py0 + py1) / 2 - 30), "@detto.galo", font=fa, fill=BRANCO, anchor="mm")
        d.text((cx, (py0 + py1) / 2 + 50), "CURTE • COMENTA • SEGUE", font=fb, fill=AMARELO, anchor="mm")
    else:
        d.text((cx, topo_txt + 50), "@detto.galo", font=fa, fill=BRANCO, anchor="mm")
        d.text((cx, topo_txt + 130), "SEGUE AÍ", font=fb, fill=AMARELO, anchor="mm")
        d.line((px0 + 60, topo_txt + 175, px1 - 60, topo_txt + 175), fill=(255, 255, 255, 50), width=2)
        for n, linha in enumerate(["CURTE O VÍDEO", "COMENTA SUA OPINIÃO", "ATIVA O SININHO"]):
            d.text((cx, topo_txt + 220 + n * 46), linha, font=fc, fill=(220, 220, 220), anchor="mm")
    # mascote (sua caricatura) ou selo
    if L["mascote"]:
        mx0, my0, mx1, my1 = L["mascote"]
        if cfg.get("mascote") and Path(cfg["mascote"]).exists():
            m = Image.open(cfg["mascote"]).convert("RGBA")
            m.thumbnail((mx1 - mx0, my1 - my0))
            img.paste(m, (mx0, my1 - m.height), m)
        else:
            sx, sy = mx0 + 40, my1 - 150
            d.rounded_rectangle((sx, sy, sx + 210, sy + 110), 18, fill=AMARELO)
            d.text((sx + 105, sy + 55), "REACT", font=fonte("Anton-Regular.ttf", 64), fill=PRETO, anchor="mm")
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def encaixa(f, w, h, foco=None):
    """Recorta f para a proporção w:h (no foco = (cx, cy) do rosto, se houver) e redimensiona."""
    fh, fw = f.shape[:2]
    alvo = w / h
    if fw / fh > alvo:
        nw = int(fh * alvo)
        cx = foco[0] * fw if foco else fw / 2
        x0 = int(np.clip(cx - nw / 2, 0, fw - nw))
        f = f[:, x0:x0 + nw]
    else:
        nh = int(fw / alvo)
        cy = foco[1] * fh if foco else fh / 2
        y0 = int(np.clip(cy - nh * 0.45, 0, fh - nh))
        f = f[y0:y0 + nh]
    return cv2.resize(f, (w, h), interpolation=cv2.INTER_AREA)


def moldura(dst, rect, cor=AMARELO, esp=8):
    x0, y0, x1, y1 = [int(v) for v in rect]
    c = (cor[2], cor[1], cor[0])
    cv2.rectangle(dst, (x0 - esp, y0 - esp), (x1 + esp, y1 + esp), c, esp * 2 - 2)


def ease(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def compor(base, L, frame_video, frame_cam, k_pausa, foco_cam):
    """k_pausa: 0 = layout com o vídeo; 1 = só você na tela; entre 0 e 1 = transição de zoom."""
    W, H = L["W"], L["H"]
    out = base.copy()
    if k_pausa < 1 and frame_video is not None:
        x0, y0, x1, y1 = L["video"]
        out[y0:y1, x0:x1] = encaixa(frame_video, x1 - x0, y1 - y0)
    # câmera: do quadro para a tela cheia
    cx0, cy0, cx1, cy1 = L["cam"]
    u = ease(k_pausa)
    r = (cx0 * (1 - u), cy0 * (1 - u), cx1 + (W - cx1) * u, cy1 + (H - cy1) * u)
    rw, rh = int(r[2] - r[0]), int(r[3] - r[1])
    if frame_cam is not None and rw > 10 and rh > 10:
        zoom = 1 + 0.08 * math.sin(math.pi * u)  # leve empurrão de zoom na transição
        cam = encaixa(frame_cam, int(rw * zoom), int(rh * zoom), foco_cam)
        oy, ox = (cam.shape[0] - rh) // 2, (cam.shape[1] - rw) // 2
        cam = cam[oy:oy + rh, ox:ox + rw]
        if 0 < u < 1:  # flash de luz no meio do zoom
            cam = cv2.addWeighted(cam, 1, np.full_like(cam, 255), 0.25 * math.sin(math.pi * u), 0)
        out[int(r[1]):int(r[1]) + rh, int(r[0]):int(r[0]) + rw] = cam
        if u < 1:
            moldura(out, (r[0], r[1], r[0] + rw, r[1] + rh), esp=max(1, int(8 * (1 - u))))
    if 0.9 <= k_pausa:  # selo discreto enquanto você fala
        cv2.rectangle(out, (40, 40), (300, 110), (58, 255, 232), -1)
        cv2.putText(out, "DETTO REAGE", (58, 90), cv2.FONT_HERSHEY_DUPLEX, 1.3, (10, 8, 8), 3, cv2.LINE_AA)
    return out


# ================================================================== principal

def main():
    cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    cam, tela, orig = Path(cfg["camera"]), Path(cfg["tela"]), Path(cfg["original"])
    arq = cam.with_suffix(cam.suffix + ".react.json")
    if arq.exists() and not cfg.get("refazer"):
        info = json.loads(arq.read_text(encoding="utf-8"))
        print(f"Usando o que já foi lido: {arq}")
    else:
        info = ler_react(cfg)
        arq.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    trechos, off_cam = info["trechos"], info["offset_camera"]
    print(f"Câmera = tela {off_cam:+.2f} s (confiança {info['confianca_sincronia']})")
    for tr in trechos:
        print(f"  {tr[0]:<5} {tr[1]:7.2f} → {tr[2]:7.2f}" + (f"   original {tr[1] + tr[3]:.2f}s" if tr[0] == "toca" else ""))

    L = layout(cfg.get("formato", "horizontal"))
    base = fundo(cfg, L)
    _, _, fps_c, dur_c = sonda(cam)
    dur = trechos[-1][2]
    FPS = 30
    # rosto médio na câmera (para o enquadramento)
    foco = rosto_medio(cam)

    def estado(t):
        """(k_pausa, tempo no original ou None)"""
        for n, tr in enumerate(trechos):
            if tr[1] <= t < tr[2]:
                if tr[0] == "pausa":
                    dentro = min(t - tr[1], tr[2] - t)
                    k = min(1.0, dentro / 0.35) if tr[2] - tr[1] > 0.8 else 0.0
                    ref = next((x for x in trechos[:n][::-1] if x[0] == "toca"), None)
                    return k, (tr[1] + ref[3]) if ref else None
                return 0.0, t + tr[3]
        return 0.0, None

    trab = cam.with_name(cam.stem + "_react_tmp")
    trab.mkdir(exist_ok=True)
    montar_audio(cfg, trechos, off_cam, dur, trab / "audio.wav")
    saida = cfg.get("saida") or str(cam.with_name(cam.stem + "_react.mp4"))
    vo, vc = cv2.VideoCapture(str(orig)), cv2.VideoCapture(str(cam))
    fps_o = vo.get(cv2.CAP_PROP_FPS) or 30
    leitor_o, leitor_c = Leitor(vo, fps_o), Leitor(vc, fps_c)
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                           "-s", f"{L['W']}x{L['H']}", "-r", str(FPS), "-i", "-", "-i", str(trab / "audio.wav"),
                           "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
                           "-movflags", "+faststart", saida], stdin=subprocess.PIPE)
    n = int(dur * FPS)
    for i in range(n):
        t = i / FPS
        k, to = estado(t)
        fv = leitor_o.em(to) if to is not None else None
        fc = leitor_c.em(t + off_cam)
        ff.stdin.write(compor(base, L, fv, fc, k, foco).tobytes())
        if i % 300 == 0:
            print(f"\r{t:6.1f}/{dur:.1f} s", end="", flush=True)
    ff.stdin.close()
    ff.wait()
    print(f"\nPronto: {saida}")


class Leitor:
    """Lê quadros em ordem crescente de tempo sem ficar pulando (rápido)."""

    def __init__(self, cap, fps):
        self.cap, self.fps, self.i, self.f = cap, fps, -1, None

    def em(self, t):
        if t is None or t < 0:
            return self.f
        alvo = int(t * self.fps)
        if alvo < self.i or alvo > self.i + 90:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, alvo)
            self.i = alvo - 1
        while self.i < alvo:
            ok, f = self.cap.read()
            if not ok:
                break
            self.f, self.i = f, self.i + 1
        return self.f


def rosto_medio(video):
    modelo = PONTE / "yunet.onnx"
    if not modelo.exists():
        return None
    cap = cv2.VideoCapture(str(video))
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    det = cv2.FaceDetectorYN.create(str(modelo), "", (640, int(H * 640 / W)), 0.6, 0.3, 20)
    pts = []
    for k in np.linspace(0, max(0, n - 1), 25).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(k))
        ok, f = cap.read()
        if not ok:
            continue
        _, fs = det.detect(cv2.resize(f, (640, int(H * 640 / W))))
        if fs is not None and len(fs):
            x, y, w, h = max(fs, key=lambda r: r[2] * r[3])[:4] * W / 640
            pts.append(((x + w / 2) / W, (y + h / 2) / H))
    cap.release()
    return tuple(np.median(pts, axis=0)) if pts else None


def montar_audio(cfg, trechos, off_cam, dur, destino):
    """Original limpo nos trechos tocados (abaixa quando você fala) + sua voz tratada."""
    sys.path.insert(0, str(PONTE / "tools"))
    voz_filtro = ("highpass=f=75,afftdn=nf=-25,equalizer=f=250:width_type=o:width=1:g=-2,"
                  "equalizer=f=3500:width_type=o:width=1.5:g=3,deesser=i=0.4,"
                  "acompressor=threshold=-20dB:ratio=3:attack=5:release=120:makeup=2")
    sr = 48000
    voz = audio(cfg["camera"], sr, voz_filtro)
    org = audio(cfg["original"], sr)
    n = int(dur * sr)
    v = np.zeros(n, np.float32)
    a0 = int(off_cam * sr)
    if a0 >= 0:
        seg = voz[a0:a0 + n]
        v[:len(seg)] = seg
    else:
        seg = voz[: n + a0]
        v[-a0:-a0 + len(seg)] = seg
    o = np.zeros(n, np.float32)
    for tr in trechos:
        if tr[0] != "toca":
            continue
        i0, i1 = int(tr[1] * sr), int(tr[2] * sr)
        s0 = int((tr[1] + tr[3]) * sr)
        pedaco = org[max(0, s0):max(0, s0) + (i1 - i0)]
        o[i0:i0 + len(pedaco)] = pedaco
        f = min(len(pedaco), int(0.03 * sr))  # sem estalo nas emendas
        if f:
            o[i0:i0 + f] *= np.linspace(0, 1, f)
            o[i0 + len(pedaco) - f:i0 + len(pedaco)] *= np.linspace(1, 0, f)
    # abaixa o original quando você fala
    env = np.convolve(np.abs(v), np.ones(int(0.15 * sr)) / int(0.15 * sr), mode="same")
    fala = np.clip((env - 0.01) / 0.03, 0, 1)
    ganho = 0.8 - 0.55 * np.convolve(fala, np.ones(int(0.2 * sr)) / int(0.2 * sr), mode="same")
    mix = v + o * ganho
    pico = np.abs(mix).max() or 1
    mix = np.tanh(mix / pico * 1.4) * 0.9
    tmp = destino.with_suffix(".raw.wav")
    import wave
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((mix * 32000).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp), "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
                    "-ar", str(sr), str(destino)], check=True)


if __name__ == "__main__":
    main()
