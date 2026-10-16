# -*- coding: utf-8 -*-
"""PAINEL DETTO — cuida da postagem automática pelo navegador (no PC ou no celular, na mesma rede Wi-Fi).

    python tools\\painel\\painel.py              → abre http://localhost:8730 (e mostra o endereço para o celular)
    python tools\\painel\\painel.py --instalar   → liga o painel sozinho quando o Windows inicia + atalho na Área de Trabalho
    python tools\\painel\\painel.py --desinstalar

Enquanto o painel está aberto ele mesmo posta (confere a fila a cada 5 min). Não precisa de nada instalado além do Python.
"""
import argparse
import datetime as dt
import hmac
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import webbrowser
from http import server as hserver
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
sys.path.insert(0, str(TOOLS / "postar"))
import postar as P  # noqa: E402

sys.path.insert(0, str(AQUI))
import edicao as EDI  # noqa: E402

VIDEO_EXT = P.VIDEO_EXT
REELS = None  # pasta dos reels (E:\DETTO\reels)
BASE = None  # pasta da postagem (E:\DETTO\postar)
CACHE = {"pendentes": {}, "limite": {}, "quando": 0, "erro": {}}
TRABALHO = {"postando": "", "reels": None, "login": None}
TRAVA_CFG = threading.Lock()


def reels_pasta():
    if os.name == "nt" and Path("E:/").exists():
        return Path("E:/DETTO/reels")
    return Path.home() / "DETTO" / "reels"


def py_filho():
    """python para os processos filhos (login, reels): no Windows, python.exe sem janela (o pythonw abriria
    uma janela preta a cada ffmpeg)"""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        exe = exe.with_name("python.exe")
    return str(exe), ({"creationflags": 0x08000000} if os.name == "nt" else {})


def cfg():
    return P.prepara(BASE)


def grava_cfg(muda):
    """altera o config.json da postagem sem perder o resto"""
    with TRAVA_CFG:
        f = BASE / "config.json"
        d = P.le_json(f, {})
        muda(d)
        P.grava_json(f, d)


def nome_seguro(n):
    n = Path(str(n)).name
    n = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", n).strip(" .")
    return n or "video.mp4"


def conta_de(k):
    for c in cfg()["contas"]:
        if P.chave(c) == k:
            return c
    raise ValueError(f"conta desconhecida: {k}")


def tam_txt(b):
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024 or u == "GB":
            return f"{b:.0f} {u}" if u in ("B", "KB") else f"{b:.1f} {u}"
        b /= 1024


def ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


# ------------------------------------------------------------------ o que o painel mostra
def atualiza_cache(forca=False):
    """rascunhos do TikTok e limite do Instagram (perguntam às APIs: no máximo a cada 3 min)"""
    if not forca and time.time() - CACHE["quando"] < 180:
        return
    CACHE["quando"] = time.time()
    c_ = cfg()
    try:
        atualiza_views(c_)
    except Exception as e:
        P.log(f"views dos reels teste: {e}")
    for c in c_["contas"]:
        k = P.chave(c)
        if not (BASE / "tokens" / f"{c['plataforma']}_{c['conta']}.json").exists():
            continue
        try:
            if c["plataforma"] == "instagram":
                CACHE["limite"][k] = P.ig_limite(c_, BASE, c["conta"])
            elif c_["tiktok"].get("modo") not in ("direto", "studio"):
                CACHE["pendentes"][k] = P.tt_pendentes(c_, BASE, c["conta"])[1]
            CACHE["erro"].pop(k, None)
        except Exception as e:
            CACHE["erro"][k] = str(e)[:200]


def atualiza_views(c_, forca=False):
    """visualizações dos reels TESTE do Instagram (a cada 30 min), para avisar quando bater a meta"""
    for c in c_["contas"]:
        if c["plataforma"] != "instagram" or not (BASE / "tokens" / f"instagram_{c['conta']}.json").exists():
            continue
        k = P.chave(c)
        feitos = 0
        for f in sorted((BASE / "postados" / k).glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:60]:
            d = P.le_json(f, {})
            if not d.get("teste") or d.get("situacao") in ("promovido", "ignorado") or not d.get("id"):
                continue
            try:
                quando = dt.datetime.fromisoformat(d.get("quando", "2000-01-01"))
            except ValueError:
                continue
            if (dt.datetime.now() - quando).days > 30:
                continue
            if not forca and time.time() - d.get("views_quando", 0) < 1800:
                continue
            v = P.ig_views(c_, BASE, c["conta"], d["id"])
            if v is not None:
                d.update(views=v, views_quando=time.time())
                if v >= int(c.get("meta_views") or 0) > 0 and not d.get("bateu"):
                    d["bateu"] = dt.datetime.now().isoformat(timespec="minutes")
                    P.log(f"{k}: reel teste {d.get('video', f.stem)} bateu {v} views — mande para os seguidores no app")
                P.grava_json(f, d)
            feitos += 1
            if feitos >= 25:
                break


