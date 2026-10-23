# -*- coding: utf-8 -*-
"""Aba HISTÓRIAS do painel: as séries, os episódios prontos e o botão de fazer o próximo.

O trabalho pesado é do tools/historias/historias.py; aqui só mostramos e chamamos (um episódio por vez, como as
outras partes do painel).
"""
import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
sys.path.insert(0, str(TOOLS / "historias"))

PROC = {"p": None, "serie": "", "log": []}


def _h():
    import historias as H

    return H


def pasta():
    return _h().pasta_padrao()


def cfg():
    return _h().prepara(pasta())


def rodando():
    return bool(PROC["p"] and PROC["p"].poll() is None)


def estado():
    H = _h()
    p = pasta()
    c = H.prepara(p)
    out = []
    for f in H.series(p):
        s = H.le_json(f, {}) or {}
        eps = s.get("episodios", [])
        ult = eps[-1] if eps else None
        out.append({
            "pasta": f.parent.name,
            "nome": s.get("nome", f.parent.name),
            "tema": s.get("tema", ""),
            "mundo": s.get("mundo", ""),
            "conta": s.get("conta", ""),
            "ligada": bool(s.get("ligada", True)),
            "n": len(eps),
            "personagens": s.get("personagens", []),
            "ultimo": ({"n": ult["n"], "titulo": ult.get("titulo", ""), "escolha": ult.get("escolha", {}),
                        "resultado": (ult.get("resultado") or {}).get("texto", ""),
                        "arquivo": Path(ult.get("arquivo", "")).name if ult.get("arquivo") else "",
                        "capa": f"ep_{ult['n']:02d}/capa.jpg" if (f.parent / f"ep_{ult['n']:02d}" / "capa.jpg").exists() else "",
                        "existe": bool(ult.get("arquivo") and Path(ult["arquivo"]).exists())} if ult else None),
            "perfil": "arte/perfil.png" if (f.parent / "arte" / "perfil.png").exists() else "",
            "grade": "arte/grade.jpg" if (f.parent / "arte" / "grade.jpg").exists() else "",
        })
    return {"pasta": str(p), "series": out, "rodando": rodando(), "serie_rodando": PROC["serie"],
            "log": PROC["log"][-14:], "contas": c.get("contas", []), "por_dia": c.get("por_dia", 1),
            "duracao_s": c.get("duracao_s", 80), "auto_postar": bool(c.get("auto_postar", True)),
            "marca": c.get("marca", ""), "voz_voicestudio": c.get("voz_voicestudio", "")}


def _roda(args, serie=""):
    """roda o historias.py em outro processo e guarda o registro para o painel mostrar"""
    if rodando():
        return {"ok": False, "erro": "já tem um episódio sendo feito"}
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        exe = exe.with_name("python.exe")
    PROC["serie"] = serie
    PROC["log"] = []
    cmd = [str(exe), "-u", str(TOOLS / "historias" / "historias.py"), "--pasta", str(pasta()), *args]
    pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                          errors="replace", cwd=str(PONTE), env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                          **({"creationflags": 0x08000000} if os.name == "nt" else {}))
    PROC["p"] = pr

    def lendo():
        for linha in pr.stdout:
            PROC["log"].append(linha.rstrip()[:300])
            del PROC["log"][:-200]
        PROC["serie"] = ""

    threading.Thread(target=lendo, daemon=True).start()
    return {"ok": True}


def _roda_capa(serie):
    """refaz as capas dos episódios e a arte de perfil (o mesmo programa, só que o capa.py)"""
    if rodando():
        return {"ok": False, "erro": "espere o episódio terminar"}
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        exe = exe.with_name("python.exe")
    PROC["serie"] = serie or "capas"
    PROC["log"] = []
    cmd = [str(exe), "-u", str(TOOLS / "historias" / "capa.py"), "--pasta", str(pasta())] + (["--serie", serie] if serie else [])
    pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                          errors="replace", cwd=str(PONTE), env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                          **({"creationflags": 0x08000000} if os.name == "nt" else {}))
    PROC["p"] = pr

    def lendo():
        for linha in pr.stdout:
            PROC["log"].append(linha.rstrip()[:300])
            del PROC["log"][:-200]
        PROC["serie"] = ""

    threading.Thread(target=lendo, daemon=True).start()
    return {"ok": True}


