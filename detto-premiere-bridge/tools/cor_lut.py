# -*- coding: utf-8 -*-
"""COR EXATA: aprende a conversão HDR→SDR de um vídeo de referência (o mesmo vídeo exportado pelo CapCut) e passa
a usar ela em tudo (master SDR, edição, reels, vlog).

    python tools\\cor_lut.py "IMG_7743.MOV" "IMG_7743 capcut.mp4"

1) No CapCut: importe a gravação do iPhone (aceite o aviso "HDR → SDR"), NÃO mexa em nada e exporte (1080p).
2) Rode o comando acima com o original e o exportado. Ele compara quadro a quadro e grava
   tools\\cor\\referencia.cube (uma tabela de cor 33x33x33). A partir daí toda gravação HLG do iPhone é convertida
   por essa tabela = a mesma cor do CapCut. Os masters SDR antigos são refeitos sozinhos.
3) Para voltar ao de antes: apague tools\\cor\\referencia.cube (ou DETTO_TONEMAP=compat).

Use um vídeo com bastante cor (pele, parede, roupa, céu): quanto mais cores aparecem, mais exata a tabela.
"""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from cor import LUT, ENTRADA_LUT, filtro_lut  # noqa: E402

N = 33
W = 216  # largura das miniaturas comparadas (rápido e sem ruído de compressão)


def duracao(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    return float((r.stdout or "0").strip() or 0)


def tamanho(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:stream_side_data=rotation",
                        "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    nums = [x for x in (r.stdout or "").replace("\n", ",").split(",") if x.strip().lstrip("-").isdigit()]
    w, h = int(nums[0]), int(nums[1])
    if len(nums) > 2 and abs(int(nums[2])) in (90, 270):
        w, h = h, w
    return w, h


def quadros(f, vf, fps, w, h, ini=0.0, dur=None):
    """quadros RGB 0..1 (float32) a `fps`, tamanho w x h"""
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{ini:.3f}", "-i", str(f)]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vf", f"fps={fps},{vf}scale={w}:{h}:flags=area,format=rgb48le", "-f", "rawvideo", "-"]
    r = subprocess.run(cmd, capture_output=True)
    a = np.frombuffer(r.stdout, np.uint16).astype(np.float32) / 65535.0
    n = a.size // (w * h * 3)
    return a[: n * w * h * 3].reshape(n, h, w, 3)


def ref_rgb(f):
    """referência SDR → RGB pelo zscale (matriz BT.709, faixa de TV), sem mexer na cor"""
    return "zscale=min=709:rin=tv:r=full,format=gbrp16le,"


def alinha(a, b, fps):
    """atraso (em quadros) de b em relação a a pelo brilho médio de cada quadro"""
    la = a.mean(axis=(1, 2, 3))
    lb = b.mean(axis=(1, 2, 3))
    melhor, k = -9, 0
    for d in range(-int(fps * 3), int(fps * 3) + 1):
        if d >= 0:
            x, y = la[: len(la) - d] if d else la, lb[d:]
        else:
            x, y = la[-d:], lb[: len(lb) + d]
        n = min(len(x), len(y))
        if n < fps * 2:
            continue
        x, y = x[:n] - x[:n].mean(), y[:n] - y[:n].mean()
        c = float((x * y).sum() / (np.sqrt((x * x).sum() * (y * y).sum()) + 1e-9))
        if c > melhor:
            melhor, k = c, d
    return k, melhor


def termos(x):
    r, g, b = x[:, 0], x[:, 1], x[:, 2]
    t = [np.ones_like(r), r, g, b]
    for p in range(3):
        for q in range(p, 3):
            t.append(x[:, p] * x[:, q])
    for p in range(3):
        for q in range(p, 3):
            for s in range(q, 3):
                t.append(x[:, p] * x[:, q] * x[:, s])
    return np.stack(t, 1)


def ajusta(src, dst):
    """tabela 33³: polinômio de 3º grau (base, preenche as cores que não aparecem) + correção por célula onde há dados"""
    A = termos(src)
    coef, *_ = np.linalg.lstsq(A, dst, rcond=None)
    g = np.linspace(0, 1, N, dtype=np.float32)
    bb, gg, rr = np.meshgrid(g, g, g, indexing="ij")  # .cube: R varia mais rápido
    grade = np.stack([rr.ravel(), gg.ravel(), bb.ravel()], 1)
    base = termos(grade) @ coef
    # resíduo médio por célula (vizinhança 3x3x3), peso = quantidade de pixels
    resid = dst - A @ coef
    idx = np.clip(np.rint(src * (N - 1)).astype(int), 0, N - 1)
    soma = np.zeros((N, N, N, 3), np.float64)
    cont = np.zeros((N, N, N), np.float64)
    np.add.at(soma, (idx[:, 2], idx[:, 1], idx[:, 0]), resid)
    np.add.at(cont, (idx[:, 2], idx[:, 1], idx[:, 0]), 1)
    from scipy.ndimage import uniform_filter
    s = np.stack([uniform_filter(soma[..., c], 3, mode="nearest") for c in range(3)], -1)
    c = uniform_filter(cont, 3, mode="nearest")
    corr = s / np.maximum(c, 1e-9)[..., None] * (c / (c + 2.0 / 27))[..., None]
    out = base + corr.reshape(-1, 3)
    return np.clip(out, 0, 1), coef


def grava_cube(tab, f):
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "w", encoding="ascii") as o:
        o.write("TITLE \"DETTO referencia (CapCut)\"\n")
        o.write(f"LUT_3D_SIZE {N}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n")
        for r, g, b in tab:
            o.write(f"{r:.6f} {g:.6f} {b:.6f}\n")


