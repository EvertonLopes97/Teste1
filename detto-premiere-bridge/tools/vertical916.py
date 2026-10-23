# -*- coding: utf-8 -*-
"""Transforma um vídeo JÁ EDITADO em 16:9 num vertical 9:16 dinâmico (TikTok / Reels / Shorts).

    python tools/vertical916.py edicao.mp4 [vertical.mp4] [--grafico pip|tela|dividido] [--partes 60]

Quadro a quadro ele vê o que está na tela:
  - só você (câmera)        → faixa centrada no seu rosto (cabe a legenda) com fundo desfocado
  - gráfico / foto na tela  → o gráfico é recortado e mostrado GRANDE no meio:
        --grafico pip       (padrão) com você pequeno no canto
        --grafico tela      só o gráfico, sem a câmera
        --grafico dividido  gráfico em cima, você embaixo
--partes 60: também corta em partes de até 60 s (para postar em sequência).

Quando o vídeo foi feito por este sistema, o melhor é renderizar direto em vertical a partir do
plano (editar.py já entrega vertical_completo.mp4); este script é para vídeos já prontos.
"""
import argparse
import subprocess
import urllib.request
from pathlib import Path

import cv2
import numpy as np

AQUI = Path(__file__).resolve().parent
MODELO = AQUI.parent / "yunet.onnx"
URL = ("https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
       "face_detection_yunet/face_detection_yunet_2023mar.onnx")
OW, OH = 1080, 1920
PW, PH = 380, 470  # câmera pequena


def analisar(video, amostras=8):
    """Rosto (YuNet) e um quadro pequeno por amostra, para achar os gráficos depois."""
    if not MODELO.exists():
        urllib.request.urlretrieve(URL, MODELO)
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    esc = 640 / W
    det = cv2.FaceDetectorYN.create(str(MODELO), "", (640, int(H * esc)), 0.6, 0.3, 20)
    passo, i, am, mini = max(1, round(fps / amostras)), 0, [], []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % passo == 0:
            _, fs = det.detect(cv2.resize(f, (640, int(H * esc))))
            face = None
            if fs is not None and len(fs):
                x, y, w, h = max(fs, key=lambda r: r[2] * r[3])[:4] / esc
                face = ((x + w / 2) / W, (y + h / 2) / H, w / W)
            am.append([i / fps, face])
            mini.append(cv2.resize(f, (192, 108), interpolation=cv2.INTER_AREA).astype(np.int16))
        i += 1
    cap.release()
    return am, np.array(mini), fps, W, H


def caixa_grafico(m, fundo, face):
    """Tem gráfico/foto? Se o seu rosto foi para a direita (o sistema abre espaço para o gráfico)
    ou se a tela mudou quase toda. Devolve a caixa do gráfico (x0, y0, x1, y1 em fração)."""
    dif = np.abs(m - fundo).max(axis=2) > 40
    h, w = dif.shape
    if face and face[0] > 0.6:
        limite = min(0.55, face[0] - 0.17)
    elif dif[:, : int(w * 0.62)].mean() > 0.62 and not face:
        limite = 0.62
    else:
        return None
    zona = dif[:, : int(w * limite)]
    cols = np.where(zona.mean(axis=0) > 0.45)[0]
    rows = np.where(zona.mean(axis=1) > 0.35)[0]
    if len(cols) > w * limite * 0.35 and len(rows) > h * 0.3:  # aperta na parte que mudou (o card)
        return (cols[0] / w, rows[0] / h, (cols[-1] + 1) / w, (rows[-1] + 1) / h)
    return (0.0, 0.0, limite, 1.0)


