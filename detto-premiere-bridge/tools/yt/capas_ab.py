"""Teste A/B das capas: views por VARIANTE (rosto | gancho | tema), de cada vídeo já postado.
python tools\\yt\\capas_ab.py --pasta E:\\DETTO\\canal_galo [--min-horas 24]
Compara views por hora de vida (vídeo mais velho tem mais views só por ter mais tempo)."""
import argparse
import datetime as dt
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "canal"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", required=True)
    ap.add_argument("--min-horas", type=float, default=24)
    a = ap.parse_args()
    pasta = Path(a.pasta)
    import youtube_up
    from googleapiclient.discovery import build

    posts = []
    for f in sorted((pasta / "prontos").glob("*/post.json")):
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if p.get("status") == "postado" and p.get("youtube") and p.get("thumb_variante"):
            posts.append(p)
    if not posts:
        print("nenhum vídeo postado com variante registrada ainda")
        return
    yt = build("youtube", "v3", credentials=youtube_up.credenciais(pasta), cache_discovery=False)
    ids = [p["youtube"].rsplit("/", 1)[-1] for p in posts]
    info = {}
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="statistics,snippet", id=",".join(ids[i:i + 50])).execute()
        for it in r.get("items", []):
            info[it["id"]] = it
    por = {}
    agora = dt.datetime.now(dt.timezone.utc)
    for p, vid in zip(posts, ids):
        it = info.get(vid)
        if not it:
            continue
        pub = dt.datetime.fromisoformat(it["snippet"]["publishedAt"].replace("Z", "+00:00"))
        h = (agora - pub).total_seconds() / 3600
        if h < a.min_horas:
            continue
        v = int(it["statistics"].get("viewCount", 0))
        por.setdefault(p["thumb_variante"], []).append(v / h)
    print("views por HORA de vida, por variante (mediana):")
    for k, xs in sorted(por.items(), key=lambda kv: -statistics.median(kv[1])):
        print(f"  {k:7s} {statistics.median(xs):7.1f}  ({len(xs)} vídeos)")
    if any(len(x) < 5 for x in por.values()):
        print("AVISO: menos de 5 vídeos em alguma variante — ainda é cedo para concluir.")


if __name__ == "__main__":
    main()
