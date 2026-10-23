# -*- coding: utf-8 -*-
"""Aba CANAIS do painel: os dois canais automáticos do YouTube (notícias e vlogs).

- cada canal tem a sua pasta (E:\\DETTO\\canal_galo, E:\\DETTO\\canal_vlogs), o seu config.json e o seu login (token.json);
  a credencial do Google (client_secret.json) fica em E:\\DETTO\\youtube\\ e vale para os dois;
- "Ligado" = o painel roda o canal sozinho (notícias a cada 2 h das 8h às 23h; vlogs olham o Drive a cada 10 min);
- "Postar sozinho" = posta assim que fica pronto; desligado = espera você aprovar aqui;
- um trabalho pesado por vez (não monta canal enquanto uma edição roda, e vice-versa).
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
sys.path.insert(0, str(TOOLS / "canal"))
import comum  # noqa: E402


def _raiz():
    if os.name == "nt" and Path("E:/").exists():
        return Path("E:/DETTO")
    return Path.home() / "DETTO"


CANAIS = {
    "noticias": {"nome": "Notícias", "script": TOOLS / "canal" / "canal.py", "pasta": None, "dir": "canal_galo",
                 "intervalo_min": 120, "janela": (8, 23)},
    "vlogs": {"nome": "Vlogs", "script": TOOLS / "canal" / "canal_vlog.py", "pasta": None, "dir": "canal_vlogs",
              "intervalo_min": 10, "janela": (0, 23)},
}
PESADO = {"id": None, "p": None, "o_que": ""}  # montagem (uma por vez)
POSTANDO = {"p": None, "fila": [], "o_que": ""}  # envios para o YouTube (um por vez, leves)
TRAVA = threading.Lock()
LOG = print


def pasta(c):
    if CANAIS[c]["pasta"] is None:
        CANAIS[c]["pasta"] = _raiz() / CANAIS[c]["dir"]
    return Path(CANAIS[c]["pasta"])


def cfg_de(c):
    p = pasta(c)
    if not (p / "config.json").exists():  # cria o config padrão do canal
        _roda(c, ["--preparar"], so_preparar=True)
    return comum.le(p / "config.json", {}) or {}


def grava_cfg(c, muda):
    f = pasta(c) / "config.json"
    d = comum.le(f, {}) or {}
    muda(d)
    comum.grava(f, d)


def estado_local(c):
    return comum.le(pasta(c) / "painel_canal.json", {}) or {}


def grava_estado(c, **kw):
    f = pasta(c) / "painel_canal.json"
    d = comum.le(f, {}) or {}
    d.update(kw)
    pasta(c).mkdir(parents=True, exist_ok=True)
    comum.grava(f, d)


def py():
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        exe = exe.with_name("python.exe")
    return str(exe), ({"creationflags": 0x08000000} if os.name == "nt" else {})


def _roda(c, args, so_preparar=False, log_nome="canal.log", env_extra=None):
    exe, extra = py()
    p = pasta(c)
    p.mkdir(parents=True, exist_ok=True)
    cmd = [exe, "-u", str(CANAIS[c]["script"]), "--pasta", str(p), *args]
    if so_preparar:  # só cria as pastas e o config.json
        subprocess.run(cmd, cwd=str(PONTE), capture_output=True, timeout=300, env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **extra)
        return None
    logf = open(p / log_nome, "a", encoding="utf-8")
    logf.write(f"\n===== {dt.datetime.now():%d/%m %H:%M} {' '.join(args) or 'rodada'} =====\n")
    logf.flush()
    return subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, cwd=str(PONTE),
                            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", **(env_extra or {})}, **extra)


def segredo():
    for f in (_raiz() / "youtube" / "client_secret.json", pasta("noticias") / "client_secret.json", pasta("vlogs") / "client_secret.json"):
        if f.exists():
            return f
    return None


def ocupado():
    """o painel está montando um canal agora (a edição espera)"""
    p = PESADO["p"]
    return bool(p and p.poll() is None)


def _tail(f, n=40):
    if not f.exists():
        return []
    with open(f, encoding="utf-8", errors="replace") as g:
        return [l.rstrip() for l in g.readlines()[-n:]]


def _pronto_info(c, pr, d):
    vid = pr / (d.get("video") or "video.mp4")
    return {"id": pr.name, "titulo": d.get("titulo") or pr.name, "status": d.get("status", ""), "erro": d.get("erro", ""),
            "youtube": d.get("youtube", ""), "shorts_youtube": [x for x in d.get("shorts_youtube", []) if x],
            "video": vid.name if vid.exists() else "", "thumb": d.get("thumb") if d.get("thumb") and (pr / d["thumb"]).exists() else "",
            "shorts": [s["arquivo"] for s in d.get("shorts", []) if (pr / s["arquivo"]).exists()],
            "criado": (d.get("criado") or "")[:16].replace("T", " "), "descricao": d.get("descricao", ""), "tags": d.get("tags", []),
            "trechos": d.get("trechos", [])}


def estado():
    out = {}
    for c in CANAIS:
        p = pasta(c)
        cf = comum.le(p / "config.json", {}) or {}
        el = estado_local(c)
        prs = [_pronto_info(c, pr, d) for pr, d in comum.prontos(p)[:15]] if p.exists() else []
        x = {"nome": CANAIS[c]["nome"], "pasta": str(p), "ligado": bool(el.get("ligado")), "auto_postar": bool(cf.get("auto_postar")),
             "login": (p / "token.json").exists(), "canal_yt": el.get("canal_yt", ""), "ultimo": el.get("ultimo", ""),
             "rodando": PESADO["id"] == c and ocupado(), "postando": POSTANDO["o_que"] if POSTANDO["o_que"].startswith(c) else "",
             "prontos": prs, "esperando": sum(1 for x in prs if x["status"] == "aguardando"),
             "log": _tail(p / "canal.log"), "shorts": cf.get("shorts", 2), "privacidade": cf.get("privacidade", "public"),
             "mesclar_assunto": bool(cf.get("mesclar_assunto", False)),
             "campeonatos_ligado": bool(cf.get("campeonatos_ligado", True))}
        if c == "noticias":
            pf = p / "pautas.txt"
            x["pautas"] = [l.strip() for l in pf.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")] if pf.exists() else []
            x["feitas"] = _tail(p / "pautas_feitas.txt", 8)
            x["mascaras"] = sorted(f.name for f in (p / "mascara").glob("*") if f.is_file()) if (p / "mascara").exists() else []
            x["voz"] = (p / "voz" / "minha_voz.wav").exists()
            # VoiceStudio (open source, no PC dele): está aberto? quais vozes tem?
            try:
                sys.path.insert(0, str(TOOLS / "canal"))
                import voz as _voz

                url = cf.get("voicestudio") or _voz.voicestudio_url()
                x["vs_url"] = url
                x["vs_ligado"] = _voz.voicestudio_ligado(url, tempo=2)
                x["vs_vozes"] = _voz.voicestudio_vozes(url) if x["vs_ligado"] else []
            except Exception:
                x["vs_url"], x["vs_ligado"], x["vs_vozes"] = "", False, []
            x["voz_voicestudio"] = cf.get("voz_voicestudio", "")
            x["sem_voicestudio"] = bool(cf.get("sem_voicestudio"))
            x["velocidade_voz"] = cf.get("velocidade_voz", 1.0)
            x["nome_canal"] = cf.get("nome_canal", "")
            x["duracao"] = cf.get("duracao_alvo_min", 12)
            x["max_dia"] = cf.get("max_videos_dia", 2)
        else:
            sys.path.insert(0, str(TOOLS / "canal"))
            try:
                import canal_vlog

                raiz = canal_vlog.raiz_drive({**canal_vlog.CONFIG_PADRAO, **cf})
            except Exception:
                raiz = None
            hist = comum.le(p / "historico.json", {"feitos": {}}) or {"feitos": {}}
            pastas = []
            if raiz and raiz.exists():
                for d_ in sorted(raiz.iterdir(), key=lambda q: q.stat().st_mtime, reverse=True)[:20]:
                    if d_.is_dir():
                        n = sum(1 for f in d_.iterdir() if f.suffix.lower() in {".mov", ".mp4", ".m4v", ".mkv"})
                        pastas.append({"nome": d_.name, "clipes": n, "status": (hist["feitos"].get(d_.name) or {}).get("status", "novo")})
            x.update(drive=str(raiz or ""), drive_cfg=cf.get("drive", ""), pastas_drive=pastas, estilo=cf.get("estilo", ""),
                     duracao=cf.get("duracao", 10))
        out[c] = x
    out["segredo"] = bool(segredo())
    out["pasta_youtube"] = str(_raiz() / "youtube")
    out["fila_postar"] = len(POSTANDO["fila"])
    return out


def _pronto(c, pid):
    pr = pasta(c) / "prontos" / Path(pid).name
    if not (pr / "post.json").exists():
        raise ValueError("não achei esse vídeo")
    return pr


def arquivo(c, pid, nome):
    if c not in CANAIS:
        raise ValueError("canal")
    f = _pronto(c, pid) / Path(nome).name
    if not f.exists():
        raise ValueError("não achei")
    return f


def acao(nome, d):
    c = d.get("c")
    if c not in CANAIS and nome not in ("canal_segredo",):
        raise ValueError("canal?")
    if nome == "canal_cfg":
        if "ligado" in d:
            grava_estado(c, ligado=bool(d["ligado"]))

        def muda(x):
            for k in ("auto_postar", "mesclar_assunto", "campeonatos_ligado"):
                if k in d:
                    x[k] = bool(d[k])
            for k in ("shorts", "duracao", "duracao_alvo_min", "max_videos_dia"):
                if k in d:
                    x[k] = max(0, int(float(d[k])))
            for k in ("estilo", "nome_canal", "drive", "privacidade", "voicestudio", "voz_voicestudio"):
                if k in d:
                    x[k] = str(d[k]).strip()
            if "sem_voicestudio" in d:
                x["sem_voicestudio"] = bool(d["sem_voicestudio"])
            if "velocidade_voz" in d:
                x["velocidade_voz"] = max(0.5, min(2.0, float(d["velocidade_voz"])))
            if x.get("privacidade") not in ("public", "unlisted", "private"):
                x["privacidade"] = "public"
        cfg_de(c)
        grava_cfg(c, muda)
    elif nome == "canal_pautas":
        f = pasta(c) / "pautas.txt"
        cfg_de(c)
        linhas = [l.strip() for l in str(d.get("texto", "")).splitlines() if l.strip()]
        ja = f.read_text(encoding="utf-8").splitlines() if f.exists() else ["# uma pauta por linha: link, arquivo do PC ou assunto"]
        f.write_text("\n".join(ja + [l for l in linhas if l not in ja]) + "\n", encoding="utf-8")
        if d.get("agora"):
            return roda_agora(c)
    elif nome == "canal_tira_pauta":
        f = pasta(c) / "pautas.txt"
        if f.exists():
            alvo = str(d.get("linha", "")).strip()
            f.write_text("\n".join(l for l in f.read_text(encoding="utf-8").splitlines() if l.strip() != alvo) + "\n", encoding="utf-8")
    elif nome == "canal_rodar":
        return roda_agora(c)
    elif nome == "canal_teste":
        return roda_agora(c, teste=True)
    elif nome == "canal_parar":
        p = PESADO["p"]
        if p and p.poll() is None and PESADO["id"] == c:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
            else:
                p.terminate()
    elif nome == "canal_aprovar":
        pr = _pronto(c, d.get("id", ""))
        post = comum.le(pr / "post.json", {})
        for k in ("titulo", "descricao"):
            if d.get(k):
                post[k] = str(d[k]).strip()
        if isinstance(d.get("tags"), str):
            post["tags"] = [t.strip().lstrip("#") for t in re.split(r"[,\n]", d["tags"]) if t.strip()]
        post["status"] = "na_fila"
        comum.grava(pr / "post.json", post)
        with TRAVA:
            POSTANDO["fila"].append((c, str(pr)))
        return {"ok": True}
    elif nome == "canal_descartar":
        pr = _pronto(c, d.get("id", ""))
        post = comum.le(pr / "post.json", {})
        post["status"] = "descartado"
        comum.grava(pr / "post.json", post)
        if d.get("apagar"):
            shutil.rmtree(pr, ignore_errors=True)
    elif nome == "canal_refazer_vlog":
        # tira o vlog do histórico: a próxima rodada monta de novo
        f = pasta(c) / "historico.json"
        h = comum.le(f, {"feitos": {}}) or {"feitos": {}}
        h["feitos"].pop(str(d.get("nome", "")), None)
        comum.grava(f, h)
    elif nome == "canal_login":
        if not segredo():
            raise ValueError("falta o client_secret.json (passo 1 do guia nesta aba)")
        p = pasta(c)
        p.mkdir(parents=True, exist_ok=True)
        if not (p / "client_secret.json").exists():
            shutil.copyfile(segredo(), p / "client_secret.json")
        exe, extra = py()
        lf = open(p / "login.log", "w", encoding="utf-8")
        PESADO_LOGIN[c] = subprocess.Popen([exe, "-u", str(CANAIS[c]["script"]), "--pasta", str(p), "--login"], stdout=lf, stderr=subprocess.STDOUT,
                                           cwd=str(PONTE), env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **extra)
    elif nome == "canal_login_resultado":
        f = pasta(c) / "login.log"
        t = f.read_text(encoding="utf-8", errors="replace")[-2000:] if f.exists() else ""
        m = re.search(r"Ligado ao canal: (.+?) \(", t)
        if m:
            grava_estado(c, canal_yt=m.group(1))
        url = (re.findall(r"https://accounts\.google\.com/\S+", t) or [""])[-1]
        pl = PESADO_LOGIN.get(c)
        return {"rodando": bool(pl and pl.poll() is None), "texto": t, "url": url}
    elif nome == "canal_segredo":
        try:
            j = json.loads(d.get("texto", ""))
        except ValueError:
            raise ValueError("esse arquivo não é o client_secret.json (JSON)") from None
        if "installed" not in j and "web" not in j:
            raise ValueError("credencial errada: crie uma do tipo 'App para computador' (LEIA-ME)")
        dd = _raiz() / "youtube"
        dd.mkdir(parents=True, exist_ok=True)
        comum.grava(dd / "client_secret.json", j)
    elif nome == "canal_abrir":
        alvo = pasta(c) / {"mascara": "mascara", "voz": "voz", "prontos": "prontos"}.get(d.get("qual", ""), "")
        alvo.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(alvo))  # noqa: S606
    else:
        raise ValueError("ação?")
    return None


PESADO_LOGIN = {}


def roda_agora(c, forcar=True, teste=False):
    """teste = monta com voz de computador (sem a sua voz clonada), não posta — para ver a edição"""
    with TRAVA:
        if ocupado():
            raise ValueError(f"já tem um canal montando agora ({CANAIS[PESADO['id']]['nome']})")
        args = ["--forcar"] if (forcar and c == "noticias") else []
        if teste:
            args = ["--forcar", "--nao-postar"] if c == "noticias" else args
        PESADO.update(id=c, p=_roda(c, args, env_extra={"DETTO_VOZ_FALSA": "1"} if teste else None), o_que="montando (teste)" if teste else "montando")
        grava_estado(c, ultimo=dt.datetime.now().isoformat(timespec="minutes"))
    LOG(f"canal {CANAIS[c]['nome']}: rodada começou")
    return {"ok": True}


def laco(log=print, edicao_ocupada=lambda: False):
    """roda os canais ligados na hora certa e posta os aprovados"""
    global LOG
    LOG = log
    # aprovados que ficaram na fila quando o painel fechou
    for c in CANAIS:
        try:
            for pr, d in comum.prontos(pasta(c)):
                if d.get("status") in ("na_fila", "postando"):
                    POSTANDO["fila"].append((c, str(pr)))
        except Exception:
            pass
    while True:
        try:
            # 1) postar (leve; pode junto com montagem)
            pp = POSTANDO["p"]
            if pp is not None and pp.poll() is not None:
                log(f"canal {POSTANDO['o_que']}: {'postado' if pp.returncode == 0 else 'ERRO ao postar (veja o registro do canal)'}")
                POSTANDO.update(p=None, o_que="")
            if POSTANDO["p"] is None and POSTANDO["fila"]:
                with TRAVA:
                    c, pr = POSTANDO["fila"].pop(0)
                POSTANDO.update(p=_roda(c, ["--postar", pr]), o_que=f"{c}: {Path(pr).name}")
            # 2) montagem: terminou?
            p = PESADO["p"]
            if p is not None and p.poll() is not None:
                c = PESADO["id"]
                log(f"canal {CANAIS[c]['nome']}: rodada terminou ({'ok' if p.returncode == 0 else 'com erro'})")
                PESADO.update(id=None, p=None, o_que="")
            # 3) hora de rodar algum canal ligado?
            if not ocupado() and not edicao_ocupada():
                agora = dt.datetime.now()
                for c, info in CANAIS.items():
                    el = estado_local(c)
                    if not el.get("ligado"):
                        continue
                    h0, h1 = info["janela"]
                    if not (h0 <= agora.hour <= h1):
                        continue
                    try:
                        ult = dt.datetime.fromisoformat(el.get("ultimo") or "2000-01-01")
                    except ValueError:
                        ult = dt.datetime(2000, 1, 1)
                    if (agora - ult).total_seconds() >= info["intervalo_min"] * 60:
                        roda_agora(c, forcar=False)
                        break
        except Exception as e:
            log(f"canais: erro no laço ({e})")
        time.sleep(20)
