# -*- coding: utf-8 -*-
"""Voz CLONADA (a sua) para a narração do canal: Chatterbox Multilingual (grátis, roda no seu PC).

    python tools/canal/voz.py falas.json pasta_saida --ref voz\\minha_voz.wav

falas.json: [{"id": "f01", "texto": "..."}]  →  pasta_saida/f01.wav (mesmo texto + mesma voz = reaproveita).
A referência é um áudio SEU de 10 a 30 s, falando normal, sem música (quanto mais limpo, mais parecido).
Na placa NVIDIA é bem mais rápido; sem ela roda no processador (mais lento, mesmo resultado).
Primeira vez: instala o chatterbox-tts e baixa o modelo (~3 GB).
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def instala():
    try:
        import chatterbox.mtl_tts  # noqa: F401

        return
    except ImportError:
        pass
    print("voz: instalando o Chatterbox (uma vez só, alguns minutos)...", flush=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "chatterbox-tts", "protobuf>=6.31.1"], check=False)
    import chatterbox.mtl_tts  # noqa: F401


def frases(texto, maximo=220):
    """quebra em frases curtas (o modelo perde o fio em texto longo)"""
    partes = re.split(r"(?<=[.!?…])\s+", re.sub(r"\s+", " ", texto.strip()))
    out = []
    for p in partes:
        while len(p) > maximo:
            corte = p.rfind(",", 0, maximo)
            corte = corte if corte > 60 else p.rfind(" ", 0, maximo)
            out.append(p[:corte + 1].strip())
            p = p[corte + 1:].strip()
        if p:
            out.append(p)
    return out


def voz_de_teste(texto, saida):
    """voz de computador em português (só para testar a montagem enquanto a sua voz não chega)"""
    import shutil
    import tempfile
    tmp = Path(tempfile.gettempdir()) / f"detto_voz_{os.getpid()}.wav"
    try:
        if os.name == "nt":
            ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'pt*' } | Select-Object -First 1; "
                  "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; $s.Rate = 1; "
                  f"$s.SetOutputToWaveFile('{tmp}'); $s.Speak([Console]::In.ReadToEnd()); $s.Dispose()")
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], input=texto, text=True, encoding="utf-8",
                           capture_output=True, timeout=120)
        elif shutil.which("espeak-ng"):
            subprocess.run(["espeak-ng", "-v", "pt-br", "-s", "165", "-w", str(tmp), texto], capture_output=True, timeout=120)
        if tmp.exists() and tmp.stat().st_size > 2000:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-ar", "24000", "-ac", "1", str(saida)], check=True)
            return True
    except Exception:
        pass
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("falas")
    ap.add_argument("saida")
    ap.add_argument("--ref", required=False, default="", help="áudio seu (10–30 s) para clonar")
    ap.add_argument("--exagero", type=float, default=0.6, help="emoção (0,3 calmo … 0,9 empolgado)")
    a = ap.parse_args()
    falas = json.loads(Path(a.falas).read_text(encoding="utf-8"))
    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    ref = Path(a.ref) if a.ref else None
    if ref and not ref.exists():
        print(f"voz: não achei a sua voz em {ref} — usando a voz padrão do modelo")
        ref = None
    chave_ref = hashlib.sha1(ref.read_bytes()).hexdigest()[:8] if ref else "padrao"
    falta = []
    for f in falas:
        h = hashlib.sha1(f"{chave_ref}|{a.exagero}|{f['texto']}".encode()).hexdigest()[:10]
        f["arquivo"] = str(out / f"{f['id']}_{h}.wav")
        if not Path(f["arquivo"]).exists():
            falta.append(f)
    if falta and os.environ.get("DETTO_VOZ_FALSA"):
        # TESTE sem a sua voz (sem baixar o modelo): voz de computador em português — Windows (voz "Maria"),
        # espeak-ng no Linux; sem nenhuma, um tom baixo com o tempo da fala
        for f in falta:
            if not voz_de_teste(f["texto"], f["arquivo"]):
                d = max(1.0, len(f["texto"].split()) * 0.36)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=f=200:d={d:.2f}", "-af", "volume=0.05",
                                "-ar", "24000", f["arquivo"]], check=True)
        falta = []
    if falta:
        instala()
        import torch
        import torchaudio
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        dev = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"voz: {len(falta)} falas na sua voz ({'placa de vídeo' if dev == 'cuda' else 'processador'})...", flush=True)
        m = ChatterboxMultilingualTTS.from_pretrained(device=dev)
        for k, f in enumerate(falta):
            pedacos = []
            for fr in frases(f["texto"]):
                kw = {"language_id": "pt", "exaggeration": a.exagero}
                if ref:
                    kw["audio_prompt_path"] = str(ref)
                w = m.generate(fr, **kw)
                pedacos += [w, torch.zeros(1, int(m.sr * 0.18))]
            torchaudio.save(f["arquivo"], torch.cat(pedacos, dim=1), m.sr)
            print(f"voz: {k + 1}/{len(falta)}", flush=True)
    Path(a.falas).write_text(json.dumps(falas, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
