"""LISTA OS VÍDEOS/PRODUTOS DE SHOP QUE ESTÃO VIRANDO e põe no produtos.txt (06/nov).

`python tools\\shop\\viral_shop.py [--pasta E:\\DETTO\\shop] [--quantos 40] [--categoria cozinha] [--sem-por]`
Para cada categoria do config do Shop, busca no YouTube os vídeos CURTOS de achadinho/TikTok Shop mais recentes
(a listagem já traz views e duração — de graça, sem abrir vídeo), fica com os que têm views por categoria
acima da mediana e escreve `link | nome | ` no produtos.txt, que o shop.py transforma em vídeo. Link que já
virou vídeo ou já está na lista não volta. `virais_shop.txt` guarda o que foi achado (link, views, título).
LIMITE DITO NA CARA: o TikTok em si não deixa robô listar; aqui o "viral" é o do YouTube Shorts sobre o produto.
"""

import argparse
import datetime as dt
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent))

SUFIXOS = ["achadinho tiktok shop", "tiktok shop vale a pena", "comprei na shopee achadinho", "produto viral tiktok"]
LIXO = re.compile(r"(#\w+|\|.*$|—.*$|-\s*tiktok shop.*$|tiktok shop|achadinhos?|shopee|vale a pena\??|link na bio|\bshorts\b)", re.I)


def limpa_nome(t):
    n = LIXO.sub(" ", t or "")
    n = re.sub(r"[^\w\sÀ-ÿ,.%/+-]", " ", n)
    return re.sub(r"\s+", " ", n).strip()[:70]


def lista(termo, n=15):
    url = "https://www.youtube.com/results?search_query=" + termo.replace(" ", "+") + "&sp=CAI%253D"
    try:
        r = subprocess.run(["yt-dlp", "--flat-playlist", "--dump-json", "--playlist-end", str(n), url],
                           capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
    except Exception:   # noqa: BLE001
        return []
    out = []
    for l in r.stdout.splitlines():
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


def escolhe(itens, ja):
    """filtra (curto, com views, não repetido) e fica com os acima da mediana de views do grupo"""
    bons = []
    for i in itens:
        vid, dur, v = i.get("id"), i.get("duration") or 0, i.get("view_count") or 0
        if not vid or dur > 120 or (dur and dur < 8) or vid in ja:
            continue
        nome = limpa_nome(i.get("title"))
        if len(nome) < 6:
            continue
        bons.append({"id": vid, "views": v, "dur": dur, "nome": nome, "link": f"https://www.youtube.com/shorts/{vid}",
                     "titulo": i.get("title") or ""})
    if len(bons) >= 4:
        med = statistics.median(b["views"] for b in bons)
        bons = [b for b in bons if b["views"] >= med]
    return sorted(bons, key=lambda b: b["views"], reverse=True)


def main():
    import shop as S

    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", default=str(S.pasta_padrao()))
    ap.add_argument("--quantos", type=int, default=40)
    ap.add_argument("--categoria")
    ap.add_argument("--sem-por", action="store_true", help="só lista, não escreve no produtos.txt")
    a = ap.parse_args()
    base = Path(a.pasta)
    cfg = S.prepara(base)
    hist = S.le_json(base / "historico.json", {}) or {}
    f = base / "produtos.txt"
    texto = f.read_text(encoding="utf-8")
    ja = set(re.findall(r"[\w-]{11}", texto)) | set(re.findall(r"[\w-]{11}", " ".join((hist.get("links") or {}).keys())))
    vistos = base / "virais_vistos.txt"
    if vistos.exists():
        ja |= set(vistos.read_text(encoding="utf-8").split())
    cats = [a.categoria] if a.categoria else (cfg.get("categorias") or [])
    achados = []
    for cat in cats:
        for suf in SUFIXOS[:2]:
            for b in escolhe(lista(f"{cat} {suf}"), ja | {x["id"] for x in achados}):
                b["categoria"] = cat
                achados.append(b)
    # mistura as categorias (uma de cada vez) para o dia não sair 30 vídeos de cozinha
    por_cat = {}
    for b in achados:
        por_cat.setdefault(b["categoria"], []).append(b)
    mix = []
    while any(por_cat.values()) and len(mix) < a.quantos:
        for c in list(por_cat):
            if por_cat[c] and len(mix) < a.quantos:
                mix.append(por_cat[c].pop(0))
    hoje = dt.date.today().isoformat()
    with open(base / "virais_shop.txt", "a", encoding="utf-8") as g:
        for b in mix:
            g.write(f"{hoje}\t{b['views']}\t{b['categoria']}\t{b['link']}\t{b['titulo']}\n")
    if not a.sem_por and mix:
        with open(f, "a", encoding="utf-8") as g:
            for b in mix:
                g.write(f"{b['link']} | {b['nome']}\n")
        with open(vistos, "a", encoding="utf-8") as g:
            g.write("\n".join(b["id"] for b in mix) + "\n")
    S.log(f"viral_shop: {len(mix)} produto(s) novo(s) {'listado(s)' if a.sem_por else 'no produtos.txt'}")
    for b in mix[:10]:
        S.log(f"   {b['views']:>9} views · {b['categoria']} · {b['nome']}")


if __name__ == "__main__":
    main()
