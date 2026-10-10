# -*- coding: utf-8 -*-
"""Conferência antes de entregar (roda sozinha no fim do editar.py).

    python tools/conferir.py <job>/horizontal.mp4 "<gravação>" [--job <job>]

Confere e escreve <job>/conferencia.txt + conferencia.jpg (original × editado lado a lado):
  1. COR: quadros só com a câmera comparados com o mesmo instante da gravação (convertida
     certo, inclusive HDR do iPhone). Cor lavada, mais escura/clara ou sem saturação = AVISO.
  2. FOTOS: quais jogadores ficaram sem foto (e de onde veio cada foto).
  3. ÁUDIO: volume final (-14 LUFS é o padrão das redes).
  4. Arquivo: H.264, BT.709, duração.
Sai com código 0 mesmo com avisos; o resumo diz OK ou ATENÇÃO.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cor import filtro_cor, info_cor  # noqa: E402


def quadro(video, t, filtro="", largura=640):
    vf = ",".join(x for x in [filtro, f"scale={largura}:-2"] if x)
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-vf", vf,
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    import cv2
    import numpy as np
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)


def area(im):
    """Sem a faixa da legenda (embaixo) e o selo @detto.galo (canto de cima)."""
    h, w = im.shape[:2]
    return im[int(h * 0.08): int(h * 0.72), : int(w * 0.8)]


def stats(im):
    import cv2
    hsv = cv2.cvtColor(area(im), cv2.COLOR_BGR2HSV)
    return {"sat": float(hsv[..., 1].mean()), "luz": float(hsv[..., 2].mean())}


def momentos_so_camera(job, n=4, ate=None):
    """Instantes (timeline) com a câmera em tela cheia, sem gráfico e sem zoom, e o tempo na gravação."""
    d = json.loads((job / "tmp" / "direction.json").read_text(encoding="utf-8"))
    plan = json.loads((job / "EDIT_PLAN.json").read_text(encoding="utf-8"))
    ocupado = [(i["start"] - 0.4, i["end"] + 0.4) for i in d["items"] if i["type"] not in ("caption", "watermark")]
    ocupado += [(p["start"] - 0.2, p["end"] + 0.2) for p in d.get("punches", []) + d.get("pushes", [])]
    ocupado += [(s["start"], s["end"]) for s in d.get("shots", []) if s.get("z", 1) != 1]
    dur = min(d["duration"], ate or d["duration"])
    out = []
    for k in range(1, 40):
        t = dur * k / 40
        if any(a <= t < b for a, b in ocupado):
            continue
        c = next((c for c in plan["cuts"] if c["timeline"] <= t < c["timeline"] + (c["end"] - c["start"])), None)
        if c:
            out.append((t, c["start"] + (t - c["timeline"])))
    if len(out) > n:
        out = [out[int(i * (len(out) - 1) / (n - 1))] for i in range(n)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("saida")
    ap.add_argument("gravacao")
    ap.add_argument("--job")
    a = ap.parse_args()
    saida = Path(a.saida)
    grav = Path(a.gravacao)
    job = Path(a.job) if a.job else saida.parent
    linhas, avisos = [], []

    # arquivo
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,color_primaries,color_transfer,width,height:format=duration",
                         "-of", "json", str(saida)], capture_output=True, text=True)
    info = json.loads(pr.stdout or "{}")
    v = next((s for s in info.get("streams", []) if s.get("width")), {})
    linhas.append(f"Arquivo: {saida.name} {v.get('width')}x{v.get('height')} {v.get('codec_name')} "
                  f"cor {v.get('color_primaries', '?')}/{v.get('color_transfer', '?')}, {float(info.get('format', {}).get('duration', 0)):.1f} s")

    # cor
    ic = info_cor(grav)
    filtro = filtro_cor(grav)
    linhas.append(f"Gravação: {'HDR ' + ic['transfer'] + ' (iPhone) → convertida para SDR' if ic['hdr'] else 'SDR'} ({ic['primaries'] or 'bt709'}, {ic['pix_fmt']})")
    pares = []
    try:
        import cv2
        import numpy as np
        momentos = momentos_so_camera(job, ate=float(info.get("format", {}).get("duration", 0)) or None)
        for t, src in momentos:
            o = quadro(saida, t)
            g = quadro(grav, src, filtro)
            if o is None or g is None:
                continue
            g = cv2.resize(g, (o.shape[1], o.shape[0]))
            so, sg = stats(o), stats(g)
            dif = float(np.sqrt(((area(o).astype(float) - area(g).astype(float)) ** 2).mean()))
            pares.append((t, o, g, so, sg, dif))
        if pares:
            rs = sum(p[3]["sat"] for p in pares) / max(1e-6, sum(p[4]["sat"] for p in pares))
            dl = sum(p[3]["luz"] - p[4]["luz"] for p in pares) / len(pares)
            dm = sum(p[5] for p in pares) / len(pares)
            linhas.append(f"Cor (câmera, {len(pares)} quadros): saturação {rs * 100:.0f}% da gravação, brilho {dl:+.0f}, diferença média {dm:.1f}")
            if rs < 0.85:
                avisos.append("cor mais lavada que a gravação (saturação baixa)")
            if abs(dl) > 18:
                avisos.append(f"brilho diferente da gravação ({dl:+.0f})")
            if dm > 14:
                avisos.append("imagem diferente da gravação (confira o enquadramento/cor)")
            # folha de conferência: gravação × editado
            linhas_img = []
            for t, o, g, *_ in pares:
                for im, txt in ((g, f"GRAVACAO {t:.0f}s"), (o, "EDITADO")):
                    cv2.putText(im, txt, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
                    cv2.putText(im, txt, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (59, 255, 182), 2)
                linhas_img.append(np.hstack([g, o]))
            cv2.imwrite(str(job / "conferencia.jpg"), np.vstack(linhas_img), [cv2.IMWRITE_JPEG_QUALITY, 85])
        else:
            avisos.append("não consegui comparar a cor (sem trecho só de câmera)")
    except Exception as e:  # conferência nunca derruba a entrega
        avisos.append(f"conferência de cor falhou: {e}")

    # fotos
    jf = job / "jogadores.json"
    if jf.exists():
        j = json.loads(jf.read_text(encoding="utf-8"))
        linhas.append(f"Fotos: {len(j.get('players', {}))} jogadores conferidos pelo elenco, {len(j.get('sem_foto', []))} sem foto")
        for s in j.get("sem_foto", []):
            linhas.append(f"  sem foto: {s}")

    # áudio
    r = subprocess.run(["ffmpeg", "-v", "info", "-nostats", "-i", str(saida), "-vn", "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr or "")
    if m:
        lufs = float(m[-1])
        linhas.append(f"Áudio: {lufs:.1f} LUFS (alvo -14)")
        if abs(lufs + 14) > 2.5:
            avisos.append(f"volume fora do padrão ({lufs:.1f} LUFS)")

    resumo = "CONFERÊNCIA: OK" if not avisos else "CONFERÊNCIA: ATENÇÃO — " + "; ".join(avisos)
    txt = "\n".join([resumo, *linhas, "", "Veja conferencia.jpg (gravação × editado)."]) + "\n"
    (job / "conferencia.txt").write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
