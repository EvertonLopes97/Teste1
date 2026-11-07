#!/usr/bin/env python3
"""A aba REAGIR do painel — o vídeo narrado de notícia (conteúdo em cima, a reação dele embaixo).

Mesmo molde do shop_painel.py: um processo por vez, o registro ao vivo na tela e os prontos para
assistir/baixar. Quem faz o vídeo é o tools/narrado/narrado.py.
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
sys.path.insert(0, str(TOOLS / "narrado"))

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}
PROC = {"p": None, "o_que": "", "log": []}


def _n():
    import narrado as N
    return N


def pasta():
    return _n().raiz() / "narrado"


def rodando():
    return PROC["p"] is not None and PROC["p"].poll() is None


def _linhas(f, n=8):
    try:
        return [l.rstrip() for l in f.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()][-n:]
    except OSError:
        return []


def estado():
    base = pasta()
    prontos = []
    praiz = base / "prontos"
    if praiz.is_dir():
        for dia in sorted(praiz.iterdir(), reverse=True)[:3]:
            if not dia.is_dir():
                continue
            for job in sorted(dia.iterdir(), reverse=True):
                if not job.is_dir():
                    continue
                tem = {f.name for f in job.iterdir() if f.suffix.lower() in VIDEO_EXT}
                titulo = job.name.replace("-", " ")
                post = job / "post.txt"
                if post.exists():
                    # a PRIMEIRA linha é o título (o `_linhas` devolve as ÚLTIMAS: com ele saía a legenda)
                    try:
                        for l in post.read_text(encoding="utf-8", errors="replace").splitlines():
                            if l.strip():
                                titulo = l.strip()[:90]
                                break
                    except OSError:
                        pass
                prontos.append({"dia": dia.name, "job": job.name, "titulo": titulo,
                                "topo": "topo.mp4" in tem, "completo": "completo.mp4" in tem})
            if len(prontos) >= 12:
                break
    return {"pasta": str(base), "rodando": rodando(), "o_que": PROC["o_que"],
            "log": PROC["log"][-14:], "prontos": prontos[:12]}


def _roda(args, o_que=""):
    if rodando():
        return {"ok": False, "erro": "já tem um vídeo sendo feito"}
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        exe = exe.with_name("python.exe")
    PROC["o_que"] = o_que
    PROC["log"] = []
    cmd = [str(exe), "-u", str(TOOLS / "narrado" / "narrado.py"), "--pasta", str(pasta()), *[str(a) for a in args]]
    pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                          errors="replace", cwd=str(PONTE), env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                          **({"creationflags": 0x08000000} if os.name == "nt" else {}))
    PROC["p"] = pr

    def lendo():
        for linha in pr.stdout:
            PROC["log"].append(linha.rstrip())
            del PROC["log"][:-400]
        pr.wait()

    threading.Thread(target=lendo, daemon=True).start()
    return {"ok": True}


def acao(nome, d):
    if nome == "narrado_fazer":
        assunto = str(d.get("assunto", "")).strip()
        args = []
        if assunto:
            args += ["--assunto", assunto]
        else:
            args += ["--quente"]
        if d.get("tema") == "gta":
            args += ["--tema", "gta", "--tela-cheia", "--fila"]
            if d.get("fonte_canal"):
                args += ["--fonte-canal", str(d["fonte_canal"])]
        seg = int(float(d.get("segundos") or 60))
        args += ["--segundos", str(max(20, min(90, seg)))]
        if d.get("sem_clipes"):
            args += ["--sem-clipes"]
        reacao = str(d.get("reacao", "")).strip()
        if reacao and Path(reacao).exists():
            args += ["--reacao", reacao]
        return _roda(args, assunto or "notícia quente")
    if nome == "narrado_montar":
        # ele gravou a reação olhando o topo.mp4 e agora é só juntar (segundos, não minutos)
        dia, job = Path(str(d.get("dia", ""))).name, Path(str(d.get("job", ""))).name
        reacao = str(d.get("reacao", "")).strip().strip('"')
        alvo = pasta() / "prontos" / dia / job
        if not (alvo / "topo.mp4").exists():
            return {"ok": False, "erro": "não achei o topo.mp4 desse vídeo"}
        if not reacao or not Path(reacao).exists():
            return {"ok": False, "erro": "não achei a gravação da reação nesse caminho"}
        return _roda(["--montar", str(alvo), "--reacao", reacao], f"juntando a reação em {job}")
    if nome == "narrado_parar":
        if rodando():
            PROC["p"].terminate()
        return {"ok": True}
    return {"ok": False, "erro": f"ação desconhecida: {nome}"}


def arquivo(dia, job, nome):
    """o mp4 pronto, para assistir/baixar no painel"""
    d = dia or dt.date.today().isoformat()
    f = pasta() / "prontos" / Path(str(d)).name / Path(str(job)).name / Path(str(nome)).name
    return f if f.exists() and f.suffix.lower() in VIDEO_EXT else None
