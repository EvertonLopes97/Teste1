"""Aba SHOP do painel — vídeos de TikTok Shop automáticos (tools\\shop\\shop.py).

Mostra as três origens de produto juntas: os links colados, as pastas dos produtos que chegaram em casa e a
busca por categoria. Um vídeo por vez (o shop.py tem a própria trava).
"""

import datetime as dt
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


_FLOW = {"t": 0.0, "v": None}


def _flow_mod():
    p = str(TOOLS / "flow")
    if p not in sys.path:
        sys.path.insert(0, p)
    import flow_service
    return flow_service


def _flow_estado(cfg, forca=False):
    """saúde do Chrome do Flow (porta 9222) para o painel; guardada 8 s para o painel não ficar batendo na porta"""
    import time
    if not forca and _FLOW["v"] is not None and time.time() - _FLOW["t"] < 8:
        return _FLOW["v"]
    try:
        v = _flow_mod().saude(cfg)
    except Exception as e:   # noqa: BLE001
        v = {"chrome": False, "flow_aberto": False, "logado": None, "msg": f"não consegui verificar ({str(e)[:80]})"}
    v.update({"modelo": str(cfg.get("flow_modelo") or ""), "duracao": int(cfg.get("flow_duracao") or 0), "avatar": str(cfg.get("flow_avatar") or ""),
              "usar_avatar": bool(cfg.get("flow_usar_avatar")), "max_dia": int(cfg.get("flow_max_dia", 40)),
              "seguro_baixo": int(cfg.get("seguro_baixo") or 0), "projeto": str(cfg.get("flow_projeto_url") or "")})
    _FLOW["t"], _FLOW["v"] = time.time(), v
    return v