def planejar(am, mini):
    fundo = np.median(mini, axis=0)  # a maior parte do vídeo é só a câmera
    cena = []
    for (t, face), m in zip(am, mini):
        cx, cy, fw = face if face else (np.nan,) * 3
        caixa = caixa_grafico(m, fundo, face)
        cena.append([t, "graf" if caixa else "cam", cx, cy, fw, caixa])
    # trocas muito rápidas (< 0,4 s) são ruído
    k = 0
    while k < len(cena):
        j = k
        while j + 1 < len(cena) and cena[j + 1][1] == cena[k][1]:
            j += 1
        if cena[j][0] - cena[k][0] < 0.4 and 0 < k and j + 1 < len(cena) and cena[k - 1][1] == cena[j + 1][1]:
            for c in cena[k:j + 1]:
                c[1], c[5] = cena[k - 1][1], cena[k - 1][5]
        k = j + 1
    # dentro de cada trecho tudo parado: mediana do rosto e da caixa
    k, ultimo = 0, (0.5, 0.42, 0.12)
    while k < len(cena):
        j = k
        while j + 1 < len(cena) and cena[j + 1][1] == cena[k][1]:
            j += 1
        bloco = cena[k:j + 1]
        rosto = []
        for idx in (2, 3, 4):
            v = [c[idx] for c in bloco if not np.isnan(c[idx])]
            rosto.append(float(np.median(v)) if v else ultimo[idx - 2])
        ultimo = tuple(rosto)
        cxs = [c[5] for c in bloco if c[5]]
        caixa = tuple(float(np.median([b[q] for b in cxs])) for q in range(4)) if cxs else None
        for c in bloco:
            c[2], c[3], c[4] = rosto
            c[5] = caixa
            if c[1] == "graf" and caixa is None:
                c[1] = "cam"
        k = j + 1
    return cena


