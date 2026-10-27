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


TAM_MIN = 5_000_000   # o pose_landmarker_full.task tem ~9,4 MB; menor que isso é download pela metade


def erro(msg):
    """morre com um motivo que dá para LER (o painel mostra a última linha do registro)"""
    print(f"\nERRO: {msg}", flush=True)
    raise SystemExit(1)


def garante_modelo(modelo):
    """o .task vem no git pull; se faltar ou estiver pela metade, baixa de novo (para um .tmp e só então renomeia,
    senão um download interrompido deixa um arquivo quebrado que faz o MediaPipe cuspir o grafo inteiro e sair)"""
    try:
        tam = modelo.stat().st_size
    except OSError:
        tam = 0
    if tam >= TAM_MIN:
        return modelo
    print(f"modelo de pose {'faltando' if not tam else f'pela metade ({tam} bytes)'} — baixando...", flush=True)
    tmp = modelo.with_suffix(".task.baixando")
    try:
        urllib.request.urlretrieve(MODELO_URL, tmp)
        if tmp.stat().st_size < TAM_MIN:
            raise OSError(f"o download veio com {tmp.stat().st_size} bytes")
        tmp.replace(modelo)
    except Exception as e:
        tmp.unlink(missing_ok=True)
        erro(f"não consegui baixar o modelo de pose ({str(e)[:200]}).\n"
             f"   Baixe à mão de {MODELO_URL}\n   e salve em {modelo}")
    return modelo


def abre_detector(modelo):
    """cria o PoseLandmarker. Falhou = o MediaPipe despeja o grafo inteiro e some com o motivo: aqui ele aparece,
    e ainda tentamos o modo IMAGE, que é mais compatível com versão antiga do mediapipe."""
    base = mp.tasks.BaseOptions(model_asset_path=str(modelo))
    for modo in (mp.tasks.vision.RunningMode.VIDEO, mp.tasks.vision.RunningMode.IMAGE):
        try:
            opts = mp.tasks.vision.PoseLandmarkerOptions(
                base_options=base, running_mode=modo, num_poses=1,
                min_pose_detection_confidence=0.5, min_tracking_confidence=0.5)
            d = mp.tasks.vision.PoseLandmarker.create_from_options(opts)
            if modo != mp.tasks.vision.RunningMode.VIDEO:
                print("aviso: o modo VIDEO do MediaPipe não abriu; sigo quadro a quadro (modo IMAGE)")
            d._detto_modo = modo
            return d
        except Exception as e:
            msg = str(e).replace("\n", " ")[:300]
            print(f"MediaPipe não abriu no modo {modo}: {msg}", flush=True)
    erro(f"o MediaPipe não conseguiu carregar o modelo de pose (mediapipe {getattr(mp, '__version__', '?')}).\n"
         f"   Modelo: {modelo} ({modelo.stat().st_size if modelo.exists() else 0} bytes)\n"
         "   Tente: pip install --upgrade mediapipe   — e apague o .task para ele baixar de novo.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("saida")
    p.add_argument("--fps", type=float, default=30)
    p.add_argument("--modelo", default=str(AQUI / "pose_landmarker_full.task"))
    a = p.parse_args()
    modelo = garante_modelo(Path(a.modelo))

    det = abre_detector(modelo)
    cap = cv2.VideoCapture(a.video)  # o OpenCV já aplica a rotação do celular
    if not cap.isOpened():
        erro(f"o OpenCV não conseguiu abrir o vídeo: {a.video}\n"
             "   Confira se o arquivo existe e se abre no player. Vídeo do iPhone em HEVC às vezes precisa do\n"
             "   master SDR antes (python tools\\sdr.py \"<video>\").")
    fps_in = cap.get(cv2.CAP_PROP_FPS) or 30
    if not (1 <= fps_in <= 240):   # metadado estragado faria o relógio do MediaPipe andar para trás
        print(f"aviso: fps do vídeo veio estranho ({fps_in}); uso 30")
        fps_in = 30
    passo = max(1, round(fps_in / a.fps))
    saida, i, W, H = [], 0, 0, 0
    ultimo_ms = -1
    with det:
        while True:
            ok, f = cap.read()
            if not ok:
                break
            if i % passo == 0:
                H, W = f.shape[:2]
                t = i / fps_in
                img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
                if getattr(det, "_detto_modo", None) == mp.tasks.vision.RunningMode.IMAGE:
                    r = det.detect(img)
                else:
                    ms = max(int(t * 1000), ultimo_ms + 1)   # o MediaPipe exige relógio SEMPRE crescente
                    ultimo_ms = ms
                    r = det.detect_for_video(img, ms)
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
    if not saida:
        erro(f"não li nenhum quadro de {a.video} (o OpenCV abriu mas não veio imagem).")
    com_pessoa = sum(1 for _, pts in saida if pts)
    if com_pessoa == 0:
        erro(f"li {len(saida)} quadros, mas não achei NINGUÉM na imagem.\n"
             "   A passagem do elenco precisa de você em quadro, de corpo visível. Confira se é a gravação certa.")
    if com_pessoa < len(saida) * 0.2:
        print(f"aviso: só achei você em {com_pessoa} de {len(saida)} quadros — os gestos podem sair errados")
    Path(a.saida).write_text(json.dumps({"fps": fps_in / passo, "w": W, "h": H, "q": saida}), encoding="utf-8")
    print(f"\n{len(saida)} quadros -> {a.saida}")


if __name__ == "__main__":
    main()
