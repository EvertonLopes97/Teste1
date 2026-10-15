# -*- coding: utf-8 -*-
"""POSTAGEM AUTOMÁTICA no Instagram (Reels) e no TikTok, pelas APIs oficiais.

    python tools\\postar\\postar.py                                  → uma rodada: posta o próximo de cada conta que estiver na hora
    python tools\\postar\\postar.py --agendar                        → o Windows roda a cada 20 min (PC ligado)
    python tools\\postar\\postar.py --login instagram --conta detto.galo
    python tools\\postar\\postar.py --login tiktok --conta detto.galo
    python tools\\postar\\postar.py --login tiktok --conta detto.tv
    python tools\\postar\\postar.py --status                         → fila, postados e rascunhos pendentes de cada conta
    python tools\\postar\\postar.py --agora video.mp4 --para instagram:detto.galo   (posta já, fora da fila)

PASTA (padrão E:\\DETTO\\postar):
  entrada\\instagram_detto.galo\\, entrada\\tiktok_detto.galo\\, entrada\\tiktok_detto.tv\\ …
      FILA: jogue o vídeo (.mp4) e, se quiser, um .txt com o MESMO NOME (legenda + tags). Sai na ordem do nome.
      Os reels automáticos (tools\\reels\\reels.py) já caem aqui sozinhos.
  postados\\<conta>\\   o que já foi (vídeo + .json com o link);  falhas\\<conta>\\  o que deu erro 3 vezes
  config.json         chaves dos apps (Meta / TikTok), contas, intervalo entre posts, horário
  tokens\\             logins (renovam sozinhos)

INSTAGRAM: posta de verdade (Reels, com legenda), sozinho. Até ~100 por dia pela API.
TIKTOK: até o TikTok aprovar o app ("audit"), vai como RASCUNHO para a caixa de entrada do TikTok da conta:
  você recebe a notificação no celular, abre, cola a legenda (fica em legendas_tiktok_<conta>.txt) e toca em Publicar.
  O TikTok deixa no máximo 5 rascunhos pendentes por conta: o sistema só manda o próximo quando tiver vaga.
  Com o app aprovado, mude "modo": "direto" no config.json e passa a postar sozinho, com legenda.
"""
import argparse
import datetime as dt
import hashlib
from http import server as hserver
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

AQUI = Path(__file__).resolve().parent
GRAPH = "https://graph.facebook.com"
TT = "https://open.tiktokapis.com"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}

CONFIG_PADRAO = {
    "instagram": {"app_id": "", "app_secret": "", "config_id": "", "versao": "v23.0", "porta_login": 8724},
    "tiktok": {"client_key": "", "client_secret": "", "redirect": "http://localhost:8723/callback/", "modo": "rascunho", "ia": False},
    "contas": [
        {"plataforma": "instagram", "conta": "detto.galo", "intervalo_min": 80, "horas": "08-23"},
        {"plataforma": "tiktok", "conta": "detto.galo", "intervalo_min": 80, "horas": "08-23"},
        {"plataforma": "tiktok", "conta": "detto.tv", "intervalo_min": 120, "horas": "08-23"},
    ],
}


def log(m):
    print(f"[{dt.datetime.now():%H:%M}] {m}", flush=True)


def le_json(f, padrao):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def grava_json(f, d):
    Path(f).parent.mkdir(parents=True, exist_ok=True)
    Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def pasta_padrao():
    if os.name == "nt" and Path("E:/").exists():
        return Path("E:/DETTO/postar")
    return Path.home() / "DETTO" / "postar"


def prepara(base):
    cfg_f = base / "config.json"
    if not cfg_f.exists():
        grava_json(cfg_f, CONFIG_PADRAO)
    cfg = json.loads(json.dumps(CONFIG_PADRAO))
    lido = le_json(cfg_f, {})
    for k, v in lido.items():
        cfg[k] = {**cfg.get(k, {}), **v} if isinstance(v, dict) and isinstance(cfg.get(k), dict) else v
    for c in cfg["contas"]:
        for p in ("entrada", "postados", "falhas"):
            (base / p / chave(c)).mkdir(parents=True, exist_ok=True)
    (base / "tokens").mkdir(exist_ok=True)
    leia = base / "LEIA-ME.txt"
    if not leia.exists() and (AQUI / "LEIA-ME.txt").exists():
        shutil.copyfile(AQUI / "LEIA-ME.txt", leia)
    return cfg


