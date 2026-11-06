#!/usr/bin/env python3
"""A aba CLIPES DE IA do painel — o Video Studio sem script de PowerShell nenhum.

Mesmo molde do shop_painel.py: um trabalho por vez, o registro ao vivo na tela e os prontos para
assistir/baixar. Quem faz o trabalho é o tools/studio/studio.py.
"""
import datetime as dt
import os
import sys
import threading
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
sys.path.insert(0, str(TOOLS / "studio"))

VIDEO_EXT = {".mp4", ".webm", ".mov"}
FOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}
TRAB = {"t": None, "o_que": "", "log": [], "fim": True}


def _s():
    import studio as S
    return S


def saida():
    for d in ("E:/DETTO/clipes_ia", "D:/DETTO/clipes_ia"):
        p = Path(d)
        if p.parent.exists():
            return p
    return Path.home() / "DETTO" / "clipes_ia"


def rodando():
    return TRAB["t"] is not None and TRAB["t"].is_alive()


def _log(m):
    TRAB["log"].append(str(m))
    del TRAB["log"][:-300]
    print(m, flush=True)


def estado():
    S = _s()
    comfy = os.environ.get("DETTO_COMFY") or S.COMFY_PADRAO
    lig = S.ligado(comfy)
    mods, i2v = {}, False
    if lig and not rodando():
        mods = S.modelos(comfy)
        i2v = S.tem_no("LTXVImgToVideo", comfy)
    ram = 0.0
    try:
        if os.name == "nt":
            import ctypes

            class M(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("mem", ctypes.c_ulong), ("tp", ctypes.c_ulonglong),
                            ("ap", ctypes.c_ulonglong), ("tpf", ctypes.c_ulonglong), ("apf", ctypes.c_ulonglong),
                            ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
            m = M()
            m.l = ctypes.sizeof(M)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            ram = round(m.ap / (1024 ** 3), 1)
        else:
            ram = round(os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / (1024 ** 3), 1)
    except Exception:
        ram = 0.0
    prontos = []
    base = saida()
    if base.is_dir():
        for dia in sorted((d for d in base.iterdir() if d.is_dir()), reverse=True)[:3]:
            for f in sorted(dia.iterdir(), reverse=True):
                if f.suffix.lower() in VIDEO_EXT:
                    prontos.append({"dia": dia.name, "nome": f.name})
            if len(prontos) >= 24:
                break
    return {"comfy": lig, "comfy_url": comfy, "i2v": i2v,
            "ckpt": mods.get("ckpt", ""), "t5": mods.get("t5", ""), "erro_modelos": mods.get("erro", ""),
            "ram": ram, "pasta": str(base), "rodando": rodando(), "o_que": TRAB["o_que"],
            "log": TRAB["log"][-16:], "prontos": prontos[:24]}


def _comeca(fn, o_que):
    if rodando():
        return {"ok": False, "erro": "já tem um trabalho rodando"}
    TRAB["o_que"] = o_que
    TRAB["log"] = []
    t = threading.Thread(target=fn, daemon=True)
    TRAB["t"] = t
    t.start()
    return {"ok": True}


def _dia():
    d = saida() / dt.date.today().isoformat()
    d.mkdir(parents=True, exist_ok=True)
    return d


def acao(nome, d):
    S = _s()
    comfy = os.environ.get("DETTO_COMFY") or S.COMFY_PADRAO

    if nome == "studio_texto":
        linhas = [l.strip() for l in str(d.get("prompts", "")).splitlines()
                  if l.strip() and not l.strip().startswith("#")]
        if not linhas:
            return {"ok": False, "erro": "escreva pelo menos um prompt (um por linha)"}
        frames = max(25, min(121, int(float(d.get("frames") or 49))))

        def tarefa():
            try:
                if not S.ligado(comfy):
                    return _log("O ComfyUI não respondeu. Abra ele primeiro (o botão aqui em cima explica como).")
                mods = S.modelos(comfy)
                if mods.get("erro") or not mods.get("ckpt"):
                    return _log(f"O ComfyUI não listou os modelos LTXV ({mods.get('erro', '')})")
                _log(f"{len(linhas)} clipe(s) | {frames} frames | modelo: {mods['ckpt']}")
                pedidos = [(p[:50], S.pedido_texto(p, frames, mods)) for p in linhas]
                S.roda(pedidos, _dia(), comfy, log=_log, prefixo="texto")
            except Exception as e:
                _log(f"parou: {str(e)[:300]}")
        return _comeca(tarefa, f"{len(linhas)} clipe(s) a partir de texto")

    if nome == "studio_fotos":
        pasta = Path(str(d.get("pasta", "")).strip().strip('"'))
        if not pasta.is_dir():
            return {"ok": False, "erro": "não achei essa pasta"}
        fotos = [f for f in sorted(pasta.iterdir()) if f.suffix.lower() in FOTO_EXT]
        if not fotos:
            return {"ok": False, "erro": "não tem foto (.jpg/.png/.webp) nessa pasta"}
        frames = max(25, min(121, int(float(d.get("frames") or 49))))
        mov = str(d.get("movimento", "")).strip()

        def tarefa():
            try:
                if not S.ligado(comfy):
                    return _log("O ComfyUI não respondeu. Abra ele primeiro.")
                if not S.tem_no("LTXVImgToVideo", comfy):
                    return _log("Este ComfyUI não tem o nó LTXVImgToVideo. Atualize o ComfyUI.")
                mods = S.modelos(comfy)
                if mods.get("erro") or not mods.get("ckpt"):
                    return _log(f"O ComfyUI não listou os modelos LTXV ({mods.get('erro', '')})")
                _log(f"{len(fotos)} foto(s) | {frames} frames | modelo: {mods['ckpt']}")
                tmp = _dia() / "_preparando"
                tmp.mkdir(exist_ok=True)
                pedidos = []
                for i, f in enumerate(fotos):
                    try:
                        pronta = S.prepara_foto(f, tmp / f"p{i:02d}.png")
                        no_comfy = S.manda_imagem(pronta, comfy)
                    except Exception as e:
                        _log(f"   pulei {f.name}: {str(e)[:140]}")
                        continue
                    m = mov or S.MOVIMENTOS[i % len(S.MOVIMENTOS)]
                    pedidos.append((f.stem, S.pedido_imagem(no_comfy, m, frames, mods)))
                if not pedidos:
                    return _log("nenhuma foto deu certo")
                S.roda(pedidos, _dia(), comfy, log=_log, prefixo="produto")
                for x in tmp.glob("*"):
                    x.unlink(missing_ok=True)
                tmp.rmdir()
            except Exception as e:
                _log(f"parou: {str(e)[:300]}")
        return _comeca(tarefa, f"{len(fotos)} clipe(s) a partir das suas fotos")

    return {"ok": False, "erro": f"ação desconhecida: {nome}"}


def arquivo(dia, nome):
    f = saida() / Path(str(dia)).name / Path(str(nome)).name
    return f if f.exists() and f.suffix.lower() in VIDEO_EXT else None
