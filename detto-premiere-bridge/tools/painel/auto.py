"""AUTOMÁTICO DO PAINEL (06/nov, pedido dele: "quero que faça isso automático").

Três laços leves, todos com prazo e sem derrubar o painel se falharem:
 1. RELATÓRIO: a cada 5 min escreve status.json/status.txt em <Drive>\\DETTO\\status (ou <DETTO>\\status) —
    é o que o assistente agendado lê para dizer o que está acontecendo e consertar.
 2. ALERTAS: rodada passando de N min, "NÃO RODEI"/Traceback novo no registro, atualização feita/revertida
    → celular (Telegram/Discord, o mesmo `viral.avisa`). Cada aviso só sai 1x.
 3. ATUALIZAÇÃO SOZINHA: git fetch; atrasado e NADA rodando → pull --ff-only → teste_rapido → se quebrar,
    volta à versão de antes; se passar, reinicia o painel (os._exit(7), como o botão).
Chaves em painel.json de config da postagem: ("painel": {"auto_atualizar": true, "alerta_rodada_min": 60}).
"""

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
RAIZ_GIT = PONTE.parent

AVISADOS = {}      # chave -> quando (aviso 1x por janela)
RODADA = {}        # canal -> começo (monotonic) da rodada em andamento
ULTIMO = {"status": "", "update": "", "update_msg": ""}


def agora():
    return dt.datetime.now().strftime("%d/%m %H:%M")


