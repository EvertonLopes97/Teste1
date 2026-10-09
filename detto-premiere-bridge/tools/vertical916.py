# -*- coding: utf-8 -*-
"""Transforma um vídeo JÁ EDITADO em 16:9 num vertical 9:16 dinâmico (TikTok / Reels / Shorts).

    python tools/vertical916.py edicao.mp4 [vertical.mp4] [--partes 60]

Quadro a quadro ele vê onde você está:
  - você na tela (câmera)       → recorte 9:16 centrado no seu rosto (parado, sem tremer)
  - gráfico/foto + você ao lado → tela dividida: gráfico em cima, você embaixo
--partes 60: também corta em partes de até 60 s (para postar em sequência).

Quando o vídeo foi feito por este sistema, o melhor é renderizar direto em vertical a partir do
plano (editar.py já faz isso: vertical_completo.mp4); este script é para vídeos já prontos.
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


def rostos(video, amostras=10):
    if not MODELO.exists():
        urllib.request.urlretrieve(URL, MODELO)
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    esc = 640 / W
    det = cv2.FaceDetectorYN.create(str(MODELO), "", (640, int(H * esc)), 0.6, 0.3, 20)
    passo, i, out = max(1, round(fps / amostras)), 0, []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % passo == 0:
            _, fs = det.detect(cv2.resize(f, (640, int(H * esc))))
            if fs is not None and len(fs):
                x, y, w, h = max(fs, key=lambda r: r[2] * r[3])[:4] / esc
                out.append((i / fps, (x + w / 2) / W, (y + h / 2) / H, w / W))
            else:
                out.append((i / fps, None, None, None))
        i += 1
    cap.release()
    return out, fps, W, H


def planejar(amostras, W, H):
    """Modo por amostra: 'cam' (recorte no rosto) ou 'div' (gráfico em cima, você embaixo)."""
    modos = []
    for t, cx, cy, fw in amostras:
        if cx is None:
            modos.append([t, "div" if modos and modos[-1][1] == "div" else "cam", np.nan, np.nan, np.nan])
        elif cx > 0.62:  # rosto deslocado para a direita = tem gráfico/foto à esquerda
            modos.append([t, "div", cx, cy, fw])
        else:
            modos.append([t, "cam", cx, cy, fw])
    # tira trocas rápidas (< 0,5 s): o gráfico entra e sai de uma vez
    k = 0
    while k < len(modos):
        j = k
        while j + 1 < len(modos) and modos[j + 1][1] == modos[k][1]:
            j += 1
        if modos[j][0] - modos[k][0] < 0.5 and 0 < k and j + 1 < len(modos) and modos[k - 1][1] == modos[j + 1][1]:
            for m in modos[k:j + 1]:
                m[1] = modos[k - 1][1]
        k = j + 1
    # posição do recorte parada dentro de cada trecho (mediana do rosto)
    k = 0
    while k < len(modos):
        j = k
        while j + 1 < len(modos) and modos[j + 1][1] == modos[k][1]:
            j += 1
        for idx, padrao in ((2, 0.5 if modos[k][1] == "cam" else 0.78), (3, 0.42), (4, 0.12)):
            vals = [m[idx] for m in modos[k:j + 1] if not np.isnan(m[idx])]
            med = float(np.median(vals)) if vals else padrao
            for m in modos[k:j + 1]:
                m[idx] = med
        k = j + 1
    return modos


def quadro(f, modo, cx, cy, fw):
    H, W = f.shape[:2]
    if modo == "cam":
        # faixa central em volta do rosto (larga o bastante para a legenda caber) + fundo desfocado
        lw = int(W * 0.5)
        x0 = int(np.clip(cx * W - lw / 2, 0, W - lw))
        meio = cv2.resize(f[:, x0:x0 + lw], (OW, int(OW * H / lw)), interpolation=cv2.INTER_AREA)
        s = OH / H
        g = cv2.resize(f, (int(W * s), OH), interpolation=cv2.INTER_AREA)
        gx = int(np.clip(cx * g.shape[1] - OW / 2, 0, g.shape[1] - OW))
        fundo = cv2.GaussianBlur(cv2.resize(g[:, gx:gx + OW], (OW // 4, OH // 4)), (0, 0), 10)
        fundo = (cv2.resize(fundo, (OW, OH)) * 0.4).astype(np.uint8)
        y = (OH - meio.shape[0]) // 2
        fundo[y:y + meio.shape[0]] = meio
        return fundo
    # dividido: em cima o lado esquerdo (gráfico/foto), embaixo você
    esq = f[:, : int(W * 0.56)]
    alto = int(OW * esq.shape[0] / esq.shape[1])
    topo = cv2.resize(esq, (OW, alto), interpolation=cv2.INTER_AREA)
    resto = OH - alto
    lado = max(fw * W * 2.6, W * 0.26)  # janela em volta do rosto, proporção do espaço de baixo
    lw, lh = lado, lado * resto / OW
    x0 = int(np.clip(cx * W - lw / 2, 0, W - lw))
    y0 = int(np.clip(cy * H - lh * 0.42, 0, H - lh))
    baixo = cv2.resize(f[y0:y0 + int(lh), x0:x0 + int(lw)], (OW, resto), interpolation=cv2.INTER_AREA)
    out = np.vstack([topo, baixo])
    cv2.line(out, (0, alto), (OW, alto), (255, 255, 255), 6)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("saida", nargs="?")
    p.add_argument("--partes", type=float, default=0)
    a = p.parse_args()
    video = Path(a.video)
    saida = Path(a.saida or video.with_name(video.stem + "_9x16.mp4"))
    amostras, fps, W, H = rostos(video)
    modos = planejar(amostras, W, H)
    tempos = np.array([m[0] for m in modos])
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
        k = int(np.clip(np.searchsorted(tempos, i / fps) - 1, 0, len(modos) - 1))
        _, modo, cx, cy, fw = modos[k]
        ff.stdin.write(quadro(f, modo, cx, cy, fw).tobytes())
        i += 1
    cap.release()
    ff.stdin.close()
    ff.wait()
    print(f"Vertical: {saida}")
    if a.partes:
        dur = i / fps
        n = int(np.ceil(dur / a.partes))
        for k in range(n):
            parte = saida.with_name(f"{saida.stem}_parte{k + 1}.mp4")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{k * a.partes:.2f}", "-t", f"{a.partes:.2f}",
                            "-i", str(saida), "-c", "copy", str(parte)], check=True)
            print(f"  {parte}")


if __name__ == "__main__":
    main()