def chave(c):
    return f"{c['plataforma']}_{c['conta']}"


# ------------------------------------------------------------------ HTTP (sem dependências)
def http(metodo, url, dados=None, cab=None, corpo=None, tempo=120):
    cab = dict(cab or {})
    if dados is not None and corpo is None:
        if cab.get("Content-Type", "").startswith("application/json"):
            corpo = json.dumps(dados).encode()
        else:
            corpo = urllib.parse.urlencode(dados).encode()
            cab.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=corpo, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=tempo) as r:
            txt = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "replace")
        try:
            j = json.loads(txt)
        except ValueError:
            j = {"raw": txt[:500]}
        raise RuntimeError(f"HTTP {e.code}: {json.dumps(j, ensure_ascii=False)[:600]}") from None
    try:
        return json.loads(txt) if txt else {}
    except ValueError:
        return {"raw": txt}


def espera_codigo(porta, caminho="/"):
    """servidor local que recebe o ?code= do login (o navegador volta para http://localhost:PORTA/...)"""
    achado = {}

    class H(hserver.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            achado.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            ok = "code" in achado
            self.wfile.write(f"<h2>{'Pronto! Pode fechar esta aba.' if ok else 'Login não concluído: ' + achado.get('error_description', achado.get('error', '?'))}</h2>".encode())

        def log_message(self, *a):
            pass

    srv = hserver.HTTPServer(("127.0.0.1", porta), H)
    t = threading.Thread(target=srv.handle_request, daemon=True)
    t.start()
    t.join(timeout=600)
    srv.server_close()
    return achado


# ------------------------------------------------------------------ INSTAGRAM (Facebook Login for Business + envio direto do arquivo)
def ig_login(cfg, base, conta, token_colado=None):
    ic = cfg["instagram"]
    if not ic.get("app_id") or not ic.get("app_secret"):
        sys.exit("Preencha instagram.app_id e instagram.app_secret no config.json (LEIA-ME, parte INSTAGRAM).")
    v, porta = ic["versao"], int(ic.get("porta_login", 8724))
    if token_colado:
        # plano B: token gerado no Graph API Explorer (developers.facebook.com/tools/explorer)
        curto = token_colado.strip()
    else:
        redir = f"http://localhost:{porta}/"
        estado = secrets.token_urlsafe(12)
        perm = {"config_id": ic["config_id"]} if ic.get("config_id") else {
            "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,business_management"}
        url = (f"https://www.facebook.com/{v}/dialog/oauth?" + urllib.parse.urlencode({
            "client_id": ic["app_id"], "redirect_uri": redir, "state": estado, "response_type": "code", **perm}))
        print(f"Abrindo o navegador para entrar com o Facebook ligado ao Instagram @{conta}...\n{url}")
        webbrowser.open(url)
        r = espera_codigo(porta)
        if r.get("state") != estado or "code" not in r:
            sys.exit(f"Login cancelado ou inválido: {r}\nPlano B: --login instagram --conta {conta} --token <token do Graph API Explorer>")
        curto = http("GET", f"{GRAPH}/{v}/oauth/access_token?" + urllib.parse.urlencode(
            {"client_id": ic["app_id"], "client_secret": ic["app_secret"], "redirect_uri": redir, "code": r["code"]}))["access_token"]
    longo = http("GET", f"{GRAPH}/{v}/oauth/access_token?" + urllib.parse.urlencode(
        {"grant_type": "fb_exchange_token", "client_id": ic["app_id"], "client_secret": ic["app_secret"], "fb_exchange_token": curto}))["access_token"]
    pags = http("GET", f"{GRAPH}/{v}/me/accounts?" + urllib.parse.urlencode(
        {"fields": "name,access_token,instagram_business_account{id,username}", "access_token": longo}))
    achou = None
    for p in pags.get("data", []):
        ig = p.get("instagram_business_account") or {}
        print(f"   página {p.get('name')}: Instagram @{ig.get('username', '-')}")
        if ig.get("username", "").lower() == conta.lower().lstrip("@"):
            achou = (p, ig)
    if not achou:
        sys.exit(f"Não achei o Instagram @{conta} ligado a uma página sua. Confira: Instagram profissional + ligado à página do Facebook (LEIA-ME).")
    p, ig = achou
    # o token da página tirado do token longo do usuário não expira
    grava_json(base / "tokens" / f"instagram_{conta}.json", {"ig_id": ig["id"], "username": ig["username"], "pagina": p["name"], "token": p["access_token"]})
    print(f"Instagram @{ig['username']} ligado (página {p['name']}).")


def ig_posta(cfg, base, conta, video, legenda):
    tk = le_json(base / "tokens" / f"instagram_{conta}.json", None)
    if not tk:
        raise RuntimeError(f"Instagram @{conta} sem login: python tools\\postar\\postar.py --login instagram --conta {conta}")
    v, igid, token = cfg["instagram"]["versao"], tk["ig_id"], tk["token"]
    # 1) contêiner de Reels com envio direto do arquivo (não precisa hospedar o vídeo)
    c = http("POST", f"{GRAPH}/{v}/{igid}/media", {"media_type": "REELS", "upload_type": "resumable", "caption": legenda[:2200],
                                                  "share_to_feed": "true", "access_token": token})
    cid, uri = c["id"], c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{v}/{c['id']}"
    dados = Path(video).read_bytes()
    up = http("POST", uri, cab={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(dados))}, corpo=dados, tempo=900)
    if not up.get("success", True):
        raise RuntimeError(f"envio do arquivo recusado: {up}")
    # 2) espera o Instagram processar
    for _ in range(90):
        st = http("GET", f"{GRAPH}/{v}/{cid}?" + urllib.parse.urlencode({"fields": "status_code,status", "access_token": token}))
        sc = st.get("status_code")
        if sc == "FINISHED":
            break
        if sc in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram não aceitou o vídeo: {st.get('status')}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram demorou demais para processar o vídeo")
    # 3) publica
    pub = http("POST", f"{GRAPH}/{v}/{igid}/media_publish", {"creation_id": cid, "access_token": token})
    mid = pub["id"]
    link = http("GET", f"{GRAPH}/{v}/{mid}?" + urllib.parse.urlencode({"fields": "permalink", "access_token": token})).get("permalink", "")
    return {"id": mid, "link": link}


