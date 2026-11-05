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
    # canal de GTA 6: o MESMO canal.py, com o preset gta6 (fontes, persona e regras no config da pasta)
    "gta6": {"nome": "GTA 6", "script": TOOLS / "canal" / "canal.py", "pasta": None, "dir": "canal_gta6",
             "intervalo_min": 180, "janela": (8, 23), "preset": "gta6"},
}
PESADO = {"id": None, "p": None, "o_que": ""}  # montagem (uma por vez)
POSTANDO = {"p": None, "fila": [], "o_que": ""}  # envios para o YouTube (um por vez, leves)
# FILA DE ESPERA das montagens (01/11, pedido dele): só cabe UMA montagem por vez (voz + render comem o PC
# inteiro), mas clicar "Rodar agora" com outra rodando NÃO faz mais nada — o canal entra aqui e começa sozinho
# assim que o anterior termina. Antes o botão só devolvia um erro e parecia que o clique não tinha pegado.
ESPERA = []   # [{"c": "noticias", "forcar": True, "teste": False, "pedido": "2026-11-01T14:10"}]
TRAVA = threading.Lock()
LOG = print
EDICAO_OCUPADA = lambda: False   # noqa: E731  (o painel põe a função de verdade no laco)


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
    pre = ["--preset", CANAIS[c]["preset"]] if CANAIS[c].get("preset") else []
    cmd = [exe, "-u", str(CANAIS[c]["script"]), "--pasta", str(p), *pre, *args]
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


def cookies_info():
    """o cookies.txt do YouTube: existe? de quando é? ainda tem o login dentro?

    É a resposta para "por que o canal não baixa": sem este arquivo o YouTube responde "Sign in to confirm
    you're not a bot" e NENHUM vídeo é baixado (05/nov)."""
    f = _raiz() / "cookies.txt"
    perfil = _raiz() / "postar" / "perfil_youtube"
    try:
        if not f.is_file() or f.stat().st_size < 100:
            return {"existe": False, "perfil": perfil.is_dir() and any(perfil.iterdir())}
        txt = f.read_text(encoding="utf-8", errors="replace")
        dias = (time.time() - f.stat().st_mtime) / 86400
        logado = any(p in txt for p in ("SAPISID", "LOGIN_INFO"))
        return {"existe": True, "dias": round(dias, 1), "logado": logado,
                "quantos": sum(1 for l in txt.splitlines() if l.strip() and not l.startswith("#")),
                "perfil": perfil.is_dir() and any(perfil.iterdir())}
    except OSError:
        return {"existe": False, "perfil": False}


def estado():
    out = {}
    for c in CANAIS:
        p = pasta(c)
        cf = comum.le(p / "config.json", {}) or {}
        el = estado_local(c)
        prs = [_pronto_info(c, pr, d) for pr, d in comum.prontos(p)[:15]] if p.exists() else []
        tv_ = travado(c)   # uma rodada está com a trava agora? (quem, se o pid estiver anotado)
        x = {"nome": CANAIS[c]["nome"], "pasta": str(p), "ligado": bool(el.get("ligado")), "auto_postar": bool(cf.get("auto_postar")),
             "login": (p / "token.json").exists(), "canal_yt": el.get("canal_yt", ""), "ultimo": el.get("ultimo", ""),
             "rodando": PESADO["id"] == c and ocupado(), "postando": POSTANDO["o_que"] if POSTANDO["o_que"].startswith(c) else "",
             "prontos": prs, "esperando": sum(1 for x in prs if x["status"] == "aguardando"),
             "log": _tail(p / "canal.log"), "shorts": cf.get("shorts", 2), "privacidade": cf.get("privacidade", "public"),
             "mesclar_assunto": bool(cf.get("mesclar_assunto", False)), "travado": bool(tv_), "travado_quem": tv_,
             "erro": el.get("erro", ""), "erro_em": el.get("erro_em", ""), "na_espera": na_espera(c),
             "campeonatos_ligado": bool(cf.get("campeonatos_ligado", True))}
        if CANAIS[c]["script"].name == "canal.py":   # notícias e GTA 6 (mesmo motor: pautas, voz, máscara)
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
    out["cookies"] = cookies_info()
    out["pasta_youtube"] = str(_raiz() / "youtube")
    out["fila_postar"] = len(POSTANDO["fila"])
    out["montando"] = CANAIS[PESADO["id"]]["nome"] if (PESADO["id"] and ocupado()) else ""
    out["espera"] = [CANAIS[x["c"]]["nome"] + (" (teste)" if x.get("teste") else "") for x in ESPERA]
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


