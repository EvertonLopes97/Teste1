# -*- coding: utf-8 -*-
"""MASTER SDR: converte a gravação HDR do iPhone (HLG) para SDR UMA VEZ, antes de editar — o que você fazia no CapCut.

    python tools\\sdr.py "gravação.MOV"            → "gravação SDR.mp4" ao lado (cor certa, sem perder qualidade)
    python tools\\sdr.py "pasta"                   → todos os vídeos HDR da pasta
    python tools\\sdr.py "gravação.MOV" --placa 0  → sem a placa de vídeo (mais lento)

Cor: SÓ converte (não "colore"): libplacebo na placa de vídeo usando o Dolby Vision que o iPhone grava junto — a mesma
conversão do iPhone/CapCut para tela comum. Sem libplacebo: zscale ajustado para dar o mesmo resultado (cor.py). Qualidade: lado maior até 1920 (o tamanho da edição; --4k mantém tudo), mesmo fps, H.264 alta qualidade na RTX (NVENC, cq 16) ou x264 crf 14 —
visualmente igual ao original. Áudio copiado (o "áudio espacial" do iPhone, que o FFmpeg não abre, fica de fora).
Mantém a data de gravação (os vlogs usam para pôr os clipes em ordem). Já convertido = reaproveita.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from cor import PLACEBO, filtro_cor, info_cor, placebo_ok  # noqa: E402

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv"}
VERSAO = "detto_cor v3"  # v3: zscale natural sempre (o libplacebo da placa saiu estourado)  # muda quando a conversão muda: masters antigos são refeitos
_NVENC = None


def tem_nvenc():
    global _NVENC
    if _NVENC is None:
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2", "-c:v", "h264_nvenc", "-f", "null", "-"],
                           capture_output=True, text=True)
        _NVENC = r.returncode == 0
    return _NVENC


def audio_bom(f):
    """o primeiro áudio que o FFmpeg deste PC abre (iPhone novo: o 1º é o "espacial", APAC)"""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    for k, c in enumerate(r.stdout.split()):
        if not c or c in ("unknown", "none") or "apac" in c:
            continue
        t = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-map", f"0:a:{k}", "-t", "0.2", "-f", "null", "-"], capture_output=True, text=True)
        if t.returncode == 0:
            return k
    return None


def _versao(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment", "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    return (r.stdout or "").strip()


def master_sdr(video, saida=None, placa=True, log=print, full=None):
    """devolve o caminho do vídeo SDR (o próprio vídeo se já for SDR). full=True mantém o 4K (padrão: lado maior até
    1920 — o tamanho em que tudo é editado e exportado; 4x mais rápido)"""
    if full is None:
        full = os.environ.get("DETTO_SDR_4K", "") == "1"
    video = Path(video)
    filtro = filtro_cor(video)
    if not filtro:
        return video
    saida = Path(saida) if saida else video.with_name(f"{video.stem} SDR.mp4")
    if saida.exists() and saida.stat().st_mtime >= video.stat().st_mtime and saida.stat().st_size > 1000 and _versao(saida) == VERSAO:
        return saida
    log(f"Cor: {video.name} é HDR ({info_cor(video)['transfer']}) → convertendo para SDR antes de editar: {saida.name}")
    a = audio_bom(video)
    if placa and tem_nvenc():
        enc = ["-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq", "16", "-b:v", "0", "-profile:v", "high"]
    else:
        enc = ["-c:v", "libx264", "-preset", "medium", "-crf", "14"]
    tmp = saida.with_name(saida.stem + ".parcial.mp4")
    placebo = info_cor(video)["hdr"] and placebo_ok(video)
    cmd = ["ffmpeg", "-y", "-v", "error"] + (["-init_hw_device", "vulkan"] if placebo else []) + ["-i", str(video), "-map", "0:v:0"]
    cmd += (["-map", f"0:a:{a}", "-c:a", "copy"] if a is not None else [])
    reduz = "" if full else "scale='if(gt(iw,ih),min(1920,iw),-2)':'if(gt(iw,ih),-2,min(1920,ih))':flags=lanczos,"
    log(f"   conversão: {'libplacebo + Dolby Vision (placa de vídeo)' if placebo else 'zscale'}")
    cmd += ["-vf", reduz + (PLACEBO if placebo else filtro)] + enc + ["-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                                    "-color_range", "tv", "-map_metadata", "0", "-metadata", f"comment={VERSAO}", "-movflags", "+faststart", str(tmp)]
    r = subprocess.run(cmd)
    if r.returncode != 0 and "h264_nvenc" in enc:
        log("   a placa de vídeo recusou; convertendo pelo processador")
        cmd = [x for x in cmd]
        i = cmd.index("-c:v")
        cmd[i:i + len(enc)] = ["-c:v", "libx264", "-preset", "medium", "-crf", "14"]
        r = subprocess.run(cmd)
    if r.returncode != 0 and placebo:
        log("   libplacebo falhou; convertendo pelo zscale")
        cmd = [x for x in cmd if x not in ("-init_hw_device", "vulkan")]
        cmd[cmd.index("-vf") + 1] = reduz + filtro
        r = subprocess.run(cmd)
    if r.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"não consegui converter {video.name} para SDR")
    os.replace(tmp, saida)
    st = video.stat()
    os.utime(saida, (st.st_atime, max(st.st_mtime, saida.stat().st_mtime)))
    return saida


def main():
    ap = argparse.ArgumentParser(description="HDR do iPhone → SDR (cor certa) antes de editar")
    ap.add_argument("alvo")
    ap.add_argument("--placa", type=int, default=1, help="1 = usa a placa de vídeo (NVENC) se tiver")
    ap.add_argument("--4k", dest="full", action="store_true", help="mantém a resolução original (mais lento e maior)")
    a = ap.parse_args()
    alvo = Path(a.alvo)
    vids = sorted(p for p in alvo.iterdir() if p.suffix.lower() in VIDEO_EXT and not p.stem.endswith(" SDR")) if alvo.is_dir() else [alvo]
    for v in vids:
        out = master_sdr(v, placa=bool(a.placa), full=a.full)
        print(f"{v.name}: {'já era SDR' if out == v else out.name}")


if __name__ == "__main__":
    main()