def ig_limite(cfg, base, conta):
    tk = le_json(base / "tokens" / f"instagram_{conta}.json", None)
    if not tk:
        return None
    try:
        r = http("GET", f"{GRAPH}/{cfg['instagram']['versao']}/{tk['ig_id']}/content_publishing_limit?" + urllib.parse.urlencode(
            {"fields": "quota_usage,config", "access_token": tk["token"]}))
        d = (r.get("data") or [{}])[0]
        return d.get("quota_usage"), (d.get("config") or {}).get("quota_total")
    except Exception:
        return None


# ------------------------------------------------------------------ TIKTOK (Content Posting API)
def tt_login(cfg, base, conta):
    tc = cfg["tiktok"]
    if not tc.get("client_key") or not tc.get("client_secret"):
        sys.exit("Preencha tiktok.client_key e tiktok.client_secret no config.json (LEIA-ME, parte TIKTOK).")
    redir = tc["redirect"]
    escopos = "user.info.basic,video.upload" + (",video.publish" if tc.get("modo") == "direto" else "")
    estado = secrets.token_urlsafe(12)
    params = {"client_key": tc["client_key"], "scope": escopos, "response_type": "code", "redirect_uri": redir, "state": estado}
    verificador = None
    local = urllib.parse.urlparse(redir).hostname in ("localhost", "127.0.0.1")
    if local:
        # app de computador: PKCE (o TikTok usa o SHA-256 em hexadecimal)
        verificador = secrets.token_urlsafe(48)[:64]
        params.update({"code_challenge": hashlib.sha256(verificador.encode()).hexdigest(), "code_challenge_method": "S256"})
    url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)
    print(f"Abrindo o navegador: entre no TikTok com a conta @{conta} e autorize.\n{url}")
    webbrowser.open(url)
    if local:
        r = espera_codigo(urllib.parse.urlparse(redir).port or 80)
    else:
        volta = input("Depois de autorizar, cole aqui o endereço COMPLETO da página para onde o TikTok te mandou: ").strip()
        r = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(volta).query).items()}
    if r.get("state") != estado or "code" not in r:
        sys.exit(f"Login cancelado ou inválido: {r}")
    corpo = {"client_key": tc["client_key"], "client_secret": tc["client_secret"], "code": r["code"], "grant_type": "authorization_code", "redirect_uri": redir}
    if verificador:
        corpo["code_verifier"] = verificador
    tok = http("POST", f"{TT}/v2/oauth/token/", corpo)
    if "access_token" not in tok:
        sys.exit(f"TikTok recusou o login: {tok}")
    tok["expira"] = time.time() + int(tok.get("expires_in", 86400)) - 120
    grava_json(base / "tokens" / f"tiktok_{conta}.json", tok)
    info = http("GET", f"{TT}/v2/user/info/?fields=display_name", cab={"Authorization": f"Bearer {tok['access_token']}"})
    nome = ((info.get("data") or {}).get("user") or {}).get("display_name", "?")
    print(f"TikTok ligado: {nome} (salvo como {conta}). Confira se é a conta certa!")


