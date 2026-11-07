#!/usr/bin/env python3
"""
Rastreamento do rosto na gravação (para zooms e janelas sempre centrados no rosto).

    python facetrack.py video.mov face.json --model yunet.onnx [--fps 5]

Saída: {"fps": 5, "points": [{"t": 0.0, "cx": 0.51, "cy": 0.38, "w": 0.16}, ...]}
com coordenadas normalizadas (0–1) na imagem original. Quadros sem rosto são
interpolados e a trajetória é suavizada (mediana + média móvel) para a câmera
virtual não tremer.
"""
import argparse
import json
import subprocess

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--model", required=True)
    ap.add_argument("--fps", type=float, default=5.0)
    a = ap.parse_args()

    W, H = 640, 360
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", a.video, "-vf", f"fps={a.fps},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        stdout=subprocess.PIPE,
    )
    det = cv2.FaceDetectorYN.create(a.model, "", (W, H), 0.7, 0.3, 50)
    raw = []
    i = 0
    while True:
        buf = proc.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        _, faces = det.detect(img)
        if faces is not None and len(faces):
            f = max(faces, key=lambda r: r[2] * r[3])
            x, y, w, h = f[:4]
            raw.append((i / a.fps, (x + w / 2) / W, (y + h / 2) / H, w / W))
        else:
            raw.append((i / a.fps, None, None, None))
        i += 1
    proc.wait()

    t = np.array([r[0] for r in raw])
    def series(k):
        v = np.array([np.nan if r[k] is None else r[k] for r in raw], dtype=float)
        ok = ~np.isnan(v)
        if not ok.any():
            return np.full_like(t, {1: 0.5, 2: 0.4, 3: 0.18}[k])
        v = np.interp(t, t[ok], v[ok])
        # mediana (remove picos) + média móvel (~1 s)
        k1 = 5
        pad = np.pad(v, k1 // 2, mode="edge")
        med = np.array([np.median(pad[j:j + k1]) for j in range(len(v))])
        k2 = int(a.fps) | 1
        ker = np.ones(k2) / k2
        return np.convolve(np.pad(med, k2 // 2, mode="edge"), ker, mode="valid")

    cx, cy, fw = series(1), series(2), series(3)
    found = sum(1 for r in raw if r[1] is not None)
    json.dump(
        {
            "fps": a.fps,
            "detected": found,
            "samples": len(raw),
            "points": [{"t": round(float(t[j]), 3), "cx": round(float(cx[j]), 4), "cy": round(float(cy[j]), 4), "w": round(float(fw[j]), 4)} for j in range(len(raw))],
        },
        open(a.out, "w"),
    )
    print(f"rosto detectado em {found}/{len(raw)} amostras")


if __name__ == "__main__":
    main()
