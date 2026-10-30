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
import canais as CAN  # noqa: E402
import historias_painel as HIS  # noqa: E402
import shop_painel as SHP  # noqa: E402

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
        # o mesmo aviso no máximo a cada 6 h (antes enchia o registro a cada 3 min)
        if CACHE.get("erro_views") != str(e) or time.time() - CACHE.get("erro_views_quando", 0) > 6 * 3600:
            P.log(f"views dos reels teste: {e}")
            CACHE.update(erro_views=str(e), erro_views_quando=time.time())
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
                    "graduar": d.get("graduar", "manual"), "fb": (d.get("facebook") or {}).get("link", ""),
                    "fb_erro": d.get("facebook_erro", "")})
    return out


def item(p):
    st = p.stat()
    leg = P.legenda_de(p)
    return {"nome": p.name, "tam": tam_txt(st.st_size), "legenda": leg, "quando": dt.datetime.fromtimestamp(st.st_mtime).strftime("%d/%m %H:%M")}


def estado_painel():
    c_ = cfg()
    est = P.le_estado(BASE)
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
            "facebook": c.get("facebook", True) is not False, "fb_pend": est.get(k, {}).get("fb_pendentes") or {},
            "pausa_ate": (dt.datetime.fromtimestamp(est.get(k, {}).get("pausa_ate", 0)).strftime("%d/%m %H:%M")
                          if est.get(k, {}).get("pausa_ate", 0) > time.time() else ""),
            "pausa_motivo": est.get(k, {}).get("pausa_motivo", ""),
            "teste_ativos": len(P.testes_ativos(BASE, k)) if P.ig_e_teste(c_, c) else 0,
            "teste_vagas": int(c.get("max_teste") or est.get(k, {}).get("teste_vagas") or 0),
            "teste_sem_vaga": P.vaga_de_teste(c_, BASE, c, est, k)[0],
            "teste_libera": (lambda q: q.strftime("%d/%m %H:%M") if q else "")(P.vaga_de_teste(c_, BASE, c, est, k)[1]),
            "teste_normal": P.cai_para_normal(c_, c) if P.ig_e_teste(c_, c) else False,
            "teste_pasta": str(P.pasta_celular(BASE, c)) if P.ig_e_teste(c_, c) else "",
            "teste_preparados": len(P.le_json(arq_teste_preparados(c), [])) if P.ig_e_teste(c_, c) else 0,
            # vídeos que a API não conseguiu postar e já estão na pasta do Drive esperando você postar
            "celular": [{"nome": n, **(v if isinstance(v, dict) else {})}
                        for n, v in sorted((est.get(k, {}).get("celular") or {}).items())],
            "testes": testes_de(c) if c["plataforma"] == "instagram" else [],
            "intervalo_min": c.get("intervalo_min", 80), "horas": c.get("horas", "08-23"), "max_dia": c.get("max_dia", 0),
            "login": (BASE / "tokens" / f"{c['plataforma']}_{c['conta']}.json").exists(),
            "fila": [item(p) for p in fila], "postados": len(feitos), "hoje": P.postados_hoje(est, k),
            "ultimo": (est.get(k, {}).get("ultimo") or "")[:16].replace("T", " "),
            "proximo": prox.strftime("%d/%m %H:%M"), "proximo_ja": prox <= dt.datetime.now(),
            "falhas": falhas, "ultimos": ult, "pendentes": pend_l if pend is not None else None,
            "studio": eh_studio, "plano": plano,
            "preparados": len(P.le_json(arq_preparados(c), [])) if eh_studio else 0,
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
        "reels": {"prontos_hoje": len(prontos), "inicios": inicios, "links": links[:30], "n_links": len(links),
                  "auto_links": rcfg.get("auto_links", True), "feitos": feitos_links(), "falhos": links_falhos(),
                  "travado": reels_rodando(),
                  "rodando": bool(t and t.poll() is None), "postar": rcfg.get("postar", ["todas"]),
                  "log": [l.rstrip() for l in rlog]},
        "log": [l.rstrip() for l in log], "disco": tam_txt(livre), "disco_pouco": livre < 15 * 1024 ** 3,
        "edicao": EDI.lista(), "pasta_edicao": str(EDI.ED), "editando": EDI.PROC["id"] or "",
        "pin": bool((c_.get("painel") or {}).get("pin")), "drive": str(EDI.drive_raiz() or ""), "endereco": f"http://{ip_local()}:{PORTA}",
        "pastas": {"postar": str(BASE), "reels": str(REELS), "edicao": str(EDI.ED)},
        "agora": dt.datetime.now().strftime("%d/%m %H:%M"),
        "canais": CAN.estado(),
        "historias": HIS.estado(),
        "shop": SHP.estado(),
        "claude": claude_estado(),
        "codigo_novo": codigo_novo(),
        "versao": PAINEL_VERSAO,
    }