def _mata(pid):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True, timeout=20)
        else:
            os.kill(int(pid), 9)
        return True
    except Exception:  # noqa: BLE001
        return False


def _processos_do_canal(c):
    """os python.exe que estão rodando o canal.py DESTA pasta (quando o pid não ficou anotado na trava).

    Sem isto, uma trava sem pid era um beco sem saída: o botão Destravar dizia "não tinha trava presa" e o
    canal ficava morto até ele achar o processo no Gerenciador de Tarefas (01/nov).
    """
    alvo = str(pasta(c)).lower()
    script = CANAIS[c]["script"].name.lower()
    desta, quaisquer = [], []
    linhas = []
    try:
        if os.name == "nt":
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
                                "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],
                               capture_output=True, text=True, timeout=30)
            dados = json.loads(r.stdout or "[]")
            if isinstance(dados, dict):
                dados = [dados]
            linhas = [(int(p.get("ProcessId") or 0), (p.get("CommandLine") or "").lower()) for p in dados]
        else:
            r = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True, timeout=20)
            for l in (r.stdout or "").splitlines():
                pid_, _, args = l.strip().partition(" ")
                if pid_.isdigit():
                    linhas.append((int(pid_), args.lower()))
    except Exception:  # noqa: BLE001
        return []
    for p, linha in linhas:
        if p in (0, os.getpid()) or script not in linha:
            continue
        # a pasta na linha de comando é o casamento CERTO; sem ela, ainda é um canal.py candidato (a trava sem
        # pid só acontece quando algo já deu errado, e deixar o canal morto é pior)
        (desta if alvo in linha else quaisquer).append(p)
    return desta or quaisquer


def destrava(c):
    """DESTRAVAR SEMPRE RESOLVE (01/nov). Antes, trava sem pid anotado = beco sem saída: o botão dizia "não tinha
    trava presa" e o canal continuava morto. Agora, em ordem: pid morto → livre; pid vivo → encerra; sem pid →
    procura o python.exe que está rodando o canal.py DESTA pasta e encerra; nada rodando → apaga o arquivo."""
    sys.path.insert(0, str(TOOLS / "reels"))
    from reels import dono_da_trava, trava_rodada

    f = pasta(c) / ".canal_rodando"
    quem, pid = dono_da_trava(pasta(c), ".canal_rodando")
    if pid and not vivo(pid):
        f.unlink(missing_ok=True)
        return {"ok": True, "msg": f"o processo {pid} já tinha morrido — destravei"}
    if pid:
        if _mata(pid):
            LOG(f"canal {CANAIS[c]['nome']}: encerrei o processo {pid} que estava com a trava ({quem})")
            return {"ok": True, "msg": f"encerrei o processo {pid}. Clique em Rodar agora."}
        return {"ok": False, "erro": f"não consegui encerrar o processo {pid}"}
    # SEM PID ANOTADO: ninguém está com ela, ou é um processo que não anotou
    t = trava_rodada(pasta(c), ".canal_rodando", so_testa=True)
    if t:
        t.close()
        f.unlink(missing_ok=True)
        return {"ok": True, "msg": "não tinha ninguém trabalhando; apaguei a trava que ficou para trás. "
                                   "Clique em Rodar agora."}
    mortos = [p for p in _processos_do_canal(c) if _mata(p)]
    if mortos:
        time.sleep(1.5)
        f.unlink(missing_ok=True)
        LOG(f"canal {CANAIS[c]['nome']}: encerrei {len(mortos)} processo(s) do canal.py ({', '.join(map(str, mortos))})")
        return {"ok": True, "msg": f"encerrei {len(mortos)} processo(s) que estavam rodando este canal. "
                                   "Clique em Rodar agora."}
    return {"ok": False, "erro": "a trava está presa e eu não achei o processo. Feche TODOS os python.exe no "
                                 "Gerenciador de Tarefas (Ctrl+Shift+Esc), reabra o painel e rode de novo."}