def main():
    ap = argparse.ArgumentParser(description="aprende a cor do CapCut (HDR→SDR) a partir do mesmo vídeo exportado")
    ap.add_argument("original", help="gravação do iPhone (HDR)")
    ap.add_argument("referencia", help="o mesmo vídeo exportado pelo CapCut (SDR), sem nenhum ajuste")
    ap.add_argument("--saida", default=str(LUT))
    a = ap.parse_args()
    orig, ref = Path(a.original), Path(a.referencia)
    wo, ho = tamanho(orig)
    wr, hr = tamanho(ref)
    if abs(wo / ho - wr / hr) > 0.02:
        sys.exit(f"Os dois vídeos têm formatos diferentes ({wo}x{ho} e {wr}x{hr}): exporte do CapCut sem cortar/girar.")
    w = W if wo <= ho else int(W * 16 / 9) // 2 * 2
    h = int(round(w * ho / wo / 2)) * 2
    fps = 10
    print("Lendo os dois vídeos...")
    A = quadros(orig, ENTRADA_LUT, fps, w, h)
    B = quadros(ref, ref_rgb(ref), fps, w, h)
    d, c = alinha(A, B, fps)
    print(f"   alinhamento: {d / fps:+.1f} s (semelhança {c:.2f})")
    if c < 0.6:
        print("   AVISO: os vídeos não parecem o mesmo trecho — confira se é o mesmo vídeo.")
    if d >= 0:
        A, B = A[: len(A) - d] if d else A, B[d:]
    else:
        A, B = A[-d:], B[: len(B) + d]
    n = min(len(A), len(B))
    A, B = A[:n], B[:n]
    # só pixels estáveis: tira bordas e onde muda muito de um quadro para o outro (movimento = desalinhado)
    mov = np.zeros(A.shape[:3], bool)
    if n > 2:
        dm = np.abs(np.diff(B.mean(-1), axis=0))
        mov[1:] |= dm > 0.04
        mov[:-1] |= dm > 0.04
    m = ~mov
    m[:, :3], m[:, -3:], m[:, :, :3], m[:, :, -3:] = False, False, False, False
    src, dst = A[m].reshape(-1, 3), B[m].reshape(-1, 3)
    if len(src) > 1_500_000:
        k = np.random.default_rng(1).choice(len(src), 1_500_000, replace=False)
        src, dst = src[k], dst[k]
    print(f"   {len(src):,} pixels comparados em {n} quadros")
    tab, _ = ajusta(src, dst)
    saida = Path(a.saida)
    grava_cube(tab, saida)
    # confere: aplica a tabela no original e compara com o CapCut
    C = quadros(orig, ENTRADA_LUT + filtro_lut(saida) + ",", fps, w, h)
    if d >= 0:
        C = C[: len(C) - d] if d else C
    else:
        C = C[-d:]
    C = C[:n]
    e = np.abs(C[m] - B[m]).mean() * 255
    print(f"Pronto: {saida}")
    print(f"   diferença média para o CapCut: {e:.1f} (de 255; abaixo de 3 = igual a olho nu)")
    print("   A partir de agora toda gravação HDR do iPhone usa essa cor (master SDR, edição, reels, vlog).")


if __name__ == "__main__":
    main()