def tt_token(cfg, base, conta):
    f = base / "tokens" / f"tiktok_{conta}.json"
    tok = le_json(f, None)
    if not tok:
        raise RuntimeError(f"TikTok @{conta} sem login: python tools\\postar\\postar.py --login tiktok --conta {conta}")
    if time.time() > tok.get("expira", 0):
        novo = http("POST", f"{TT}/v2/oauth/token/", {"client_key": cfg["tiktok"]["client_key"], "client_secret": cfg["tiktok"]["client_secret"],
                                                       "grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
        if "access_token" not in novo:
            raise RuntimeError(f"login do TikTok @{conta} venceu: faça --login de novo ({novo})")
        novo["expira"] = time.time() + int(novo.get("expires_in", 86400)) - 120
        tok.update(novo)
        grava_json(f, tok)
    return tok["access_token"]


def tt_status(token, publish_id):
    r = http("POST", f"{TT}/v2/post/publish/status/fetch/", {"publish_id": publish_id},
             cab={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"})
    return (r.get("data") or {}).get("status", "?")


def tt_pendentes(cfg, base, conta):
    """rascunhos enviados que você ainda não publicou no app (o TikTok aceita no máximo 5)"""
    f = base / "postados" / f"tiktok_{conta}" / "_rascunhos.json"
    lista = le_json(f, [])
    if not lista:
        return 0, lista
    token = tt_token(cfg, base, conta)
    vivos = []
    for r in lista:
        try:
            st = tt_status(token, r["publish_id"])
        except Exception:
            st = "?"
        r["status"] = st
        # ainda na caixa de entrada = pendente; publicado/falhou/sumiu (>24 h) = libera a vaga
        if st in ("SEND_TO_USER_INBOX", "PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD") and time.time() - r["quando"] < 86400:
            vivos.append(r)
    grava_json(f, vivos)
    return len(vivos), vivos


def tt_posta(cfg, base, conta, video, legenda):
    tc = cfg["tiktok"]
    token = tt_token(cfg, base, conta)
    cab = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    tam = Path(video).stat().st_size
    # pedaços de 10 MB (o último leva o resto); arquivo pequeno vai inteiro
    pedaco = tam if tam < 10 * 1024 * 1024 else 10 * 1024 * 1024
    n = max(1, tam // pedaco)
    fonte = {"source": "FILE_UPLOAD", "video_size": tam, "chunk_size": pedaco, "total_chunk_count": n}
    if tc.get("modo") == "direto":
        info = http("POST", f"{TT}/v2/post/publish/creator_info/query/", {}, cab=cab).get("data", {})
        opcoes = info.get("privacy_level_options") or ["SELF_ONLY"]
        corpo = {"post_info": {"title": legenda[:2200], "privacy_level": "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in opcoes else opcoes[0],
                               "disable_duet": False, "disable_stitch": False, "disable_comment": False, "brand_content_toggle": False,
                               "brand_organic_toggle": False, "is_aigc": bool(tc.get("ia"))}, "source_info": fonte}
        r = http("POST", f"{TT}/v2/post/publish/video/init/", corpo, cab=cab)
    else:
        r = http("POST", f"{TT}/v2/post/publish/inbox/video/init/", {"source_info": fonte}, cab=cab)
    d = r.get("data") or {}
    if not d.get("upload_url"):
        raise RuntimeError(f"TikTok não abriu o envio: {r}")
    tipo = {".mov": "video/quicktime", ".webm": "video/webm"}.get(Path(video).suffix.lower(), "video/mp4")
    with open(video, "rb") as fh:
        for k in range(n):
            ini = k * pedaco
            fim = tam - 1 if k == n - 1 else ini + pedaco - 1
            fh.seek(ini)
            bloco = fh.read(fim - ini + 1)
            http("PUT", d["upload_url"], cab={"Content-Type": tipo, "Content-Length": str(len(bloco)), "Content-Range": f"bytes {ini}-{fim}/{tam}"},
                 corpo=bloco, tempo=900)
    pid = d.get("publish_id", "")
    for _ in range(60):
        st = tt_status(token, pid)
        if st in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
            break
        if st == "FAILED":
            raise RuntimeError("TikTok recusou o vídeo (status FAILED)")
        time.sleep(5)
    if tc.get("modo") != "direto":
        f = base / "postados" / f"tiktok_{conta}" / "_rascunhos.json"
        lista = le_json(f, [])
        lista.append({"publish_id": pid, "video": Path(video).name, "quando": time.time()})
        grava_json(f, lista)
        # a legenda vai para um arquivo fácil de copiar (o rascunho chega sem legenda)
        with open(base / f"legendas_tiktok_{conta}.txt", "a", encoding="utf-8") as g:
            g.write(f"\n===== {dt.datetime.now():%d/%m %H:%M} — {Path(video).name} =====\n{legenda}\n")
    return {"id": pid, "link": "", "modo": tc.get("modo", "rascunho")}


# ------------------------------------------------------------------ fila
def legenda_de(video):
    """o .txt com o mesmo nome: tudo antes de '---' (o resto é anotação: texto da tela, link do original)"""
    for txt in (Path(video).with_suffix(".txt"),):
        if txt.exists():
            return txt.read_text(encoding="utf-8").split("\n---")[0].strip()
    return ""


def na_hora(c, ultimo):
    h0, h1 = (int(x) for x in str(c.get("horas", "08-23")).split("-"))
    agora = dt.datetime.now()
    if not (h0 <= agora.hour <= h1):
        return False
    return not ultimo or (agora - ultimo).total_seconds() >= c.get("intervalo_min", 80) * 60


def posta_um(cfg, base, c, video):
    leg = legenda_de(video)
    if c["plataforma"] == "instagram":
        return ig_posta(cfg, base, c["conta"], video, leg)
    return tt_posta(cfg, base, c["conta"], video, leg)


def rodada(cfg, base):
    estado = le_json(base / "estado.json", {})
    for c in cfg["contas"]:
        k = chave(c)
        fila = sorted(p for p in (base / "entrada" / k).iterdir() if p.suffix.lower() in VIDEO_EXT)
        if not fila:
            continue
        ultimo = dt.datetime.fromisoformat(estado[k]["ultimo"]) if estado.get(k, {}).get("ultimo") else None
        if not na_hora(c, ultimo):
            continue
        if c["plataforma"] == "tiktok" and cfg["tiktok"].get("modo") != "direto":
            try:
                n, _ = tt_pendentes(cfg, base, c["conta"])
            except Exception as e:
                log(f"{k}: não consegui ver os rascunhos ({e})")
                continue
            if n >= 5:
                log(f"{k}: 5 rascunhos esperando você publicar no app — o próximo vai quando liberar")
                continue
        video = fila[0]
        log(f"{k}: postando {video.name} ({len(fila)} na fila)")
        try:
            r = posta_um(cfg, base, c, video)
        except Exception as e:
            falhas = estado.setdefault(k, {}).setdefault("falhas", {})
            falhas[video.name] = falhas.get(video.name, 0) + 1
            log(f"{k}: ERRO ({falhas[video.name]}/3): {e}")
            if falhas[video.name] >= 3:
                for f in [video, video.with_suffix(".txt")]:
                    if f.exists():
                        shutil.move(str(f), str(base / "falhas" / k / f.name))
                log(f"{k}: {video.name} foi para falhas\\ (3 erros seguidos)")
            grava_json(base / "estado.json", estado)
            continue
        destino = base / "postados" / k
        for f in [video, video.with_suffix(".txt")]:
            if f.exists():
                shutil.move(str(f), str(destino / f.name))
        grava_json(destino / f"{video.stem}.json", {"quando": dt.datetime.now().isoformat(timespec="seconds"), **r})
        estado.setdefault(k, {})["ultimo"] = dt.datetime.now().isoformat(timespec="seconds")
        estado[k].setdefault("falhas", {}).pop(video.name, None)
        grava_json(base / "estado.json", estado)
        log(f"{k}: OK {'(rascunho no app do TikTok: abra a notificação e publique)' if r.get('modo') == 'rascunho' else r.get('link', '')}")


def status(cfg, base):
    estado = le_json(base / "estado.json", {})
    for c in cfg["contas"]:
        k = chave(c)
        fila = [p for p in (base / "entrada" / k).iterdir() if p.suffix.lower() in VIDEO_EXT]
        feitos = [p for p in (base / "postados" / k).glob("*.json") if not p.name.startswith("_")]
        extra = ""
        if c["plataforma"] == "instagram":
            lim = ig_limite(cfg, base, c["conta"])
            extra = f" | limite hoje: {lim[0]}/{lim[1]}" if lim else " | sem login"
        elif cfg["tiktok"].get("modo") != "direto":
            try:
                n, _ = tt_pendentes(cfg, base, c["conta"])
                extra = f" | rascunhos esperando você: {n}/5"
            except Exception:
                extra = " | sem login"
        print(f"{k}: {len(fila)} na fila, {len(feitos)} postados, último {estado.get(k, {}).get('ultimo', '-')}{extra}")


def agendar(base):
    if os.name != "nt":
        sys.exit("O agendamento é do Windows. Aqui use o cron.")
    bat = base / "postar.bat"
    bat.write_text(f'@echo off\n"{sys.executable}" "{Path(__file__).resolve()}" --pasta "{base}" >> "{base / "postar.log"}" 2>&1\n', encoding="utf-8")
    r = subprocess.run(["schtasks", "/Create", "/F", "/SC", "MINUTE", "/MO", "20", "/TN", "DETTO postar", "/TR", f'"{bat}"'], capture_output=True, text=True)
    print(r.stdout or r.stderr)
    if r.returncode == 0:
        print(f"Agendado: confere a fila a cada 20 min (respeita intervalo e horário de cada conta). Log: {base / 'postar.log'}")
        print('Tirar: schtasks /Delete /TN "DETTO postar" /F')


def enfileira(base, video, destinos, legenda_txt=None, nome=None):
    """põe um vídeo pronto na fila das contas ("instagram:detto.galo", "tiktok:detto.tv"...). Usado pelos reels.
    nome = nome do arquivo na fila (padrão: o do vídeo)."""
    out = []
    for d in destinos:
        plat, conta = d.split(":", 1)
        pasta = Path(base) / "entrada" / f"{plat}_{conta}"
        pasta.mkdir(parents=True, exist_ok=True)
        alvo = pasta / (nome or Path(video).name)
        try:
            os.link(video, alvo)  # mesmo disco: não gasta espaço
        except OSError:
            shutil.copyfile(video, alvo)
        if legenda_txt and Path(legenda_txt).exists():
            shutil.copyfile(legenda_txt, alvo.with_suffix(".txt"))
        out.append(alvo)
    return out


def main():
    ap = argparse.ArgumentParser(description="postagem automática Instagram + TikTok")
    ap.add_argument("--pasta", default=str(pasta_padrao()))
    ap.add_argument("--login", choices=["instagram", "tiktok"])
    ap.add_argument("--conta")
    ap.add_argument("--token", help="(Instagram, plano B) token do Graph API Explorer")
    ap.add_argument("--agendar", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--agora", help="vídeo para postar já (fora da fila)")
    ap.add_argument("--para", help="instagram:detto.galo / tiktok:detto.tv (com --agora)")
    a = ap.parse_args()
    base = Path(a.pasta)
    cfg = prepara(base)
    if a.login:
        if not a.conta:
            sys.exit("Diga a conta: --conta detto.galo")
        return ig_login(cfg, base, a.conta, a.token) if a.login == "instagram" else tt_login(cfg, base, a.conta)
    if a.agendar:
        return agendar(base)
    if a.status:
        return status(cfg, base)
    if a.agora:
        plat, conta = (a.para or "").split(":", 1)
        r = posta_um(cfg, base, {"plataforma": plat, "conta": conta}, Path(a.agora))
        print(json.dumps(r, ensure_ascii=False))
        return
    rodada(cfg, base)


if __name__ == "__main__":
    main()