def acao(nome, d):
    H = _h()
    if nome == "hist_novo":
        ideia = str(d.get("ideia", "")).strip()
        if not ideia:
            return {"ok": False, "erro": "escreva a ideia da história"}
        return _roda(["--novo", ideia] + (["--conta", d["conta"]] if d.get("conta") else []), "nova")
    if nome == "hist_episodio":
        extra = []
        if str(d.get("continuar", "")).lower() in ("a", "b"):
            extra += ["--continuar", str(d["continuar"]).lower()]
        if str(d.get("rumo", "")).strip():
            extra += ["--rumo", str(d["rumo"]).strip()[:600]]
        return _roda(["--serie", d["pasta"], "--quantos", "1", *extra], d.get("pasta", ""))
    if nome == "hist_apurar":
        return _roda(["--apurar"], "votos")
    if nome == "hist_capas":
        return _roda_capa(d.get("pasta", ""))
    if nome == "hist_serie_cfg":
        f = pasta() / "series" / d["pasta"] / "serie.json"
        s = H.le_json(f, {}) or {}
        for k in ("ligada",):
            if k in d:
                s[k] = bool(d[k])
        for k in ("conta", "mundo", "tema"):
            if k in d:
                s[k] = str(d[k]).strip()
        H.grava_json(f, s)
        return {"ok": True}
    if nome == "hist_cfg":
        f = pasta() / "config.json"
        c = H.le_json(f, {}) or {}
        for k in ("marca", "voz_voicestudio"):
            if k in d:
                c[k] = str(d[k]).strip()
        for k in ("por_dia", "duracao_s"):
            if k in d:
                c[k] = max(1, int(float(d[k])))
        if "auto_postar" in d:
            c["auto_postar"] = bool(d["auto_postar"])
        if "contas" in d:
            c["contas"] = [x.strip() for x in str(d["contas"]).split(",") if x.strip()]
        H.grava_json(f, {**H.CONFIG_PADRAO, **c})
        return {"ok": True}
    if nome == "hist_parar":
        if rodando():
            PROC["p"].terminate()
        return {"ok": True}
    return {"ok": False, "erro": f"ação desconhecida: {nome}"}


def arquivo(serie, nome):
    """um arquivo da série para o painel mostrar/baixar: o mp4 do episódio, a capa ou a arte de perfil.
    `nome` pode vir como "episodio.mp4" (acha o último) ou com a pasta junto ("ep_03/capa.jpg", "arte/perfil.png")."""
    f = (pasta() / "series" / serie).resolve()
    nome = str(nome or "").replace("\\", "/").strip("/")
    if "/" in nome:
        p = (f / nome).resolve()
        return p if p.exists() and str(p).startswith(str(f)) and ".." not in nome else None
    for p in sorted(f.glob(f"ep_*/{nome}")) + sorted(f.glob("ep_*/episodio.mp4")):
        if p.exists():
            return p
    return None


def laco(log=print, ocupado=None):
    """uma vez por dia faz o próximo episódio de cada série ligada (e apura os votos antes)"""
    while True:
        try:
            c = cfg()
            if c.get("auto_postar") and not rodando() and not (ocupado and ocupado()):
                hoje = dt.date.today().isoformat()
                marca = pasta() / ".ultimo_dia"
                feito = marca.read_text(encoding="utf-8").strip() if marca.exists() else ""
                if feito != hoje and 8 <= dt.datetime.now().hour <= 21:
                    marca.write_text(hoje, encoding="utf-8")
                    log("histórias: fazendo os episódios do dia")
                    _roda(["--quantos", str(int(c.get("por_dia", 1)))], "do dia")
        except Exception as e:
            log(f"histórias: {e}")
        time.sleep(300)
