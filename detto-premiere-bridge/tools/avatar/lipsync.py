#!/usr/bin/env python3
"""VOCÊ FALANDO DE VERDADE (12/nov, pedido dele: "eu aparecendo como se estivesse falando") — sincronia labial LOCAL.

Um vídeo-base seu (10–20 s olhando para a câmera) + a narração na sua voz clonada → o mesmo vídeo com a SUA boca
mexendo no que é dito. De graça, roda na placa do PC (Wav2Lip; cabe em 4 GB).

Fica ISOLADO do resto do DETTO: `<DETTO>\\ferramentas\\wav2lip\\` com o código, os pesos (~530 MB) e um Python
próprio (venv, ~3 GB com o PyTorch) — as bibliotecas velhas do Wav2Lip não tocam o Python do painel.

  python tools\\avatar\\lipsync.py --instalar
  python tools\\avatar\\lipsync.py --teste base.mp4 fala.wav [saida.mp4]

NÃO conferido no PC dele: a qualidade da boca (o Wav2Lip gera 96x96 px na boca; rosto muito grande na tela borra).
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = "https://github.com/Rudrabha/Wav2Lip.git"
PESOS = {
    "checkpoints/wav2lip_gan.pth": ("https://huggingface.co/camenduru/Wav2Lip/resolve/main/checkpoints/wav2lip_gan.pth", 400e6),
    "face_detection/detection/sfd/s3fd.pth": ("https://huggingface.co/camenduru/Wav2Lip/resolve/main/checkpoints/s3fd-619a316812.pth", 80e6),
}


def raiz_detto():
    for c in (os.environ.get("DETTO_PASTA"), r"E:\DETTO", str(Path.home() / "DETTO")):
        if c and Path(c).is_dir():
            return Path(c)
    return Path.home() / "DETTO"


def pasta():
    return Path(os.environ.get("DETTO_WAV2LIP") or raiz_detto() / "ferramentas" / "wav2lip")


def _py(p):
    return p / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def instalado(p=None):
    p = Path(p or pasta())
    return (_py(p).exists() and (p / "Wav2Lip" / "inference.py").exists()
            and all((p / "Wav2Lip" / k).exists() and (p / "Wav2Lip" / k).stat().st_size > v[1] for k, v in PESOS.items()))


def _baixa(url, destino, minimo, log):
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and destino.stat().st_size > minimo:
        return
    tmp = destino.with_suffix(destino.suffix + ".baixando")
    log(f"baixando {destino.name}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    if tmp.stat().st_size < minimo:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"{destino.name} veio incompleto; rode de novo")
    tmp.replace(destino)


def _remenda(w2l):
    """o Wav2Lip é de 2020: 2 linhas não rodam com as bibliotecas de hoje"""
    a = w2l / "audio.py"
    t = a.read_text(encoding="utf-8")
    t2 = t.replace("librosa.filters.mel(hp.sample_rate, hp.n_fft, n_mels=hp.num_mels,",
                   "librosa.filters.mel(sr=hp.sample_rate, n_fft=hp.n_fft, n_mels=hp.num_mels,")
    if t2 != t:
        a.write_text(t2, encoding="utf-8")
    i = w2l / "inference.py"
    t = i.read_text(encoding="utf-8")
    t2 = t.replace("checkpoint = torch.load(checkpoint_path)", "checkpoint = torch.load(checkpoint_path, weights_only=False)") \
          .replace("map_location=lambda storage, loc: storage)", "map_location=lambda storage, loc: storage, weights_only=False)")
    if t2 != t:
        i.write_text(t2, encoding="utf-8")
    s = w2l / "face_detection" / "detection" / "sfd" / "sfd_detector.py"
    if s.exists():
        t = s.read_text(encoding="utf-8")
        t2 = t.replace("model_weights = torch.load(path_to_detector)", "model_weights = torch.load(path_to_detector, weights_only=False)")
        if t2 != t:
            s.write_text(t2, encoding="utf-8")


def instala(log=print):
    p = pasta()
    p.mkdir(parents=True, exist_ok=True)
    livre = shutil.disk_usage(str(p)).free / 1e9
    if livre < 6 and not instalado(p):
        raise RuntimeError(f"só {livre:.1f} GB livres em {p}; a sincronia labial precisa de ~4 GB")
    w2l = p / "Wav2Lip"
    if not (w2l / "inference.py").exists():
        log("copiando o Wav2Lip do GitHub...")
        subprocess.run(["git", "clone", "--depth", "1", REPO, str(w2l)], check=True)
    _remenda(w2l)
    if not _py(p).exists():
        log("criando o Python separado (venv)...")
        subprocess.run([sys.executable, "-m", "venv", str(p / "venv")], check=True)
    py = str(_py(p))
    log("instalando o PyTorch com placa de vídeo (2–3 GB, demora)...")
    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip", "-q"], check=False)
    r = subprocess.run([py, "-m", "pip", "install", "-q", "torch", "torchvision", "--index-url",
                        "https://download.pytorch.org/whl/cu121"])
    if r.returncode != 0:
        log("sem o pacote da placa; instalo o PyTorch comum (fica mais lento)")
        subprocess.run([py, "-m", "pip", "install", "-q", "torch", "torchvision"], check=True)
    subprocess.run([py, "-m", "pip", "install", "-q", "numpy<2", "opencv-python", "librosa", "scipy", "tqdm", "numba"], check=True)
    for rel, (url, minimo) in PESOS.items():
        _baixa(url, w2l / rel, minimo, log)
    log(f"sincronia labial instalada em {p}" if instalado(p) else "instalação incompleta — rode de novo")
    return instalado(p)


def _chave_fal():
    """FAL_KEY do ambiente ou `fal_chave` do config do Shop (a mesma chave do painel)"""
    if os.environ.get("FAL_KEY"):
        return True
    try:
        import json
        cfg = json.loads((raiz_detto() / "shop" / "config.json").read_text(encoding="utf-8"))
        if str(cfg.get("fal_chave") or "").strip():
            os.environ["FAL_KEY"] = str(cfg["fal_chave"]).strip()
            return True
    except Exception:   # noqa: BLE001
        pass
    return False


def sincroniza_nuvem(base, wav, saida, log=print):
    """LatentSync (modelo ABERTO, Apache-2.0, melhor que o Wav2Lip) rodando no fal.ai — para quem não tem placa grande.
    Pago por uso. Devolve Path ou None (nunca derruba quem chamou)."""
    if not _chave_fal():
        return None
    try:
        tools = str(Path(__file__).resolve().parent.parent / "shop")
        if tools not in sys.path:
            sys.path.insert(0, tools)
        import fal
        import ia_video
        tmp = Path(saida).parent / "lipsync_nuvem"
        tmp.mkdir(parents=True, exist_ok=True)
        pequeno, mp3 = tmp / "base.mp4", tmp / "fala.mp3"
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(base), "-t", "20", "-an", "-vf", "scale=720:-2,fps=25",
                        "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-y", str(pequeno)], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-ac", "1", "-b:a", "96k", "-y", str(mp3)], check=True)
        log("   sincronia labial na nuvem (LatentSync, fal.ai — PAGO por uso)...")
        t0 = time.time()
        r = fal.roda(os.environ.get("DETTO_FAL_LIPSYNC") or fal.MODELOS["lipsync"],
                     {"video_url": ia_video._link_publico(pequeno), "audio_url": ia_video._link_publico(mp3)}, 1200, log)
        url = (r.get("video") or {}).get("url")
        if not url:
            raise RuntimeError(f"sem vídeo na resposta ({str(r)[:120]})")
        ia_video._baixa(url, Path(saida))
        shutil.rmtree(tmp, ignore_errors=True)
        log(f"   sincronia labial (nuvem) pronta em {time.time() - t0:.0f}s")
        return Path(saida)
    except Exception as e:   # noqa: BLE001
        log(f"   sincronia labial na nuvem falhou ({str(e)[:200]}); sigo sem ela")
        return None


def sincroniza(base, wav, saida, log=print, largura=1080, prazo=1500):
    """base (vídeo seu, rosto visível) + wav → saida.mp4 com a boca no que é falado. Devolve Path ou None (nunca derruba
    quem chamou: sem instalação, sem rosto ou erro = None e o chamador usa o vídeo sem sincronia)."""
    p = pasta()
    if os.environ.get("DETTO_LIPSYNC") == "nuvem" or not instalado(p):
        return sincroniza_nuvem(base, wav, saida, log)    # sem o Wav2Lip local: usa a nuvem, se houver chave
    saida = Path(saida)
    w2l = p / "Wav2Lip"
    tmp = saida.parent / "lipsync_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    # base menor e curta = rápido e cabe na memória (o Wav2Lip repete o vídeo-base até o fim do áudio)
    pequeno = tmp / "base.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(base), "-t", "20", "-an", "-vf", f"scale={largura}:-2,fps=25",
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-y", str(pequeno)], check=False)
    if not pequeno.exists():
        return None
    t0 = time.time()
    env = {**os.environ, "TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD": "1", "PYTHONIOENCODING": "utf-8"}
    cmd = [str(_py(p)), "inference.py", "--checkpoint_path", "checkpoints/wav2lip_gan.pth", "--face", str(pequeno),
           "--audio", str(wav), "--outfile", str(saida), "--pads", "0", "15", "0", "0",
           "--face_det_batch_size", "4", "--wav2lip_batch_size", "32"]
    try:
        r = subprocess.run(cmd, cwd=str(w2l), env=env, capture_output=True, text=True, timeout=prazo,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        log(f"   sincronia labial: passou de {prazo // 60} min e foi encerrada; sigo sem ela")
        return None
    finally:
        shutil.rmtree(w2l / "temp", ignore_errors=True)
        (w2l / "temp").mkdir(exist_ok=True)
    shutil.rmtree(tmp, ignore_errors=True)
    if r.returncode != 0 or not saida.exists() or saida.stat().st_size < 20000:
        erro = [l for l in (r.stderr or r.stdout or "").splitlines() if l.strip()]
        log(f"   sincronia labial falhou ({(erro[-1] if erro else 'sem saída')[:160]}); tento a nuvem se houver chave")
        return sincroniza_nuvem(base, wav, saida, log)
    log(f"   sincronia labial pronta em {time.time() - t0:.0f}s")
    return saida


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instalar", action="store_true")
    ap.add_argument("--teste", nargs="+", metavar=("BASE", "WAV"), help="base.mp4 fala.wav [saida.mp4]")
    a = ap.parse_args()
    if a.instalar:
        sys.exit(0 if instala() else 1)
    if a.teste and len(a.teste) >= 2:
        if not instalado():
            sys.exit("ainda não instalado: python tools\\avatar\\lipsync.py --instalar")
        s = Path(a.teste[2] if len(a.teste) > 2 else Path(a.teste[0]).with_name("teste_lipsync.mp4"))
        r = sincroniza(a.teste[0], a.teste[1], s)
        print(f"pronto: {r}" if r else "não deu — veja a mensagem acima")
        return
    print("instalado" if instalado() else "não instalado", "em", pasta())


if __name__ == "__main__":
    main()