def desfocado(img):
    p = cv2.resize(img, (OW // 6, OH // 6), interpolation=cv2.INTER_AREA)
    p = cv2.GaussianBlur(p, (0, 0), 6)
    return (cv2.resize(p, (OW, OH)) * 0.4).astype(np.uint8)


def faixa_cam(f, cx):
    H, W = f.shape[:2]
    lw = int(W * 0.5)
    x0 = int(np.clip(cx * W - lw / 2, 0, W - lw))
    meio = cv2.resize(f[:, x0:x0 + lw], (OW, int(OW * H / lw)), interpolation=cv2.INTER_AREA)
    out = desfocado(f[:, x0:x0 + lw])
    y = (OH - meio.shape[0]) // 2
    out[y:y + meio.shape[0]] = meio
    return out


def camera_pequena(f, cx, cy, fw):
    H, W = f.shape[:2]
    lw = min(max(fw * W * 2.4, W * 0.18), H * PW / PH * 0.95)  # cabe na altura do quadro
    lh = lw * PH / PW
    x0 = int(np.clip(cx * W - lw / 2, 0, W - lw))
    y0 = int(np.clip(cy * H - lh * 0.4, 0, H - lh))
    cam = cv2.resize(f[y0:y0 + int(lh), x0:x0 + int(lw)], (PW, PH), interpolation=cv2.INTER_AREA)
    mask = np.zeros((PH, PW), np.uint8)
    cv2.rectangle(mask, (28, 0), (PW - 28, PH), 255, -1)
    cv2.rectangle(mask, (0, 28), (PW, PH - 28), 255, -1)
    for c in ((28, 28), (PW - 28, 28), (28, PH - 28), (PW - 28, PH - 28)):
        cv2.circle(mask, c, 28, 255, -1)
    return cam, mask


def quadro(f, modo, cx, cy, fw, caixa, estilo):
    H, W = f.shape[:2]
    if modo == "cam":
        return faixa_cam(f, cx)
    pad = 0.012
    x0, y0 = max(0, int((caixa[0] - pad) * W)), max(0, int((caixa[1] - pad) * H))
    x1, y1 = min(W, int((caixa[2] + pad) * W)), min(H, int((caixa[3] + pad) * H))
    g = f[y0:y1, x0:x1]
    out = desfocado(g)
    if estilo == "dividido":
        alto = int(OH * 0.5)
        larg = min(OW - 40, int(alto * g.shape[1] / g.shape[0]))
        alto = int(larg * g.shape[0] / g.shape[1])
        gg = cv2.resize(g, (larg, alto), interpolation=cv2.INTER_AREA)
        out[(OH // 2 - alto) // 2:(OH // 2 - alto) // 2 + alto, (OW - larg) // 2:(OW - larg) // 2 + larg] = gg
        resto = OH // 2
        lw = max(fw * W * 2.6, W * 0.26)
        lh = lw * resto / OW
        a0 = int(np.clip(cx * W - lw / 2, 0, W - lw))
        b0 = int(np.clip(cy * H - lh * 0.42, 0, H - lh))
        out[OH // 2:] = cv2.resize(f[b0:b0 + int(lh), a0:a0 + int(lw)], (OW, resto), interpolation=cv2.INTER_AREA)
        cv2.line(out, (0, OH // 2), (OW, OH // 2), (255, 255, 255), 6)
        return out
    larg = OW - 60
    alto = int(larg * g.shape[0] / g.shape[1])
    if alto > OH * 0.62:
        alto = int(OH * 0.62)
        larg = int(alto * g.shape[1] / g.shape[0])
    gg = cv2.resize(g, (larg, alto), interpolation=cv2.INTER_AREA)
    y = (OH - alto) // 2 - (150 if estilo == "pip" else 0)
    xo = (OW - larg) // 2
    out[y:y + alto, xo:xo + larg] = gg
    if estilo == "pip":
        cam, mask = camera_pequena(f, cx, cy, fw)
        px, py = OW - PW - 40, OH - PH - 150
        borda = cv2.dilate(mask, np.ones((13, 13), np.uint8))
        bm = cv2.copyMakeBorder(borda, 6, 6, 6, 6, cv2.BORDER_CONSTANT, value=0)
        reg = out[py - 6:py + PH + 6, px - 6:px + PW + 6]
        reg[bm > 0] = (255, 255, 255)
        area = out[py:py + PH, px:px + PW]
        area[mask > 0] = cam[mask > 0]
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("saida", nargs="?")
    p.add_argument("--grafico", choices=["pip", "tela", "dividido"], default="pip")
    p.add_argument("--partes", type=float, default=0)
    a = p.parse_args()
    video = Path(a.video)
    saida = Path(a.saida or video.with_name(video.stem + "_9x16.mp4"))
    am, mini, fps, W, H = analisar(video)
    cena = planejar(am, mini)
    tempos = np.array([c[0] for c in cena])
    cap = cv2.VideoCapture(str(video))
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OW}x{OH}",
                           "-r", f"{fps:.5f}", "-i", "-", "-i", str(video), "-map", "0:v", "-map", "1:a?",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(saida)],
                          stdin=subprocess.PIPE)
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        k = int(np.clip(np.searchsorted(tempos, i / fps + 1e-6) - 1, 0, len(cena) - 1))
        _, modo, cx, cy, fw, caixa = cena[k]
        ff.stdin.write(quadro(f, modo, cx, cy, fw, caixa, a.grafico).tobytes())
        i += 1
    cap.release()
    ff.stdin.close()
    ff.wait()
    n = sum(1 for k in range(len(cena)) if cena[k][1] == "graf" and (k == 0 or cena[k - 1][1] != "graf"))
    print(f"Vertical: {saida}  ({n} entradas de gráfico/foto)")
    if a.partes:
        dur = i / fps
        for k in range(int(np.ceil(dur / a.partes))):
            parte = saida.with_name(f"{saida.stem}_parte{k + 1}.mp4")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{k * a.partes:.2f}", "-t", f"{a.partes:.2f}",
                            "-i", str(saida), "-c:v", "libx264", "-crf", "19", "-c:a", "aac", str(parte)], check=True)
            print(f"  {parte}")


if __name__ == "__main__":
    main()
