# -*- coding: utf-8 -*-
"""CAPAS DOS EPISÓDIOS e ARTE DE PERFIL da série.

O perfil de uma série só parece uma série quando a GRADE é igual em todo episódio: "EPISÓDIO", o número grande em
dourado, o título em caixa alta, o desenho da cena atrás e o nome da série no rodapé. É esse padrão (o mesmo dos
perfis que viralizaram) que faz quem chega no episódio 7 voltar e ver o 1.

    python tools\\historias\\capa.py                       → refaz a capa de todos os episódios de todas as séries
    python tools\\historias\\capa.py --serie apocalipse    → só essa (e a arte de perfil dela)
    python tools\\historias\\capa.py --serie X --perfil    → só a arte de perfil

Saídas, dentro da pasta da série:
    ep_NN\\capa.jpg          capa do reels (1080x1920) — é a que sobe junto com o vídeo
    ep_NN\\capa_grade.jpg    o quadrado do meio, como o Instagram mostra na GRADE do perfil
    arte\\perfil.png         foto de perfil (1080x1080 pensada para o recorte redondo)
    arte\\grade.jpg          as capas lado a lado, para você ver o perfil montado
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent


def log(m):
    print(m, flush=True)


def _cena_bonita(rot):
    """a cena que vira o fundo da capa: a mais cheia (gente + objetos), fora da cartela A/B e das cenas vazias"""
    cenas = [c for c in (rot.get("cenas") or []) if not c.get("escolha")]
    if not cenas:
        return {"cenario": "cidade", "luz": "noite"}
    def nota(c):
        return (len(c.get("pessoas") or []) * 3 + len(c.get("objetos") or []) * 2
                + len(c.get("silhuetas") or []) + (2 if c.get("plano") in ("geral", "medio") else 0))
    melhor = max(cenas, key=nota)
    c = dict(melhor)
    c["plano"] = "geral" if c.get("plano") == "close" else c.get("plano", "geral")
    return c


def _roda(pedido, log=log):
    f = Path(pedido["_tmp"])
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(pedido, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(["node", str(AQUI / "arte.js"), str(f)], cwd=str(PONTE), capture_output=True, text=True)
    f.unlink(missing_ok=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "arte.js falhou")[-300:])
    for linha in (r.stdout or "").splitlines():
        if linha.strip():
            log(f"    {linha.strip()}")


def capa_episodio(serie, rot, n, saida, log=log):
    """a capa de UM episódio (e o quadrado da grade ao lado)"""
    saida = Path(saida)
    titulo = ((rot.get("capa") or {}).get("titulo") or rot.get("titulo") or "").strip()
    _roda({"_tmp": str(saida.parent / "_arte.json"), "pecas": [{
        "tipo": "capa", "saida": str(saida), "grade": str(saida.parent / "capa_grade.jpg"),
        "cena": _cena_bonita(rot), "numero": n, "titulo": titulo,
        "serie": serie.get("nome", ""), "emoji": serie.get("emoji") or "📖",
    }]}, log)
    return saida


def arte_perfil(serie_f, log=log):
    """a foto de perfil da série + a folha com as capas já feitas (para você ver a grade montada)"""
    base = Path(serie_f).parent
    serie = json.loads(Path(serie_f).read_text(encoding="utf-8-sig"))
    arte = base / "arte"
    rot = None
    for f in sorted(base.glob("ep_*/roteiro.json")):
        rot = json.loads(f.read_text(encoding="utf-8-sig"))
        break
    # o personagem da série, com a roupa dele, posicionado no quadrado da foto de perfil
    fig = {}
    for c in (rot or {}).get("cenas", []):
        if c.get("pessoas"):
            fig = dict(c["pessoas"][0])
            break
    base_cena = _cena_bonita(rot or {})
    cena = {"cenario": base_cena.get("cenario", "cidade"), "luz": base_cena.get("luz", "noite"),
            "movimento": "zoom", "plano": "geral", "semente": 4, "objetos": [], "gatos": [], "silhuetas": [],
            "pessoas": [{**fig, "x": 0.5, "y": 0.70, "alt": 620, "pose": "olhando", "cara": "serio",
                         "falando": False, "olhando": 1}]}
    _roda({"_tmp": str(arte / "_arte.json"), "pecas": [{
        "tipo": "perfil", "saida": str(arte / "perfil.png"), "cena": cena,
        "serie": serie.get("nome", ""), "sub": serie.get("sub_perfil") or "NOVO EPISÓDIO TODO DIA",
    }]}, log)
    folha = _folha(base, arte / "grade.jpg", log)
    return arte / "perfil.png", folha


def _folha(base, saida, log=log):
    """as capas já feitas, lado a lado em 3 colunas — é o perfil como ele vai aparecer"""
    capas = sorted(base.glob("ep_*/capa_grade.jpg"))
    if not capas:
        return None
    entradas = []
    for c in capas[:12]:
        entradas += ["-i", str(c)]
    n = len(capas[:12])
    grafo = "".join(f"[{i}:v]scale=360:360,setsar=1[g{i}];" for i in range(n))
    grafo += "".join(f"[g{i}]" for i in range(n)) + f"xstack=inputs={n}:layout="
    grafo += "|".join(f"{(i % 3) * 360}_{(i // 3) * 360}" for i in range(n)) + ",format=yuv420p[v]"
    if n < 3:  # o xstack precisa de uma grade cheia; com 1 ou 2 capas basta empilhar na horizontal
        grafo = "".join(f"[{i}:v]scale=360:360,setsar=1[g{i}];" for i in range(n))
        grafo += "".join(f"[g{i}]" for i in range(n)) + f"hstack=inputs={n},format=yuv420p[v]"
    sys.path.insert(0, str(TOOLS))
    from ffcompat import filtro_complexo

    g = Path(saida).parent / "_grafo.txt"
    g.parent.mkdir(parents=True, exist_ok=True)
    g.write_text(grafo, encoding="utf-8")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *entradas, *filtro_complexo(str(g)), "-map", "[v]",
                        "-frames:v", "1", str(saida)], capture_output=True, text=True)
    g.unlink(missing_ok=True)
    if r.returncode != 0:
        log(f"    grade: não montei ({(r.stderr or '')[-140:]})")
        return None
    log(f"    grade do perfil: {saida}")
    return saida


def main():
    import historias as HI

    ap = argparse.ArgumentParser(description="capas dos episódios e arte de perfil das séries")
    ap.add_argument("--pasta", default=str(HI.pasta_padrao()))
    ap.add_argument("--serie", default="")
    ap.add_argument("--perfil", action="store_true", help="só a arte de perfil")
    a = ap.parse_args()
    fs = [f for f in HI.series(Path(a.pasta)) if not a.serie or HI.slug(a.serie) in f.parent.name]
    if not fs:
        log(f"nenhuma série em {Path(a.pasta) / 'series'}")
        return
    for f in fs:
        serie = HI.le_json(f, {}) or {}
        log(f"\n=== {serie.get('nome')} ===")
        if not a.perfil:
            for job in sorted(f.parent.glob("ep_*")):
                rot = HI.le_json(job / "roteiro.json")
                if not rot:
                    continue
                try:
                    capa_episodio(serie, rot, int(job.name.split("_")[1]), job / "capa.jpg")
                except Exception as e:
                    log(f"    {job.name}: {str(e)[:160]}")
        try:
            arte_perfil(f)
        except Exception as e:
            log(f"    perfil: {str(e)[:160]}")


if __name__ == "__main__":
    main()
