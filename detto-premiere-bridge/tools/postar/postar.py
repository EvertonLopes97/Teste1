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
TIKTOK: pelo TIKTOK STUDIO (padrão "modo": "studio"): nada vai pela API; o painel planeja os horários e prepara
  a pasta com os vídeos + legendas, você agenda no site e marca "Agendei". (O TikTok não aprova app para postar
  nas próprias contas; "rascunho"/"direto" pela API continuam disponíveis no config.json.)
"""
import argparse
import datetime as dt
import hashlib
from http import server as hserver
import json
import re
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
GRAPH_IG = "https://graph.instagram.com"  # API do Instagram com login do Instagram (token "IGAA...")
TT = "https://open.tiktokapis.com"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}

CONFIG_PADRAO = {
    "pausado": False,  # true = não posta nada (o painel tem o botão)
    "instagram": {"app_id": "", "app_secret": "", "config_id": "", "versao": "v23.0", "porta_login": 8724},
    "tiktok": {"client_key": "", "client_secret": "", "redirect": "http://localhost:8723/callback/", "modo": "studio", "ia": False},
    "contas": [
        # intervalo_min = minutos entre posts; horas = janela do dia; max_dia = 0 sem limite; ativo = false pausa só esta conta
        # Instagram: teste = posta como REELS TESTE (só para quem não te segue); graduar "manual" = você manda para os
        # seguidores no app quando bater a meta_views (o painel avisa); "automatico" = o Instagram decide pelo desempenho
        # facebook = posta o mesmo vídeo (Reels) na página do Facebook ligada ao Instagram, logo depois do Instagram
        {"plataforma": "instagram", "conta": "detto.galo", "intervalo_min": 80, "horas": "08-23", "max_dia": 0, "ativo": True,
         "teste": True, "graduar": "manual", "meta_views": 10000, "facebook": True, "max_teste": 0},
        {"plataforma": "tiktok", "conta": "detto.galo", "intervalo_min": 80, "horas": "08-23", "max_dia": 0, "ativo": True},
        {"plataforma": "tiktok", "conta": "detto.tv", "intervalo_min": 120, "horas": "08-23", "max_dia": 0, "ativo": True},
    ],
}


LOG_F = None  # prepara() aponta para <pasta>/postar.log (o painel mostra)


def log(m):
    linha = f"[{dt.datetime.now():%d/%m %H:%M}] {m}"
    print(linha, flush=True)
    if LOG_F:
        try:
            with open(LOG_F, "a", encoding="utf-8") as f:
                f.write(linha + "\n")
        except OSError:
            pass


def le_json(f, padrao):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def grava_json(f, d):
    """gravação ATÔMICA (26/out): write_text apaga o arquivo e escreve depois — quem lesse no meio pegava um JSON
    pela metade. No estado.json isso APAGAVA a pausa da conta: o le_json devolvia {} sem reclamar e a rodada
    seguinte achava que a conta estava livre, tentava de novo e o Instagram bloqueava mais ainda. Agora escreve
    num .tmp e troca de nome de uma vez (os.replace), então quem lê sempre vê um arquivo inteiro."""
    f = Path(f)
    f.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(d, ensure_ascii=False, indent=1)
    tmp = f.with_name(f.name + f".tmp{os.getpid()}")
    tmp.write_text(txt, encoding="utf-8")
    if f.name == "estado.json" and f.exists():
        try:
            shutil.copy2(f, f.with_suffix(".bak"))  # cópia de segurança: se o estado estragar, não perde a pausa
        except OSError:
            pass
    os.replace(tmp, f)


def le_estado(base):
    """estado.json, com a cópia de segurança quando o arquivo estiver estragado (senão um estado ilegível viraria
    {} e a conta perderia a pausa e a contagem do dia)"""
    f = Path(base) / "estado.json"
    d = le_json(f, None)
    if isinstance(d, dict):
        return d
    if f.exists():
        d = le_json(f.with_suffix(".bak"), None)
        log("estado.json estava estragado — voltei pela cópia de segurança" if isinstance(d, dict)
            else "estado.json estava estragado e não tinha cópia — começando do zero")
        if isinstance(d, dict):
            return d
    return {}


def muda_estado(base, fn):
    """relê o estado do disco, aplica a mudança e grava. O painel e a tarefa do Windows rodam juntos: quem gravava
    um estado lido minutos antes apagava o que o outro tinha escrito no meio (era assim que a pausa de 24 h sumia).
    Devolve o estado já gravado."""
    estado = le_estado(base)
    fn(estado)
    grava_json(Path(base) / "estado.json", estado)
    return estado


def pausa_conta(base, estado, k, segundos, motivo=""):
    """pausa a conta: grava relendo do disco (para não apagar o que outro processo escreveu) e deixa o motivo à
    vista no painel"""
    ate = time.time() + segundos
    def aplica(e):
        c = e.setdefault(k, {})
        c["pausa_ate"] = max(c.get("pausa_ate", 0), ate)
        c["pausa_motivo"] = motivo
    muda_estado(base, aplica)
    c = estado.setdefault(k, {})
    c["pausa_ate"] = max(c.get("pausa_ate", 0), ate)
    c["pausa_motivo"] = motivo


def pasta_padrao():
    if os.name == "nt" and Path("E:/").exists():
        return Path("E:/DETTO/postar")
    return Path.home() / "DETTO" / "postar"


def prepara(base):
    global LOG_F
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    LOG_F = base / "postar.log"
    cfg_f = base / "config.json"
    if not cfg_f.exists():
        grava_json(cfg_f, CONFIG_PADRAO)
    cfg = json.loads(json.dumps(CONFIG_PADRAO))
    lido = le_json(cfg_f, {})
    for k, v in lido.items():
        cfg[k] = {**cfg.get(k, {}), **v} if isinstance(v, dict) and isinstance(cfg.get(k), dict) else v
    # TikTok: o padrão agora é o TikTok Studio (o TikTok não aprova app para postar nas próprias contas).
    # Quem ficou com "rascunho" sem nunca ter posto as chaves do app passa para "studio".
    if cfg["tiktok"].get("modo") == "rascunho" and not cfg["tiktok"].get("client_key"):
        cfg["tiktok"]["modo"] = "studio"
        d = le_json(cfg_f, {})
        d.setdefault("tiktok", {})["modo"] = "studio"
        grava_json(cfg_f, d)
    for c in cfg["contas"]:
        for k_, v_ in CONFIG_PADRAO["contas"][0].items():
            if k_ in ("teste", "graduar", "meta_views", "max_teste", "teste_cai_para_normal") and c.get("plataforma") != "instagram":
                continue
            c.setdefault(k_, v_ if k_ not in ("plataforma", "conta") else c.get(k_))
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
def ig_login_instagram(cfg, base, conta, token):
    """token da "API do Instagram com login do Instagram" (developers.facebook.com → app → Casos de uso → API do
    Instagram → Gerar token). Não precisa de Página do Facebook nem da chave do app. Vale 60 dias e renova sozinho."""
    v = cfg["instagram"]["versao"]
    eu = http("GET", f"{GRAPH_IG}/{v}/me?" + urllib.parse.urlencode({"fields": "user_id,username", "access_token": token}))
    nome = eu.get("username", "")
    if nome.lower() != conta.lower().lstrip("@"):
        sys.exit(f"Esse token é do Instagram @{nome}, não do @{conta}. Gere o token logado na conta certa.")
    grava_json(base / "tokens" / f"instagram_{conta}.json", {"ig_id": str(eu.get("user_id") or eu.get("id")), "username": nome,
                                                             "token": token, "host": "instagram", "renovado": time.time()})
    print(f"Instagram @{nome} ligado (login do Instagram, sem página).")


def ig_token(cfg, base, conta):
    """o token salvo; o do login do Instagram (60 dias) é renovado sozinho a cada ~20 dias"""
    f = base / "tokens" / f"instagram_{conta}.json"
    tk = le_json(f, None)
    if tk and tk.get("host") == "instagram" and time.time() - tk.get("renovado", 0) > 20 * 86400:
        try:
            r = http("GET", f"{GRAPH_IG}/refresh_access_token?" + urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": tk["token"]}))
            if r.get("access_token"):
                tk.update(token=r["access_token"], renovado=time.time())
                grava_json(f, tk)
                log(f"instagram_{conta}: token renovado")
        except Exception as e:
            log(f"instagram_{conta}: não consegui renovar o token ({e}); se passar de 60 dias, gere outro")
    return tk


def ig_host(tk):
    return GRAPH_IG if tk.get("host") == "instagram" else GRAPH


def ig_login(cfg, base, conta, token_colado=None):
    if token_colado and token_colado.strip().startswith("IG"):
        return ig_login_instagram(cfg, base, conta, token_colado.strip())
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
            "scope": "instagram_basic,instagram_content_publish,instagram_manage_insights,pages_show_list,pages_read_engagement,pages_manage_posts,business_management"}
        url = (f"https://www.facebook.com/{v}/dialog/oauth?" + urllib.parse.urlencode({
            "client_id": ic["app_id"], "redirect_uri": redir, "state": estado, "response_type": "code", **perm}))
        print(f"Abrindo o navegador para entrar com o Facebook ligado ao Instagram @{conta}...\n{url}")
        webbrowser.open(url)
        r = espera_codigo(porta)
        if r.get("state") != estado or "code" not in r:
            sys.exit(f"Login cancelado ou inválido: {r}\nPlano B: --login instagram --conta {conta} --token <token do Graph API Explorer>")
        curto = http("GET", f"{GRAPH}/{v}/oauth/access_token?" + urllib.parse.urlencode(
            {"client_id": ic["app_id"], "client_secret": ic["app_secret"], "redirect_uri": redir, "code": r["code"]}))["access_token"]
    try:
        longo = http("GET", f"{GRAPH}/{v}/oauth/access_token?" + urllib.parse.urlencode(
            {"grant_type": "fb_exchange_token", "client_id": ic["app_id"], "client_secret": ic["app_secret"], "fb_exchange_token": curto}))["access_token"]
    except Exception as e:
        print(f"   (não troquei por token longo: {e}; sigo com o token colado)")
        longo = curto
    achou = None
    try:
        pags = http("GET", f"{GRAPH}/{v}/me/accounts?" + urllib.parse.urlencode(
            {"fields": "name,access_token,instagram_business_account{id,username}", "access_token": longo}))
    except Exception as e:
        print(f"   (lista de páginas: {e})")
        pags = {}
    for p in pags.get("data", []):
        ig = p.get("instagram_business_account") or {}
        print(f"   página {p.get('name')}: Instagram @{ig.get('username', '-')}")
        if ig.get("username", "").lower() == conta.lower().lstrip("@"):
            achou = (p, ig)
    if not achou:
        # token gerado já como token da PÁGINA (Explorer com "Usuário ou Página" = a página)
        try:
            me = http("GET", f"{GRAPH}/{v}/me?" + urllib.parse.urlencode(
                {"fields": "id,name,instagram_business_account{id,username}", "access_token": longo}))
            ig = me.get("instagram_business_account") or {}
            print(f"   token da página {me.get('name')}: Instagram @{ig.get('username', '-')}")
            if ig.get("username", "").lower() == conta.lower().lstrip("@"):
                achou = ({"id": me.get("id"), "name": me.get("name"), "access_token": longo}, ig)
        except Exception as e:
            print(f"   (token como página: {e})")
    if not achou:
        sys.exit(f"Não achei o Instagram @{conta} ligado a uma página sua. Confira: Instagram profissional + ligado à página do Facebook (LEIA-ME).")
    p, ig = achou
    # o token da página tirado do token longo do usuário não expira
    grava_json(base / "tokens" / f"instagram_{conta}.json", {"ig_id": ig["id"], "username": ig["username"], "pagina": p["name"],
                                                             "pagina_id": p.get("id", ""), "token": p["access_token"]})
    print(f"Instagram @{ig['username']} ligado (página {p['name']}).")
    try:
        fb_permissao(cfg, base, conta)
        print(f"Facebook: a página {p['name']} pode receber os vídeos.")
    except Exception as e:
        print(f"Facebook: {e}")


def _multipart(url, campos, campo_arq, video, tempo=900):
    limite = "----detto" + secrets.token_hex(8)
    nome = Path(video).name.encode("ascii", "replace").decode().replace('"', "").replace("?", "_")
    corpo = b"".join(f"--{limite}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in campos.items())
    corpo += (f"--{limite}\r\nContent-Disposition: form-data; name=\"{campo_arq}\"; filename=\"{nome}\"\r\n"
              f"Content-Type: video/mp4\r\n\r\n").encode() + Path(video).read_bytes() + f"\r\n--{limite}--\r\n".encode()
    req = urllib.request.Request(url, data=corpo, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={limite}", "User-Agent": "detto-postar"})
    with urllib.request.urlopen(req, timeout=tempo) as r:
        return r.read().decode("utf-8", "replace").strip()


class VideoQuebrado(RuntimeError):
    """o arquivo não abre/decodifica: vai direto para falhas, sem gastar tentativas no Instagram"""


SEM_INTERNET = ("getaddrinfo failed", "errno 11001", "errno 11002", "name or service not known", "temporary failure in name resolution",
                "network is unreachable", "no route to host", "winerror 10051", "winerror 10065")


def normaliza_ig(video, pasta):
    """cópia no padrão que o Instagram aceita sempre: H.264 High 4:2:0, mesmo fps (até 60), GOP fechado de 2 s, até 1080x1920,
    ~8 Mbit/s, AAC 128k 48 kHz estéreo, moov no começo (faststart), cor BT.709. Mesmo vídeo = reaproveita."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    saida = pasta / (Path(video).stem[:80] + ".ig.mp4")
    if saida.exists() and saida.stat().st_mtime >= Path(video).stat().st_mtime and saida.stat().st_size > 1000:
        return saida
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True)
    tem_audio = bool(r.stdout.strip())
    def tenta(audio_original, fps_fixo, tolerante=0):
        vf = ("scale='if(gt(iw,1080),1080,iw)':-2:flags=lanczos,scale=trunc(iw/2)*2:trunc(ih/2)*2,"
              + ("fps=30," if fps_fixo else "fps='min(60,source_fps)',") + "format=yuv420p")
        cmd = ["ffmpeg", "-v", "error", "-y"]
        if tolerante:
            # vídeo com pedaço estragado (o decodificador parava: "Terminating thread with return code"): um fio só,
            # joga fora os quadros quebrados e, na última, corta o finalzinho (onde costuma estar o estrago)
            cmd += ["-threads", "1", "-fflags", "+genpts+discardcorrupt+igndts", "-err_detect", "ignore_err", "-ec", "3"]
            if tolerante > 1:
                d = duracao(video)
                if d > 3:
                    cmd += ["-t", f"{d - 0.6:.2f}"]
        else:
            cmd += ["-fflags", "+genpts", "-err_detect", "ignore_err"]
        cmd += ["-i", str(video)]
        if not audio_original:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        cmd += ["-map", "0:v:0", "-map", "0:a:0" if audio_original else "1:a:0", "-shortest",
                "-vf", vf, "-c:v", "libx264", "-profile:v", "high", "-level", "4.2", "-preset", "medium", "-crf", "20",
                "-maxrate", "12M", "-bufsize", "24M", "-force_key_frames", "expr:gte(t,n_forced*2)", "-sc_threshold", "0", "-bf", "2",
                "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(saida)]
        return subprocess.run(cmd, capture_output=True, text=True)

    # 1) normal; 2) áudio do vídeo vazio/quebrado ("stream received no packets") → silêncio no lugar;
    # 3) FFmpeg sem "source_fps" → 30 fps. O original quebrado o Instagram recusa (2207082 / código 0).
    erro = ""
    for audio_original, fps_fixo, tol in ((tem_audio, False, 0), (False, False, 0), (False, True, 0),
                                          (tem_audio, True, 1), (False, True, 1), (False, True, 2)):
        rr = tenta(audio_original, fps_fixo, tol)
        if rr.returncode == 0 and saida.exists() and saida.stat().st_size > 1000:
            if audio_original != tem_audio:
                log("   (o áudio deste vídeo estava vazio/quebrado: foi com silêncio)")
            if tol:
                log("   (o vídeo tinha um pedaço estragado: foi consertado" + (" e o finalzinho saiu)" if tol > 1 else ")"))
            return saida
        erro = rr.stderr.strip().splitlines()[-1][:200] if rr.stderr.strip() else f"código {rr.returncode}"
    # o original estragado o Instagram SEMPRE recusa (2207082 / código 0): não adianta mandar e gastar ação da conta
    raise VideoQuebrado(f"o arquivo do vídeo está estragado (o FFmpeg não consegue ler: {erro}) — refaça este reel")


def _confere_link(url, tamanho, log=log):
    """O LINK FUNCIONA MESMO? Baixa os primeiros bytes de fora e confere o tamanho. Sem isso o link ruim ia para o
    Instagram, ele não conseguia baixar (2207082 / código 0) e o vídeo gastava as 4 tentativas e caía nas falhas."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-65535"})
        with urllib.request.urlopen(req, timeout=90) as r:
            if r.status not in (200, 206):
                return f"respondeu {r.status}"
            tipo = (r.headers.get("Content-Type") or "").lower()
            if "html" in tipo:
                return f"devolveu página HTML em vez do vídeo ({tipo})"
            faixa = r.headers.get("Content-Range") or ""
            total = int(faixa.rsplit("/", 1)[-1]) if "/" in faixa and faixa.rsplit("/", 1)[-1].isdigit() else \
                int(r.headers.get("Content-Length") or 0)
            pedaco = r.read(65536)
        if not pedaco:
            return "não veio nenhum byte"
        if b"ftyp" not in pedaco[:64] and b"moov" not in pedaco[:4096]:
            return "o que veio não parece um MP4"
        if total and r.status == 206 and abs(total - tamanho) > 1024:
            return f"tamanho diferente ({total} em vez de {tamanho})"
        return ""
    except Exception as e:
        return str(e)[:150]


def _link_catbox(video, ctx):
    url = _multipart("https://catbox.moe/user/api.php", {"reqtype": "fileupload"}, "fileToUpload", video, tempo=600)
    if not url.startswith("https://"):
        raise RuntimeError(f"catbox: {url[:120]}")
    return url, None


def _link_litterbox(video, ctx):
    url = _multipart("https://litterbox.catbox.moe/resources/internals/api.php", {"reqtype": "fileupload", "time": "1h"},
                     "fileToUpload", video, tempo=600)
    if not url.startswith("https://"):
        raise RuntimeError(f"litterbox: {url[:120]}")
    return url, None


def _link_0x0(video, ctx):
    """0x0.st — upload anônimo simples, link direto (serve o arquivo com o tipo certo)"""
    url = _multipart("https://0x0.st", {"expires": "2"}, "file", video, tempo=600)
    if not url.startswith("https://"):
        raise RuntimeError(f"0x0: {url[:120]}")
    return url, None


def _link_tmpfiles(video, ctx):
    r = json.loads(_multipart("https://tmpfiles.org/api/v1/upload", {}, "file", video, tempo=600))
    url = (r.get("data") or {}).get("url", "")
    if not url.startswith("http"):
        raise RuntimeError(f"tmpfiles: {str(r)[:120]}")
    return url.replace("http://", "https://").replace("tmpfiles.org/", "tmpfiles.org/dl/", 1), None


def _cloudflared(base, log=log):
    """o programa do túnel (uma vez só, ~40 MB, direto do GitHub da Cloudflare)"""
    pasta = Path(base) / "ferramentas"
    pasta.mkdir(parents=True, exist_ok=True)
    exe = pasta / ("cloudflared.exe" if os.name == "nt" else "cloudflared")
    if exe.exists() and exe.stat().st_size > 1_000_000:
        return exe
    arq = {"nt": "cloudflared-windows-amd64.exe"}.get(os.name, "cloudflared-linux-amd64")
    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{arq}"
    log(f"túnel: baixando o cloudflared uma vez só ({url})...")
    tmp = exe.with_suffix(".baixando")
    req = urllib.request.Request(url, headers={"User-Agent": "detto-postar"})
    with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    tmp.replace(exe)
    if os.name != "nt":
        exe.chmod(0o755)
    log("túnel: cloudflared pronto.")
    return exe


def _link_tunel(video, ctx):
    """O VÍDEO FICA NO SEU PC e o Instagram baixa direto daqui, por um endereço público temporário da Cloudflare
    (cloudflared "quick tunnel", de graça e sem conta). Não depende de site de hospedagem — é o que funciona quando
    o Catbox e companhia estão fora do ar ou bloqueados pelo seu provedor. O endereço morre junto com o envio."""
    import http.server
    import socketserver
    import threading

    base, log_ = ctx["base"], ctx["log"]
    exe = _cloudflared(base, log_)
    video = Path(video)
    nome = secrets.token_hex(8) + ".mp4"  # nome sorteado: ninguém acha o endereço por acaso
    pasta = Path(base) / "tmp_tunel"
    shutil.rmtree(pasta, ignore_errors=True)
    pasta.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(video, pasta / nome)

    class Servidor(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(pasta), **k)

        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", 0), Servidor)
    porta = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    pr = subprocess.Popen([str(exe), "tunnel", "--url", f"http://127.0.0.1:{porta}", "--no-autoupdate"],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                          **({"creationflags": 0x08000000} if os.name == "nt" else {}))

    def fecha():
        for f in (pr.terminate, pr.kill):
            try:
                f()
                pr.wait(timeout=10)
                break
            except Exception:
                continue
        httpd.shutdown()
        shutil.rmtree(pasta, ignore_errors=True)

    try:
        url, fim = "", time.time() + 75
        while time.time() < fim and pr.poll() is None:
            linha = pr.stdout.readline()
            if not linha:
                continue
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", linha)
            if m:
                url = m.group(0)
                break
        if not url:
            raise RuntimeError("o cloudflared não abriu o endereço público (sua internet bloqueia o túnel?)")
        threading.Thread(target=lambda: [pr.stdout.readline() for _ in iter(int, 1)], daemon=True).start()
        time.sleep(4)  # o endereço leva uns segundos para valer em toda a Cloudflare
        return f"{url}/{nome}", fecha
    except Exception:
        fecha()
        raise


HOSPEDAGENS = {"tunel": ("seu PC (túnel Cloudflare)", _link_tunel), "catbox": ("Catbox", _link_catbox),
               "0x0": ("0x0.st", _link_0x0), "tmpfiles": ("tmpfiles", _link_tmpfiles), "litterbox": ("Litterbox", _link_litterbox)}
ORDEM_PADRAO = ["tunel", "catbox", "0x0", "tmpfiles", "litterbox"]


def link_temporario(video, cfg=None, base=None, conta=None, tentativa=0):
    """O Reels TESTE só funciona com o vídeo num link público (o envio direto do arquivo ignora o "teste" e posta
    normal). Devolve (url, fechar). Cada hospedagem é CONFERIDA antes de ir para o Instagram (baixa os primeiros
    bytes de fora): link que não serve é descartado na hora, em vez de virar erro 2207082 e queimar as tentativas.
    Ordem: o túnel do seu PC primeiro (não depende de ninguém), depois os sites. Troque em "hospedagem" no config."""
    ordem = [x for x in ((cfg or {}).get("instagram", {}).get("hospedagem") or ORDEM_PADRAO) if x in HOSPEDAGENS] or ORDEM_PADRAO
    ctx = {"base": Path(base or "."), "cfg": cfg or {}, "conta": conta, "log": log}
    tamanho = Path(video).stat().st_size
    erros = []
    for chave in ordem:
        nome, f = HOSPEDAGENS[chave]
        fechar = None
        try:
            url, fechar = f(video, ctx)
            ruim = _confere_link(url, tamanho)
            if ruim:
                raise RuntimeError(f"o link não serve: {ruim}")
            log(f"{conta or ''}: Reels TESTE — vídeo em {nome} (link conferido)")
            return url, fechar
        except Exception as e:
            erros.append(f"{nome}: {str(e)[:120]}")
            log(f"{conta or ''}: {nome} não deu certo ({str(e)[:140]})")
            if fechar:
                try:
                    fechar()
                except Exception:
                    pass
    raise RuntimeError("não consegui um link que o Instagram consiga baixar (" + " | ".join(erros)[:400]
                       + "). Tenta de novo na próxima rodada.")


def ig_posta(cfg, base, conta, video, legenda, teste=False, graduar="manual", tentativa=0):
    tk = ig_token(cfg, base, conta)
    if not tk:
        raise RuntimeError(f"Instagram @{conta} sem login: python tools\\postar\\postar.py --login instagram --conta {conta}")
    v, igid, token = cfg["instagram"]["versao"], tk["ig_id"], tk["token"]
    G = ig_host(tk)
    video = normaliza_ig(video, Path(base) / "tmp_ig")
    # 1) contêiner de Reels: normal = envio direto do arquivo; TESTE = vídeo num link temporário (o Instagram só
    #    respeita o "teste" desse jeito — com o envio direto ele ignorou e postou para todo mundo)
    params = {"media_type": "REELS", "upload_type": "resumable", "caption": legenda[:2200], "share_to_feed": "true", "access_token": token}
    if teste:
        # REELS TESTE: aparece só para quem não te segue; "MANUAL" = você manda para os seguidores no app,
        # "SS_PERFORMANCE" = o Instagram manda sozinho se for bem
        params["trial_params"] = json.dumps({"graduation_strategy": "SS_PERFORMANCE" if graduar == "automatico" else "MANUAL"})
        params.pop("share_to_feed")
        params.pop("upload_type")
        params["video_url"], fechar = link_temporario(video, cfg, base, conta, tentativa)
    else:
        fechar = None
    try:
        return _ig_publica(cfg, base, conta, video, params, teste, graduar, G, v, igid, token)
    finally:
        if fechar:
            try:
                fechar()  # derruba o túnel / apaga o arquivo temporário
            except Exception as e:
                log(f"{conta}: não consegui fechar a hospedagem temporária ({e})")


def _ig_publica(cfg, base, conta, video, params, teste, graduar, G, v, igid, token):
    try:
        c = http("POST", f"{G}/{v}/{igid}/media", params)
    except RuntimeError as e:
        if teste and "trial" in str(e).lower():
            raise RuntimeError(f"o Instagram não aceitou como Reels teste ({e}). Confira se a conta já tem 'Reels de teste' no app; "
                               f"ou desligue 'Reels teste' no painel") from None
        raise
    cid = c["id"]
    if not teste:
        uri = c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{v}/{c['id']}"
        dados = Path(video).read_bytes()
        up = http("POST", uri, cab={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(dados))}, corpo=dados, tempo=900)
        if not up.get("success", True):
            raise RuntimeError(f"envio do arquivo recusado: {up}")
    # 2) espera o Instagram processar
    for _ in range(90):
        st = http("GET", f"{G}/{v}/{cid}?" + urllib.parse.urlencode({"fields": "status_code,status", "access_token": token}))
        sc = st.get("status_code")
        if sc == "FINISHED":
            break
        if sc in ("ERROR", "EXPIRED"):
            dica = " (o Instagram não conseguiu baixar o vídeo do link)" if "2207082" in str(st.get("status")) else ""
            raise RuntimeError(f"Instagram não aceitou o vídeo: {st.get('status')}{dica}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram demorou demais para processar o vídeo")
    # 3) publica
    pub = http("POST", f"{G}/{v}/{igid}/media_publish", {"creation_id": cid, "access_token": token})
    mid = pub["id"]
    link = http("GET", f"{G}/{v}/{mid}?" + urllib.parse.urlencode({"fields": "permalink", "access_token": token})).get("permalink", "")
    return {"id": mid, "link": link, **({"teste": True, "graduar": graduar} if teste else {})}


def ig_views(cfg, base, conta, media_id):
    """visualizações de um reel (precisa da permissão instagram_manage_insights no login)"""
    tk = ig_token(cfg, base, conta)
    if not tk:
        return None
    v = cfg["instagram"]["versao"]
    for metrica in ("views", "plays"):
        try:
            r = http("GET", f"{ig_host(tk)}/{v}/{media_id}/insights?" + urllib.parse.urlencode({"metric": metrica, "access_token": tk["token"]}))
            d = (r.get("data") or [{}])[0]
            val = (d.get("values") or [{}])[0].get("value")
            if val is None:
                val = (d.get("total_value") or {}).get("value")
            if val is not None:
                return int(val)
        except RuntimeError as e:
            if "permission" in str(e).lower() or "(#10)" in str(e):
                raise RuntimeError("falta a permissão de estatísticas: refaça o login do Instagram no painel") from None
    return None


def ig_limite(cfg, base, conta):
    tk = ig_token(cfg, base, conta)
    if not tk:
        return None
    try:
        r = http("GET", f"{ig_host(tk)}/{cfg['instagram']['versao']}/{tk['ig_id']}/content_publishing_limit?" + urllib.parse.urlencode(
            {"fields": "quota_usage,config", "access_token": tk["token"]}))
        d = (r.get("data") or [{}])[0]
        return d.get("quota_usage"), (d.get("config") or {}).get("quota_total")
    except Exception:
        return None


# ------------------------------------------------------------------ FACEBOOK (página ligada ao Instagram)
def fb_pagina(cfg, base, conta):
    """(id da página, token da página, nome) — o mesmo login do Instagram (token da página)"""
    f = base / "tokens" / f"instagram_{conta}.json"
    tk = le_json(f, None)
    if not tk:
        raise RuntimeError(f"Instagram @{conta} sem login (o Facebook usa o mesmo login)")
    if tk.get("host") == "instagram":
        raise RuntimeError("o login atual é o 'login do Instagram', que não posta no Facebook: refaça o login do Instagram "
                           "no painel pelo Facebook (botão Conectar)")
    if not tk.get("pagina_id"):
        me = http("GET", f"{GRAPH}/{cfg['instagram']['versao']}/me?" + urllib.parse.urlencode({"fields": "id,name", "access_token": tk["token"]}))
        tk["pagina_id"] = me["id"]
        tk.setdefault("pagina", me.get("name", ""))
        grava_json(f, tk)
    return tk["pagina_id"], tk["token"], tk.get("pagina", "")


def _erro_fb(e):
    t = str(e)
    if "(#200)" in t or "pages_manage_posts" in t or "permission" in t.lower() or "(#10)" in t:
        return RuntimeError("falta a permissão de postar na página (pages_manage_posts): no app da Meta adicione a permissão "
                            "e refaça o login do Instagram no painel (LEIA-ME, parte FACEBOOK). Detalhe: " + t[:200])
    return e


def fb_permissao(cfg, base, conta):
    """confere se o token da página pode postar (sem postar nada). O token é de PÁGINA (não tem /me/permissions):
    pergunta ao /debug_token com a chave do app quais permissões ele carrega."""
    pid, token, _ = fb_pagina(cfg, base, conta)
    ic = cfg["instagram"]
    if not (ic.get("app_id") and ic.get("app_secret")):
        return True  # sem a chave do app não dá para conferir; a primeira postagem mostra
    r = http("GET", f"{GRAPH}/{ic['versao']}/debug_token?" + urllib.parse.urlencode(
        {"input_token": token, "access_token": f"{ic['app_id']}|{ic['app_secret']}"}))
    escopos = set((r.get("data") or {}).get("scopes") or [])
    if escopos and "pages_manage_posts" not in escopos:
        raise _erro_fb("pages_manage_posts")
    return True


def duracao(video):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                           capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def fb_posta(cfg, base, conta, video, legenda):
    """posta o vídeo na página do Facebook: Reels (até 90 s) ou vídeo normal (mais longo)"""
    pid, token, nome = fb_pagina(cfg, base, conta)
    v = cfg["instagram"]["versao"]
    try:
        if duracao(video) > 90:
            r = json.loads(_multipart(f"https://graph-video.facebook.com/{v}/{pid}/videos",
                                      {"description": legenda[:5000], "access_token": token}, "source", video, tempo=1800))
            if not r.get("id"):
                raise RuntimeError(f"Facebook recusou o vídeo: {r}")
            return {"id": r["id"], "link": f"https://www.facebook.com/{pid}/videos/{r['id']}", "pagina": nome}
        s = http("POST", f"{GRAPH}/{v}/{pid}/video_reels", {"upload_phase": "start", "access_token": token})
        vid = s["video_id"]
        dados = Path(video).read_bytes()
        up = http("POST", s.get("upload_url") or f"https://rupload.facebook.com/video-upload/{v}/{vid}",
                  cab={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(dados))}, corpo=dados, tempo=900)
        if not up.get("success", True):
            raise RuntimeError(f"envio do arquivo recusado: {up}")
        fim = http("POST", f"{GRAPH}/{v}/{pid}/video_reels", {"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                                                               "description": legenda[:5000], "access_token": token})
        if not fim.get("success", True):
            raise RuntimeError(f"Facebook não publicou: {fim}")
        for _ in range(36):  # até ~6 min processando
            st = http("GET", f"{GRAPH}/{v}/{vid}?" + urllib.parse.urlencode({"fields": "status", "access_token": token})).get("status") or {}
            fases = [st.get(x) or {} for x in ("uploading_phase", "processing_phase", "publishing_phase")]
            if any(f_.get("status") == "error" for f_ in fases) or st.get("video_status") == "error":
                erro = next((f_.get("errors") for f_ in fases if f_.get("errors")), None) or st
                raise RuntimeError(f"Facebook não aceitou o vídeo: {json.dumps(erro, ensure_ascii=False)[:300]}")
            if (st.get("publishing_phase") or {}).get("status") == "complete" or st.get("video_status") in ("ready", "published"):
                break
            time.sleep(10)
        return {"id": vid, "link": f"https://www.facebook.com/reel/{vid}", "pagina": nome}
    except RuntimeError as e:
        raise _erro_fb(e) from None


def fb_depois(cfg, base, c, video, estado, r):
    """depois do Instagram: o mesmo vídeo na página do Facebook. Falhou = fica pendente e tenta de novo nas próximas
    rodadas (até 3 vezes); o post do Instagram não é afetado."""
    k = chave(c)
    try:
        fb = fb_posta(cfg, base, c["conta"], video, legenda_de(video))
        r["facebook"] = fb
        log(f"{k}: Facebook OK {fb.get('link', '')}")
        estado.setdefault(k, {}).setdefault("fb_pendentes", {}).pop(Path(video).name, None)
    except Exception as e:
        pend = estado.setdefault(k, {}).setdefault("fb_pendentes", {})
        n = pend.get(Path(video).name, {}).get("n", 0) + 1
        r["facebook_erro"] = str(e)[:300]
        if n < 3:
            pend[Path(video).name] = {"n": n, "erro": str(e)[:300]}
        else:
            pend.pop(Path(video).name, None)
        log(f"{k}: Facebook ERRO ({n}/3): {e}")
    return r


def fb_pendentes(cfg, base, estado):
    """tenta de novo os vídeos que foram para o Instagram mas não para o Facebook"""
    for c in cfg["contas"]:
        if c["plataforma"] != "instagram" or c.get("facebook", True) is False:
            continue
        k = chave(c)
        for nome in list((estado.get(k, {}).get("fb_pendentes") or {}).keys()):
            video = base / "postados" / k / nome
            if not video.exists():
                estado[k]["fb_pendentes"].pop(nome, None)
                continue
            jf = video.with_suffix(".json")
            d = le_json(jf, {})
            d.pop("facebook_erro", None)
            fb_depois(cfg, base, c, video, estado, d)
            grava_json(jf, d)
        grava_json(base / "estado.json", estado)


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


def fila_de(base, k):
    """vídeos esperando na conta, na ordem de saída: a ordem arrumada no painel (_ordem.json) e depois o nome"""
    pasta = Path(base) / "entrada" / k
    if not pasta.exists():
        return []
    vids = [p for p in pasta.iterdir() if p.suffix.lower() in VIDEO_EXT]
    ordem = le_json(pasta / "_ordem.json", [])
    pos = {n: i for i, n in enumerate(ordem)}
    return sorted(vids, key=lambda p: (pos.get(p.name, 10 ** 6), p.name.lower()))


def janela(c):
    try:
        h0, h1 = (int(x) for x in str(c.get("horas", "08-23")).split("-"))
    except ValueError:
        h0, h1 = 8, 23
    return h0, h1


def postados_hoje(estado, k):
    h = estado.get(k, {}).get("hoje", {})
    return h.get("n", 0) if h.get("dia") == dt.date.today().isoformat() else 0


def teto_dia(c):
    """máximo de posts por dia. Instagram sem limite configurado = 10 (o Instagram limita os Reels teste pela API
    — falam em ~20/dia — e muitos posts/tentativas seguidos dão bloqueio de ações na conta, até no app)"""
    m = c.get("max_dia") or 0
    if not m and c.get("plataforma") == "instagram":
        return 10
    return m


def ig_e_teste(cfg, c):
    return c.get("plataforma") == "instagram" and bool(c.get("teste"))


def conta_tentativa_teste(estado, k):
    """conta as IDAS ao Instagram de Reels teste no dia (não só as que deram certo). Cada tentativa cria o
    contêiner lá, então a que volta com 2207078 também gasta o limite — contar só os sucessos fazia o sistema
    insistir a tarde toda."""
    e = estado.setdefault(k, {})
    t = e.setdefault("teste_hoje", {})
    hoje = dt.date.today().isoformat()
    if t.get("dia") != hoje:
        t.clear()
        t["dia"] = hoje
    t["n"] = t.get("n", 0) + 1
    return t["n"]


def teste_hoje(estado, k):
    t = estado.get(k, {}).get("teste_hoje", {})
    return t.get("n", 0) if t.get("dia") == dt.date.today().isoformat() else 0


TESTE_JANELA_H = 72  # o Instagram avalia cada Reels teste por 72 h; é nessa janela que ele conta as vagas


def testes_ativos(base, k):
    """Reels TESTE que ainda estão NA JANELA de avaliação (72 h), do mais antigo para o mais novo.
    O 2207078 NÃO é cota por dia: é "máximo de reels teste publicados pela Content Publishing API" — um limite de
    testes ATIVOS, e separado do app (por isso pelo celular ele sobe). Contar por dia travava a conta sem motivo."""
    out = []
    for f in (Path(base) / "postados" / k).glob("*.json"):
        if f.name.startswith("_"):
            continue
        d = le_json(f, {})
        if not isinstance(d, dict) or not d.get("teste") or d.get("situacao") in ("promovido", "ignorado"):
            continue
        if d.get("via") == "app":
            continue  # postado POR VOCÊ no celular: o limite do 2207078 é só do que sobe pela API
        try:
            q = dt.datetime.fromisoformat(d.get("quando", ""))
        except ValueError:
            continue
        if (dt.datetime.now() - q).total_seconds() < TESTE_JANELA_H * 3600:
            out.append((q, d.get("video") or f.stem))
    return sorted(out)


def vaga_de_teste(cfg, base, c, estado, k):
    """("", quando_libera) = pode mandar Reels teste agora; (motivo, quando_libera) = sem vaga.
    A gente não adivinha o número: ele é APRENDIDO quando o Instagram recusa (quantos testes estavam ativos ali),
    então nunca trava abaixo do que a conta já conseguiu."""
    if not ig_e_teste(cfg, c):
        return "", None
    e = estado.get(k, {})
    vagas = int(c.get("max_teste") or e.get("teste_vagas") or 0)
    ativos = testes_ativos(base, k)
    libera = (ativos[0][0] + dt.timedelta(hours=TESTE_JANELA_H)) if ativos else None
    if vagas and len(ativos) >= vagas:
        return f"o Instagram deixa {vagas} Reels teste ativo(s) pela API e já tem {len(ativos)}", libera
    if e.get("teste_ate", 0) > time.time():
        return "o Instagram recusou Reels teste há pouco (sem vaga)", dt.datetime.fromtimestamp(e["teste_ate"])
    return "", libera


def sem_vaga_de_teste(base, k, estado):
    """guarda o que o Instagram ensinou com o 2207078: quantos testes cabiam e quando a próxima vaga abre"""
    ativos = testes_ativos(base, k)
    libera = (ativos[0][0] + dt.timedelta(hours=TESTE_JANELA_H)) if ativos else dt.datetime.now() + dt.timedelta(hours=2)
    def aplica(e):
        d = e.setdefault(k, {})
        if ativos:
            d["teste_vagas"] = len(ativos)  # era isso que cabia quando ele recusou
        d["teste_ate"] = libera.timestamp()
        d["teste_recusa"] = dt.datetime.now().isoformat(timespec="minutes")
        d.pop("teste_limite_visto", None)  # modelo antigo (teto por dia) — estava errado
    muda_estado(base, aplica)
    estado.update(le_estado(base))
    return libera


def drive_raiz():
    """onde está o Google Drive para computador (o mesmo caminho que o painel usa)"""
    cands = []
    for letra in "GHIJKFE":
        for nome in ("Meu Drive", "My Drive"):
            cands.append(f"{letra}:/{nome}")
    cands += [str(Path.home() / "Google Drive"), str(Path.home() / "Meu Drive")]
    for c in cands:
        if Path(c).is_dir():
            return Path(c)
    return None


def pasta_celular(base, c):
    """a pasta de onde VOCÊ baixa no celular e posta como Reels teste. No Drive (aparece no app do celular);
    sem Drive, fica no PC."""
    raiz = drive_raiz()
    return (raiz / "DETTO" / "reels_teste" / c["conta"]) if raiz else (Path(base) / "reels_teste" / c["conta"])


def manda_para_celular(cfg, base, c, video, estado, motivo=""):
    """a API não deu conta do Reels TESTE: o vídeo vai para a pasta do Drive COM A LEGENDA e você posta pelo
    celular (onde o limite é bem maior). Sai da fila para não ficar tentando à toa; o painel avisa."""
    k = chave(c)
    base = Path(base)
    pasta = pasta_celular(base, c)
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / video.name
    try:
        shutil.copyfile(video, alvo)   # cópia: o Drive sobe o arquivo; o original sai da fila logo abaixo
    except OSError as e:
        log(f"{k}: não consegui copiar para a pasta do celular ({e}) — {video.name} fica na fila")
        return None
    leg = legenda_de(video).split("\n---")[0].strip()
    (pasta / f"{video.stem}.txt").write_text(
        f"{leg}\n\n--- como postar ---\n"
        f"No celular: app do Drive → abra este vídeo → ⋮ → Enviar cópia → Instagram → Reels →\n"
        f"cole a legenda acima → na tela de compartilhar, ligue \"Reel de teste\" → Compartilhar.\n"
        f"Depois, no painel: \"✔ Postei\".\n", encoding="utf-8")
    # sai da fila e fica registrado como "esperando você postar pelo celular"
    espera = base / "celular" / k
    espera.mkdir(parents=True, exist_ok=True)
    for f in (video, video.with_suffix(".txt")):
        if f.exists():
            shutil.move(str(f), str(espera / f.name))

    def aplica(e):
        d = e.setdefault(k, {}).setdefault("celular", {})
        d[video.name] = {"quando": dt.datetime.now().isoformat(timespec="minutes"), "motivo": motivo,
                         "pasta": str(pasta)}
    muda_estado(base, aplica)
    estado.update(le_estado(base))
    log(f"{k}: {video.name} foi para a PASTA DO CELULAR ({pasta}) com a legenda — {motivo or 'a API não aceitou o Reels teste'}. "
        f"Baixe pelo app do Drive e poste como Reel de teste; depois marque \"Postei\" no painel.")
    return alvo


def vai_para_celular(cfg, c):
    """sem vaga de teste, o vídeo vai sozinho para a pasta do Drive (padrão LIGADO — ele pediu assim).
    Desligar: "teste_para_celular": false na conta ou no config do Instagram."""
    v = c.get("teste_para_celular")
    if v is None:
        v = cfg.get("instagram", {}).get("teste_para_celular")
    return True if v is None else bool(v)


def cai_para_normal(cfg, c):
    """sem vaga de teste, o vídeo sobe como reels NORMAL? PADRÃO: NÃO (26/out). Ele quer tudo em Reels TESTE —
    subir como normal mandava o vídeo para a página principal, para todos os seguidores, que é o contrário do
    teste. Sem vaga, o vídeo espera (e a pasta do celular resolve os que não cabem pela API).
    Ligar: "teste_cai_para_normal": true na conta ou no config do Instagram."""
    v = c.get("teste_cai_para_normal")
    if v is None:
        v = cfg.get("instagram", {}).get("teste_cai_para_normal")
    return False if v is None else bool(v)


def proximo(c, estado, k):
    """quando esta conta pode postar de novo (datetime), pelo intervalo, horário e limite do dia"""
    agora = dt.datetime.now().replace(second=0, microsecond=0)
    ult = estado.get(k, {}).get("ultimo")
    t = agora
    if ult:
        t = max(t, dt.datetime.fromisoformat(ult) + dt.timedelta(minutes=c.get("intervalo_min", 80)))
    h0, h1 = janela(c)
    if teto_dia(c) and postados_hoje(estado, k) >= teto_dia(c):
        t = max(t, (agora + dt.timedelta(days=1)).replace(hour=h0, minute=0))
    if t.hour < h0:
        t = t.replace(hour=h0, minute=0)
    elif t.hour > h1:
        t = (t + dt.timedelta(days=1)).replace(hour=h0, minute=0)
    return t


def na_hora(c, ultimo, estado=None, k=None):
    if estado is not None:
        return proximo(c, estado, k) <= dt.datetime.now()
    h0, h1 = janela(c)
    agora = dt.datetime.now()
    if not (h0 <= agora.hour <= h1):
        return False
    return not ultimo or (agora - ultimo).total_seconds() >= c.get("intervalo_min", 80) * 60


def studio(cfg, c):
    """TikTok pelo TikTok Studio / Kwai pelo app: o sistema planeja e prepara a pasta, você agenda/posta (nada vai
    pela API — o Kwai não tem API de postagem)"""
    return c["plataforma"] == "kwai" or (c["plataforma"] == "tiktok" and cfg["tiktok"].get("modo", "studio") == "studio")


def planeja(c, estado, k, n, ocupados=None, dias=10):
    """horários dos próximos n vídeos da conta (intervalo, janela do dia e máximo por dia). O TikTok Studio
    agenda de 15 min a 10 dias à frente."""
    h0, h1 = janela(c)
    agora = dt.datetime.now().replace(second=0, microsecond=0)
    t = agora + dt.timedelta(minutes=20)
    ult = estado.get(k, {}).get("ultimo")
    if ult:
        t = max(t, dt.datetime.fromisoformat(ult) + dt.timedelta(minutes=c.get("intervalo_min", 80)))
    por_dia = dict(ocupados or {})
    out = []
    while len(out) < n and t < agora + dt.timedelta(days=dias):
        if t.hour < h0:
            t = t.replace(hour=h0, minute=0)
        elif t.hour > h1:
            t = (t + dt.timedelta(days=1)).replace(hour=h0, minute=0)
            continue
        dia = t.date().isoformat()
        if teto_dia(c) and por_dia.get(dia, 0) >= teto_dia(c):
            t = (t + dt.timedelta(days=1)).replace(hour=h0, minute=0)
            continue
        out.append(t)
        por_dia[dia] = por_dia.get(dia, 0) + 1
        t = t + dt.timedelta(minutes=c.get("intervalo_min", 80))
    return out


def agendados_por_dia(base, k):
    """quantos vídeos já foram agendados no TikTok Studio em cada dia (para o máximo por dia)"""
    cont = {}
    for f in (Path(base) / "postados" / k).glob("*.json"):
        d = le_json(f, {}) if not f.name.startswith("_") else {}
        if isinstance(d, dict) and d.get("agendado_para"):
            dia = d["agendado_para"][:10]
            cont[dia] = cont.get(dia, 0) + 1
    return cont


def marca_agendado(base, c, video, quando):
    """você agendou no TikTok Studio: sai da fila e vai para postados com o horário"""
    k = chave(c)
    video = Path(video)
    destino = Path(base) / "postados" / k
    destino.mkdir(parents=True, exist_ok=True)
    for f in [video, video.with_suffix(".txt")]:
        if f.exists():
            shutil.move(str(f), str(destino / f.name))
    grava_json(destino / f"{video.stem}.json", {"quando": dt.datetime.now().isoformat(timespec="seconds"), "video": video.name,
                                                "agendado_para": quando.isoformat(timespec="minutes"), "modo": "studio", "link": ""})
    estado = le_json(Path(base) / "estado.json", {})
    e = estado.setdefault(k, {})
    if not e.get("ultimo") or e["ultimo"] < quando.isoformat(timespec="seconds"):
        e["ultimo"] = quando.isoformat(timespec="seconds")
    grava_json(Path(base) / "estado.json", estado)
    log(f"{k}: {video.name} " + (f"postado no Kwai (planejado para {quando:%d/%m %H:%M})" if c["plataforma"] == "kwai"
                                  else f"agendado no TikTok Studio para {quando:%d/%m %H:%M}"))


# ------------------------------------------------------------------ YouTube Shorts (canal que você já tem)
def yt_pasta(base, conta):
    """login do canal (token.json) em tokens\\youtube_<conta>\\. A credencial do Google Cloud: a dessa pasta (outro projeto
    = outra cota diária) ou a compartilhada com os canais automáticos (E:\\DETTO\\youtube\\client_secret.json)."""
    p = Path(base) / "tokens" / f"youtube_{conta}"
    p.mkdir(parents=True, exist_ok=True)
    if not (p / "client_secret.json").exists():
        for f in (Path(base).parent / "youtube" / "client_secret.json", Path(base) / "youtube" / "client_secret.json"):
            if f.exists():
                shutil.copyfile(f, p / "client_secret.json")
                break
    return p


def _yt():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "canal"))
    import youtube_up
    return youtube_up


def yt_login(base, conta):
    yu = _yt()
    p = yt_pasta(base, conta)
    yu.credenciais(p, abrir_navegador=True)
    nome, cid = yu.canal_logado(p)
    grava_json(Path(base) / "tokens" / f"youtube_{conta}.json", {"canal": nome, "id": cid, "quando": dt.datetime.now().isoformat(timespec="seconds")})
    print(f"Ligado ao canal do YouTube: {nome}. Os Shorts da conta youtube:{conta} vão para ele.")


def yt_posta(base, conta, video, legenda):
    """Short: vertical até 3 min; título = 1ª linha da legenda + #Shorts; tags = as hashtags da legenda"""
    d = duracao(video)
    if d and d > 180:
        raise RuntimeError(f"Short tem que ter até 3 min (este tem {d:.0f} s)")
    texto = re.sub(r"#\S+", "", legenda or "").strip()
    titulo = ((texto.splitlines() or [""])[0].strip() or Path(video).stem)[:88].strip() + " #Shorts"
    tags = [t.lstrip("#") for t in re.findall(r"#[\wÀ-ÿ]+", legenda or "")][:15]
    desc = (legenda or "") + ("" if "#shorts" in (legenda or "").lower() else "\n\n#Shorts")
    vid = _yt().posta(yt_pasta(base, conta), video, titulo, desc, tags, privacidade="public", sintetico=False, log=log, categoria="23")
    return {"link": f"https://youtube.com/shorts/{vid}", "id": vid}


def posta_um(cfg, base, c, video, como_teste=None):
    if studio(cfg, c):
        raise RuntimeError("esta conta é postada por você (TikTok Studio / app do Kwai): use a pasta preparada no painel")
    leg = legenda_de(video)
    if c["plataforma"] == "youtube":
        return yt_posta(base, c["conta"], video, leg)
    if c["plataforma"] == "instagram":
        n = (le_json(base / "estado.json", {}).get(chave(c), {}).get("falhas") or {}).get(Path(video).name, 0)
        teste = bool(c.get("teste")) if como_teste is None else bool(como_teste)
        return ig_posta(cfg, base, c["conta"], video, leg, teste=teste, graduar=c.get("graduar", "manual"), tentativa=n)
    return tt_posta(cfg, base, c["conta"], video, leg)


def processo_vivo(pid):
    """o processo ainda existe? (trava deixada por um painel que foi fechado/atualizado no meio de uma postagem)"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes

        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        codigo = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(codigo))
        ctypes.windll.kernel32.CloseHandle(h)
        return codigo.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class trava:
    """impede duas postagens ao mesmo tempo (painel + tarefa do Windows). Trava de um processo que já morreu
    (painel fechado ou atualizado no meio de uma postagem) é ignorada na hora — antes segurava a fila por 45 min."""

    def __init__(self, base):
        self.f = Path(base) / ".postando"
        self.ok = False
        self.dono = ""

    def __enter__(self):
        try:
            if self.f.exists():
                pid = (self.f.read_text(errors="replace").split() or [""])[0]
                idade = time.time() - self.f.stat().st_mtime
                if idade < 45 * 60 and processo_vivo(pid):
                    self.dono = f"desde {dt.datetime.fromtimestamp(self.f.stat().st_mtime):%H:%M}"
                    return self
                log(f"trava antiga de postagem removida ({'processo fechado' if idade < 45 * 60 else 'mais de 45 min'})")
            self.f.write_text(f"{os.getpid()} {int(time.time())}")
            self.ok = True
        except OSError:
            pass
        return self

    def __exit__(self, *a):
        if self.ok:
            self.f.unlink(missing_ok=True)


def posta_da_fila(cfg, base, c, video, estado, forcar=False):
    """posta um vídeo da fila da conta e move para postados (ou conta a falha). Devolve o resultado ou None.
    forcar=True = o botão "postar já" do painel (passa por cima da pausa)."""
    k = chave(c)
    # relê o estado AGORA (26/out): a rodada leu o estado antes de começar e, se outro processo pausou a conta no
    # meio, o vídeo ia de novo para o Instagram e renovava o bloqueio. A pausa é conferida aqui também.
    estado.clear()
    estado.update(le_estado(base))
    pausa = estado.get(k, {}).get("pausa_ate", 0)
    if pausa > time.time() and not forcar:
        log(f"{k}: a conta está pausada até {dt.datetime.fromtimestamp(pausa):%d/%m %H:%M}"
            + (f" ({estado[k].get('pausa_motivo')})" if estado[k].get("pausa_motivo") else "")
            + f" — {video.name} continua na fila")
        return None
    # Reels TESTE: tem vaga? Sem vaga o vídeo sobe como reels NORMAL em vez de ficar parado na fila
    como_teste = ig_e_teste(cfg, c)
    if como_teste:
        motivo, libera = vaga_de_teste(cfg, base, c, estado, k)
        if motivo:
            quando = f" (a próxima vaga abre {libera:%d/%m %H:%M})" if libera else ""
            if cai_para_normal(cfg, c):
                como_teste = False
                log(f"{k}: sem vaga de Reels teste — {motivo}{quando}. {video.name} vai como reels NORMAL.")
            elif vai_para_celular(cfg, c):
                log(f"{k}: sem vaga de Reels teste — {motivo}{quando}.")
                manda_para_celular(cfg, base, c, video, estado, f"sem vaga na API{quando}")
                return None
            else:
                log(f"{k}: sem vaga de Reels teste — {motivo}{quando}. {video.name} espera na fila "
                    f'(para ir à pasta do celular: "teste_para_celular": true)')
                return None
    log(f"{k}: postando {video.name}" + (" (Reels teste)" if como_teste else ""))
    if como_teste:
        muda_estado(base, lambda e: conta_tentativa_teste(e, k))
    try:
        r = posta_um(cfg, base, c, video, como_teste=como_teste)
    except Exception as e:
        txt = str(e)
        bloqueio = "2207078" in txt or "too many actions" in txt.lower() or '"code": 9,' in txt
        if bloqueio:
            # 2207078 = "máximo de reels teste publicados pela Content Publishing API": NÃO é cota por dia e não
            # é bloqueio da conta (pelo celular ele continua postando). Então a conta NÃO para mais 24 h: fecha só
            # a porta do TESTE até a vaga abrir e, na próxima rodada, o vídeo sobe como reels normal.
            # "muitas ações" (código 9 sem o 2207078) é bloqueio de verdade: aí sim a conta pausa.
            if "2207078" in txt:
                libera = sem_vaga_de_teste(base, k, estado)
                pausa_conta(base, estado, k, 10 * 60, "sem vaga de Reels teste (tento como normal já)")
                ativos = testes_ativos(base, k)
                log(f"{k}: o Instagram não aceitou mais um Reels TESTE (já tem {len(ativos)} ativo(s) na janela de "
                    f"{TESTE_JANELA_H} h; a vaga abre {libera:%d/%m %H:%M}). NÃO é bloqueio da conta e não conta erro.")
                if not cai_para_normal(cfg, c) and vai_para_celular(cfg, c):
                    manda_para_celular(cfg, base, c, video, estado,
                                       f"a API recusou (2207078); a vaga abre {libera:%d/%m %H:%M}")
                else:
                    log(f"{k}: {video.name} " + ("sobe como reels NORMAL na próxima rodada (10 min)."
                                                 if cai_para_normal(cfg, c) else "espera a vaga na fila."))
                return None
            horas = float(cfg.get("instagram", {}).get("pausa_bloqueio_h") or 24)
            pausa_conta(base, estado, k, horas * 3600, 'bloqueio de "muitas ações"')
            log(f"{k}: o Instagram deu bloqueio de \"muitas ações\" — pauso a conta por {horas:g} h (não insista "
                f"pelo app também); {video.name} continua na fila (não conta como erro)")
            return None
        if any(x in txt.lower() for x in SEM_INTERNET):
            # o PC ficou sem internet (DNS): não é culpa do vídeo — não conta erro, espera 10 min
            pausa_conta(base, estado, k, 10 * 60, "o PC ficou sem internet")
            log(f"{k}: sem internet no PC agora ({txt[:120]}) — tento de novo em 10 min (não conta como erro)")
            return None
        if "não consegui um link" in txt:
            # nenhuma hospedagem serviu (Catbox fora do ar, provedor bloqueando, túnel sem abrir): o VÍDEO está bom,
            # quem falhou foi a hospedagem — não conta erro, senão o vídeo ia para falhas\ sem culpa nenhuma
            pausa_conta(base, estado, k, 10 * 60, "nenhuma hospedagem do link serviu")
            log(f"{k}: nenhuma hospedagem serviu agora — tento de novo em 10 min (não conta como erro)")
            return None
        falhas = estado.setdefault(k, {}).setdefault("falhas", {})
        quando = estado[k].setdefault("falhas_t", {})
        if time.time() - quando.get(video.name, 0) > 12 * 3600:
            falhas.pop(video.name, None)  # erro de outro dia (ex.: no bloqueio de ontem) não conta para hoje
        if isinstance(e, VideoQuebrado):
            falhas[video.name] = 3  # arquivo estragado: não adianta tentar de novo → falhas já
            if ig_e_teste(cfg, c):
                # o vídeo nem chegou ao Instagram: devolve a tentativa, senão um arquivo estragado comia o
                # limite de Reels teste do dia
                def devolve(e_):
                    t = e_.setdefault(k, {}).get("teste_hoje") or {}
                    if t.get("dia") == dt.date.today().isoformat():
                        t["n"] = max(0, t.get("n", 1) - 1)
                muda_estado(base, devolve)
        else:
            # depois de um erro, a conta espera 10 min antes de tentar QUALQUER vídeo (antes tentava o próximo na
            # hora, vários seguidos, e o Instagram bloqueou por "muitas ações")
            estado[k]["pausa_ate"] = time.time() + 10 * 60
            estado[k]["pausa_motivo"] = "erro há pouco (espero antes de tentar outro)"
        falhas[video.name] = falhas.get(video.name, 0) + 1
        quando[video.name] = time.time()
        n = falhas[video.name]
        # espera antes de tentar de novo (erro do Instagram costuma passar; e vai por outro link): 15 min, 45 min, 2 h
        espera = [15, 45, 120][min(n, 3) - 1]
        estado[k].setdefault("espera", {})[video.name] = time.time() + espera * 60
        log(f"{k}: ERRO ({n}/4): {e}" + (f" — tento de novo em {espera} min" if n < 4 else ""))
        if n >= 4 and not isinstance(e, VideoQuebrado) and como_teste and vai_para_celular(cfg, c):
            # o VÍDEO está bom — quem falhou foi o envio. Em vez de falhas\, vai para a pasta do celular.
            falhas.pop(video.name, None)
            quando.pop(video.name, None)
            grava_json(base / "estado.json", estado)
            manda_para_celular(cfg, base, c, video, estado, f"4 tentativas de envio falharam ({str(e)[:90]})")
            return None
        if n >= 4:
            for f in [video, video.with_suffix(".txt")]:
                if f.exists():
                    shutil.move(str(f), str(base / "falhas" / k / f.name))
            log(f"{k}: {video.name} foi para falhas\\ " + ("(arquivo estragado)" if isinstance(e, VideoQuebrado) else "(4 erros seguidos)"))
            falhas.pop(video.name, None)  # o mesmo nome de novo na fila começa do zero
            quando.pop(video.name, None)
        grava_json(base / "estado.json", estado)
        return None
    (Path(base) / "tmp_ig" / (video.stem[:80] + ".ig.mp4")).unlink(missing_ok=True)
    destino = base / "postados" / k
    destino.mkdir(parents=True, exist_ok=True)
    for f in [video, video.with_suffix(".txt")]:
        if f.exists():
            shutil.move(str(f), str(destino / f.name))
    if c["plataforma"] == "instagram" and c.get("facebook", True) is not False:
        fb_depois(cfg, base, c, destino / video.name, estado, r)
    grava_json(destino / f"{video.stem}.json", {"quando": dt.datetime.now().isoformat(timespec="seconds"), "video": video.name, **r})
    e = estado.setdefault(k, {})
    e["ultimo"] = dt.datetime.now().isoformat(timespec="seconds")
    e.setdefault("falhas", {}).pop(video.name, None)
    hoje = dt.date.today().isoformat()
    e["hoje"] = {"dia": hoje, "n": postados_hoje(estado, k) + 1}
    grava_json(base / "estado.json", estado)
    log(f"{k}: OK {'(rascunho no app do TikTok: abra a notificação e publique)' if r.get('modo') == 'rascunho' else r.get('link', '')}")
    return r


def rodada(cfg, base):
    base = Path(base)
    if cfg.get("pausado"):
        return
    with trava(base) as t:
        if not t.ok:
            log(f"rodada: outra postagem ainda em andamento ({t.dono}); confiro de novo na próxima")
            return
        estado = le_estado(base)
        try:
            fb_pendentes(cfg, base, estado)
        except Exception as e:
            log(f"Facebook (pendentes): {e}")
        for c in cfg["contas"]:
            k = chave(c)
            if c.get("ativo") is False or studio(cfg, c):
                continue
            fila = fila_de(base, k)
            if not fila or not na_hora(c, None, estado, k):
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
            if estado.get(k, {}).get("pausa_ate", 0) > time.time():
                continue  # conta em pausa (limite do Instagram ou erro há pouco) — o painel mostra até quando
            espera = estado.get(k, {}).get("espera", {})
            pronto = [v for v in fila if espera.get(v.name, 0) <= time.time()]
            if pronto:
                posta_da_fila(cfg, base, c, pronto[0], estado)


def status(cfg, base):
    estado = le_estado(base)
    for c in cfg["contas"]:
        k = chave(c)
        fila = fila_de(base, k)
        feitos = [p for p in (base / "postados" / k).glob("*.json") if not p.name.startswith("_")]
        extra = ""
        if c["plataforma"] == "instagram":
            lim = ig_limite(cfg, base, c["conta"])
            extra = f" | limite hoje: {lim[0]}/{lim[1]}" if lim else " | sem login"
        elif studio(cfg, c):
            extra = " | pelo TikTok Studio (agende pelo painel)"
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
    bat.write_text(f'@echo off\n"{sys.executable}" "{Path(__file__).resolve()}" --pasta "{base}" >> "{base / "erros.log"}" 2>&1\n', encoding="utf-8")
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
    ap.add_argument("--login", choices=["instagram", "tiktok", "youtube"])
    ap.add_argument("--conta")
    ap.add_argument("--token", help="(Instagram, plano B) token do Graph API Explorer")
    ap.add_argument("--agendar", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--agora", help="vídeo para postar já (fora da fila)")
    ap.add_argument("--teste-facebook", metavar="CONTA", help="confere se o login do Instagram CONTA pode postar na página do Facebook")
    ap.add_argument("--para", help="instagram:detto.galo / tiktok:detto.tv (com --agora)")
    a = ap.parse_args()
    base = Path(a.pasta)
    cfg = prepara(base)
    if a.login:
        if not a.conta:
            sys.exit("Diga a conta: --conta detto.galo")
        if a.login == "youtube":
            return yt_login(base, a.conta)
        return ig_login(cfg, base, a.conta, a.token) if a.login == "instagram" else tt_login(cfg, base, a.conta)
    if a.agendar:
        return agendar(base)
    if a.status:
        return status(cfg, base)
    if a.teste_facebook:
        try:
            tk = ig_token(cfg, base, a.teste_facebook) or {}
            ic = cfg["instagram"]
            if ic.get("app_id") and ic.get("app_secret") and tk.get("token"):
                r = http("GET", f"{GRAPH}/{ic['versao']}/debug_token?" + urllib.parse.urlencode(
                    {"input_token": tk["token"], "access_token": f"{ic['app_id']}|{ic['app_secret']}"}))
                esc = sorted((r.get("data") or {}).get("scopes") or [])
                print("Permissões do login salvo: " + (", ".join(esc) or "(nenhuma informada)"))
                for falta in ("instagram_content_publish", "instagram_manage_insights", "pages_manage_posts"):
                    if esc and falta not in esc:
                        print(f"   FALTA: {falta} — adicione no app da Meta (Casos de uso → Permissões) e conecte de novo")
            pid, _, nome = fb_pagina(cfg, base, a.teste_facebook)
            fb_permissao(cfg, base, a.teste_facebook)
            print(f"OK: a página {nome} ({pid}) pode receber os vídeos.")
        except Exception as e:
            print(f"Facebook: {e}")
        return
    if a.agora:
        plat, conta = (a.para or "").split(":", 1)
        c = next((x for x in cfg["contas"] if x["plataforma"] == plat and x["conta"] == conta), {"plataforma": plat, "conta": conta})
        r = posta_um(cfg, base, c, Path(a.agora))
        if plat == "instagram" and c.get("facebook", True) is not False:
            fb_depois(cfg, base, c, Path(a.agora), {}, r)
        print(json.dumps(r, ensure_ascii=False))
        return
    rodada(cfg, base)


if __name__ == "__main__":
    main()