def testes_de(c):
    """reels teste postados (para a lista com views e meta)"""
    k = P.chave(c)
    out = []
    for f in sorted((BASE / "postados" / k).glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:40]:
        d = P.le_json(f, {})
        if not d.get("teste") or d.get("situacao") == "ignorado":
            continue
        out.append({"arq": f.name, "nome": d.get("video") or f.stem, "quando": (d.get("quando") or "")[:16].replace("T", " "),
                    "link": d.get("link", ""), "views": d.get("views"), "situacao": d.get("situacao", ""),
                    "bateu": bool(d.get("views") is not None and int(c.get("meta_views") or 0) > 0 and d["views"] >= int(c["meta_views"])),
                    "graduar": d.get("graduar", "manual")})
    return out


def item(p):
    st = p.stat()
    leg = P.legenda_de(p)
    return {"nome": p.name, "tam": tam_txt(st.st_size), "legenda": leg, "quando": dt.datetime.fromtimestamp(st.st_mtime).strftime("%d/%m %H:%M")}


def estado_painel():
    c_ = cfg()
    est = P.le_json(BASE / "estado.json", {})
    contas = []
    for c in c_["contas"]:
        k = P.chave(c)
        fila = P.fila_de(BASE, k)
        pasta_ok = BASE / "postados" / k
        feitos = sorted((p for p in pasta_ok.glob("*.json") if not p.name.startswith("_")), key=lambda p: p.stat().st_mtime, reverse=True)
        ult = []
        for f in feitos[:8]:
            d = P.le_json(f, {})
            q_ = d.get("agendado_para") or d.get("quando") or ""
            ult.append({"nome": d.get("video") or f.stem, "quando": q_[:16].replace("T", " "), "link": d.get("link", ""),
                        "modo": d.get("modo", "")})
        falhas = [item(p) for p in sorted((BASE / "falhas" / k).glob("*")) if p.suffix.lower() in VIDEO_EXT]
        pend = CACHE["pendentes"].get(k)
        pend_l = []
        for r in pend or []:
            txt = (pasta_ok / r.get("video", "")).with_suffix(".txt")
            pend_l.append({"nome": r.get("video", ""), "legenda": txt.read_text(encoding="utf-8").split("\n---")[0].strip() if txt.exists() else "",
                           "quando": dt.datetime.fromtimestamp(r.get("quando", 0)).strftime("%d/%m %H:%M")})
        prox = P.proximo(c, est, k)
        eh_studio = P.studio(c_, c)
        plano = []
        if eh_studio:
            slots = P.planeja(c, est, k, len(fila), P.agendados_por_dia(BASE, k))
            for i_, v_ in enumerate(fila):
                plano.append(slots[i_].strftime("%Y-%m-%dT%H:%M") if i_ < len(slots) else "")
            if slots:
                prox = slots[0]
        lim = CACHE["limite"].get(k)
        contas.append({
            "k": k, "plataforma": c["plataforma"], "conta": c["conta"], "ativo": c.get("ativo", True) is not False,
            "teste": bool(c.get("teste")), "graduar": c.get("graduar", "manual"), "meta_views": int(c.get("meta_views") or 0),
            "testes": testes_de(c) if c["plataforma"] == "instagram" else [],
            "intervalo_min": c.get("intervalo_min", 80), "horas": c.get("horas", "08-23"), "max_dia": c.get("max_dia", 0),
            "login": (BASE / "tokens" / f"{c['plataforma']}_{c['conta']}.json").exists(),
            "fila": [item(p) for p in fila], "postados": len(feitos), "hoje": P.postados_hoje(est, k),
            "ultimo": (est.get(k, {}).get("ultimo") or "")[:16].replace("T", " "),
            "proximo": prox.strftime("%d/%m %H:%M"), "proximo_ja": prox <= dt.datetime.now(),
            "falhas": falhas, "ultimos": ult, "pendentes": pend_l if pend is not None else None,
            "studio": eh_studio, "plano": plano,
            "preparados": len(P.le_json(BASE / "tiktok_studio" / f"_preparados_{c['conta']}.json", [])) if eh_studio else 0,
            "limite": list(lim) if lim else None, "erro": CACHE["erro"].get(k, ""),
            "tentativas": est.get(k, {}).get("falhas", {}),
        })
    hoje = dt.date.today().isoformat()
    prontos = list((REELS / "prontos" / hoje).glob("*.mp4")) if (REELS / "prontos" / hoje).exists() else []
    inicios = sorted(p.stem for p in (REELS / "inicios").glob("*") if p.suffix.lower() in VIDEO_EXT) if (REELS / "inicios").exists() else []
    links = []
    if (REELS / "links.txt").exists():
        links = [l.strip() for l in (REELS / "links.txt").read_text(encoding="utf-8").splitlines() if l.strip().startswith("http")]
    rcfg = P.le_json(REELS / "config.json", {})
    log = []
    if (BASE / "postar.log").exists():
        with open(BASE / "postar.log", encoding="utf-8", errors="replace") as f:
            log = f.readlines()[-80:]
    rlog = []
    if (REELS / "painel_reels.log").exists():
        with open(REELS / "painel_reels.log", encoding="utf-8", errors="replace") as f:
            rlog = f.readlines()[-30:]
    livre = shutil.disk_usage(BASE).free
    t = TRABALHO["reels"]
    return {
        "pausado": bool(c_.get("pausado")), "contas": contas, "postando": TRABALHO["postando"],
        "tiktok": {"modo": c_["tiktok"].get("modo", "studio"), "ia": bool(c_["tiktok"].get("ia")),
                   "chaves": bool(c_["tiktok"].get("client_key") and c_["tiktok"].get("client_secret"))},
        "instagram": {"chaves": bool(c_["instagram"].get("app_id") and c_["instagram"].get("app_secret"))},
        "reels": {"prontos_hoje": len(prontos), "inicios": inicios, "links": links[-10:], "n_links": len(links),
                  "rodando": bool(t and t.poll() is None), "postar": rcfg.get("postar", ["instagram:detto.galo", "tiktok:detto.galo"]),
                  "log": [l.rstrip() for l in rlog]},
        "log": [l.rstrip() for l in log], "disco": tam_txt(livre), "disco_pouco": livre < 15 * 1024 ** 3,
        "edicao": EDI.lista(), "pasta_edicao": str(EDI.ED), "editando": EDI.PROC["id"] or "",
        "pin": bool((c_.get("painel") or {}).get("pin")), "endereco": f"http://{ip_local()}:{PORTA}",
        "pastas": {"postar": str(BASE), "reels": str(REELS), "edicao": str(EDI.ED)},
        "agora": dt.datetime.now().strftime("%d/%m %H:%M"),
    }