SUBIU_EM = time.time()
# Versão do PYTHON que está rodando. O painel.html é lido do disco a cada acesso, então depois de um `git pull` o
# navegador recebe a tela NOVA enquanto o Python continua o VELHO (foi o que aconteceu: a aba Histórias apareceu
# vazia e o Instagram continuou no caminho antigo). A tela compara esta versão com a dela e avisa.
PAINEL_VERSAO = "2026-10-29c"


def codigo_novo():
    """O painel roda o Python que estava em disco QUANDO ele abriu. Depois de um `git pull` o processo continua com o
    código velho (foi o que aconteceu com a correção do Instagram) — aqui ele percebe sozinho e avisa."""
    try:
        novos = []
        for pasta in (TOOLS,):
            for f in pasta.rglob("*"):
                if f.suffix.lower() not in (".py", ".js", ".html", ".css") or "__pycache__" in f.parts or "node_modules" in f.parts:
                    continue
                if f.stat().st_mtime > SUBIU_EM + 2:
                    novos.append(f.name)
                if len(novos) >= 6:
                    break
        return sorted(set(novos))[:6]
    except Exception:
        return []


def claude_estado():
    """o Claude da assinatura respondendo no lugar do Gemini: quantas hoje, falhas, se está REPETINDO a mesma pergunta"""
    try:
        sys.path.insert(0, str(TOOLS))
        from roteiro_ia import le_uso_claude
        u = le_uso_claude()
    except Exception:
        return {}
    agora = time.time()
    ult = u.get("ultimas", [])
    rep = {}
    for x in ult:
        if x.get("h") and agora - x["t"] < 3600:
            rep[x["h"]] = rep.get(x["h"], 0) + 1
    repetindo = max(rep.values(), default=0)
    return {"n": u.get("n", 0), "falhas": u.get("falhas", 0), "seguidas": u.get("seguidas", 0), "parado": bool(u.get("parado")),
            "motivo": u.get("motivo", ""), "repetindo": repetindo if repetindo >= 3 else 0,
            "ultimas": [{"hora": dt.datetime.fromtimestamp(x["t"]).strftime("%H:%M"), "ok": x["ok"], "de": x["de"],
                         "s": x.get("s", 0), "erro": x.get("erro", "")} for x in ult[-8:]][::-1]}


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
                # "postar já" é você mandando: passa por cima da pausa e do teto do dia
                P.posta_da_fila(c_, BASE, c, video, est, forcar=True)
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
    if nome.startswith("canal_"):
        return CAN.acao(nome, d)
    if nome.startswith("hist_"):
        return HIS.acao(nome, d)
    if nome.startswith("shop_"):
        return SHP.acao(nome, d)
    if nome == "reiniciar":
        # fecha o painel; quem abriu pelo atalho/tarefa do Windows sobe de novo sozinho
        P.log("painel: reiniciando para pegar o código novo")
        threading.Timer(1.0, lambda: os._exit(7)).start()
        return {"ok": True}
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
                    if "facebook" in d:
                        x["facebook"] = bool(d["facebook"])
                    if d.get("graduar") in ("manual", "automatico"):
                        x["graduar"] = d["graduar"]
                    if "meta_views" in d:
                        x["meta_views"] = max(0, int(d["meta_views"]))
                    if "teste_cai_para_normal" in d:
                        # ligado = sem vaga de teste o vídeo sobe para TODO MUNDO; desligado (padrão) = espera
                        x["teste_cai_para_normal"] = bool(d["teste_cai_para_normal"])
                    if "max_teste" in d:
                        x["max_teste"] = max(0, int(d["max_teste"]))
        grava_cfg(muda)
    elif nome == "nova_conta":
        plat, conta = d["plataforma"], d["conta"].strip().lstrip("@").lower()
        if plat not in ("instagram", "tiktok", "youtube", "kwai") or not re.fullmatch(r"[\w.]{2,40}", conta):
            raise ValueError("conta inválida")

        def muda(c):
            lista = c.setdefault("contas", json.loads(json.dumps(P.CONFIG_PADRAO["contas"])))
            if any(P.chave(x) == f"{plat}_{conta}" for x in lista):
                raise ValueError("essa conta já existe")
            # YouTube: cada envio gasta 1.600 da cota de 10.000/dia do projeto do Google (dividida com os canais) → até 4/dia
            lista.append({"plataforma": plat, "conta": conta, "intervalo_min": 180 if plat == "youtube" else 120, "horas": "08-23",
                          "max_dia": 4 if plat == "youtube" else 0, "ativo": True})
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
        est.get(k, {}).get("espera", {}).pop(n, None)
        P.grava_json(BASE / "estado.json", est)
    elif nome == "tentar_todas":
        # devolve TODOS os vídeos com erro desta conta para a fila (ex.: depois de uma rodada em que a hospedagem
        # do Reels teste estava fora do ar e os vídeos foram para falhas\ sem culpa)
        k = d["k"]
        est = P.le_json(BASE / "estado.json", {})
        n = 0
        for f in sorted((BASE / "falhas" / k).glob("*")):
            if f.suffix.lower() not in VIDEO_EXT:
                continue
            for g in (f, f.with_suffix(".txt")):
                if g.exists():
                    shutil.move(str(g), str(BASE / "entrada" / k / g.name))
            est.get(k, {}).get("falhas", {}).pop(f.name, None)
            est.get(k, {}).get("espera", {}).pop(f.name, None)
            n += 1
        P.grava_json(BASE / "estado.json", est)
        return {"ok": True, "n": n}
    elif nome == "claude_parar":
        sys.path.insert(0, str(TOOLS))
        from roteiro_ia import grava_uso_claude, le_uso_claude
        u = le_uso_claude()
        u["parado"] = bool(d.get("parado"))
        u["motivo"] = "parado por você no painel" if u["parado"] else ""
        u["seguidas"] = 0
        grava_uso_claude(u)
    elif nome == "tira_pausa":
        est = P.le_json(BASE / "estado.json", {})
        est.get(d["k"], {}).pop("pausa_ate", None)
        P.grava_json(BASE / "estado.json", est)
    elif nome == "teste_reset":
        # esquece o teto de Reels teste que a conta aprendeu numa recusa (ele pode ter ficado baixo demais e
        # prender a conta); a próxima rodada experimenta de novo
        def _limpa(e):
            x = e.setdefault(d["k"], {})
            for campo in ("teste_vagas", "teste_ate", "teste_sonda", "teste_recusa", "pausa_ate"):
                x.pop(campo, None)
        P.muda_estado(BASE, _limpa)
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
            if "drive" in d:
                c.setdefault("painel", {})["drive"] = str(d["drive"]).strip()
                EDI.DRIVE = c["painel"]["drive"] or None
                if EDI.DRIVE:
                    os.environ["DETTO_DRIVE"] = str(EDI.DRIVE)
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
        if reels_rodando():
            raise ValueError("outro reels.py está rodando agora (a tarefa do Windows) — espere ele terminar")
        n = max(1, min(20, int(d.get("quantos", 5))))
        logf = log_reels()
        exe, extra = py_filho()
        cmd = [exe, "-u", str(TOOLS / "reels" / "reels.py"), "--pasta", str(REELS), "--quantos", str(n)]
        TRABALHO["reels"] = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, text=True, cwd=str(TOOLS.parent),
                                             env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **extra)
    elif nome == "reels_parar":
        t = TRABALHO["reels"]
        if t and t.poll() is None:
            t.terminate()
    elif nome == "reels_link":
        # um ou vários links (um por linha, ou separados por espaço): vão para a lista e são feitos sozinhos
        novos = re.findall(r"https?://\S+", str(d.get("url", "")))
        if not novos:
            raise ValueError("cole um link (https://...)")
        REELS.mkdir(parents=True, exist_ok=True)
        f = REELS / "links.txt"
        ja = set(l.strip() for l in f.read_text(encoding="utf-8").splitlines()) if f.exists() else set()
        novos = [u for u in dict.fromkeys(novos) if u not in ja]
        with open(f, "a", encoding="utf-8") as g:
            for u in novos:
                g.write(u + "\n")
        # link colado de novo = fazer de novo (tira do histórico de já usados)
        hf = REELS / "historico.json"
        h = P.le_json(hf, {})
        if h.get("usados"):
            antes = len(h["usados"])
            h["usados"] = {k: v for k, v in h["usados"].items() if not (isinstance(v, dict) and v.get("url") in novos)}
            if len(h["usados"]) != antes:
                P.grava_json(hf, h)
        return {"ok": True, "n": len(novos)}
    elif nome == "reels_auto":
        f = REELS / "config.json"
        rc = P.le_json(f, {})
        rc["auto_links"] = bool(d.get("on"))
        P.grava_json(f, rc)
    elif nome == "reels_tira_link":
        f = REELS / "links.txt"
        if f.exists():
            alvo = str(d.get("url", "")).strip()
            f.write_text("\n".join(l for l in f.read_text(encoding="utf-8").splitlines() if l.strip() != alvo) + "\n", encoding="utf-8")
    elif nome == "reels_postar":
        f = REELS / "config.json"
        rc = P.le_json(f, {})
        rc["postar"] = [x for x in d.get("para", []) if x == "todas" or re.fullmatch(r"(instagram|tiktok|youtube|kwai):[\w.]+", x)]
        P.grava_json(f, rc)
    elif nome == "studio_agendei":
        # você agendou no TikTok Studio: os vídeos saem da fila com o horário planejado
        c = conta_de(d["k"])
        k = d["k"]
        fila = P.fila_de(BASE, k)
        slots = P.planeja(c, P.le_json(BASE / "estado.json", {}), k, len(fila), P.agendados_por_dia(BASE, k))
        pedidos = set(nome_seguro(n) for n in d.get("nomes", []))
        if d.get("da_pasta"):
            pedidos |= set(P.le_json(arq_preparados(c), []))
        feitos = 0
        for v, t in zip(fila, slots):
            if v.name in pedidos:
                P.marca_agendado(BASE, c, v, t)
                feitos += 1
        if d.get("da_pasta") or not P.fila_de(BASE, k):
            limpa_studio(c)
            (arq_preparados(c)).unlink(missing_ok=True)
        return {"ok": True, "feitos": feitos}
    elif nome == "teste_preparar":
        return prepara_teste(conta_de(d["k"]), int(d.get("quantos") or 0))
    elif nome == "teste_postei":
        return teste_postei(conta_de(d["k"]), d.get("nomes"))
    elif nome == "celular_postei":
        # você baixou do Drive e postou como Reel de teste pelo app
        return celular_postei(conta_de(d["k"]), d.get("nomes"))
    elif nome == "celular_devolver":
        # mudou de ideia: o vídeo volta para a fila da API
        return celular_devolver(conta_de(d["k"]), d.get("nomes"))
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
        if reels_rodando():
            raise ValueError("outro reels.py está rodando agora (a tarefa do Windows) — espere ele terminar")
        url = str(d.get("url", "")).strip()
        if not re.match(r"https?://\S+$", url):
            raise ValueError("cole um link (https://...)")
        exe, extra = py_filho()
        cmd = [exe, "-u", str(TOOLS / "reels" / "reels.py"), "--pasta", str(REELS), "--clip", url, "--modo", d.get("modo") if d.get("modo") in ("troca", "novo") else "troca"]
        if d.get("inicio"):
            cmd += ["--inicio", str(d["inicio"])]
        logf = log_reels()
        TRABALHO["reels"] = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, text=True, cwd=str(TOOLS.parent),
                                             env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **extra)
    elif nome.startswith("ed_"):
        fn = {"ed_drive": EDI.drive_pastas, "ed_novo": EDI.novo, "ed_caminho": EDI.de_caminho, "ed_iniciar": EDI.iniciar, "ed_roteiro": EDI.roteiro,
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


def arq_preparados(c):
    """lista dos vídeos que estão na pasta preparada (TikTok: o nome antigo, por conta)"""
    (BASE / "tiktok_studio").mkdir(parents=True, exist_ok=True)
    return BASE / "tiktok_studio" / (f"_preparados_{c['conta']}.json" if c["plataforma"] == "tiktok" else f"_preparados_{P.chave(c)}.json")


def pasta_teste(c):
    """pasta do REELS TESTE que VOCÊ posta pelo celular. A API tem um limite próprio e pequeno de reels teste
    (2207078: "máximo publicado pela Content Publishing API"); no app do Instagram você consegue os 10 do dia.
    Então o que não cabe pela API vai para esta pasta no Drive, com a legenda, e você posta como TESTE pelo app."""
    try:
        raiz = EDI.drive_raiz()
    except Exception:
        raiz = None
    return (Path(raiz) / "DETTO" / "reels_teste" / c["conta"]) if raiz else (BASE / "reels_teste" / c["conta"])


def arq_teste_preparados(c):
    (BASE / "reels_teste").mkdir(parents=True, exist_ok=True)
    return BASE / "reels_teste" / f"_preparados_{P.chave(c)}.json"


def prepara_teste(c, quantos=0):
    """põe os próximos vídeos da fila do Instagram na pasta do celular, com LEGENDAS.txt"""
    k = P.chave(c)
    fila = P.fila_de(BASE, k)
    if not fila:
        raise ValueError("a fila do Instagram está vazia")
    fila = fila[:quantos] if quantos else fila[:10]
    p = pasta_teste(c)
    p.mkdir(parents=True, exist_ok=True)
    for f in p.iterdir():
        try:
            f.unlink()
        except OSError:
            pass
    linhas = [f"REELS TESTE — @{c['conta']}  (pelo APP do Instagram, no celular)",
              "A API do Instagram só deixa alguns reels teste ativos; no app você consegue os 10 do dia.",
              "",
              "No celular: app do Drive → abra o vídeo → ⋮ → Enviar cópia → Instagram → Reels →",
              "cole a legenda abaixo → na tela de compartilhar, ligue \"Reel de teste\" (Trial reel) → Compartilhar.",
              "Depois, aqui no painel: \"✔ Postei os da pasta\".", ""]
    preparados = []
    for i, v in enumerate(fila, 1):
        curto = nome_seguro(re.sub(r"^\d{4}-\d{2}-\d{2}( \d{4,6})? ?", "", v.stem))[:60]
        nome = f"{i:02d} - {curto}{v.suffix.lower()}"
        preparados.append(v.name)
        try:
            os.link(v, p / nome)
        except OSError:
            shutil.copyfile(v, p / nome)
        linhas += [f"--- {nome}", P.legenda_de(v).split("\n---")[0].strip(), ""]
    (p / "LEGENDAS.txt").write_text("\n".join(linhas), encoding="utf-8")
    P.grava_json(arq_teste_preparados(c), preparados)
    return {"ok": True, "n": len(preparados), "pasta": str(p)}


def teste_postei(c, nomes=None):
    """você postou os da pasta pelo app: eles saem da fila e entram em postados como teste feito no celular
    (via=app, que NÃO conta no limite da API)"""
    k = P.chave(c)
    pedidos = set(nome_seguro(n) for n in (nomes or [])) or set(P.le_json(arq_teste_preparados(c), []))
    destino = BASE / "postados" / k
    destino.mkdir(parents=True, exist_ok=True)
    feitos = 0
    for v in P.fila_de(BASE, k):
        if v.name not in pedidos:
            continue
        for f in (v, v.with_suffix(".txt")):
            if f.exists():
                shutil.move(str(f), str(destino / f.name))
        P.grava_json(destino / f"{v.stem}.json", {
            "quando": dt.datetime.now().isoformat(timespec="seconds"), "video": v.name,
            "teste": True, "via": "app", "graduar": c.get("graduar", "manual"), "link": ""})
        feitos += 1
    p = pasta_teste(c)
    if p.exists():
        for f in p.iterdir():
            try:
                f.unlink()
            except OSError:
                pass
    arq_teste_preparados(c).unlink(missing_ok=True)
    return {"ok": True, "feitos": feitos}


def celular_postei(c, nomes=None):
    """você postou pelo celular: o vídeo sai da espera e entra em postados como teste feito no app
    (via=app, que NÃO gasta o limite da API). Também limpa a cópia da pasta do Drive."""
    k = P.chave(c)
    est = P.le_estado(BASE)
    espera = est.get(k, {}).get("celular") or {}
    pedidos = [nome_seguro(n) for n in (nomes or [])] or list(espera)
    destino = BASE / "postados" / k
    destino.mkdir(parents=True, exist_ok=True)
    feitos = 0
    for n in pedidos:
        if n not in espera:
            continue
        v = BASE / "celular" / k / n
        for f in (v, v.with_suffix(".txt")):
            if f.exists():
                shutil.move(str(f), str(destino / f.name))
        P.grava_json(destino / f"{Path(n).stem}.json", {
            "quando": dt.datetime.now().isoformat(timespec="seconds"), "video": n,
            "teste": True, "via": "app", "graduar": c.get("graduar", "manual"), "link": ""})
        d_ = Path(espera[n].get("pasta") or P.pasta_celular(BASE, c))
        for f in (d_ / n, (d_ / n).with_suffix(".txt")):
            f.unlink(missing_ok=True)
        feitos += 1
    P.muda_estado(BASE, lambda e: [e.setdefault(k, {}).setdefault("celular", {}).pop(n, None) for n in pedidos])
    return {"ok": True, "feitos": feitos}


def celular_devolver(c, nomes=None):
    """devolve para a fila da API os vídeos que estavam esperando você postar pelo celular"""
    k = P.chave(c)
    est = P.le_estado(BASE)
    espera = est.get(k, {}).get("celular") or {}
    pedidos = [nome_seguro(n) for n in (nomes or [])] or list(espera)
    fila = BASE / "entrada" / k
    fila.mkdir(parents=True, exist_ok=True)
    n_ = 0
    for n in pedidos:
        v = BASE / "celular" / k / n
        if not v.exists():
            continue
        for f in (v, v.with_suffix(".txt")):
            if f.exists():
                shutil.move(str(f), str(fila / f.name))
        d_ = Path((espera.get(n) or {}).get("pasta") or P.pasta_celular(BASE, c))
        for f in (d_ / n, (d_ / n).with_suffix(".txt")):
            f.unlink(missing_ok=True)
        n_ += 1
    P.muda_estado(BASE, lambda e: [e.setdefault(k, {}).setdefault("celular", {}).pop(n, None) for n in pedidos])
    return {"ok": True, "n": n_}


def pasta_studio(c):
    if c["plataforma"] == "kwai":
        # Kwai: pasta no Google Drive (aparece no celular, de onde você posta pelo app); sem Drive, no PC
        try:
            raiz = EDI.drive_raiz()
        except Exception:
            raiz = None
        return (Path(raiz) / "DETTO" / "kwai" / c["conta"]) if raiz else (BASE / "kwai" / c["conta"])
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
    if c["plataforma"] == "kwai":
        linhas = [f"KWAI — @{c['conta']}  (pelo app do Kwai no celular)",
                  "Esta pasta está no Google Drive (DETTO\\kwai\\" + c["conta"] + "). No celular, no horário de cada vídeo:",
                  "app do Drive → abra o vídeo → ⋮ → Enviar cópia → Kwai (ou Salvar no dispositivo e escolher no Kwai) →",
                  "cole a legenda abaixo → Publicar. Depois, no painel: \"Postei os N da pasta\" (ou o ✔ de cada vídeo).", ""]
    else:
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
    P.grava_json(arq_preparados(c), preparados)
    if os.name == "nt":
        try:
            os.startfile(str(p))  # noqa: S606
        except OSError:
            pass
    P.log(f"{k}: pasta {'do Kwai' if c['plataforma'] == 'kwai' else 'do TikTok Studio'} pronta com {len(slots)} vídeos: {p}")
    return {"ok": True, "pasta": str(p), "n": len(slots)}


def ed_postar(d, pasta=None, rels=None):
    """manda um vídeo pronto da edição para a fila das contas"""
    p = pasta or EDI.pasta_de(d.get("id", ""))
    para = [x for x in d.get("para", []) if re.fullmatch(r"(instagram|tiktok|youtube|kwai):[\w.]+", x)]
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
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass   # o navegador fechou a aba/atualizou no meio do envio: não é erro, e enchia o registro de traceback

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
            if u.path == "/canal_arquivo":
                return self._manda(CAN.arquivo(q.get("c", ""), q.get("id", ""), q.get("nome", "")), baixar=q.get("baixar") == "1")
            # era "caminho" (variável que não existe): NameError -> erro 500 em /historia, /shop_arquivo e
            # /ed_arquivo, ou seja, assistir/baixar história, vídeo de Shop e saída de edição não abria
            if u.path == "/historia":
                return self._manda(HIS.arquivo(q.get("s", ""), q.get("a") or q.get("nome", "episodio.mp4")),
                                   baixar=q.get("baixar") == "1")
            if u.path == "/shop_arquivo":
                return self._manda(SHP.arquivo(q.get("nome", ""), q.get("dia", "")), baixar=q.get("baixar") == "1")
            if u.path == "/ed_arquivo":
                return self._manda(EDI.arquivo(q.get("id", ""), q.get("rel", "")), baixar=q.get("baixar") == "1")
            self._json({"erro": "não achei"}, 404)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass   # aba fechada no meio do pedido
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
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass   # aba fechada no meio do pedido
        except Exception as e:
            traceback.print_exc()
            self._json({"erro": str(e)}, 500)


def feitos_links():
    """últimos links processados (links_feitos.txt: "data ok|FALHOU link")"""
    f = REELS / "links_feitos.txt"
    if not f.exists():
        return []
    out = []
    for l in f.read_text(encoding="utf-8", errors="replace").splitlines()[-12:][::-1]:
        p = l.split(" ", 2)
        if len(p) == 3:
            out.append({"dia": p[0], "ok": p[1] == "ok", "url": p[2]})
    return out


def links_falhos():
    """links que saíram da lista SEM virar reels, com o motivo (links_falhos.txt). Antes isso só aparecia no
    registro, que era apagado a cada disparo — e você ficava sem saber por que o link não virou vídeo."""
    f = REELS / "links_falhos.txt"
    if not f.exists():
        return []
    out = []
    for l in f.read_text(encoding="utf-8", errors="replace").splitlines()[-8:][::-1]:
        p_ = l.split("\t")
        if len(p_) >= 3:
            out.append({"quando": p_[0], "url": p_[1], "motivo": p_[2]})
    return out


def reels_rodando():
    """True = já existe um reels.py trabalhando (a trava .reels_rodando é do sistema: só experimenta pegá-la)"""
    f = REELS / ".reels_rodando"
    if not f.exists():
        return False
    try:
        g = open(f, "a+")
    except OSError:
        return True
    try:
        if os.name == "nt":
            import msvcrt
            g.seek(0)
            msvcrt.locking(g.fileno(), msvcrt.LK_NBLCK, 1)
            msvcrt.locking(g.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(g.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(g.fileno(), fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        g.close()


def log_reels():
    """registro dos reels em modo ACRESCENTA (antes abria com "w" e apagava o motivo da falha anterior a cada
    disparo — por isso não dava para ver por que um link não virou reels). Passa de 2 MB, começa de novo."""
    f = REELS / "painel_reels.log"
    try:
        if f.exists() and f.stat().st_size > 2_000_000:
            f.replace(f.with_suffix(".log.1"))
    except OSError:
        pass
    return open(f, "a", encoding="utf-8")


def laco_links():
    """links colados no painel: o PC vai fazendo um atrás do outro e cada reel pronto já entra na fila.
    A cada 10 min também puxa os começos novos da pasta "Começo" do Drive (renomeia e põe em inicios\\)."""
    time.sleep(30)
    ultimo_import = 0.0
    while True:
        try:
            t = TRABALHO["reels"]
            if time.time() - ultimo_import > 600 and not (t and t.poll() is None):
                ultimo_import = time.time()
                exe, extra = py_filho()
                logf = log_reels()
                TRABALHO["reels"] = subprocess.Popen([exe, "-u", str(TOOLS / "reels" / "reels.py"), "--pasta", str(REELS), "--importar"],
                                                     stdout=logf, stderr=subprocess.STDOUT, text=True, cwd=str(TOOLS.parent),
                                                     env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **extra)
                time.sleep(45)
                continue
            rc = P.le_json(REELS / "config.json", {})
            f = REELS / "links.txt"
            t = TRABALHO["reels"]
            tem = f.exists() and any(l.strip().startswith("http") for l in f.read_text(encoding="utf-8").splitlines())
            if rc.get("auto_links", True) and tem and not (t and t.poll() is None) and not cfg().get("pausado"):
                # a trava é de OUTRO reels.py (a tarefa do Windows, ou um que ficou aberto): disparar aqui só fazia
                # o filho morrer na hora ("outro reels.py já está rodando") e o laço repetia isso a cada 45 s sem
                # fazer link nenhum — era por isso que links enviados nunca ficavam prontos (26/out)
                if reels_rodando():
                    if time.time() - CACHE.get("aviso_trava_reels", 0) > 1800:
                        CACHE["aviso_trava_reels"] = time.time()
                        P.log("reels: outro reels.py está rodando (tarefa do Windows) — os links da lista esperam a vez")
                    time.sleep(45)
                    continue
                exe, extra = py_filho()
                cmd = [exe, "-u", str(TOOLS / "reels" / "reels.py"), "--pasta", str(REELS), "--so-links", "--quantos", "0"]
                logf = log_reels()
                TRABALHO["reels"] = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, text=True, cwd=str(TOOLS.parent),
                                                     env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **extra)
                P.log("reels: fazendo os links da lista")
        except Exception as e:
            P.log(f"reels: erro no laço dos links ({e})")
        time.sleep(45)


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
    EDI.DRIVE = (P.le_json(BASE / "config.json", {}).get("painel") or {}).get("drive") or None
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
        threading.Thread(target=laco_links, daemon=True).start()
    EDI.OCUPADO = CAN.ocupado  # a edição espera o canal terminar de montar (e o canal espera a edição)
    if EDI.DRIVE:
        os.environ["DETTO_DRIVE"] = str(EDI.DRIVE)
    threading.Thread(target=EDI.laco, kwargs={"log": P.log, "ao_terminar": edicao_pronta}, daemon=True).start()
    threading.Thread(target=HIS.laco, kwargs={"log": P.log, "ocupado": lambda: CAN.ocupado() or bool(EDI.PROC["p"] and EDI.PROC["p"].poll() is None)},
                     daemon=True).start()
    threading.Thread(target=CAN.laco, kwargs={"log": P.log, "edicao_ocupada": lambda: bool(EDI.PROC["p"] and EDI.PROC["p"].poll() is None)},
                     daemon=True).start()
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
