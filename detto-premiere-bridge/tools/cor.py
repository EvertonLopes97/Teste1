# -*- coding: utf-8 -*-
"""Cor da gravação (o mesmo que tools/motion/ffopts.js → corDaGravacao).

iPhone grava em HDR (HLG / Dolby Vision, BT.2020, 10 bits). Convertido direto para H.264 SDR
fica lavado e sem cor. filtro_cor(video) devolve o filtro do FFmpeg que converte para SDR
BT.709 do jeito certo ("" quando a gravação já é SDR). DETTO_TONEMAP=clip|hable|0 troca o modo.
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


def filtro_cor(video):
    i = info_cor(video)
    tm = os.environ.get("DETTO_TONEMAP", "mobius").lower()
    if (i["hdr"] or "bt2020" in i["primaries"]) and not tem_zscale():
        print("AVISO: gravação em HDR, mas este FFmpeg não tem o filtro zscale; a cor pode sair lavada.")
        return ""
    if i["hdr"] and tm != "0":
        return (f"zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap={tm}:desat=0,"
                "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
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