# ------------------------------------------------------------------ ações
def posta_agora(k, nome):
    if TRABALHO["postando"]:
        raise ValueError(f"já estou postando: {TRABALHO['postando']}")
    c_ = cfg()
    c = conta_de(k)
    video = BASE / "entrada" / k / nome_seguro(nome)
    if not video.exists():
        raise ValueError("vídeo não está mais na fila")

    def vai():
        TRABALHO["postando"] = f"{nome} → {k}"
        try:
            with P.trava(BASE) as t:
                if not t.ok:
                    P.log(f"{k}: já tem uma postagem em andamento; tente de novo em alguns minutos")
                    return
                est = P.le_json(BASE / "estado.json", {})
                P.posta_da_fila(c_, BASE, c, video, est)
        except Exception as e:
            P.log(f"{k}: erro ao postar agora: {e}")
        finally:
            TRABALHO["postando"] = ""
            CACHE["quando"] = 0

    threading.Thread(target=vai, daemon=True).start()


def rodada_ja():
    def vai():
        TRABALHO["postando"] = "conferindo a fila"
        try:
            P.rodada(cfg(), BASE)
        except Exception as e:
            P.log(f"erro na rodada: {e}")
        finally:
            TRABALHO["postando"] = ""
    threading.Thread(target=vai, daemon=True).start()


