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


def destino():
    """`Meu Drive\\DETTO\\Narrados` (onde saem os prontos, a lista e as pastas reacoes\\ e fotos\\)"""
    try:
        import edicao
        raiz = edicao.drive_raiz()
    except Exception:  # noqa: BLE001
        raiz = None
    return (Path(raiz) / "DETTO" / "Narrados") if raiz else pasta()


def lista_linhas():
    try:
        return [l.strip() for l in (destino() / "lista.txt").read_text(encoding="utf-8-sig").splitlines()
                if l.strip() and not l.strip().startswith("#")]
    except OSError:
        return []


def prioridade():
    """há na lista algo marcado com `!` (prioridade)? Então canais/Shop/automáticos esperam e esse vai assim que o atual terminar."""
    try:
        return any(l.strip().startswith("!") for l in (destino() / "lista.txt").read_text(encoding="utf-8-sig").splitlines())
    except OSError:
        return False


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
    return {"pasta": str(base), "lista": lista_linhas(), "destino": str(destino()), "rodando": rodando(), "o_que": PROC["o_que"],
            "formatos": FORMATOS_ROTEIRO,
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


FORMATOS_ROTEIRO = {
    "reagir": "Reagir (notícia em cima, sua reação embaixo — vai para o Drive)",
    "short": "Short tela cheia (Galo) — vai para a fila de postagem",
    "short_gta": "Short do GTA 6 — sobe no canal do GTA",
    "highlight_gta": "Highlight do GTA 6 — jogo em cima, espaço para a sua reação",
}


def args_do_roteiro(item, pasta_gta=None):
    """`ROTEIRO[formato]: <arquivo> | <assunto>` → o que o narrado_fazer precisa (formato, arquivo, assunto)"""
    import re
    m = re.match(r"\s*ROTEIRO(?:\[(\w+)\])?\s*:\s*(.*)$", item, re.I)
    if not m:
        return None
    formato = (m.group(1) or "reagir").lower()
    arq_r, _, assunto_r = m.group(2).partition("|")
    d = {"texto_arquivo": arq_r.strip(), "assunto": assunto_r.strip() or "roteiro", "segundos": 90}
    if formato == "short":
        d.update(tela_cheia=True, fila=True)
    elif formato == "short_gta":
        d.update(tema="gta", tela_cheia=True, fila=True)
        if pasta_gta:
            d["fonte_canal"] = str(pasta_gta)
    elif formato == "highlight_gta":
        d.update(tema="gta", highlight=True)
    return d


def acao(nome, d):
    if nome == "narrado_fazer":
        assunto = str(d.get("assunto", "")).strip()
        args = []
        if assunto:
            args += ["--assunto", assunto]
        elif d.get("viral"):
            args += ["--viral"]
        else:
            args += ["--quente"]
        if d.get("drive"):
            args += ["--drive", str(d["drive"])]
        if d.get("tema") in ("gta", "historia"):
            args += ["--tema", d["tema"]]
        if (d.get("tema") == "gta" and not d.get("highlight")) or d.get("tela_cheia"):
            args += ["--tela-cheia"] + ([] if d.get("drive") else ["--fila"])
        if d.get("fila") and "--fila" not in args:      # short do roteiro dele: vai para a fila (e o de GTA sobe no canal)
            args += ["--fila"]
        if d.get("fonte_canal"):
            args += ["--fonte-canal", str(d["fonte_canal"])]
        if not d.get("drive") and not str(d.get("reacao", "")).strip():
            args += ["--drive", str(destino())]
        seg = int(float(d.get("segundos") or 60))
        args += ["--segundos", str(max(20, min(90, seg)))]
        if d.get("sem_clipes"):
            args += ["--sem-clipes"]
        if d.get("texto_arquivo") and Path(str(d["texto_arquivo"])).exists():
            args += ["--texto-arquivo", str(d["texto_arquivo"])]
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
    if nome == "narrado_lista":
        # um assunto por linha; o automático faz um vídeo de cada, em sequência (Drive\\DETTO\\Narrados\\lista.txt)
        novas = [l.strip() for l in str(d.get("texto", "")).splitlines() if l.strip()]
        f = destino() / "lista.txt"
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            antigas = [] if d.get("substituir") else [l for l in lista_linhas()]
            if d.get("prioridade"):    # passa na frente: `!` no começo (tira o ! se já tinha)
                novas = ["!" + l.lstrip("!") for l in novas]
                antigas = novas + antigas
                novas = []
            f.write_text("\n".join(antigas + novas) + "\n", encoding="utf-8")
        except OSError as e:
            return {"ok": False, "erro": f"não consegui gravar a lista ({str(e)[:100]})"}
        return {"ok": True, "n": len(novas)}
    if nome == "narrado_roteiro":
        # o roteiro (a narração) COLADO por ele: grava em Narrados\\roteiros\\ e põe na lista como `ROTEIRO: <arquivo> | <assunto>`
        texto = str(d.get("texto", "")).strip()
        assunto = " ".join(str(d.get("assunto", "")).split())[:110] or " ".join(texto.split()[:8])
        if len(texto.split()) < 20:
            return {"ok": False, "erro": "cole o roteiro inteiro (pelo menos 20 palavras)"}
        import re
        if re.search(r"\[[^\]\n]{3,}\]", texto):     # o modelo com [colchetes] ainda no texto: a voz leria isso
            return {"ok": False, "erro": "ainda tem [colchetes] do modelo no roteiro — troque pelo seu texto"}
        nome_arq = re.sub(r"[^\w-]+", "_", assunto.lower())[:50] or "roteiro"
        pasta_r = destino() / "roteiros"
        try:
            pasta_r.mkdir(parents=True, exist_ok=True)
            arq = pasta_r / (dt.datetime.now().strftime("%d%H%M") + "_" + nome_arq + ".txt")
            arq.write_text(texto + "\n", encoding="utf-8")
        except OSError as e:
            return {"ok": False, "erro": f"não consegui gravar o roteiro ({str(e)[:100]})"}
        # FORMATO (26/nov, "deixe poder colocar roteiro em cada lugar"): o mesmo roteiro vira Reagir (reação embaixo,
        # Drive), short em tela cheia do Galo (fila de postagem), short do GTA 6 (sobe no canal do GTA) ou highlight
        # do GTA (espaço da reação embaixo).
        formato = str(d.get("formato") or "reagir").strip().lower()
        if formato not in FORMATOS_ROTEIRO:
            formato = "reagir"
        marca = "ROTEIRO" if formato == "reagir" else f"ROTEIRO[{formato}]"
        linha = ("!" if d.get("prioridade") else "") + f"{marca}: {arq} | {assunto}"
        return acao("narrado_lista", {"texto": linha}) if not d.get("prioridade") else acao("narrado_lista", {"texto": linha.lstrip("!"), "prioridade": True})
    if nome == "narrado_prioridade":
        # passa um item da lista para a frente (e marca prioridade)
        alvo = str(d.get("linha", "")).strip().lstrip("!")
        f = destino() / "lista.txt"
        linhas = lista_linhas()
        resto = [l for l in linhas if l.lstrip("!") != alvo]
        if len(resto) == len(linhas):
            return {"ok": False, "erro": "não achei esse item na lista"}
        try:
            f.write_text("\n".join(["!" + alvo] + resto) + "\n", encoding="utf-8")
        except OSError as e:
            return {"ok": False, "erro": str(e)[:100]}
        return {"ok": True}
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