def vivo(pid):
    """esse processo ainda existe? (sem matar nada e sem precisar do psutil)"""
    if not pid or pid == os.getpid():
        return False
    try:
        if os.name == "nt":
            import ctypes

            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))   # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            saiu = ctypes.c_ulong(0)
            ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(saiu))
            ctypes.windll.kernel32.CloseHandle(h)
            return saiu.value == 259   # STILL_ACTIVE
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, AttributeError):
        return False


def travado(c):
    """quem está com a trava do canal, se houver (para o painel avisar).

    NÃO TESTA PEGANDO A TRAVA (01/nov). Antes testava: o painel chamava `trava_rodada` a cada carregamento de
    tela, e isso (1) ESCREVIA o pid do painel dentro do arquivo, mentindo sobre quem é o dono, (2) TRUNCAVA o
    arquivo, apagando o pid do dono de verdade — e era por isso que o registro dizia "outro canal.py está com a
    trava ()", sem pid nenhum — e (3) disputava a trava com o canal.py no exato segundo em que ele começava,
    matando a rodada na largada. O canal de notícias ficou das 18h16 às 20h46 sem rodar por causa disso.
    Agora eu só LEIO o pid anotado e pergunto se aquele processo está vivo.
    """
    f = pasta(c) / ".canal_rodando"
    if not f.exists():
        return ""
    try:
        sys.path.insert(0, str(TOOLS / "reels"))
        from reels import dono_da_trava

        quem, pid = dono_da_trava(pasta(c), ".canal_rodando")
        if pid:
            return quem if vivo(pid) else ""      # pid morto = trava velha, o arquivo só ficou para trás
        # sem pid anotado: só então eu testo pegando — e devolvo na hora, sem escrever nada
        from reels import trava_rodada

        t = trava_rodada(pasta(c), ".canal_rodando", so_testa=True)
        if t:
            t.close()
            return ""
        return "um processo sem pid anotado"
    except Exception:  # noqa: BLE001
        return ""


def pega_cookies(atualizar=False):
    """ENTRAR NO YOUTUBE DE UMA VEZ (05/nov, pedido dele: "quero um botão").

    `atualizar=False` abre uma JANELA do nosso Chromium para ele entrar na conta uma vez; depois disso o
    `atualizar=True` reexporta do perfil salvo sem janela e sem login. Roda em segundo plano: a janela fica
    aberta esperando ele, então o painel não pode ficar travado junto."""
    alvo = TOOLS / "postar" / "cookies_youtube.py"
    if not alvo.exists():
        raise ValueError("não achei o cookies_youtube.py (rode o ATUALIZAR.ps1)")
    # `py()` devolve (executável, extras) — passar a TUPLA inteira para o Popen estourava
    # "expected str, bytes or os.PathLike object, not tuple" (05/nov, erro meu)
    exe, extra = py()
    args = [exe, str(alvo)] + (["--atualizar"] if atualizar else ["--minutos", "8"])
    reg = _raiz() / "postar" / "cookies.log"
    reg.parent.mkdir(parents=True, exist_ok=True)
    with reg.open("a", encoding="utf-8") as f:
        f.write(f"\n===== {dt.datetime.now():%d/%m %H:%M} {'atualizar' if atualizar else 'entrar'} =====\n")
        f.flush()
        subprocess.Popen(args, cwd=str(PONTE), stdout=f, stderr=subprocess.STDOUT, **extra)
    if atualizar:
        return {"ok": True, "msg": "Atualizando os cookies do perfil salvo — confira em alguns segundos."}
    return {"ok": True, "msg": "Abri uma janela do navegador: ENTRE NA SUA CONTA DO GOOGLE. "
                               "Eu fecho sozinho quando detectar o login e salvo o cookies.txt."}


def acao(nome, d):
    c = d.get("c")
    if c not in CANAIS and nome not in ("canal_segredo", "canal_cookies"):
        raise ValueError("canal?")
    if nome == "canal_cookies":
        return pega_cookies(bool(d.get("atualizar")))
    if nome == "canal_destravar":
        return destrava(c)
    if nome == "canal_sair_da_fila":
        with TRAVA:
            antes = len(ESPERA)
            ESPERA[:] = [x for x in ESPERA if x["c"] != c]
        return {"ok": True, "msg": f"{CANAIS[c]['nome']} saiu da fila de espera" if len(ESPERA) < antes else "não estava na fila"}
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


