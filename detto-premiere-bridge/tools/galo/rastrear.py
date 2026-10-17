# -*- coding: utf-8 -*-
"""Rastreia o seu corpo na gravação (MediaPipe Pose): mãos, rosto, ombros e quadril a cada quadro.

    python tools/galo/rastrear.py gravacao.mov movimento.json [--fps 30]

Precisa do modelo pose_landmarker_full.task na pasta tools/galo (baixado sozinho na 1ª vez).
Saída: {"fps", "w", "h", "q": [[t, {ponto: [x, y, vis]}], ...]} com x, y em pixels do vídeo já de pé.
"""
import argparse
import json
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp

AQUI = Path(__file__).resolve().parent
MODELO_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
              "pose_landmarker_full/float16/latest/pose_landmarker_full.task")
PONTOS = {"nariz": 0, "olho_e": 2, "olho_d": 5, "orelha_e": 7, "orelha_d": 8, "ombro_e": 11, "ombro_d": 12,
          "cotovelo_e": 13, "cotovelo_d": 14, "pulso_e": 15, "pulso_d": 16, "dedo_e": 19, "dedo_d": 20,
          "quadril_e": 23, "quadril_d": 24}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("saida")
    p.add_argument("--fps", type=float, default=30)
    p.add_argument("--modelo", default=str(AQUI / "pose_landmarker_full.task"))
    a = p.parse_args()
    if not Path(a.modelo).exists():
        print("baixando o modelo de pose...")
        urllib.request.urlretrieve(MODELO_URL, a.modelo)

    opts = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=a.modelo),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=1,
        min_pose_detection_confidence=0.5, min_tracking_confidence=0.5)
    cap = cv2.VideoCapture(a.video)  # o OpenCV já aplica a rotação do celular
    fps_in = cap.get(cv2.CAP_PROP_FPS) or 30
    passo = max(1, round(fps_in / a.fps))
    saida, i, W, H = [], 0, 0, 0
    with mp.tasks.vision.PoseLandmarker.create_from_options(opts) as det:
        while True:
            ok, f = cap.read()
            if not ok:
                break
            if i % passo == 0:
                H, W = f.shape[:2]
                t = i / fps_in
                r = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,
                                                  data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB)), int(t * 1000))
                pts = {}
                if r.pose_landmarks:
                    lm = r.pose_landmarks[0]
                    pts = {n: [round(lm[k].x * W, 1), round(lm[k].y * H, 1), round(lm[k].visibility, 2)]
                           for n, k in PONTOS.items()}
                saida.append([round(t, 3), pts])
                if len(saida) % 60 == 0:
                    print(f"\r{t:6.1f} s", end="", flush=True)
            i += 1
    cap.release()
    Path(a.saida).write_text(json.dumps({"fps": fps_in / passo, "w": W, "h": H, "q": saida}), encoding="utf-8")
    print(f"\n{len(saida)} quadros -> {a.saida}")


if __name__ == "__main__":
    main()
