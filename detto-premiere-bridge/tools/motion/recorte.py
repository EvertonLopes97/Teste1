# -*- coding: utf-8 -*-
"""Recorte da pessoa (máscara) nos quadros da gravação, para o "texto atrás" e o "congela".

    python tools/motion/recorte.py <pasta_cam> <pasta_mascaras> <lista.txt>

lista.txt: um número de quadro por linha (cam/000123.jpg → 123). Gera <pasta_mascaras>/000123.png
(branco com transparência = a pessoa), na metade da resolução. Só os quadros pedidos (rápido).
Linha "123 c" (congela) também gera 000123_borda.png: a máscara engordada, que vira o contorno branco.

Modelo: MediaPipe "selfie multiclass" (cabelo, boné e mãos bem recortados; baixado uma vez para
tools/motion/modelos) e, sem ele, o "selfie segmenter" que vem no projeto. Sem mediapipe instalado,
tenta instalar; se não der, sai sem máscaras (o texto vai acima da cabeça em vez de atrás).
"""
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

AQUI = Path(__file__).resolve().parent
MODELOS = AQUI / "modelos"
MULTI = MODELOS / "selfie_multiclass_256x256.tflite"
MULTI_URL = "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite"
SIMPLES = MODELOS / "selfie_segmenter.tflite"


def importa_mediapipe():
    try:
        import mediapipe  # noqa: F401

        return True
    except ImportError:
        pass
    print("recorte: instalando mediapipe (uma vez só)...", flush=True)
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "mediapipe"], capture_output=True, text=True)
    if r.returncode != 0:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--break-system-packages", "mediapipe"], capture_output=True, text=True)
    try:
        import mediapipe  # noqa: F401

        return True
    except ImportError:
        print("recorte: não consegui instalar o mediapipe (pip install mediapipe). Sem recorte: o texto vai acima da cabeça.")
        return False


def modelo():
    MODELOS.mkdir(parents=True, exist_ok=True)
    if not MULTI.exists() or MULTI.stat().st_size < 1_000_000:
        try:
            print("recorte: baixando o modelo de recorte (16 MB, uma vez só)...", flush=True)
            tmp = MULTI.with_suffix(".baixando")
            urllib.request.urlretrieve(MULTI_URL, tmp)
            tmp.replace(MULTI)
        except Exception as e:  # sem internet: usa o simples
            print(f"recorte: sem o modelo completo ({e}); usando o simples")
    if MULTI.exists() and MULTI.stat().st_size > 1_000_000:
        return MULTI, True
    return SIMPLES, False


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    cam, saida, lista = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    linhas = [l.split() for l in lista.read_text().splitlines() if l.strip()]
    quadros = sorted({int(l[0]) for l in linhas if l[0].isdigit()})
    borda = {int(l[0]) for l in linhas if l[0].isdigit() and len(l) > 1 and l[1] == "c"}
    saida.mkdir(parents=True, exist_ok=True)
    falta = [q for q in quadros if not (saida / f"{q:06d}.png").exists() or (q in borda and not (saida / f"{q:06d}_borda.png").exists())]
    if not falta:
        return
    if not importa_mediapipe():
        return
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    arq, multi = modelo()
    seg = vision.ImageSegmenter.create_from_options(
        vision.ImageSegmenterOptions(base_options=BaseOptions(model_asset_path=str(arq)), output_confidence_masks=True, output_category_mask=False)
    )
    guia = getattr(getattr(cv2, "ximgproc", None), "guidedFilter", None)
    anterior, q_ant = None, None
    print(f"recorte: {len(falta)} quadros ({'completo' if multi else 'simples'})...", flush=True)
    for n, q in enumerate(falta):
        img = cv2.imread(str(cam / f"{q:06d}.jpg"))
        if img is None:
            continue
        H, W = img.shape[:2]
        w2, h2 = W // 2, H // 2
        peq = cv2.resize(img, (w2, h2), interpolation=cv2.INTER_AREA)
        r = seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(cv2.cvtColor(peq, cv2.COLOR_BGR2RGB))))
        cm = r.confidence_masks
        m = (1.0 - cm[0].numpy_view()) if multi else cm[0].numpy_view()
        m = cv2.resize(np.asarray(m, np.float32).squeeze(), (w2, h2), interpolation=cv2.INTER_LINEAR)
        # quadros seguidos: suaviza no tempo (sem tremedeira na borda)
        if anterior is not None and q_ant == q - 1:
            m = 0.65 * m + 0.35 * anterior
        anterior, q_ant = m, q
        if guia is not None:
            m = guia(peq, m, 6, 1e-4)
        else:
            m = cv2.GaussianBlur(m, (5, 5), 0)
        a = np.clip((m - 0.3) / 0.4, 0, 1)
        rgba = np.dstack([np.full((h2, w2, 3), 255, np.uint8), (a * 255).astype(np.uint8)])
        cv2.imwrite(str(saida / f"{q:06d}.png"), rgba, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        if q in borda:
            r_ = max(3, w2 // 160)
            gorda = cv2.dilate((a * 255).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r_ + 1, 2 * r_ + 1)))
            gorda = cv2.GaussianBlur(gorda, (3, 3), 0)
            cv2.imwrite(str(saida / f"{q:06d}_borda.png"), np.dstack([np.full((h2, w2, 3), 255, np.uint8), gorda]), [cv2.IMWRITE_PNG_COMPRESSION, 3])
        if (n + 1) % 100 == 0:
            print(f"recorte: {n + 1}/{len(falta)}", flush=True)
    try:
        seg.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
    os._exit(0)  # o mediapipe às vezes trava ao fechar