def _por_que_parou(c, n=25):
    """a última linha do registro que explica a parada (o canal.py escreve "NÃO RODEI: ...")"""
    linhas = [l.strip() for l in _tail(pasta(c) / "canal.log", n) if l.strip()]
    for l in reversed(linhas):
        if "NÃO RODEI" in l or "SEM VOZ" in l or "Error" in l or "error" in l or "Traceback" in l:
            return l[:300]
    return linhas[-1][:300] if linhas else "sem nada no registro"


def na_espera(c):
    """este canal já está na fila de espera? (devolve a posição, 1 = o próximo)"""
    for i, x in enumerate(ESPERA):
        if x["c"] == c:
            return i + 1
    return 0


def _enfileira(c, forcar, teste, quem_roda):
    """põe na fila em vez de recusar o clique (o laço começa assim que o pesado atual terminar)"""
    with TRAVA:
        ja = na_espera(c)
        if ja:
            return {"ok": True, "fila": ja, "msg": f"{CANAIS[c]['nome']} já estava na fila de espera ({ja}º)"}
        ESPERA.append({"c": c, "forcar": forcar, "teste": teste, "pedido": dt.datetime.now().isoformat(timespec="minutes")})
        pos = len(ESPERA)
    LOG(f"canal {CANAIS[c]['nome']}: na FILA DE ESPERA ({pos}º) — {quem_roda} está trabalhando agora")
    return {"ok": True, "fila": pos, "msg": f"{quem_roda} está trabalhando agora. {CANAIS[c]['nome']} entrou na fila "
                                            f"de espera ({pos}º) e começa sozinho quando terminar."}


def roda_agora(c, forcar=True, teste=False, da_fila=False):
    """teste = monta com voz de computador (sem a sua voz clonada), não posta — para ver a edição

    Trabalho pesado é UM por vez. Pedido com outro rodando NÃO é recusado: entra na `ESPERA` e o laço o
    começa assim que o atual terminar (01/11, pedido dele).
    """
    if not da_fila:
        if ocupado():
            return _enfileira(c, forcar, teste, CANAIS[PESADO["id"]]["nome"] if PESADO["id"] else "outro canal")
        try:
            if EDICAO_OCUPADA():
                return _enfileira(c, forcar, teste, "uma edição")
        except Exception:  # noqa: BLE001
            pass
    with TRAVA:
        if ocupado():   # alguém pegou a vaga entre as duas conferências
            return _enfileira(c, forcar, teste, CANAIS[PESADO["id"]]["nome"] if PESADO["id"] else "outro canal")
        preso = travado(c)
        if preso and "sem pid" in preso:
            # TRAVA QUEBRADA (sem pid anotado) = beco sem saída. Antes o botão recusava e o canal ficava morto
            # até ele caçar o processo no Gerenciador de Tarefas. Agora eu destravo SOZINHO e sigo: é "clicar e
            # fazer", que é o que ele pediu. Só faço isso quando NÃO há pid — com pid vivo eu respeito a rodada.
            LOG(f"canal {CANAIS[c]['nome']}: a trava estava quebrada (sem pid); destravando sozinho")
            r = destrava(c)
            if not r.get("ok"):
                raise ValueError(r.get("erro") or "não consegui destravar")
            preso = travado(c)
        if preso:   # outra rodada está com a trava: o filho morreria em 1 s e o botão pareceria não fazer nada
            raise ValueError(f"a rodada {preso} está trabalhando agora. Espere ela acabar ou use Encerrar a rodada.")
        de_noticias = CANAIS[c]["script"].name == "canal.py"   # noticias e GTA 6 usam o mesmo script
        args = ["--forcar"] if (forcar and de_noticias) else []
        if teste:
            args = ["--forcar", "--nao-postar"] if de_noticias else args
        PESADO.update(id=c, p=_roda(c, args, env_extra={"DETTO_VOZ_FALSA": "1"} if teste else None), o_que="montando (teste)" if teste else "montando")
    # A RODADA MORREU NA LARGADA? (sem máscara, sem voz, trava, erro de código) — antes isso era invisível: o
    # botão dizia "começou", nada acontecia, e o `ultimo` já tinha sido gravado, então o AUTOMÁTICO só tentaria
    # de novo daqui a 2 h. É por isso que o canal passava o dia sem criar nada e sem avisar.
    time.sleep(2.5)
    pr = PESADO["p"]
    if pr and pr.poll() is not None:
        motivo = _por_que_parou(c)
        PESADO.update(id=None, p=None, o_que="")
        # tenta de novo em ~10 min, não daqui a 2 h
        tenta = dt.datetime.now() - dt.timedelta(minutes=max(0, CANAIS[c]["intervalo_min"] - 10))
        grava_estado(c, ultimo=tenta.isoformat(timespec="minutes"), erro=motivo,
                     erro_em=dt.datetime.now().isoformat(timespec="minutes"))
        LOG(f"canal {CANAIS[c]['nome']}: NÃO RODOU — {motivo}")
        raise ValueError(f"a rodada parou na largada: {motivo}")
    grava_estado(c, ultimo=dt.datetime.now().isoformat(timespec="minutes"), erro="")
    with TRAVA:   # começou de verdade: sai da fila de espera
        ESPERA[:] = [x for x in ESPERA if x["c"] != c]
    LOG(f"canal {CANAIS[c]['nome']}: rodada começou")
    return {"ok": True, "msg": f"{CANAIS[c]['nome']}: a rodada começou — acompanhe no registro"}