def acao(nome, d):
    if nome == "pausar":
        grava_cfg(lambda c: c.__setitem__("pausado", bool(d.get("pausado"))))
        P.log("postagem automática " + ("PAUSADA pelo painel" if d.get("pausado") else "LIGADA pelo painel"))
    elif nome == "conta":
        k = d["k"]

        def muda(c):
            for x in c.setdefault("contas", json.loads(json.dumps(P.CONFIG_PADRAO["contas"]))):
                if P.chave(x) == k:
                    if "ativo" in d:
                        x["ativo"] = bool(d["ativo"])
                    if "intervalo_min" in d:
                        x["intervalo_min"] = max(5, int(d["intervalo_min"]))
                    if "horas" in d:
                        h0, h1 = (int(v) for v in str(d["horas"]).split("-"))
                        if not (0 <= h0 <= 23 and 0 <= h1 <= 23 and h0 <= h1):
                            raise ValueError("horário inválido")
                        x["horas"] = f"{h0:02d}-{h1:02d}"
                    if "max_dia" in d:
                        x["max_dia"] = max(0, int(d["max_dia"]))
                    if "teste" in d:
                        x["teste"] = bool(d["teste"])
                    if d.get("graduar") in ("manual", "automatico"):
                        x["graduar"] = d["graduar"]
                    if "meta_views" in d:
                        x["meta_views"] = max(0, int(d["meta_views"]))
        grava_cfg(muda)
    elif nome == "nova_conta":
        plat, conta = d["plataforma"], d["conta"].strip().lstrip("@").lower()
        if plat not in ("instagram", "tiktok") or not re.fullmatch(r"[\w.]{2,40}", conta):
            raise ValueError("conta inválida")

        def muda(c):
            lista = c.setdefault("contas", json.loads(json.dumps(P.CONFIG_PADRAO["contas"])))
            if any(P.chave(x) == f"{plat}_{conta}" for x in lista):
                raise ValueError("essa conta já existe")
            lista.append({"plataforma": plat, "conta": conta, "intervalo_min": 120, "horas": "08-23", "max_dia": 0, "ativo": True})
        grava_cfg(muda)
        cfg()
    elif nome == "tirar_conta":
        k = d["k"]
        if P.fila_de(BASE, k):
            raise ValueError("a fila dessa conta não está vazia")
        grava_cfg(lambda c: c.__setitem__("contas", [x for x in c.get("contas", []) if P.chave(x) != k]))
    elif nome == "ordem":
        k = d["k"]
        P.grava_json(BASE / "entrada" / k / "_ordem.json", [nome_seguro(n) for n in d["nomes"]])
    elif nome == "legenda":
        v = BASE / d.get("onde", "entrada") / d["k"] / nome_seguro(d["nome"])
        txt = v.with_suffix(".txt")
        resto = ""
        if txt.exists():
            partes = txt.read_text(encoding="utf-8").split("\n---", 1)
            resto = "\n---" + partes[1] if len(partes) > 1 else ""
        txt.write_text(d.get("legenda", "").strip() + resto, encoding="utf-8")
    elif nome == "apagar":
        v = BASE / d.get("onde", "entrada") / d["k"] / nome_seguro(d["nome"])
        for f in (v, v.with_suffix(".txt")):
            f.unlink(missing_ok=True)
    elif nome == "tentar":
        k, n = d["k"], nome_seguro(d["nome"])
        for f in (BASE / "falhas" / k / n, (BASE / "falhas" / k / n).with_suffix(".txt")):
            if f.exists():
                shutil.move(str(f), str(BASE / "entrada" / k / f.name))
        est = P.le_json(BASE / "estado.json", {})
        est.get(k, {}).get("falhas", {}).pop(n, None)
        P.grava_json(BASE / "estado.json", est)
    elif nome == "copiar":
        # manda um vídeo da fila de uma conta também para outras
        k, n = d["k"], nome_seguro(d["nome"])
        v = BASE / "entrada" / k / n
        P.enfileira(BASE, v, [x.replace("_", ":", 1) for x in d["para"] if x != k], v.with_suffix(".txt") if v.with_suffix(".txt").exists() else None)
    elif nome == "agora":
        posta_agora(d["k"], d["nome"])
    elif nome == "rodada":
        rodada_ja()
    elif nome == "atualizar":
        CACHE["quando"] = 0
        threading.Thread(target=atualiza_cache, args=(True,), daemon=True).start()
    elif nome == "global":
        def muda(c):
            for chave_, sub, campo in (("ig_app_id", "instagram", "app_id"), ("ig_app_secret", "instagram", "app_secret"),
                                       ("ig_config_id", "instagram", "config_id"),
                                       ("tt_client_key", "tiktok", "client_key"), ("tt_client_secret", "tiktok", "client_secret")):
                if str(d.get(chave_) or "").strip():
                    c.setdefault(sub, {})[campo] = str(d[chave_]).strip()
            if d.get("tt_modo") in ("rascunho", "direto"):
                c.setdefault("tiktok", {})["modo"] = d["tt_modo"]
            if "tt_ia" in d:
                c.setdefault("tiktok", {})["ia"] = bool(d["tt_ia"])
            if "pin" in d:
                pin = str(d["pin"]).strip()
                if pin and not re.fullmatch(r"\d{4,8}", pin):
                    raise ValueError("o PIN precisa ter de 4 a 8 números")
                c.setdefault("painel", {})["pin"] = pin
        grava_cfg(muda)
    elif nome == "login":
        plat, conta = d["plataforma"], d["conta"]
        exe, extra = py_filho()
        cmd = [exe, "-u", str(TOOLS / "postar" / "postar.py"), "--pasta", str(BASE), "--login", plat, "--conta", conta]
        if d.get("token"):
            cmd += ["--token", d["token"]]
        logf = open(BASE / "login.log", "w", encoding="utf-8")
        TRABALHO["login"] = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, text=True,
                                             env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **extra)
        P.log(f"login {plat} @{conta}: abri o navegador NO PC — entre na conta e autorize")
    elif nome == "login_resultado":
        f = BASE / "login.log"
        p = TRABALHO["login"]
        return {"rodando": bool(p and p.poll() is None), "texto": f.read_text(encoding="utf-8", errors="replace")[-1500:] if f.exists() else ""}
    elif nome == "reels_gerar":
        t = TRABALHO["reels"]
        if t and t.poll() is None:
            raise ValueError("os reels já estão sendo feitos")
        n = max(1, min(20, int(d.get("quantos", 5))))
        logf = open(REELS / "painel_reels.log", "w", encoding="utf-8")
        exe, extra = py_filho()
        cmd = [exe, "-u", str(TOOLS / "reels" / "reels.py"), "--pasta", str(REELS), "--quantos", str(n)]
        TRABALHO["reels"] = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, text=True, cwd=str(TOOLS.parent),
                                             env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **extra)
    elif nome == "reels_parar":
        t = TRABALHO["reels"]
        if t and t.poll() is None:
            t.terminate()
    elif nome == "reels_link":
        url = str(d.get("url", "")).strip()
        if not re.match(r"https?://\S+$", url):
            raise ValueError("cole um link (https://...)")
        REELS.mkdir(parents=True, exist_ok=True)
        with open(REELS / "links.txt", "a", encoding="utf-8") as f:
            f.write(url + "\n")
    elif nome == "reels_postar":
        f = REELS / "config.json"
        rc = P.le_json(f, {})
        rc["postar"] = [x for x in d.get("para", []) if re.fullmatch(r"(instagram|tiktok):[\w.]+", x)]
        P.grava_json(f, rc)
    elif nome == "studio_agendei":
        # você agendou no TikTok Studio: os vídeos saem da fila com o horário planejado
        c = conta_de(d["k"])
        k = d["k"]
        fila = P.fila_de(BASE, k)
        slots = P.planeja(c, P.le_json(BASE / "estado.json", {}), k, len(fila), P.agendados_por_dia(BASE, k))
        pedidos = set(nome_seguro(n) for n in d.get("nomes", []))
        if d.get("da_pasta"):
            pedidos |= set(P.le_json(BASE / "tiktok_studio" / f"_preparados_{c['conta']}.json", []))
        feitos = 0
        for v, t in zip(fila, slots):
            if v.name in pedidos:
                P.marca_agendado(BASE, c, v, t)
                feitos += 1
        if d.get("da_pasta") or not P.fila_de(BASE, k):
            limpa_studio(c)
            (BASE / "tiktok_studio" / f"_preparados_{c['conta']}.json").unlink(missing_ok=True)
        return {"ok": True, "feitos": feitos}
    elif nome == "studio_preparar":
        return prepara_studio(conta_de(d["k"]), int(d.get("quantos") or 0))
    elif nome == "teste_marca":
        # reel teste: "promovido" = você já mandou para os seguidores; "ignorado" = some da lista
        f = BASE / "postados" / nome_seguro(d["k"]) / nome_seguro(d["arq"])
        j = P.le_json(f, None)
        if j is None:
            raise ValueError("não achei esse reel")
        j["situacao"] = d.get("como") if d.get("como") in ("promovido", "ignorado", "") else ""
        P.grava_json(f, j)
    elif nome == "views_agora":
        threading.Thread(target=lambda: atualiza_views(cfg(), True), daemon=True).start()
    elif nome == "reels_um":
        # um reel já, deste link (modo TROCA: igual ao original, só a pessoa vira você)
        t = TRABALHO["reels"]
        if t and t.poll() is None:
            raise ValueError("os reels já estão sendo feitos; espere terminar")
        url = str(d.get("url", "")).strip()
        if not re.match(r"https?://\S+$", url):
            raise ValueError("cole um link (https://...)")
        exe, extra = py_filho()
        cmd = [exe, "-u", str(TOOLS / "reels" / "reels.py"), "--pasta", str(REELS), "--clip", url, "--modo", d.get("modo") if d.get("modo") in ("troca", "novo") else "troca"]
        if d.get("inicio"):
            cmd += ["--inicio", str(d["inicio"])]
        logf = open(REELS / "painel_reels.log", "w", encoding="utf-8")
        TRABALHO["reels"] = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, text=True, cwd=str(TOOLS.parent),
                                             env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **extra)
    elif nome.startswith("ed_"):
        fn = {"ed_novo": EDI.novo, "ed_caminho": EDI.de_caminho, "ed_iniciar": EDI.iniciar, "ed_roteiro": EDI.roteiro,
              "ed_refazer": EDI.refazer, "ed_cancelar": EDI.cancelar, "ed_apagar": EDI.apagar, "ed_postar": ed_postar}.get(nome)
        if not fn:
            raise ValueError(f"ação desconhecida: {nome}")
        return fn(d)
    elif nome == "abrir_pasta":
        alvo = {"postar": BASE, "reels": REELS, "edicao": EDI.ED}.get(d.get("qual"), BASE)
        if os.name == "nt":
            os.startfile(str(alvo))  # noqa: S606 (só no PC)
    else:
        raise ValueError(f"ação desconhecida: {nome}")
    return {"ok": True}


