#!/usr/bin/env python3
"""LIMPEZA DE DISCO (13/nov, pedido dele: "verifique o que está ocupando a memória, os vídeos já postados e seus temp, e exclua").
  python tools\\limpar.py            → só MOSTRA o que ocuparia espaço e o que apagaria (nada é apagado)
  python tools\\limpar.py --apagar   → apaga de verdade o que a lista "APAGAR" mostrou
  --dias N   idade mínima (padrão 2) · --raiz PASTA (padrão E:\\DETTO ou DETTO_PASTA)
O QUE APAGA (só vídeo pesado; os .json/legenda/thumb ficam):
  1 pastas temporárias (tmp, galo_tmp, tmp_ig, lipsync_tmp, *_tmp...) sem mexer há 1 dia+
  2 postar\\postados\\*: o vídeo já postado (fica o .json com o link)
  3 canal_*\\prontos\\*: vídeos de pronto com post.json "postado"/"descartado"
  4 shop\\prontos\\<dia>: vídeos de dias anteriores (já passaram pela fila de postagem)
  5 canal_*\\fontes: vídeos-fonte baixados há 3+ dias
NUNCA TOCA: voz, máscara, tokens/login, config, fila `entrada`, `celular` (esperando você postar), `falhas`, cache pago do Shop
(`ia_video`), nada fora da raiz, nada mexido nos últimos 30 min (pode estar em uso).
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

VIDEO = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"}
TEMPS = ("tmp", "galo_tmp", "tmp_ig", "temp", "lipsync_tmp", "lipsync_nuvem")
PROTEGIDO = {"voz", "mascara", "tokens", "entrada", "celular", "falhas", "ia_video", "ferramentas", "backups", "marca"}


def raiz_padrao():
    for c in (os.environ.get("DETTO_PASTA"), r"E:\DETTO", str(Path.home() / "DETTO")):
        if c and Path(c).is_dir():
            return Path(c)
    return Path(r"E:\DETTO")


def tamanho(p):
    p = Path(p)
    if p.is_file():
        return p.stat().st_size
    t = 0
    for r, _, fs in os.walk(p):
        for f in fs:
            try:
                t += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass
    return t


def gb(n):
    return f"{n / 1e9:.2f} GB" if n >= 1e8 else f"{n / 1e6:.0f} MB"


def idade_s(p):
    """segundos desde a última alteração de QUALQUER coisa dentro (pasta em uso não é apagada)"""
    p = Path(p)
    m = p.stat().st_mtime
    if p.is_dir():
        for r, ds, fs in os.walk(p):
            for f in fs:
                try:
                    m = max(m, os.path.getmtime(os.path.join(r, f)))
                except OSError:
                    pass
    return time.time() - m


def candidatos(raiz, dias):
    """→ lista de (motivo, caminho, bytes)"""
    saida, visto = [], set()

    def add(motivo, p):
        p = Path(p)
        if p in visto or not p.exists():
            return
        visto.add(p)
        saida.append((motivo, p, tamanho(p)))

    seg = dias * 86400
    for r, ds, fs in os.walk(raiz):
        rp = Path(r)
        ds[:] = [d for d in ds if d not in PROTEGIDO]
        for d in list(ds):
            if d.lower() in TEMPS or d.lower().endswith("_tmp"):
                if idade_s(rp / d) > 86400 and idade_s(rp / d) > 1800:
                    add("temporário", rp / d)
                ds.remove(d)
    for p in (raiz / "postar" / "postados").glob("*/*") if (raiz / "postar" / "postados").is_dir() else []:
        if p.is_file() and p.suffix.lower() in VIDEO and idade_s(p) > seg:
            add("já postado", p)
    for canal in raiz.glob("canal_*"):
        for pr in (canal / "prontos").glob("*") if (canal / "prontos").is_dir() else []:
            try:
                st = json.loads((pr / "post.json").read_text(encoding="utf-8")).get("status")
            except Exception:   # noqa: BLE001
                continue
            if st in ("postado", "descartado") and idade_s(pr) > seg:
                for f in pr.glob("*"):
                    if f.is_file() and f.suffix.lower() in VIDEO:
                        add(f"pronto {st}", f)
        for f in (canal / "fontes").glob("*") if (canal / "fontes").is_dir() else []:
            if f.is_file() and f.suffix.lower() in VIDEO and idade_s(f) > 3 * 86400:
                add("fonte baixada", f)
    for dia in (raiz / "shop" / "prontos").glob("*") if (raiz / "shop" / "prontos").is_dir() else []:
        if dia.is_dir() and idade_s(dia) > max(seg, 3 * 86400):
            for f in dia.rglob("*"):
                if f.is_file() and f.suffix.lower() in VIDEO:
                    add("shop de dia anterior", f)
    return saida


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apagar", action="store_true")
    ap.add_argument("--dias", type=int, default=2)
    ap.add_argument("--raiz")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raiz = Path(a.raiz) if a.raiz else raiz_padrao()
    if not raiz.is_dir():
        sys.exit(f"não achei a pasta {raiz}")
    livre = shutil.disk_usage(str(raiz)).free
    print(f"PASTA: {raiz}   |   livre no disco: {gb(livre)}\n\nO QUE MAIS OCUPA (2 níveis):")
    itens = []
    for d in raiz.iterdir():
        if d.is_dir():
            itens.append((tamanho(d), d))
            for s in d.iterdir():
                if s.is_dir():
                    itens.append((tamanho(s), s))
    for t, d in sorted(itens, reverse=True)[:15]:
        print(f"  {gb(t):>9}  {d.relative_to(raiz)}")
    c = candidatos(raiz, a.dias)
    total = sum(t for _, _, t in c)
    print(f"\nAPAGAR ({len(c)} itens, {gb(total)}):")
    for m, p, t in sorted(c, key=lambda x: -x[2])[:40]:
        print(f"  {gb(t):>9}  [{m}]  {p.relative_to(raiz)}")
    if len(c) > 40:
        print(f"  ... e mais {len(c) - 40}")
    if not a.apagar:
        print("\n(nada foi apagado — para apagar: python tools\\limpar.py --apagar)")
        return
    feito = 0
    for _, p, t in c:
        try:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
            feito += t
        except OSError as e:
            print(f"  não consegui apagar {p.name}: {e}")
    print(f"\nAPAGADO: {gb(feito)}. Livre agora: {gb(shutil.disk_usage(str(raiz)).free)}")


if __name__ == "__main__":
    main()
