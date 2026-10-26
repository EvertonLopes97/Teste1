"""Aba SHOP do painel — vídeos de TikTok Shop automáticos (tools\\shop\\shop.py).

Mostra as três origens de produto juntas: os links colados, as pastas dos produtos que chegaram em casa e a
busca por categoria. Um vídeo por vez (o shop.py tem a própria trava).
"""

import datetime as dt
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
for p in (str(TOOLS / "shop"), str(TOOLS)):
    if p not in sys.path:
        sys.path.insert(0, p)

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
FOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
PROC = {"p": None, "log": [], "o_que": ""}


def _s():
    import shop as S

    return S


def pasta():
    return _s().pasta_padrao()


def rodando():
    return bool(PROC["p"] and PROC["p"].poll() is None)


def _linhas(f, n=10):
    try:
        return [l.rstrip() for l in Path(f).read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()][-n:][::-1]
    except OSError:
        return []


def estado():
    S = _s()
    base = pasta()
    cfg = S.prepara(base)
    links = [l.strip() for l in (base / "produtos.txt").read_text(encoding="utf-8").splitlines()
             if l.strip().startswith("http")]
    hist = S.le_json(base / "historico.json", {}) or {}
    produtos = []
    for d in sorted((base / "produtos").iterdir() if (base / "produtos").is_dir() else []):
        if not d.is_dir() or d.name.startswith("."):
            continue
        info = S.le_json(d / "produto.json", {}) or {}
        midias = [p for p in d.iterdir() if p.suffix.lower() in VIDEO_EXT | FOTO_EXT]
        produtos.append({
            "pasta": d.name,
            "nome": info.get("nome") or d.name,
            "preco": str(info.get("preco") or ""),
            "link": info.get("link") or "",
            "modo": info.get("modo") or "",
            "fotos": sum(1 for p in midias if p.suffix.lower() in FOTO_EXT),
            "videos": sum(1 for p in midias if p.suffix.lower() in VIDEO_EXT),
            "feito": (hist.get("pastas", {}).get(d.name) or {}).get("dia", ""),
        })
    dia = dt.date.today().isoformat()
    prontos = sorted((base / "prontos" / dia).glob("*.mp4")) if (base / "prontos" / dia).is_dir() else []
    falhos = []
    for l in _linhas(base / "produtos_falhos.txt", 6):
        p_ = l.split("\t")
        if len(p_) >= 3:
            falhos.append({"quando": p_[0], "url": p_[1], "motivo": p_[2]})
    return {
        "pasta": str(base), "links": links[:20], "n_links": len(links), "produtos": produtos,
        "prontos": [{"nome": p.name, "dia": dia} for p in prontos],
        "falhos": falhos, "rodando": rodando(), "o_que": PROC["o_que"], "log": PROC["log"][-14:],
        "modo": cfg.get("modo", "ia"), "duracao": cfg.get("duracao", 34),
        "categorias": cfg.get("categorias", []), "postar": cfg.get("postar", []),
        "cta": cfg.get("cta", ""), "arroba": cfg.get("arroba", ""),
    }


def _roda(args, o_que=""):
    if rodando():
        return {"ok": False, "erro": "já tem um vídeo de Shop sendo feito"}
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        exe = exe.with_name("python.exe")
    PROC["o_que"] = o_que
    PROC["log"] = []
    cmd = [str(exe), "-u", str(TOOLS / "shop" / "shop.py"), "--pasta", str(pasta()), *[str(a) for a in args]]
    pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                          errors="replace", cwd=str(PONTE), env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                          **({"creationflags": 0x08000000} if os.name == "nt" else {}))
    PROC["p"] = pr

    def lendo():
        for linha in pr.stdout:
            PROC["log"].append(linha.rstrip()[:300])
            del PROC["log"][:-200]
        PROC["o_que"] = ""

    threading.Thread(target=lendo, daemon=True).start()
    return {"ok": True}


def acao(nome, d):
    S = _s()
    base = pasta()
    if nome == "shop_links":
        novos = [l.strip() for l in str(d.get("links", "")).splitlines() if l.strip().startswith("http")]
        if not novos:
            return {"ok": False, "erro": "cole pelo menos um link (https://...)"}
        f = base / "produtos.txt"
        tinha = [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip().startswith("http")]
        junto = list(dict.fromkeys(tinha + novos))
        f.write_text("\n".join(junto) + "\n", encoding="utf-8")
        return {"ok": True, "n": len(junto) - len(tinha)}  # o que REALMENTE entrou (link repetido não conta)
    if nome == "shop_fazer":
        args = ["--quantos", int(d.get("quantos") or 1)]
        if d.get("link"):
            args = ["--link", str(d["link"]).strip()]
        elif d.get("produto"):
            args = ["--produto", str(base / "produtos" / str(d["produto"]))]
        elif d.get("categoria"):
            args = ["--achar", str(d["categoria"]).strip(), "--quantos", int(d.get("quantos") or 1)]
        elif d.get("so_links"):
            args += ["--so-links"]
        if d.get("modo") in ("ia", "eu", "vendedor"):
            args += ["--modo", d["modo"]]
        if d.get("nao_postar"):
            args += ["--nao-postar"]
        return _roda(args, d.get("link") or d.get("produto") or d.get("categoria") or "a lista")
    if nome == "shop_parar":
        if rodando():
            PROC["p"].terminate()
        return {"ok": True}
    if nome == "shop_refazer":
        marca = base / "produtos" / str(d.get("produto", "")) / ".refazer"
        if not marca.parent.is_dir():
            return {"ok": False, "erro": "não achei a pasta do produto"}
        marca.write_text("", encoding="utf-8")
        return {"ok": True}
    if nome == "shop_cfg":
        cfg = S.prepara(base)
        for k in ("modo", "duracao", "cta", "arroba", "musica"):
            if k in d:
                cfg[k] = d[k]
        if "categorias" in d:
            cfg["categorias"] = [c.strip() for c in str(d["categorias"]).split(",") if c.strip()]
        if "postar" in d:
            cfg["postar"] = ["todas"] if d["postar"] in (True, "todas") else (d["postar"] or [])
        S.grava_json(base / "config.json", cfg)
        return {"ok": True}
    return {"ok": False, "erro": f"ação desconhecida: {nome}"}


def arquivo(nome, dia=""):
    """o mp4 pronto, para assistir/baixar no painel"""
    d = dia or dt.date.today().isoformat()
    f = pasta() / "prontos" / d / Path(str(nome)).name
    return f if f.exists() and f.suffix.lower() in VIDEO_EXT else None