def pasta_studio(c):
    return BASE / "tiktok_studio" / c["conta"]


def limpa_studio(c):
    p = pasta_studio(c)
    if p.exists():
        for f in p.iterdir():
            try:
                f.unlink()
            except OSError:
                pass


def prepara_studio(c, quantos=0):
    """pasta pronta para o TikTok Studio: os vídeos com o horário no nome (ordem de agendar) + LEGENDAS.txt"""
    k = P.chave(c)
    fila = P.fila_de(BASE, k)
    slots = P.planeja(c, P.le_json(BASE / "estado.json", {}), k, len(fila), P.agendados_por_dia(BASE, k))
    if quantos:
        slots = slots[:quantos]
    if not slots:
        raise ValueError("nada para agendar (fila vazia)")
    p = pasta_studio(c)
    p.mkdir(parents=True, exist_ok=True)
    limpa_studio(c)
    dias = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
    linhas = [f"TIKTOK STUDIO — @{c['conta']}  (tiktok.com/tiktokstudio/upload)",
              "Para cada vídeo: Enviar → escolha o arquivo → cole a legenda → Agendar → data e hora abaixo.",
              "Depois, no painel: \"Agendei os N da pasta\" (ou o ✔ de cada vídeo).", ""]
    preparados = []
    for i, (v, t) in enumerate(zip(fila, slots), 1):
        curto = nome_seguro(re.sub(r"^\d{4}-\d{2}-\d{2}( \d{4,6})? ?", "", v.stem))[:60]
        nome = f"{i:02d} - {t:%d-%m %Hh%M} - {curto}{v.suffix.lower()}"
        preparados.append(v.name)
        try:
            os.link(v, p / nome)
        except OSError:
            shutil.copyfile(v, p / nome)
        linhas += [f"===== {i:02d}  {dias[t.weekday()]} {t:%d/%m}  às {t:%H:%M} =====", f"arquivo: {nome}", P.legenda_de(v) or "(sem legenda)", ""]
    (p / f"LEGENDAS - {c['conta']}.txt").write_text("\n".join(linhas), encoding="utf-8")
    P.grava_json(BASE / "tiktok_studio" / f"_preparados_{c['conta']}.json", preparados)
    if os.name == "nt":
        try:
            os.startfile(str(p))  # noqa: S606
        except OSError:
            pass
    P.log(f"{k}: pasta do TikTok Studio pronta com {len(slots)} vídeos: {p}")
    return {"ok": True, "pasta": str(p), "n": len(slots)}