def laco(log=print, edicao_ocupada=lambda: False):
    """roda os canais ligados na hora certa e posta os aprovados"""
    global LOG, EDICAO_OCUPADA
    LOG = log
    EDICAO_OCUPADA = edicao_ocupada   # o roda_agora também precisa saber, para enfileirar em vez de recusar
    # aprovados que ficaram na fila quando o painel fechou
    for c in CANAIS:
        try:
            for pr, d in comum.prontos(pasta(c)):
                if d.get("status") in ("na_fila", "postando"):
                    POSTANDO["fila"].append((c, str(pr)))
        except Exception:
            pass
    ultimo_cookie = [0.0]
    while True:
        try:
            # 0) COOKIE DO YOUTUBE: reexporta do perfil salvo 1x por dia, sem janela e sem pedir nada. É o que
            # faz o download continuar funcionando sem ele lembrar de nada (05/nov).
            try:
                ck = cookies_info()
                if ck.get("perfil") and (time.time() - ultimo_cookie[0]) > 20 * 3600 and \
                        (not ck.get("existe") or not ck.get("logado") or ck.get("dias", 0) > 1):
                    ultimo_cookie[0] = time.time()
                    log("cookies do YouTube: reexportando do perfil salvo")
                    pega_cookies(atualizar=True)
            except Exception as e:   # noqa: BLE001
                log(f"cookies do YouTube: {str(e)[:90]}")
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
            # 3) a FILA DE ESPERA vem primeiro: o que VOCÊ pediu na mão passa na frente do automático
            if not ocupado() and not edicao_ocupada() and ESPERA:
                with TRAVA:
                    pedido = ESPERA.pop(0) if ESPERA else None
                if pedido:
                    cc = pedido["c"]
                    log(f"canal {CANAIS[cc]['nome']}: a vez dele chegou (estava na fila de espera)")
                    try:
                        roda_agora(cc, forcar=pedido.get("forcar", True), teste=pedido.get("teste", False), da_fila=True)
                    except Exception as e:  # noqa: BLE001
                        # NÃO PERDE O PEDIDO (01/nov): com a trava presa isto falhava, o pedido sumia da fila e o
                        # card voltava a dizer "Rodar agora" como se nada tivesse acontecido. Volta para o fim.
                        log(f"canal {CANAIS[cc]['nome']}: não consegui começar o que estava na fila ({str(e)[:200]})")
                        with TRAVA:
                            if not na_espera(cc):
                                ESPERA.append(pedido)
                    time.sleep(1)
                    continue
            # 4) hora de rodar algum canal ligado?
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
                        try:
                            roda_agora(c, forcar=False)
                        except Exception as e:  # noqa: BLE001
                            # erro de UM canal não é "erro no laço": o laço tem que seguir para os outros
                            log(f"canal {CANAIS[c]['nome']}: não começou ({str(e)[:200]})")
                        break
        except Exception as e:
            log(f"canais: erro no laço ({e})")
        time.sleep(20)
