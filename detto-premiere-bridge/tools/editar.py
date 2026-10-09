# -*- coding: utf-8 -*-
"""Edição completa com UM comando, sem gastar o Claude:

    python tools/editar.py "C:/Users/guebe/Videos/edição ia/gravação.mp4" [--teste] [--sem-verticais]

Passos (cada um é pulado se o arquivo já existir na pasta do job, então dá para refazer só o fim):
  1. transcrição palavra por palavra (faster-whisper, na sua placa de vídeo)      → words.json
  2. rastreio do rosto (YuNet)                                                      → face.json
  3. roteiro de edição pelo Gemini (GEMINI_API_KEY)                                 → roteiro.txt
     (se preferir, escreva/edite o roteiro.txt você mesmo ou peça ao Claude e rode de novo)
  4. plano de edição (corte conservador: só pausas > 0,8 s)                         → EDIT_PLAN.json
  5. vídeo horizontal (YouTube) + o mesmo vídeo inteiro em 9:16 (TikTok/Reels) + um vertical por
     corte sugerido, com voz tratada e seus efeitos sonoros
--teste: só o primeiro minuto.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PONTE = Path(__file__).resolve().parents[1]
T = PONTE / "tools"


def roda(cmd):
    print("\n>>", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=PONTE)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("--teste", action="store_true")
    p.add_argument("--sem-verticais", action="store_true")
    p.add_argument("--titulo", default="")
    a = p.parse_args()
    video = Path(a.video).resolve()
    job = video.with_name(video.stem + "_job")
    job.mkdir(exist_ok=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(video)], capture_output=True, text=True, check=True).stdout.strip())
    py = sys.executable
    if not (job / "words.json").exists():
        roda([py, T / "transcrever.py", video, job / "words.json"])
    if not (job / "face.json").exists():
        modelo = PONTE / "yunet.onnx"
        if not modelo.exists():
            roda(["curl", "-sSfL", "-o", modelo, "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
                  "face_detection_yunet/face_detection_yunet_2023mar.onnx"])
        roda([py, T / "motion" / "facetrack.py", video, job / "face.json", "--model", modelo])
    if not (job / "roteiro.txt").exists():
        roda([py, T / "roteiro_ia.py", job / "words.json", job / "roteiro.txt", "--titulo", a.titulo])
    roda(["node", T / "roteiro-to-plan.js", job / "roteiro.txt", "--media", video, "--duration", f"{dur:.2f}",
          "--words", job / "words.json", "--gap", "0.8", "--job", video.stem, "--out", job / "EDIT_PLAN.json"])
    base = ["node", T / "render-dynamic.js", job / "EDIT_PLAN.json", "--video", video, "--face", job / "face.json",
            "--fonts", PONTE / "fonts", "--work", job / "tmp"]
    trecho = ["--from", "0", "--to", "60"] if a.teste else []
    roda(base + trecho + ["--out", job / "horizontal.mp4"])
    # o vídeo inteiro também em 9:16 (TikTok / Reels), com gráficos e legendas refeitos para o vertical
    roda(base + trecho + ["--format", "vertical", "--out", job / "vertical_completo.mp4"])
    if not a.sem_verticais and not a.teste:
        txt = (job / "roteiro.txt").read_text(encoding="utf-8")
        sec = txt.split("CORTES VERTICAIS", 1)[1] if "CORTES VERTICAIS" in txt else ""
        sec = sec.split("ERRATA", 1)[0]
        n = len(re.findall(r"^\s*\d+\.", sec, flags=re.M))
        for k in range(1, n + 1):
            roda(base + ["--cut", k, "--out", job / f"vertical_{k}.mp4"])
    print(f"\nPronto: {job}")


if __name__ == "__main__":
    main()