def ed_postar(d, pasta=None, rels=None):
    """manda um vídeo pronto da edição para a fila das contas"""
    p = pasta or EDI.pasta_de(d.get("id", ""))
    para = [x for x in d.get("para", []) if re.fullmatch(r"(instagram|tiktok):[\w.]+", x)]
    if not para:
        raise ValueError("escolha as contas")
    titulo = EDI.info(p).get("titulo", "video")
    for rel in rels or [d.get("rel", "")]:
        f = EDI.arquivo(p.name, rel)
        leg = None
        if str(d.get("legenda") or "").strip():
            leg = BASE / "_envios" / f"leg_{time.time_ns()}.txt"
            leg.parent.mkdir(exist_ok=True)
            leg.write_text(d["legenda"].strip(), encoding="utf-8")
        P.enfileira(BASE, f, para, leg, nome=f"{dt.datetime.now():%Y-%m-%d %H%M%S} {titulo} - {f.stem}.mp4")
        if leg:
            leg.unlink(missing_ok=True)
        P.log(f"edição: {titulo} / {f.name} → fila de {', '.join(para)}")
    return {"ok": True}


def edicao_pronta(p):
    """terminou: se você marcou, o vertical completo já vai para a fila"""
    para = EDI.info(p).get("opcoes", {}).get("postar") or []
    if para and EDI.info(p).get("tipo", "roteiro") != "roteiro":
        vids = [v["rel"] for v in EDI.saidas(p)["videos"] if "_parte" not in v["nome"]]
        if vids:
            ed_postar({"para": para}, pasta=p, rels=vids[:1])
        return
    job = EDI.job_de(p)
    if para and job and (job / "vertical_completo.mp4").exists():
        rel = str((job / "vertical_completo.mp4").relative_to(p)).replace("\\", "/")
        ed_postar({"para": para}, pasta=p, rels=[rel])


def recebe_envio(h, q):
    """recebe um vídeo do navegador (corpo cru, em pedaços: não enche a memória) e já põe nas pastas certas"""
    nome = nome_seguro(q.get("nome", "video.mp4"))
    destinos = [x for x in q.get("destinos", "").split(",") if x]
    legenda = q.get("legenda", "")
    tam = int(h.headers.get("Content-Length") or 0)
    if not destinos:
        raise ValueError("escolha pelo menos um destino")
    if Path(nome).suffix.lower() not in VIDEO_EXT:
        raise ValueError("só vídeo (.mp4, .mov ...)")
    tmp_dir = BASE / "_envios"
    tmp_dir.mkdir(exist_ok=True)
    tmp = tmp_dir / f"{time.time_ns()}_{nome}"
    with open(tmp, "wb") as f:
        falta = tam
        while falta > 0:
            b = h.rfile.read(min(4 * 1024 * 1024, falta))
            if not b:
                break
            f.write(b)
            falta -= len(b)
    if falta > 0:
        tmp.unlink(missing_ok=True)
        raise ValueError("envio interrompido")
    feitos = []
    contas = []
    for dst in destinos:
        if dst == "reels:inicios":
            pasta = REELS / "inicios"
            pasta.mkdir(parents=True, exist_ok=True)
            apelido = nome_seguro(q.get("apelido") or Path(nome).stem)
            alvo = pasta / f"{Path(apelido).stem}{Path(nome).suffix.lower()}"
            i = 2
            while alvo.exists():
                alvo = pasta / f"{Path(apelido).stem} {i}{Path(nome).suffix.lower()}"
                i += 1
            try:
                os.link(tmp, alvo)
            except OSError:
                shutil.copyfile(tmp, alvo)
            feitos.append("começo de reel: " + alvo.stem)
        else:
            contas.append(dst)
    if contas:
        carimbo = dt.datetime.now().strftime("%Y-%m-%d %H%M%S")
        leg_f = None
        if legenda.strip():
            leg_f = tmp.with_suffix(".txt")
            leg_f.write_text(legenda.strip(), encoding="utf-8")
        P.enfileira(BASE, tmp, contas, leg_f, nome=f"{carimbo} {Path(nome).stem}{Path(nome).suffix.lower()}")
        if leg_f:
            leg_f.unlink(missing_ok=True)
        feitos += contas
    tmp.unlink(missing_ok=True)
    P.log(f"painel: recebi {nome} ({tam_txt(tam)}) → {', '.join(feitos)}")
    return {"ok": True, "foi_para": feitos}


# ------------------------------------------------------------------ servidor
PORTA = 8730


