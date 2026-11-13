# -*- coding: utf-8 -*-
"""PEGA OS COOKIES DO YOUTUBE SOZINHO — abre uma janela, você entra na conta UMA VEZ, e acabou.

    python tools\\postar\\cookies_youtube.py              abre a janela e espera você entrar
    python tools\\postar\\cookies_youtube.py --atualizar  só RE-EXPORTA do perfil salvo (sem janela, sem login)
    python tools\\postar\\cookies_youtube.py --site instagram|tiktok

POR QUE ISSO EXISTE (05/nov)
O download do canal de GTA 6 morria em "Sign in to confirm you're not a bot", e a única saída é cookie. Mas:
 - o Chrome novo guarda os cookies com a criptografia da conta do Windows (App-Bound Encryption) e o yt-dlp
   NÃO consegue ler: dá `Failed to decrypt with DPAPI`;
 - a extensão "Get cookies.txt LOCALLY" funciona, mas é ele quem tem de exportar na mão, e o arquivo vence.

Aqui o navegador é NOSSO (o Chromium que já vem com o Playwright, o mesmo que desenha as cartelas), com
PERFIL PRÓPRIO e permanente em `<DETTO>\\postar\\perfil_<site>`. Então:
 1. a primeira vez ele entra na conta na janela que abre — uma vez só;
 2. dali em diante o `--atualizar` RE-EXPORTA do perfil salvo, sem janela e sem login, e o painel faz isso
    sozinho. Cookie vencido deixa de ser problema dele.

O arquivo sai em `<DETTO>\\cookies.txt`, que é exatamente onde o `cookies_do_pc()` do reels.py procura.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

SITES = {
    "youtube": {"url": "https://www.youtube.com/", "dominio": "youtube.com",
                "prova": ("SAPISID", "__Secure-3PAPISID", "LOGIN_INFO"),
                "como": "entre na sua conta do Google (o mesmo login do canal)"},
    "instagram": {"url": "https://www.instagram.com/", "dominio": "instagram.com",
                  "prova": ("sessionid",), "como": "entre no Instagram"},
    "tiktok": {"url": "https://www.tiktok.com/", "dominio": "tiktok.com",
               "prova": ("sessionid", "sid_tt"), "como": "entre no TikTok"},
}


def log(m):
    print(f"{dt.datetime.now():%H:%M} {m}", flush=True)


def raiz_midia():
    """a pasta da mídia dele. FORA DO WINDOWS o "E:/DETTO" vira uma pasta LITERAL chamada "E:" dentro de
    onde o programa estiver rodando — e foi assim que um teste meu criou `detto-premiere-bridge/E:/DETTO/...`
    dentro do repositório, que entrou no commit e QUEBROU o `git pull` no PC dele ("invalid path", porque
    ":" não vale em nome de arquivo no Windows). Então aqui fora isso cai no /tmp."""
    d = os.environ.get("DETTO_MIDIA")
    if d:
        return Path(d)
    if os.name == "nt":
        return Path("E:/DETTO")
    import tempfile
    return Path(tempfile.gettempdir()) / "DETTO"


def _playwright():
    try:
        from playwright.sync_api import sync_playwright   # noqa: PLC0415
        return sync_playwright
    except ImportError:
        return None


def _chromium_do_pc():
    """o Chromium que o Playwright já baixou (o mesmo das cartelas e das thumbs)"""
    base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or ""
    for raiz in [base] if base else ["/opt/pw-browsers"]:
        try:
            for d in sorted(Path(raiz).iterdir()):
                if d.name.startswith("chromium-"):
                    for sub in ("chrome-linux", "chrome-linux64"):
                        exe = d / sub / "chrome"
                        if exe.is_file():
                            return str(exe)
        except OSError:
            continue
    return None       # no Windows o Playwright acha sozinho


def netscape(cookies, dominio=""):
    """os cookies no formato cookies.txt que o yt-dlp lê.

    DOIS DETALHES que fazem o arquivo ser aceito ou ignorado em silêncio:
    - o separador é TAB, não espaço;
    - cookie de SESSÃO (sem validade) com expires=0 é DESCARTADO por quem lê o arquivo — e o cookie de
      sessão é justamente o que prova o login. Então eu dou validade de 1 ano para esses.
    """
    um_ano = int(time.time()) + 365 * 24 * 3600
    linhas = ["# Netscape HTTP Cookie File",
              "# gerado pelo DETTO (tools\\postar\\cookies_youtube.py) — não edite na mão", ""]
    n = 0
    for c in cookies:
        dom = c.get("domain") or ""
        if dominio and dominio not in dom:
            continue
        nome, valor = c.get("name"), c.get("value")
        if not nome or valor is None:
            continue
        exp = c.get("expires")
        try:
            exp = int(float(exp))
        except (TypeError, ValueError):
            exp = 0
        if exp <= 0:
            exp = um_ano
        sub = "TRUE" if dom.startswith(".") else "FALSE"
        seguro = "TRUE" if c.get("secure") else "FALSE"
        linhas.append("\t".join([dom, sub, c.get("path") or "/", seguro, str(exp), nome, str(valor)]))
        n += 1
    return "\n".join(linhas) + "\n", n


def grava(cookies, site, saida=None):
    s = SITES[site]
    txt, n = netscape(cookies, s["dominio"])
    if not n:
        return 0, None
    alvo = Path(saida) if saida else (raiz_midia() / "cookies.txt")
    alvo.parent.mkdir(parents=True, exist_ok=True)
    # O MESMO arquivo serve para todos os sites: o yt-dlp aceita um cookies.txt com vários domínios, e o
    # `cookies_do_pc()` procura UM caminho. Então eu JUNTO, mantendo os outros domínios que já estavam lá.
    antigas = []
    if alvo.exists():
        for linha in alvo.read_text(encoding="utf-8", errors="replace").splitlines():
            if linha.startswith("#") or not linha.strip():
                continue
            if s["dominio"] not in linha.split("\t")[0]:
                antigas.append(linha)
    tudo = txt.rstrip("\n").splitlines() + antigas
    alvo.write_text("\n".join(tudo) + "\n", encoding="utf-8")
    return n, alvo


def tem_login(cookies, site):
    nomes = {c.get("name") for c in cookies if SITES[site]["dominio"] in (c.get("domain") or "")}
    return any(p in nomes for p in SITES[site]["prova"])


def _pelo_node(site, minutos, atualizar, saida):
    """O CAMINHO QUE DE FATO FUNCIONA NO PC DELE (05/nov).

    A primeira versão disto só tentava o Playwright do PYTHON — que o PC dele não tem. O que o projeto
    instala e usa (cartelas, thumbs, vinheta) é o do NODE. Resultado: o programa morria na primeira linha
    e a janela nunca abria. Então o Node é tentado SEMPRE, antes de desistir."""
    import shutil as _sh

    js = Path(__file__).with_suffix(".js")
    if not js.exists() or not _sh.which("node"):
        return None
    s = SITES[site]
    args = ["node", str(js), "--saida", str(saida or (raiz_midia() / "cookies.txt")),
            "--perfil", str(raiz_midia() / "postar" / f"perfil_{site}"),
            "--dominio", s["dominio"], "--url", s["url"], "--minutos", str(minutos)]
    if atualizar:
        args.append("--atualizar")
    log("usando o Chromium do Node (o mesmo das cartelas e das thumbs)")
    try:
        return subprocess.run(args, cwd=str(Path(__file__).resolve().parent.parent.parent)).returncode
    except OSError as e:   # noqa: BLE001
        log(f"não consegui rodar o node ({str(e)[:90]})")
        return None


def pega(site="youtube", minutos=5, atualizar=False, saida=None, headless=False):
    sp = _playwright()
    if not sp:
        r = _pelo_node(site, minutos, atualizar, saida)
        if r is not None:
            return r
        log("ERRO: não achei o Playwright nem no Python nem no Node.")
        log("      Na pasta detto-premiere-bridge rode:  npm install playwright")
        log("      e depois:  npx playwright install chromium")
        return 1
    s = SITES[site]
    perfil = raiz_midia() / "postar" / f"perfil_{site}"
    perfil.mkdir(parents=True, exist_ok=True)
    primeira = not any(perfil.iterdir())
    if atualizar and primeira:
        log(f"ERRO: ainda não existe perfil salvo para o {site}. Rode SEM --atualizar uma vez, "
            "para entrar na conta.")
        return 1

    exe = _chromium_do_pc()
    with sp() as pw:
        # PERFIL PERMANENTE: é o que faz o login valer para sempre e o --atualizar não pedir nada
        ctx = pw.chromium.launch_persistent_context(
            str(perfil), headless=bool(atualizar or headless), executable_path=exe,
            locale="pt-BR", viewport={"width": 1180, "height": 860}, args=["--no-first-run"])
        try:
            pg = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                pg.goto(s["url"], timeout=60000, wait_until="domcontentloaded")
            except Exception as e:   # noqa: BLE001
                log(f"não consegui abrir {s['url']} ({str(e)[:80]})")
            if atualizar:
                pg.wait_for_timeout(3500)
                cks = ctx.cookies()
                if not tem_login(cks, site):
                    log(f"o perfil salvo NÃO está mais logado no {site}. Rode sem --atualizar e entre de novo.")
                    return 1
                n, alvo = grava(cks, site, saida)
                log(f"{n} cookie(s) do {site} atualizados em {alvo}")
                return 0

            log("")
            log("=" * 66)
            log(f"  ABRIU UMA JANELA DO NAVEGADOR. {s['como'].upper()}.")
            log("  Você faz isso UMA VEZ. Depois o painel atualiza sozinho.")
            log(f"  Eu fecho a janela sozinho quando detectar o login (até {minutos} min).")
            log("=" * 66)
            log("")
            fim = time.time() + minutos * 60
            visto = False
            while time.time() < fim:
                cks = ctx.cookies()
                if tem_login(cks, site):
                    visto = True
                    log("login detectado — esperando 4 s para pegar todos os cookies...")
                    pg.wait_for_timeout(4000)
                    cks = ctx.cookies()
                    n, alvo = grava(cks, site, saida)
                    log(f"PRONTO: {n} cookie(s) do {site} salvos em {alvo}")
                    log("O canal já pode baixar. O painel reexporta isso sozinho de vez em quando.")
                    break
                time.sleep(3)
            if not visto:
                log(f"passou de {minutos} min e eu não vi o login. Nada foi salvo — rode de novo.")
                return 1
        finally:
            try:
                ctx.close()
            except Exception:   # noqa: BLE001
                pass
    return 0


def main():
    ap = argparse.ArgumentParser(description="pega os cookies do YouTube (ou Instagram/TikTok) num navegador nosso")
    ap.add_argument("--site", default="youtube", choices=sorted(SITES))
    ap.add_argument("--minutos", type=int, default=5, help="quanto esperar você entrar na conta")
    ap.add_argument("--atualizar", action="store_true", help="só reexporta do perfil salvo (sem janela)")
    ap.add_argument("--saida", help="padrão: <DETTO>\\cookies.txt")
    ap.add_argument("--headless", action="store_true", help="sem janela (só para teste)")
    a = ap.parse_args()
    return pega(a.site, a.minutos, a.atualizar, a.saida, a.headless)


if __name__ == "__main__":
    sys.exit(main())