PEDIDO_REAL = ("The product from the uploaded photo as a premium commercial shot: slow orbital camera move around the product, "
               "soft studio lighting with gentle highlights, clean background, shallow depth of field. The product keeps EXACTLY "
               "the same shape, colors, label and printed text as the photo. No people, no extra text, no logos added, realistic.")


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
        "clipes_internet": bool(cfg.get("clipes_internet", True)),
        "clipes_quantos": int(cfg.get("clipes_quantos", 6)),
        "fotos_internet": bool(cfg.get("fotos_internet", True)),
        "ia_video": str(cfg.get("ia_video") or "desligado"), "ia_video_max": int(cfg.get("ia_video_max", 1)),
        "ia_video_s": int(cfg.get("ia_video_s", 5)),
        "flow": _flow_estado(cfg),
        "ia_chaves": {"fal": bool(cfg.get("fal_chave") or os.environ.get("FAL_KEY")), "seedance": bool(cfg.get("seedance_chave") or os.environ.get("SEEDANCE_API_KEY")),
                      "higgsfield": bool((cfg.get("hf_id") and cfg.get("hf_segredo"))
                                         or (os.environ.get("HF_API_KEY_ID") and os.environ.get("HF_API_KEY_SECRET")))},
        "narracao": bool(cfg.get("narracao", True)),
        "legenda": bool(cfg.get("legenda", True)),
        "auto": bool(cfg.get("auto", True)),
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
        if str(d.get("nome") or "").strip():
            args = ["--nome", str(d["nome"]).strip()]
        elif d.get("nomes_lista"):
            args += ["--nomes-lista"]
        elif d.get("link"):
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
        return _roda(args, d.get("nome") or d.get("link") or d.get("produto") or d.get("categoria") or "a lista")
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
        if d.get("ia_video") in ("desligado", "seedance", "higgsfield", "fal", "flow"):
            cfg["ia_video"] = d["ia_video"]
        for k in ("seedance_chave", "hf_id", "hf_segredo", "fal_chave"):
            if str(d.get(k) or "").strip():
                cfg[k] = str(d[k]).strip()
        if "ia_video_max" in d:
            cfg["ia_video_max"] = max(1, min(4, int(float(d["ia_video_max"] or 1))))
        if "ia_video_s" in d:
            cfg["ia_video_s"] = 10 if int(float(d["ia_video_s"] or 5)) >= 8 else 5
        for k in ("flow_modelo", "flow_avatar", "flow_projeto_url", "ia_video_pedido"):
            if k in d:
                cfg[k] = str(d[k] or "").strip()
        for k, a, b in (("flow_duracao", 0, 10), ("flow_max_dia", 1, 200), ("seguro_baixo", 0, 700)):
            if k in d:
                cfg[k] = max(a, min(b, int(float(d[k] or 0))))
        for k in ("clipes_internet", "fotos_internet", "narracao", "legenda", "auto", "flow_usar_avatar"):
            if k in d:
                cfg[k] = bool(d[k])
        if "clipes_quantos" in d:
            cfg["clipes_quantos"] = max(2, min(12, int(float(d["clipes_quantos"]))))
        if "categorias" in d:
            cfg["categorias"] = [c.strip() for c in str(d["categorias"]).split(",") if c.strip()]
        if "postar" in d:
            cfg["postar"] = ["todas"] if d["postar"] in (True, "todas") else (d["postar"] or [])
        S.grava_json(base / "config.json", cfg)
        return {"ok": True}
    if nome == "shop_flow_status":
        return {"ok": True, **_flow_estado(S.prepara(base), forca=True)}
    if nome == "shop_flow_abrir":
        bat = PONTE / "iniciar_chrome_flow.bat"
        if os.name != "nt" or not bat.exists():
            return {"ok": False, "erro": f"só no Windows; arquivo: {bat}"}
        subprocess.Popen(["cmd", "/c", "start", "", str(bat)], cwd=str(PONTE), creationflags=0x00000008)
        return {"ok": True}
    if nome == "shop_preset_real":
        # TikTok Shop (Produto Real): a foto REAL do produto anima no Flow (crédito da assinatura) + texto acima do card laranja
        cfg = S.prepara(base)
        cfg.update({"ia_video": "flow", "ia_video_max": 1, "ia_video_s": 5, "seguro_baixo": 480, "flow_usar_avatar": False,
                    "ia_video_pedido": str(d.get("pedido") or "").strip() or PEDIDO_REAL, "modo": "ia", "fotos_internet": False})
        S.grava_json(base / "config.json", cfg)
        _FLOW["v"] = None
        return {"ok": True}
    if nome == "shop_foto":
        # sobe a foto do produto (base64) para produtos\<nome>\
        import base64
        import re as _re
        nm = _re.sub(r"[^\w .-]", "", str(d.get("produto") or "").strip())[:60]
        arq = _re.sub(r"[^\w.-]", "_", str(d.get("arquivo") or "foto.jpg"))[:80]
        if not nm or Path(arq).suffix.lower() not in FOTO_EXT:
            return {"ok": False, "erro": "informe o nome do produto e uma foto (jpg/png/webp)"}
        try:
            dados = base64.b64decode(str(d.get("b64") or "").split(",")[-1])
        except Exception:   # noqa: BLE001
            return {"ok": False, "erro": "a foto não chegou direito"}
        if not 1000 < len(dados) < 25_000_000:
            return {"ok": False, "erro": "foto vazia ou grande demais (máx. 25 MB)"}
        dest = base / "produtos" / nm
        dest.mkdir(parents=True, exist_ok=True)
        (dest / arq).write_bytes(dados)
        info = dest / "produto.json"
        if not info.exists():
            S.grava_json(info, {"nome": str(d.get("produto")).strip()})
        return {"ok": True, "pasta": nm}
    return {"ok": False, "erro": f"ação desconhecida: {nome}"}


def arquivo(nome, dia=""):
    """o mp4 pronto, para assistir/baixar no painel"""
    d = dia or dt.date.today().isoformat()
    f = pasta() / "prontos" / d / Path(str(nome)).name
    return f if f.exists() and f.suffix.lower() in VIDEO_EXT else None
