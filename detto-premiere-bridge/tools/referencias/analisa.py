# -*- coding: utf-8 -*-
"""ANALISA VÍDEOS DE REFERÊNCIA — baixa (480p, com o cookies.txt dele), MEDE a edição e devolve um zip PEQUENO
para o Claude olhar. O Claude não abre YouTube daqui; então o PC dele faz a parte pesada e eu leio o resultado.

    python tools\\referencias\\analisa.py                       (os 3 vídeos de GTA que ele mandou)
    python tools\\referencias\\analisa.py URL1 URL2 [--sem-fala]
    python tools\\referencias\\analisa.py --arquivo video.mp4   (já baixado; não toca no YouTube)

O que sai em <Downloads>\\referencias.zip (poucos MB):
  metricas.json  duração, nº de cortes, tamanho médio/mediano do plano, cortes por minuto (abertura x resto),
                 % de silêncio, palavras por minuto e as primeiras falas
  quadros_<n>.jpg  folha com 30 quadros do vídeo todo + folha dos 12 primeiros segundos (o gancho)
  fala_<n>.txt   transcrição com tempo (se o faster-whisper estiver instalado)
"""
from __future__ import annotations

import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "reels"))

PADRAO = ["https://youtu.be/ldPslg4px1I", "https://youtu.be/vR_9x6QIUlg", "https://youtu.be/bfur3ZES_Go"]


def sh(args, timeout=1800):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def duracao(f):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], 60)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def cortes(f, limite=0.3):
    """os segundos em que a imagem muda de plano (detecção de cena do ffmpeg)"""
    r = sh(["ffmpeg", "-v", "info", "-i", str(f), "-vf", f"select='gt(scene,{limite})',showinfo", "-an", "-f", "null", "-"])
    return sorted(float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr or ""))


def silencio(f, dur):
    r = sh(["ffmpeg", "-v", "info", "-i", str(f), "-vn", "-af", "silencedetect=noise=-35dB:d=0.4", "-f", "null", "-"])
    tot = sum(float(x) for x in re.findall(r"silence_duration: ([0-9.]+)", r.stderr or ""))
    return round(100 * tot / dur, 1) if dur else 0.0


def folha(f, saida, ini, fim, quantos, colunas, larg=320):
    """uma imagem só com `quantos` quadros entre ini e fim"""
    passo = max((fim - ini) / quantos, 0.2)
    linhas = -(-quantos // colunas)
    r = sh(["ffmpeg", "-v", "error", "-y", "-ss", str(ini), "-t", str(fim - ini), "-i", str(f), "-vf",
            f"fps=1/{passo:.3f},scale={larg}:-2,tile={colunas}x{linhas}", "-frames:v", "1", "-q:v", "4", str(saida)])
    return r.returncode == 0 and Path(saida).exists()


def fala(f, saida):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    try:
        m = WhisperModel("base", device="cpu", compute_type="int8")
        segs, info = m.transcribe(str(f), vad_filter=True)
        linhas, palavras = [], 0
        for s in segs:
            linhas.append(f"[{int(s.start // 60)}:{int(s.start % 60):02d}] {s.text.strip()}")
            palavras += len(s.text.split())
        Path(saida).write_text("\n".join(linhas), encoding="utf-8")
        return {"idioma": info.language, "palavras": palavras, "primeiras": linhas[:12]}
    except Exception as e:   # noqa: BLE001
        return {"erro": str(e)[:150]}


def baixa(url, pasta):
    import reels
    arq = reels.cookies_do_pc(pasta)
    r = reels.ytdlp(["-f", "bv*[height<=480]+ba/b[height<=480]/b", "--merge-output-format", "mp4",
                     "--write-info-json", "-o", str(pasta / "%(id)s.%(ext)s"), "--print", "after_move:filepath", url],
                    arq, timeout=1500)
    cam = ((r.stdout or "").strip().splitlines() or [""])[-1]
    if cam and Path(cam).exists():
        return Path(cam), {}
    return None, ((r.stderr or "").strip().splitlines() or ["?"])[-1][:200]


def mede(f, n, saida, com_fala=True):
    dur = duracao(f)
    cs = cortes(f)
    planos = [b - a for a, b in zip([0.0] + cs, cs + [dur])]
    abre = [c for c in cs if c <= 60]
    m = {"duracao_s": round(dur, 1), "cortes": len(cs),
         "plano_medio_s": round(statistics.mean(planos), 2) if planos else 0,
         "plano_mediano_s": round(statistics.median(planos), 2) if planos else 0,
         "cortes_por_min_total": round(len(cs) / (dur / 60), 1) if dur else 0,
         "cortes_nos_primeiros_60s": len(abre),
         "silencio_pct": silencio(f, dur)}
    if dur:
        resto = [c for c in cs if c > 60]
        m["cortes_por_min_depois_de_60s"] = round(len(resto) / max((dur - 60) / 60, 0.01), 1)
        ter = [sum(1 for c in cs if i * dur / 3 <= c < (i + 1) * dur / 3) for i in range(3)]
        m["cortes_por_terco"] = ter
    folha(f, saida / f"quadros_{n}.jpg", 0, max(dur - 1, 2), 30, 6)
    folha(f, saida / f"gancho_{n}.jpg", 0, min(12, dur), 12, 4)
    if com_fala:
        fl = fala(f, saida / f"fala_{n}.txt")
        if fl:
            if fl.get("palavras") and dur:
                fl["palavras_por_min"] = round(fl["palavras"] / (dur / 60))
            m["fala"] = fl
    return m


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    com_fala = "--sem-fala" not in sys.argv
    saida = Path(tempfile.mkdtemp(prefix="ref_"))
    trabalho = saida / "videos"
    trabalho.mkdir()
    res = {}
    if "--arquivo" in sys.argv:
        itens = [(a, Path(a)) for a in args]
    else:
        itens = []
        for u in (args or PADRAO):
            print(f"baixando {u} ...", flush=True)
            f, info = baixa(u, trabalho)
            if not f:
                print(f"   NÃO baixou: {info}", flush=True)
                res[u] = {"erro": info}
                continue
            itens.append((u, f))
    for n, (u, f) in enumerate(itens, 1):
        print(f"medindo {n}/{len(itens)}: {f.name}", flush=True)
        res[u] = mede(f, n, saida, com_fala)
    (saida / "metricas.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    destino = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Downloads" / "referencias.zip"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for p in saida.iterdir():
            if p.is_file():
                z.write(p, p.name)
    print(f"\nPRONTO. Me mande: {destino}  ({destino.stat().st_size // 1024} KB)")
    print(json.dumps(res, ensure_ascii=False, indent=1)[:1500])
    return 0 if any("erro" not in v for v in res.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
