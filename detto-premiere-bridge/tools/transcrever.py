# -*- coding: utf-8 -*-
"""Transcreve a gravação palavra por palavra -> words.json  [{"w": "palavra", "s": 1.23, "e": 1.48}]

    python tools/transcrever.py gravacao.mov words.json [--modelo small] [--cpu]

Usa a placa NVIDIA se as bibliotecas CUDA estiverem instaladas; se não, roda no processador sozinho
(mais lento, mesmo resultado). Para usar a placa no Windows (uma vez):
    pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
"""
import argparse
import json
import os
import site
import sys
from pathlib import Path


def dlls_nvidia():
    """No Windows, as DLLs do CUDA instaladas pelo pip ficam em site-packages/nvidia/*/bin."""
    for base in site.getsitepackages() + [site.getusersitepackages()]:
        for pasta in Path(base).glob("nvidia/*/bin"):
            os.environ["PATH"] = str(pasta) + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(pasta))
                except OSError:
                    pass


def transcrever(video, modelo, device):
    from faster_whisper import WhisperModel
    m = WhisperModel(modelo, device=device, compute_type="int8_float16" if device == "cuda" else "int8")
    segs, _ = m.transcribe(video, language="pt", word_timestamps=True, vad_filter=True)
    palavras = []
    for seg in segs:  # a transcrição acontece aqui (é preguiçosa)
        for w in seg.words or []:
            palavras.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)})
        print(f"\r{seg.end:7.1f} s transcritos ({'placa de vídeo' if device == 'cuda' else 'processador'})",
              end="", flush=True)
    return palavras


def main():
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("saida")
    p.add_argument("--modelo", default="small")
    p.add_argument("--cpu", action="store_true")
    a = p.parse_args()
    dlls_nvidia()
    palavras = None
    if not a.cpu:
        try:
            palavras = transcrever(a.video, a.modelo, "cuda")
        except Exception as e:  # sem CUDA (cublas/cudnn) ou sem placa: segue no processador
            print(f"\nPlaca de vídeo indisponível ({str(e)[:80]}). Usando o processador...", flush=True)
    if palavras is None:
        palavras = transcrever(a.video, a.modelo, "cpu")
    with open(a.saida, "w", encoding="utf-8") as f:
        json.dump(palavras, f, ensure_ascii=False)
    print(f"\n{len(palavras)} palavras -> {a.saida}")


if __name__ == "__main__":
    sys.exit(main())