def _git(*args, tempo=90):
    try:
        r = subprocess.run(["git", "-C", str(RAIZ_GIT), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=tempo)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:   # noqa: BLE001
        return 1, str(e)[:200]


def pasta_status(drive_raiz, detto):
    """<Meu Drive>\\DETTO\\status quando o Drive está montado; senão <DETTO>\\status"""
    if drive_raiz:
        d = Path(drive_raiz) / "DETTO" / "status"
    else:
        d = Path(detto) / "status"
    d.mkdir(parents=True, exist_ok=True)
    return d


def avisa_celular(texto, log=print):
    try:
        sys.path.insert(0, str(TOOLS / "viral"))
        import viral

        cfg = viral.config(Path(os.environ["DETTO_VIRAL"]) if os.environ.get("DETTO_VIRAL") else _viral_pasta())
        return viral.avisa(texto, cfg)
    except Exception as e:   # noqa: BLE001
        log(f"auto: não consegui avisar no celular ({str(e)[:100]})")
        return False


def _viral_pasta():
    for r in (Path("E:/DETTO"), Path.home() / "DETTO"):
        if (r / "viral").is_dir():
            return r / "viral"
    return Path.home() / "DETTO" / "viral"


def avisa_1x(chave, texto, log=print, janela_min=60):
    t = time.time()
    if t - AVISADOS.get(chave, 0) < janela_min * 60:
        return
    AVISADOS[chave] = t
    log(f"auto: ALERTA — {texto[:140]}")
    avisa_celular(texto, log)


def _ultima_linha_ruim(linhas):
    for l in reversed(linhas):
        if re.search(r"NÃO RODEI|Traceback|SEM VOZ|Error:|ERROR:", l):
            return l.strip()[:220]
    return ""


def monta_status(CAN, SHP, EDI, versao):
    """o retrato do sistema para o assistente ler (tudo texto simples)"""
    rc, head = _git("rev-parse", "--short", "HEAD", tempo=15)
    s = {"quando": dt.datetime.now().isoformat(timespec="seconds"), "painel_versao": versao,
         "commit": head if rc == 0 else "?", "canais": {}, "shop_rodando": bool(SHP.rodando()),
         "edicao_rodando": bool(EDI.PROC["p"] and EDI.PROC["p"].poll() is None),
         "montando": CAN.PESADO["id"] if CAN.ocupado() else "", "fila_espera": [x["c"] for x in CAN.ESPERA],
         "ultima_atualizacao": ULTIMO["update_msg"]}
    for c in CAN.CANAIS:
        try:
            p = CAN.pasta(c)
            el = CAN.estado_local(c)
            log = CAN._tail(p / "canal.log", 60) if (p / "canal.log").exists() else []
            desde = RODADA.get(c)
            s["canais"][c] = {
                "ligado": bool(el.get("ligado")), "ultimo": el.get("ultimo", ""),
                "rodando": CAN.PESADO["id"] == c and CAN.ocupado(),
                "rodando_ha_min": round((time.monotonic() - desde) / 60) if desde else 0,
                "erro_botao": el.get("erro", ""), "ultimo_problema_no_log": _ultima_linha_ruim(log),
                "ultimas_linhas": [l[:200] for l in log[-6:]],
            }
        except Exception as e:   # noqa: BLE001
            s["canais"][c] = {"erro_ao_ler": str(e)[:150]}
    s["shop_ultimas_linhas"] = [l[:200] for l in SHP.PROC["log"][-6:]]
    try:
        base = SHP.pasta()
        dia = dt.date.today().isoformat()
        s["shop_prontos_hoje"] = len(list((base / "prontos" / dia).glob("*.mp4"))) if (base / "prontos" / dia).is_dir() else 0
    except Exception:   # noqa: BLE001
        s["shop_prontos_hoje"] = -1
    try:
        raiz = Path("E:/") if Path("E:/").exists() else Path.home()
        s["disco_livre_gb"] = round(shutil.disk_usage(raiz).free / 1e9, 1)
    except Exception:   # noqa: BLE001
        s["disco_livre_gb"] = -1
    try:
        v = subprocess.run([sys.executable, "-m", "yt_dlp", "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
        s["yt_dlp"] = v
    except Exception:   # noqa: BLE001
        s["yt_dlp"] = "?"
    try:
        s["cookies"] = CAN.cookies_info()
    except Exception:   # noqa: BLE001
        s["cookies"] = "?"
    return s


def texto_do_status(s):
    L = [f"STATUS {s['quando']} · commit {s['commit']} · painel {s['painel_versao']} · disco livre {s['disco_livre_gb']} GB",
         f"montando: {s['montando'] or '-'} · fila: {', '.join(s['fila_espera']) or '-'} · shop rodando: {s['shop_rodando']} "
         f"(prontos hoje: {s.get('shop_prontos_hoje')}) · edição: {s['edicao_rodando']} · yt-dlp {s['yt_dlp']}"]
    for c, x in s["canais"].items():
        L.append(f"[{c}] ligado={x.get('ligado')} rodando={x.get('rodando')} ({x.get('rodando_ha_min', 0)} min) "
                 f"último={x.get('ultimo')} problema={x.get('ultimo_problema_no_log') or '-'} erro_botao={x.get('erro_botao') or '-'}")
    L.append("atualização: " + (s.get("ultima_atualizacao") or "-"))
    return "\n".join(L) + "\n"


def grava_status(s, pasta):
    (pasta / "status.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    (pasta / "status.txt").write_text(texto_do_status(s), encoding="utf-8")


def confere_alertas(s, cfg_painel, log=print):
    lim = int(cfg_painel.get("alerta_rodada_min", 60))
    for c, x in s["canais"].items():
        if x.get("rodando") and x.get("rodando_ha_min", 0) >= lim:
            avisa_1x(f"lenta-{c}", f"⏱ canal {c}: rodada há {x['rodando_ha_min']} min (limite {lim}). "
                     f"Última linha: {(x.get('ultimas_linhas') or ['-'])[-1][:120]}", log, janela_min=45)
        pb = x.get("ultimo_problema_no_log")
        if pb and not x.get("rodando"):
            avisa_1x(f"erro-{c}-{hash(pb) % 100000}", f"⚠ canal {c}: {pb}", log, janela_min=360)
    if s.get("disco_livre_gb", 99) != -1 and s["disco_livre_gb"] < 8:
        avisa_1x("disco", f"💾 pouco espaço no disco: {s['disco_livre_gb']} GB livres", log, janela_min=240)


def acompanha_rodadas(CAN):
    for c in CAN.CANAIS:
        rod = CAN.PESADO["id"] == c and CAN.ocupado()
        if rod and c not in RODADA:
            RODADA[c] = time.monotonic()
        elif not rod:
            RODADA.pop(c, None)


def tudo_parado(CAN, SHP, EDI):
    return not (CAN.ocupado() or CAN.ESPERA or SHP.rodando() or CAN.POSTANDO["fila"]
                or (EDI.PROC["p"] and EDI.PROC["p"].poll() is None))


def atualiza_se_preciso(CAN, SHP, EDI, log=print):
    """pull seguro; devolve True quando o painel deve reiniciar"""
    rc, _ = _git("fetch", "--quiet", tempo=120)
    if rc != 0:
        return False
    rc, atras = _git("rev-list", "--count", "HEAD..@{u}", tempo=20)
    if rc != 0 or not atras.strip().isdigit() or int(atras) == 0:
        return False
    if not tudo_parado(CAN, SHP, EDI):
        return False
    rc, antes = _git("rev-parse", "HEAD", tempo=15)
    if rc != 0:
        return False
    rc, sujo = _git("status", "--porcelain", "--untracked-files=no", tempo=30)
    if sujo.strip():
        ULTIMO["update_msg"] = f"{agora()}: há {atras} commit(s) novos, mas há arquivos alterados no PC — não puxei"
        avisa_1x("upd-sujo", "🔄 atualização pendente, mas há arquivo alterado à mão no PC. Rode ATUALIZAR.ps1.", log, 720)
        return False
    rc, saida = _git("pull", "--ff-only", tempo=180)
    if rc != 0:
        ULTIMO["update_msg"] = f"{agora()}: pull falhou: {saida[-160:]}"
        avisa_1x("upd-pull", f"🔄 atualização automática falhou no pull: {saida[-160:]}", log, 360)
        return False
    t = subprocess.run([sys.executable, str(TOOLS / "teste_rapido.py")], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600, cwd=str(PONTE))
    if t.returncode != 0:
        _git("reset", "--hard", antes.strip(), tempo=60)
        ULTIMO["update_msg"] = f"{agora()}: código novo FALHOU no teste, voltei para {antes[:8]}"
        avisa_1x("upd-teste", f"🔄 atualização automática: o teste reprovou e VOLTEI para {antes[:8]}.\n{(t.stdout + t.stderr)[-300:]}", log, 120)
        return False
    (PONTE / ".ultima_boa").write_text(antes.strip() + "\n", encoding="utf-8")
    ULTIMO["update_msg"] = f"{agora()}: atualizei {antes[:8]} → novo ({atras} commit(s)), reiniciando"
    avisa_1x("upd-ok", f"✅ painel atualizado sozinho ({atras} commit(s)) e reiniciando.", log, 1)
    return True


def shop_meta(CAN, SHP, EDI, cp, log=print):
    """30 vídeos de Shop por dia (06/nov): quando o PC está livre e faltam vídeos, completa a lista de
    produtos (viral_shop.py) e manda o shop.py fazer um lote pequeno — um lote por vez, nunca junto com canal."""
    meta = int(cp.get("shop_meta_dia", 30))
    if meta <= 0 or not tudo_parado(CAN, SHP, EDI):
        return
    base = SHP.pasta()
    try:
        if not SHP.estado().get("auto", True):    # botão do painel (aba Shop): desligado = só faz o que ele mandar
            return
    except Exception:   # noqa: BLE001
        pass
    dia = dt.date.today().isoformat()
    feitos = len(list((base / "prontos" / dia).glob("*.mp4"))) if (base / "prontos" / dia).is_dir() else 0
    if feitos >= meta:
        return
    nf = base / "produtos_nomes.txt"

    def nomes():
        return [l for l in nf.read_text(encoding="utf-8").splitlines() if l.strip()] if nf.exists() else []

    if len(nomes()) < 3:
        log(f"auto: lista de nomes do Shop com {len(nomes())} — buscando virais")
        try:
            subprocess.run([sys.executable, str(TOOLS / "shop" / "viral_shop.py"), "--pasta", str(base), "--quantos", "40"],
                           capture_output=True, text=True, timeout=900, cwd=str(PONTE))
        except Exception as e:   # noqa: BLE001
            log(f"auto: viral_shop falhou ({str(e)[:100]})")
            return
    if not nomes():
        avisa_1x("shop-sem-produto", f"🛒 Shop: {feitos}/{meta} hoje e não achei produto novo.", log, 240)
        return
    r = SHP.acao("shop_fazer", {"nomes_lista": True, "quantos": min(2, meta - feitos)})
    log(f"auto: Shop {feitos}/{meta} hoje → lote de até 3 ({'ok' if r.get('ok') else r.get('erro')})")


def laco(CAN, SHP, EDI, versao, drive_raiz, detto, cfg_painel, reinicia, log=print):
    """roda para sempre na thread do painel; qualquer erro só vai para o registro"""
    ult_status = ult_upd = ult_shop = 0.0
    time.sleep(20)
    while True:
        try:
            acompanha_rodadas(CAN)
            cp = cfg_painel() or {}
            t = time.time()
            if t - ult_status >= 300:
                ult_status = t
                s = monta_status(CAN, SHP, EDI, versao)
                grava_status(s, pasta_status(drive_raiz(), detto()))
                confere_alertas(s, cp, log)
            if t - ult_shop >= 120 and cp.get("shop_auto", True):
                ult_shop = t
                shop_meta(CAN, SHP, EDI, cp, log)
            if cp.get("auto_atualizar", True) and t - ult_upd >= 1800:
                ult_upd = t
                if atualiza_se_preciso(CAN, SHP, EDI, log):
                    time.sleep(3)
                    reinicia()
                    return
        except Exception as e:   # noqa: BLE001
            log(f"auto: erro no laço ({str(e)[:160]})")
        time.sleep(30)
