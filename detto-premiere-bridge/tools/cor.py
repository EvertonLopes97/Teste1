# -*- coding: utf-8 -*-
"""Cor da gravação (o mesmo que tools/motion/ffopts.js → corDaGravacao).

iPhone grava em HDR (HLG / Dolby Vision, BT.2020, 10 bits). Convertido direto para H.264 SDR
fica lavado e sem cor. filtro_cor(video) devolve o filtro do FFmpeg que converte para SDR
BT.709 do jeito certo ("" quando a gravação já é SDR).

Padrão (16/out/2026): SÓ CONVERTE, não "colore". Dois caminhos, o mesmo resultado:
  1) libplacebo (placa de vídeo, Vulkan): usa os metadados Dolby Vision que o iPhone grava junto — é a conversão
     que o próprio iPhone/CapCut fazem para tela comum (pele e parede neutras, sem estourar). Usado no MASTER SDR
     (sdr.py), que vale para edição, vlog e o começo dos reels.
  2) sem libplacebo (ou dentro de filtros maiores): zscale ajustado para bater com o 1) — branco em 350 nits,
     mobius, tira só o excesso de saturação dos brilhos (desat=1) e 12% de saturação (o tone mapping do zscale
     esquenta e satura a pele).
O antigo (203 nits, mobius 0,6, desat 0) deixava a pele laranja e a parede estourada.
DETTO_TONEMAP=natural (padrão) | 203 | antigo | clip | hable | 0 ; DETTO_PLACEBO=0 desliga o libplacebo.
"""
import json
import os
import subprocess


def info_cor(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=color_transfer,color_primaries,color_space,pix_fmt", "-of", "json", str(video)],
                       capture_output=True, text=True)
    try:
        s = (json.loads(r.stdout or "{}").get("streams") or [{}])[0]
    except json.JSONDecodeError:
        s = {}
    t = s.get("color_transfer", "") or ""
    p = s.get("color_primaries", "") or ""
    return {"hdr": t in ("arib-std-b67", "smpte2084"), "transfer": t, "primaries": p, "pix_fmt": s.get("pix_fmt", "")}


def tem_zscale():
    r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
    return " zscale " in (r.stdout or "")


def cadeia_hdr(tm="natural"):
    """HLG/PQ → SDR BT.709 pelo zscale. tm: natural (padrão, igual ao Dolby Vision do iPhone), 203, antigo, clip, hable."""
    if tm == "antigo":
        return ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=mobius:desat=0,"
                "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
    if tm in ("203", "mobius"):
        return ("zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=mobius:param=0.6:desat=0,"
                "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
    if tm in ("clip", "hable", "reinhard"):
        return (f"zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap={tm}:desat=0,"
                "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
    return ("zscale=t=linear:npl=350,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=mobius:desat=1,"
            "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,eq=saturation=0.88")


PLACEBO = ("libplacebo=tonemapping=auto:colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv:"
           "format=yuv420p")
_PLACEBO_OK = None


def _quadro(video, t, vf, vulkan=False, w=320):
    """um quadro em cinza (w de largura) depois do filtro vf — para conferir a conversão"""
    import numpy as np
    cmd = ["ffmpeg", "-v", "error"] + (["-init_hw_device", "vulkan"] if vulkan else []) + [
        "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", f"{vf},scale={w}:-2", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    if r.returncode != 0 or not r.stdout:
        return None
    a = np.frombuffer(r.stdout, np.uint8).astype(float)
    return a.reshape(-1, w) if a.size % w == 0 else None


def _riscos(img):
    """linhas/colunas "riscadas" (defeito de placa/driver no libplacebo)"""
    import numpy as np
    def k(v):
        m = np.array([np.median(v[max(0, i - 2):i + 3]) for i in range(len(v))])
        return float(np.abs(v - m).mean())
    return k(img.mean(1)) + k(img.mean(0))


def placebo_ok(video=None):
    """o FFmpeg deste PC tem libplacebo e a placa (Vulkan) converte certo? Confere num quadro do próprio vídeo
    contra o zscale: mesmo brilho e sem riscos. Resultado guardado para o resto do processo."""
    global _PLACEBO_OK
    if os.environ.get("DETTO_PLACEBO", "1") == "0":
        return False
    if _PLACEBO_OK is not None and (_PLACEBO_OK is False or video is None):
        return _PLACEBO_OK
    if _PLACEBO_OK is None:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
        if " libplacebo " not in (r.stdout or ""):
            _PLACEBO_OK = False
            return False
    if video is None:
        return True
    try:
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                                 capture_output=True, text=True).stdout.strip() or 2)
        t = min(d * 0.4, max(0.0, d - 0.5))
        p = _quadro(video, t, PLACEBO, vulkan=True)
        z = _quadro(video, t, cadeia_hdr("natural"))
        if p is None or z is None or p.shape != z.shape:
            _PLACEBO_OK = False
        else:
            brilho = abs(p.mean() - z.mean())
            _PLACEBO_OK = brilho < 30 and _riscos(p) < 1.6 * _riscos(z) + 0.3
    except Exception:
        _PLACEBO_OK = False
    if not _PLACEBO_OK:
        print("Cor: libplacebo (placa) indisponível ou com defeito — usando o zscale (mesmo resultado, um pouco diferente).")
    return _PLACEBO_OK


def filtro_cor(video):
    i = info_cor(video)
    tm = os.environ.get("DETTO_TONEMAP", "natural").lower()
    if (i["hdr"] or "bt2020" in i["primaries"]) and not tem_zscale():
        print("AVISO: gravação em HDR, mas este FFmpeg não tem o filtro zscale; a cor pode sair lavada.")
        return ""
    if i["hdr"] and tm != "0":
        return cadeia_hdr(tm)
    if "bt2020" in i["primaries"]:
        return "zscale=p=bt709:t=bt709:m=bt709:r=tv,format=yuv420p"
    return ""


def sdr_se_preciso(video, pasta):
    """Gravação HDR do iPhone → cópia SDR (cor certa) para quem lê quadros com o OpenCV.
    SDR: devolve o próprio vídeo. A cópia fica em `pasta` e é reaproveitada."""
    from pathlib import Path
    video = Path(video)
    f = filtro_cor(video)
    if not f:
        return video
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    out = pasta / f"{video.stem}_sdr.mp4"
    if out.exists() and out.stat().st_mtime >= video.stat().st_mtime:
        return out
    print(f"Gravação em HDR (iPhone): convertendo a cor para SDR → {out.name}")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stats", "-i", str(video), "-vf", f, "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "14", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                    "-c:a", "copy", str(out)], check=True)
    return out