class Painel(hserver.BaseHTTPRequestHandler):
    server_version = "DettoPainel/1"

    def log_message(self, *a):
        pass

    def _caminho(self):
        # o http.server lê a linha do pedido como latin-1; acento cru (sem %) volta para UTF-8
        try:
            return urllib.parse.urlparse(self.path.encode("latin-1").decode("utf-8"))
        except (UnicodeEncodeError, UnicodeDecodeError):
            return urllib.parse.urlparse(self.path)

    def _local(self):
        return self.client_address[0] in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    def _pin_ok(self):
        if self._local():
            return True
        pin = (cfg().get("painel") or {}).get("pin") or ""
        if not pin:
            return False
        ck = self.headers.get("Cookie") or ""
        m = re.search(r"detto_pin=([^;]+)", ck)
        return bool(m and hmac.compare_digest(urllib.parse.unquote(m.group(1)), pin))

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _html(self, txt, code=200):
        b = txt.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _barrado(self):
        pin = (cfg().get("painel") or {}).get("pin")
        msg = ("<p>Digite o PIN do painel.</p><form method=post action=/entrar><input name=pin inputmode=numeric autofocus "
               "style='font-size:24px;padding:10px;width:160px'> <button style='font-size:20px;padding:10px 18px'>Entrar</button></form>"
               if pin else "<p>Para abrir pelo celular, primeiro crie um PIN no painel <b>no PC</b> (Configurações → PIN do celular).</p>")
        self._html(f"<meta name=viewport content='width=device-width'><body style='font-family:sans-serif;background:#0d1110;color:#e8f0ea;padding:24px'>"
                   f"<h2>Painel DETTO</h2>{msg}</body>", 401)

    def do_GET(self):  # noqa: N802
        u = self._caminho()
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        try:
            if not self._pin_ok():
                return self._barrado()
            if u.path in ("/", "/index.html"):
                return self._html((AQUI / "painel.html").read_text(encoding="utf-8"))
            if u.path == "/api/estado":
                atualiza_cache()
                return self._json(estado_painel())
            if u.path == "/arquivo":
                return self._arquivo(q)
            if u.path == "/ed_arquivo":
                return self._manda(EDI.arquivo(q.get("id", ""), q.get("rel", "")), baixar=q.get("baixar") == "1")
            self._json({"erro": "não achei"}, 404)
        except Exception as e:
            traceback.print_exc()
            self._json({"erro": str(e)}, 500)

    def _arquivo(self, q):
        onde = q.get("onde", "entrada")
        if onde not in ("entrada", "postados", "falhas"):
            return self._json({"erro": "pasta"}, 400)
        f = BASE / onde / nome_seguro(q.get("k", "")) / nome_seguro(q.get("nome", ""))
        if not f.exists():
            return self._json({"erro": "não achei"}, 404)
        return self._manda(f, baixar=q.get("baixar") == "1", como=nome_seguro(q["como"]) if q.get("como") else None)

    def _manda(self, f, baixar=False, como=None):
        tam = f.stat().st_size
        ini, fim = 0, tam - 1
        rg = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
        if rg:
            if rg.group(1):
                ini = int(rg.group(1))
                fim = int(rg.group(2)) if rg.group(2) else tam - 1
            else:
                ini = max(0, tam - int(rg.group(2)))
            fim = min(fim, tam - 1)
        self.send_response(206 if rg else 200)
        tipo = {".mov": "video/quicktime", ".webm": "video/webm", ".mkv": "video/x-matroska", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".webp": "image/webp", ".txt": "text/plain; charset=utf-8"}.get(f.suffix.lower(), "video/mp4")
        self.send_header("Content-Type", tipo)
        if baixar:
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(como or f.name))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fim - ini + 1))
        if rg:
            self.send_header("Content-Range", f"bytes {ini}-{fim}/{tam}")
        self.end_headers()
        with open(f, "rb") as fh:
            fh.seek(ini)
            falta = fim - ini + 1
            try:
                while falta > 0:
                    b = fh.read(min(1024 * 1024, falta))
                    if not b:
                        break
                    self.wfile.write(b)
                    falta -= len(b)
            except (ConnectionError, OSError):
                pass

    def do_POST(self):  # noqa: N802
        u = self._caminho()
        try:
            if u.path == "/entrar":
                n = int(self.headers.get("Content-Length") or 0)
                pin = urllib.parse.parse_qs(self.rfile.read(n).decode()).get("pin", [""])[0]
                self.send_response(303)
                self.send_header("Set-Cookie", f"detto_pin={urllib.parse.quote(pin)}; Max-Age=31536000; Path=/; SameSite=Strict; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
                return
            if not self._pin_ok():
                return self._json({"erro": "PIN"}, 401)
            if u.path == "/api/enviar":
                q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
                return self._json(recebe_envio(self, q))
            if u.path == "/api/ed_enviar":
                q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
                return self._json(EDI.recebe(self, q))
            if u.path.startswith("/api/"):
                n = int(self.headers.get("Content-Length") or 0)
                d = json.loads(self.rfile.read(n) or b"{}")
                return self._json(acao(u.path[5:], d) or {"ok": True})
            self._json({"erro": "não achei"}, 404)
        except ValueError as e:
            self._json({"erro": str(e)}, 400)
        except Exception as e:
            traceback.print_exc()
            self._json({"erro": str(e)}, 500)


def laco_postagem():
    """o painel aberto = postagem automática: confere a fila a cada 5 min"""
    time.sleep(20)
    while True:
        try:
            c_ = cfg()
            if not c_.get("pausado"):
                TRABALHO["postando"] = TRABALHO["postando"] or ""
                P.rodada(c_, BASE)
            atualiza_cache()
        except Exception as e:
            P.log(f"erro no painel: {e}")
        time.sleep(300)


# ------------------------------------------------------------------ instalar no Windows
def area_de_trabalho():
    for p in (Path.home() / "Desktop", Path.home() / "OneDrive" / "Desktop", Path.home() / "OneDrive" / "Área de Trabalho",
              Path.home() / "Área de Trabalho"):
        if p.exists():
            return p
    return Path.home()


def inicializar():
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def instalar():
    if os.name != "nt":
        sys.exit("--instalar é para o Windows.")
    pyw = Path(sys.executable).with_name("pythonw.exe")
    py = pyw if pyw.exists() else Path(sys.executable)
    vbs = inicializar() / "DETTO painel.vbs"
    vbs.write_text('Set s = CreateObject("WScript.Shell")\r\n'
                   f's.CurrentDirectory = "{TOOLS.parent}"\r\n'
                   f's.Run """{py}"" ""{Path(__file__).resolve()}"" --sem-navegador", 0, False\r\n', encoding="utf-8")
    atalho = area_de_trabalho() / "Painel DETTO.url"
    atalho.write_text(f"[InternetShortcut]\r\nURL=http://localhost:{PORTA}/\r\n", encoding="utf-8")
    print(f"Pronto: o painel liga sozinho quando o Windows inicia ({vbs}).\nAtalho na Área de Trabalho: {atalho}")
    subprocess.Popen(["wscript", str(vbs)])
    # confere se ligou mesmo (antes, se desse erro escondido, só aparecia "conexão recusada")
    for _ in range(20):
        time.sleep(1)
        try:
            with socket.create_connection(("127.0.0.1", PORTA), timeout=1):
                print(f"Painel ligado: http://localhost:{PORTA}")
                webbrowser.open(f"http://localhost:{PORTA}/")
                return
        except OSError:
            pass
    print("O painel NÃO ligou. O erro está em:", ERRO_F)
    if ERRO_F.exists():
        print(ERRO_F.read_text(encoding="utf-8", errors="replace")[-3000:])
    print("Rode sem o --instalar para ver o erro na tela:  python tools\\painel\\painel.py")


def desinstalar():
    for f in (inicializar() / "DETTO painel.vbs", area_de_trabalho() / "Painel DETTO.url"):
        if f.exists():
            f.unlink()
            print("removido:", f)
    print("Se o painel estiver aberto, feche pelo Gerenciador de Tarefas (pythonw.exe) ou reinicie o PC.")


def main():
    global BASE, REELS, PORTA
    ap = argparse.ArgumentParser(description="painel da postagem automática")
    ap.add_argument("--pasta", default=str(P.pasta_padrao()), help="pasta da postagem (padrão E:\\DETTO\\postar)")
    ap.add_argument("--reels", default=str(reels_pasta()), help="pasta dos reels (padrão E:\\DETTO\\reels)")
    ap.add_argument("--edicao", default=str(EDI.pasta_padrao()), help="pasta das edições (padrão E:\\DETTO\\edicao)")
    ap.add_argument("--porta", type=int, default=8730)
    ap.add_argument("--so-pc", action="store_true", help="não deixa abrir pelo celular")
    ap.add_argument("--sem-navegador", action="store_true")
    ap.add_argument("--sem-postar", action="store_true", help="só o painel, sem postar sozinho")
    ap.add_argument("--instalar", action="store_true")
    ap.add_argument("--desinstalar", action="store_true")
    a = ap.parse_args()
    BASE, REELS, PORTA = Path(a.pasta), Path(a.reels), a.porta
    EDI.ED = Path(a.edicao)
    if a.instalar:
        return instalar()
    if a.desinstalar:
        return desinstalar()
    # a pasta pode não existir ainda (primeira vez): sem ela o registro não abre e o painel escondido morria calado
    Path(a.pasta).mkdir(parents=True, exist_ok=True)
    if os.name == "nt" and sys.executable.lower().endswith("pythonw.exe"):
        # sem janela: o print iria para lugar nenhum
        sys.stdout = sys.stderr = open(Path(a.pasta) / "painel.log", "a", encoding="utf-8", buffering=1)
    cfg()
    REELS.mkdir(parents=True, exist_ok=True)
    EDI.ED.mkdir(parents=True, exist_ok=True)
    try:
        srv = hserver.ThreadingHTTPServer(("127.0.0.1" if a.so_pc else "0.0.0.0", PORTA), Painel)
    except OSError:
        print(f"O painel já está aberto (porta {PORTA}). Abrindo no navegador.")
        webbrowser.open(f"http://localhost:{PORTA}/")
        return
    srv.daemon_threads = True
    if not a.sem_postar:
        threading.Thread(target=laco_postagem, daemon=True).start()
    threading.Thread(target=EDI.laco, kwargs={"log": P.log, "ao_terminar": edicao_pronta}, daemon=True).start()
    print(f"PAINEL DETTO no ar:\n  no PC:      http://localhost:{PORTA}\n"
          f"  no celular: http://{ip_local()}:{PORTA}  (mesmo Wi-Fi; crie o PIN no painel)\n"
          f"  pastas: {BASE}  |  {REELS}\nFeche esta janela para desligar.")
    if not a.sem_navegador:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PORTA}/")).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


ERRO_F = Path(os.environ.get("TEMP") or os.environ.get("TMP") or Path.home()) / "detto_painel_erro.txt"

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        # escondido (pythonw) não tem tela: o erro fica num arquivo que o --instalar mostra
        try:
            ERRO_F.write_text(f"{dt.datetime.now():%d/%m %H:%M}\n{traceback.format_exc()}", encoding="utf-8")
        except OSError:
            pass
        raise
