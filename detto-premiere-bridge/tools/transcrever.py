# -*- coding: utf-8 -*-
"""Transcreve a gravação palavra por palavra -> words.json  [{"w": "palavra", "s": 1.23, "e": 1.48}]

    python tools/transcrever.py gravacao.mov words.json [--modelo small]

Usa a placa NVIDIA se der (cuda); se não, roda no processador (mais lento).
"""
import argparse
import json

from faster_whisper import WhisperModel

p = argparse.ArgumentParser()
p.add_argument("video")
p.add_argument("saida")
p.add_argument("--modelo", default="small")
a = p.parse_args()

try:
    modelo = WhisperModel(a.modelo, device="cuda", compute_type="int8_float16")
except Exception:
    modelo = WhisperModel(a.modelo, device="cpu", compute_type="int8")

segs, _ = modelo.transcribe(a.video, language="pt", word_timestamps=True, vad_filter=True)
palavras = []
for seg in segs:
    for w in seg.words or []:
        palavras.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)})
    print(f"\r{seg.end:7.1f} s transcritos", end="", flush=True)

with open(a.saida, "w", encoding="utf-8") as f:
    json.dump(palavras, f, ensure_ascii=False)
print(f"\n{len(palavras)} palavras -> {a.saida}")
