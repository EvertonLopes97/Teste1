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


def frases(texto, maximo=150):
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


def _apara(w, sr, torch):
    """tira o silêncio do começo/fim da frase"""
    a = w.abs().squeeze(0)
    lim = max(float(a.max()) * 0.02, 1e-4)
    idx = (a > lim).nonzero()
    if len(idx) == 0:
        return w
    i0 = max(0, int(idx[0]) - int(sr * 0.03))
    i1 = min(a.shape[0], int(idx[-1]) + int(sr * 0.08))
    return w[:, i0:i1]


def frase_boa(m, fr, ref, exag, torch, tentativas=4):
    """gera a frase e CONFERE: o modelo às vezes embola, gagueja, fica robótico ou corta — o sinal é o tamanho do
    áudio fora do normal para o texto (português falado ≈ 14 letras/s) ou picos/ruído. Refaz com outra semente."""
    esperado = max(0.8, len(fr) / 14.0)
    melhor, nota_m = None, 9e9
    for t in range(tentativas):
        torch.manual_seed(1234 + t * 97)
        kw = {"language_id": "pt", "exaggeration": exag, "cfg_weight": 0.5, "temperature": 0.7 if t == 0 else 0.6}
        if ref:
            kw["audio_prompt_path"] = str(ref)
        try:
            w = m.generate(fr, **kw)
        except TypeError:  # versão do chatterbox sem cfg_weight/temperature
            kw.pop("cfg_weight", None)
            kw.pop("temperature", None)
            w = m.generate(fr, **kw)
        w = _apara(w, m.sr, torch)
        d = w.shape[1] / m.sr
        razao = d / esperado
        # nota: quão longe do tamanho normal (0,7x a 1,6x é normal) + estouro (clipping)
        nota = abs(max(0.0, razao - 1.6)) + abs(max(0.0, 0.7 - razao)) * 2 + float((w.abs() > 0.99).float().mean()) * 50
        if nota < nota_m:
            melhor, nota_m = w, nota
        if nota < 0.05:
            break
        print(f"voz: frase estranha ({d:.1f}s para ~{esperado:.1f}s), refazendo: {fr[:50]}...", flush=True)
    return melhor


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
    if os.environ.get("DETTO_VOZ_FALSA"):
        chave_ref = "falsa"  # a voz de computador do TESTE nunca é reaproveitada num vídeo de verdade
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
        exag = min(a.exagero, 0.6)  # acima disso o modelo começa a "cantar"/embolar
        for k, f in enumerate(falta):
            pedacos = []
            for fr in frases(f["texto"]):
                w = frase_boa(m, fr, ref, exag, torch)
                pedacos += [w, torch.zeros(1, int(m.sr * 0.16))]
            torchaudio.save(f["arquivo"], torch.cat(pedacos, dim=1), m.sr)
            print(f"voz: {k + 1}/{len(falta)}", flush=True)
    Path(a.falas).write_text(json.dumps(falas, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
