#!/usr/bin/env python3
"""GOOGLE FLOW PELO CHROME REAL (19/nov, pedido dele: usar os 25 mil créditos da assinatura Google AI sem API paga).

Como funciona: `iniciar_chrome_flow.bat` abre um Chrome de verdade, logado na conta dele, com a porta de depuração 9222.
Este módulo conecta nele por CDP (Playwright `connect_over_cdp`) — o Google barra navegador "headless" puro, mas não
um Chrome normal com sessão — e faz o que ele faria com a mão: escolhe o modo, o formato 9:16, sobe a foto, digita o pedido,
clica em gerar, espera o vídeo e baixa.

  python tools\\flow\\flow_service.py --saude                 → Chrome aberto? Flow aberto? logado?
  python tools\\flow\\flow_service.py --abrir                 → abre o Chrome do Flow (o .bat)
  python tools\\flow\\flow_service.py --descobrir             → grava botões/campos da tela em flow_debug\\ (para ajustar seletores)
  python tools\\flow\\flow_service.py --teste "um cachorro correndo na praia" [--imagem foto.jpg] [--avatar]
  python tools\\flow\\flow_service.py --importar              → normaliza para 1080x1920 os .mp4 que você baixou na mão em <flow>\\entrada\\

O QUE NÃO FOI CONFERIDO (sem acesso à conta dele): os NOMES dos botões do Flow. A tela muda toda hora (em nov/2026 ela já
trocou de modelos), então cada passo procura por VÁRIOS nomes (pt/en) e, se não acha um passo opcional, segue e avisa no registro;
se não acha um passo obrigatório (caixa de texto, botão de gerar), grava captura de tela + lista de botões em `<flow>\\flow_debug\\`.
Os nomes podem ser trocados sem mexer no código: `<flow>\\seletores.json` ({"gerar": ["Criar", ...], "modelo": [...], ...}).

REGRAS PARA NÃO PERDER CRÉDITO NEM A CONTA: uma geração por vez (Lock + arquivo de trava entre processos), pausa entre gerações
(`flow_pausa_s`, 25 s), teto por dia (`flow_max_dia`, 40), cache pelo pedido+foto (o mesmo pedido nunca gasta crédito duas vezes).
Aviso honesto: o Flow não tem API para créditos de assinatura; isto é automação da interface e pode ir contra os termos do
serviço — por isso o ritmo é humano e baixo.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

CDP = "http://127.0.0.1:9222"
FLOW_URL = "https://labs.google/fx/tools/flow"
AQUI = Path(__file__).resolve().parent

# nomes (pt/en) que cada passo procura; `<flow>\seletores.json` troca/acrescenta sem mexer aqui
SELETORES = {
    "novo_projeto": ["novo projeto", "new project", "criar projeto"],
    "modo_texto": ["texto para vídeo", "texto para video", "text to video", "text-to-video"],
    "modo_frames": ["frames para vídeo", "frames para video", "frames to video", "de frames", "imagem para vídeo", "image to video"],
    "modo_ingredientes": ["ingredientes para vídeo", "ingredientes", "ingredients to video", "ingredients"],
    "retrato": ["9:16", "retrato", "portrait", "vertical"],
    "configuracoes": ["configurações", "configuracoes", "settings", "tune", "opções", "opcoes", "ajustes"],
    "gerar": ["gerar", "generate", "criar", "create", "enviar", "submit", "arrow_forward"],
    "adicionar": ["adicionar mídia", "adicionar imagem", "adicionar", "add media", "add image", "upload", "enviar imagem", "add_2", "add"],
    "confirmar": ["salvar", "save", "concluir", "done", "cortar", "crop", "confirmar", "confirm", "ok"],
    "biblioteca": ["biblioteca", "library", "meus ativos", "assets", "ingredientes salvos", "recentes", "recent"],
    "baixar": ["baixar", "download", "salvar vídeo", "save video"],
    "qualidade_720": ["720p", "original", "tamanho original", "original size"],
}
ERRO_TELA = re.compile(r"falha|falhou|failed|não foi possível|could not|couldn.t|violat|pol[ií]tica|policy|bloquead|blocked|tente novamente", re.I)


class FlowErro(Exception):
    pass


def raiz_detto():
    for c in (os.environ.get("DETTO_PASTA"), r"E:\DETTO", str(Path.home() / "DETTO")):
        if c and Path(c).is_dir():
            return Path(c)
    return Path.home() / "DETTO"


def pasta_flow(cfg=None):
    p = Path(os.environ.get("DETTO_FLOW") or (cfg or {}).get("flow_pasta") or raiz_detto() / "flow")
    for s in ("cache", "entrada", "flow_debug", "flow_downloads"):
        (p / s).mkdir(parents=True, exist_ok=True)
    return p


def seletores(pasta):
    s = {k: list(v) for k, v in SELETORES.items()}
    try:
        for k, v in json.loads((pasta / "seletores.json").read_text(encoding="utf-8-sig")).items():
            s[k] = ([v] if isinstance(v, str) else list(v)) + s.get(k, [])   # os dele vêm primeiro
    except Exception:   # noqa: BLE001
        pass
    return s


# ------------------------------------------------------------------ saúde (sem Playwright: só HTTP)
def chrome_aberto(cdp=CDP, prazo=1.5):
    """True se o Chrome do Flow responde na porta de depuração"""
    try:
        with urllib.request.urlopen(cdp.rstrip("/") + "/json/version", timeout=prazo) as r:
            return bool(json.loads(r.read().decode("utf-8", "replace")).get("Browser"))
    except Exception:   # noqa: BLE001
        return False


def abas(cdp=CDP, prazo=1.5):
    try:
        with urllib.request.urlopen(cdp.rstrip("/") + "/json/list", timeout=prazo) as r:
            return [{"url": a.get("url", ""), "titulo": a.get("title", "")} for a in json.loads(r.read().decode("utf-8", "replace"))
                    if a.get("type") == "page"]
    except Exception:   # noqa: BLE001
        return []


def saude(cfg=None):
    """para o painel: {"chrome": bool, "flow_aberto": bool, "logado": bool|None, "msg": str}"""
    cdp = (cfg or {}).get("flow_cdp") or CDP
    if not chrome_aberto(cdp):
        return {"chrome": False, "flow_aberto": False, "logado": None,
                "msg": "Chrome do Flow fechado — clique em «Abrir Chrome do Flow» (ou rode iniciar_chrome_flow.bat)"}
    ab = abas(cdp)
    flow = [a for a in ab if "labs.google" in a["url"] or "flow.google" in a["url"]]
    if any("accounts.google.com" in a["url"] for a in ab) and not flow:
        return {"chrome": True, "flow_aberto": False, "logado": False, "msg": "Chrome aberto, mas pedindo login: entre na conta Google nessa janela"}
    if not flow:
        return {"chrome": True, "flow_aberto": False, "logado": None, "msg": "Chrome conectado; o Flow será aberto na primeira geração"}
    return {"chrome": True, "flow_aberto": True, "logado": True, "msg": "Chrome conectado e Flow aberto"}


# ------------------------------------------------------------------ trava entre processos (o Lock do asyncio só vale dentro de um)
class TravaArquivo:
    def __init__(self, pasta, prazo_s=1800):
        self.f = pasta / ".flow_gerando"
        self.prazo = prazo_s

    def _dono_vivo(self):
        try:
            pid, t = self.f.read_text().split()
            if time.time() - float(t) > self.prazo:
                return False
            if os.name == "nt":
                r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
                return pid in r.stdout
            os.kill(int(pid), 0)
            return True
        except (OSError, ValueError):
            return False

    async def pega(self, espera_max=1800):
        t0 = time.time()
        while True:
            try:
                fd = os.open(str(self.f), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()} {time.time()}".encode())
                os.close(fd)
                return
            except FileExistsError:
                if not self._dono_vivo():
                    self.f.unlink(missing_ok=True)
                    continue
                if time.time() - t0 > espera_max:
                    raise FlowErro("outra geração do Flow não terminou a tempo")
                await asyncio.sleep(5)

    def solta(self):
        self.f.unlink(missing_ok=True)


# ------------------------------------------------------------------ FFmpeg: todo clipe do Flow vira 1080x1920 igual aos outros
def normaliza(entrada, saida, com_audio=False, fps=30):
    """1080x1920, SAR 1:1, fps fixo, H.264 yuv420p. Clipe horizontal ganha fundo desfocado (não corta o produto)."""
    entrada, saida = str(entrada), str(saida)
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", entrada],
                       capture_output=True, text=True)
    try:
        w, h = [int(x) for x in p.stdout.strip().split("x")[:2]]
    except ValueError:
        raise FlowErro("o ffprobe não leu o vídeo baixado do Flow") from None
    if abs(w / h - 9 / 16) < 0.03:
        vf = f"scale=1080:1920:flags=lanczos,setsar=1,fps={fps},format=yuv420p"
        fc = None
    else:
        fc = ("[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:6[bg];"
              "[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,"
              f"setsar=1,fps={fps},format=yuv420p[v]")
        vf = None
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", entrada]
    cmd += ["-filter_complex", fc, "-map", "[v]"] if fc else ["-vf", vf]
    if com_audio:
        cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", "libx264", "-crf", "17", "-preset", "veryfast", "-movflags", "+faststart", saida]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not Path(saida).exists() or Path(saida).stat().st_size < 20000:
        raise FlowErro(f"ffmpeg não normalizou o clipe ({(r.stderr or '')[-160:]})")
    return Path(saida)


# ------------------------------------------------------------------ o serviço
class FlowService:
    def __init__(self, cfg=None, log=print):
        self.cfg = cfg or {}
        self.log = log
        self.cdp = self.cfg.get("flow_cdp") or CDP
        self.pasta = pasta_flow(self.cfg)
        self.sel = seletores(self.pasta)
        self._lock = asyncio.Lock()
        self._pw = self._browser = self.ctx = None
        self._rede = []      # vídeos vistos passando pela rede (plano B de captura)

    # ---- conexão
    async def conectar(self):
        if self._browser and self._browser.is_connected():
            return
        if not chrome_aberto(self.cdp):
            raise FlowErro("o Chrome do Flow está fechado: abra iniciar_chrome_flow.bat (porta 9222) e entre na sua conta Google")
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.connect_over_cdp(self.cdp)
        self.ctx = self._browser.contexts[0] if self._browser.contexts else await self._browser.new_context()

    async def fechar(self):
        try:
            if self._browser:
                await self._browser.close()   # em CDP isto só desconecta; o Chrome dele continua aberto
        finally:
            if self._pw:
                await self._pw.stop()
            self._pw = self._browser = self.ctx = None

    async def _pausa(self, a=0.6, b=1.5):
        await asyncio.sleep(random.uniform(a, b))

    # ---- diagnóstico
    async def debug(self, page, nome):
        """captura de tela + lista de botões/campos visíveis: é o que permite ajustar os nomes em 5 minutos"""
        d = self.pasta / "flow_debug"
        marca = time.strftime("%Y%m%d_%H%M%S") + "_" + re.sub(r"\W+", "_", nome)[:30]
        try:
            await page.screenshot(path=str(d / f"{marca}.png"), full_page=False)
        except Exception:   # noqa: BLE001
            pass
        try:
            itens = await page.evaluate("""() => {
              const vis = e => { const r = e.getBoundingClientRect(); return r.width > 2 && r.height > 2; };
              return [...document.querySelectorAll('button,[role=button],[role=tab],[role=menuitem],[role=option],input,textarea,[contenteditable=true],[aria-label]')]
                .filter(vis).slice(0, 250).map(e => ({tag: e.tagName.toLowerCase(), role: e.getAttribute('role') || '',
                  aria: e.getAttribute('aria-label') || '', texto: (e.innerText || e.value || '').trim().slice(0, 60), tipo: e.type || ''}));
            }""")
            (d / f"{marca}.json").write_text(json.dumps({"url": page.url, "itens": itens}, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:   # noqa: BLE001
            pass
        self.log(f"   flow: diagnóstico gravado em {d} ({marca})")
        return marca

    # ---- achar e clicar por vários nomes
    def _candidatos(self, page, chave):
        for nome in self.sel.get(chave, []):
            rx = re.compile(re.escape(nome), re.I)
            yield page.get_by_role("button", name=rx)
            yield page.get_by_role("tab", name=rx)
            yield page.get_by_role("menuitem", name=rx)
            yield page.get_by_role("option", name=rx)
            yield page.locator(f'[aria-label*="{nome}" i]')
            yield page.get_by_text(rx)

    async def clica(self, page, chave, obrigatorio=False, espera=2500):
        for loc in self._candidatos(page, chave):
            try:
                alvo = loc.first
                if await alvo.is_visible(timeout=250):
                    await alvo.click(timeout=espera)
                    await self._pausa()
                    return True
            except Exception:   # noqa: BLE001
                continue
        if obrigatorio:
            await self.debug(page, f"sem_{chave}")
            raise FlowErro(f"não achei o botão «{chave}» no Flow (veja {self.pasta / 'flow_debug'}; ajuste em seletores.json)")
        self.log(f"   flow: não achei «{chave}» (passo opcional) — sigo com o que estava na tela")
        return False

    # ---- página
    async def pagina(self):
        await self.conectar()
        for pg in self.ctx.pages:
            if "labs.google" in pg.url or "flow.google" in pg.url:
                await pg.bring_to_front()
                return pg
        pg = await self.ctx.new_page()
        await pg.goto(self.cfg.get("flow_projeto_url") or FLOW_URL, wait_until="domcontentloaded")
        await pg.wait_for_timeout(3500)
        return pg

    async def _garante_projeto(self, pg):
        if "accounts.google.com" in pg.url:
            raise FlowErro("o Chrome do Flow pede login: entre na sua conta Google nessa janela e tente de novo")
        if self.cfg.get("flow_projeto_url") and "/project/" not in pg.url:
            await pg.goto(self.cfg["flow_projeto_url"], wait_until="domcontentloaded")
            await pg.wait_for_timeout(3000)
        if not await self._caixa_visivel(pg):
            await self.clica(pg, "novo_projeto")
            await pg.wait_for_timeout(3500)
        if not await self._caixa_visivel(pg):
            await self.debug(pg, "sem_caixa_de_texto")
            raise FlowErro("não achei a caixa de pedido do Flow (abra um projeto no Chrome do Flow ou ponha flow_projeto_url no config)")

    async def _caixa_visivel(self, pg):
        try:
            return await pg.get_by_role("textbox").last.is_visible(timeout=1500)
        except Exception:   # noqa: BLE001
            return False

    async def _videos(self, pg):
        try:
            return await pg.evaluate("""() => [...document.querySelectorAll('video')].map(v => ({
              src: v.currentSrc || v.src || (v.querySelector('source') || {}).src || '', d: v.duration || 0}))
              .filter(x => x.src)""")
        except Exception:   # noqa: BLE001
            return []

    # ---- passos
    async def _formato_e_modelo(self, pg, modelo, duracao):
        await self.clica(pg, "retrato")                       # 9:16 — opcional aqui; o normalizador cobre se não pegar
        if modelo:
            self.sel["_modelo"] = [modelo]
            if await self.clica(pg, "configuracoes"):
                await self.clica(pg, "_modelo")
        if duracao:
            self.sel["_duracao"] = [f"{duracao}s", f"{duracao} s", f"{duracao} seg"]
            await self.clica(pg, "_duracao")

    async def _sobe_imagem(self, pg, imagem):
        try:
            await pg.locator("input[type=file]").first.set_input_files(str(imagem), timeout=4000)
        except Exception:   # noqa: BLE001
            try:
                async with pg.expect_file_chooser(timeout=6000) as fc:
                    await self.clica(pg, "adicionar", obrigatorio=True)
                await (await fc.value).set_files(str(imagem))
            except Exception as e:   # noqa: BLE001
                await self.debug(pg, "sem_upload")
                raise FlowErro(f"não consegui subir a foto no Flow ({str(e)[:100]})") from e
        await pg.wait_for_timeout(2500)
        await self.clica(pg, "confirmar")                     # recorte/confirmação, se a tela pedir

    async def _avatar(self, pg, nome):
        """pega o avatar que ele já criou no Flow (pela biblioteca de ativos/ingredientes) pelo NOME"""
        await self.clica(pg, "adicionar")
        await self.clica(pg, "biblioteca")
        try:
            alvo = pg.get_by_text(re.compile(re.escape(nome), re.I)).first
            await alvo.click(timeout=5000)
            await self._pausa()
            return True
        except Exception:   # noqa: BLE001
            await self.debug(pg, "sem_avatar")
            raise FlowErro(f"não achei o avatar «{nome}» na biblioteca do Flow (confira o nome em flow_avatar)") from None

    # ---- captura
    async def _salva(self, pg, url, destino):
        destino = Path(destino)
        if url.startswith("blob:"):
            b64 = await pg.evaluate("""async u => { const r = await fetch(u); const b = new Uint8Array(await r.arrayBuffer());
              let s = ''; for (let i = 0; i < b.length; i += 32768) s += String.fromCharCode.apply(null, b.subarray(i, i + 32768)); return btoa(s); }""", url)
            destino.write_bytes(base64.b64decode(b64))
        else:
            r = await self.ctx.request.get(url, timeout=120000)    # leva os cookies do Chrome logado
            if not r.ok:
                raise FlowErro(f"download recusado ({r.status})")
            destino.write_bytes(await r.body())
        if destino.stat().st_size < 50000:
            raise FlowErro("o vídeo baixado do Flow veio vazio")
        return destino

    async def _baixa_pelo_botao(self, pg, destino):
        """plano C: o botão de baixar do próprio Flow"""
        async with pg.expect_download(timeout=60000) as dl:
            await self.clica(pg, "baixar", obrigatorio=True)
            await self.clica(pg, "qualidade_720")
        d = await dl.value
        await d.save_as(str(destino))
        return Path(destino)

    # ---- geração
    async def gerar(self, prompt, destino, imagem=None, avatar=None, modelo=None, duracao=None, timeout_s=None):
        """UMA geração (fila com Lock). Devolve o .mp4 BRUTO baixado; use normaliza() depois."""
        async with self._lock:
            trava = TravaArquivo(self.pasta)
            await trava.pega()
            try:
                return await self._gerar(prompt, destino, imagem, avatar, modelo, duracao, timeout_s or int(self.cfg.get("flow_prazo_s", 900)))
            finally:
                trava.solta()

    async def _gerar(self, prompt, destino, imagem, avatar, modelo, duracao, prazo):
        pg = await self.pagina()
        self._rede = []

        async def _resp(r):
            try:
                ct = (r.headers or {}).get("content-type", "")
                if r.status == 200 and ("video/" in ct or r.url.split("?")[0].endswith(".mp4")):
                    self._rede.append(r.url)
            except Exception:   # noqa: BLE001
                pass
        pg.on("response", lambda r: asyncio.ensure_future(_resp(r)))
        await self._garante_projeto(pg)
        if avatar:
            await self.clica(pg, "modo_ingredientes")
        elif imagem:
            await self.clica(pg, "modo_frames")
        else:
            await self.clica(pg, "modo_texto")
        await self._formato_e_modelo(pg, modelo or self.cfg.get("flow_modelo"), duracao or self.cfg.get("flow_duracao"))
        if avatar:
            await self._avatar(pg, avatar)
        if imagem:
            await self._sobe_imagem(pg, imagem)
        caixa = pg.get_by_role("textbox").last
        await caixa.click()
        try:
            await caixa.fill(prompt)
        except Exception:   # noqa: BLE001
            await pg.keyboard.type(prompt, delay=15)
        await self._pausa(1, 2)
        antes = {v["src"] for v in await self._videos(pg)}
        erros_antes = await pg.get_by_text(ERRO_TELA).count()
        n_rede = len(self._rede)
        if not await self.clica(pg, "gerar"):
            await pg.keyboard.press("Control+Enter")
        self.log(f"   flow: pedido enviado ({'avatar+' if avatar else ''}{'foto' if imagem else 'texto'}); esperando o vídeo (até {prazo // 60} min)")
        t0 = time.time()
        while time.time() - t0 < prazo:
            await asyncio.sleep(5)
            novos = [v for v in await self._videos(pg) if v["src"] not in antes and v["d"] > 1]
            if novos:
                url = novos[0]["src"]
                self.log(f"   flow: vídeo pronto em {time.time() - t0:.0f}s")
                try:
                    return await self._salva(pg, url, destino)
                except Exception as e:   # noqa: BLE001
                    self.log(f"   flow: captura direta falhou ({str(e)[:90]}); tento o botão de baixar")
                    return await self._baixa_pelo_botao(pg, destino)
            if len(self._rede) > n_rede and time.time() - t0 > 20:
                try:
                    return await self._salva(pg, self._rede[-1], destino)
                except Exception:   # noqa: BLE001
                    n_rede = len(self._rede)
            if await pg.get_by_text(ERRO_TELA).count() > erros_antes:
                await self.debug(pg, "erro_na_tela")
                raise FlowErro("o Flow recusou/falhou a geração (política de conteúdo ou erro) — veja a captura em flow_debug")
        await self.debug(pg, "demorou")
        raise FlowErro(f"o Flow não entregou o vídeo em {prazo // 60} min")


# ------------------------------------------------------------------ uso simples (síncrono) para o resto do projeto
def _uso(pasta):
    f = pasta / "uso.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:   # noqa: BLE001
        d = {}
    hoje = time.strftime("%Y-%m-%d")
    return f, (d if d.get("dia") == hoje else {"dia": hoje, "n": 0, "t": 0})


def gera_clipe(prompt, imagem=None, avatar=None, cfg=None, log=print, com_audio=False):
    """prompt (+ foto real do produto e/ou avatar) → Path de um .mp4 1080x1920 pronto, ou None (nunca derruba quem chamou).
    Cache: o mesmo pedido+foto não gasta crédito duas vezes. Teto diário em `flow_max_dia`."""
    cfg = cfg or {}
    pasta = pasta_flow(cfg)
    chave_foto = Path(imagem).read_bytes() if imagem and Path(imagem).exists() else b""
    marca = hashlib.md5(chave_foto + f"{prompt}|{avatar}|{cfg.get('flow_modelo')}|{cfg.get('flow_duracao')}|{com_audio}".encode()).hexdigest()[:16]
    pronto = pasta / "cache" / f"flow_{marca}.mp4"
    if pronto.exists() and pronto.stat().st_size > 50000:
        log(f"   flow: clipe já guardado ({pronto.name}) — não gasta crédito")
        return pronto
    f_uso, uso = _uso(pasta)
    if uso["n"] >= int(cfg.get("flow_max_dia", 40)):
        log(f"   flow: teto do dia atingido ({uso['n']} gerações) — sigo sem Flow")
        return None
    espera = int(cfg.get("flow_pausa_s", 25)) - (time.time() - uso.get("t", 0))
    if espera > 0:
        time.sleep(min(espera, 60))
    bruto = pasta / "flow_downloads" / f"{marca}_bruto.mp4"

    async def _roda():
        s = FlowService(cfg, log)
        try:
            return await s.gerar(prompt, bruto, imagem=imagem, avatar=avatar)
        finally:
            await s.fechar()
    try:
        asyncio.run(_roda())
        uso["n"] += 1
        uso["t"] = time.time()
        f_uso.write_text(json.dumps(uso), encoding="utf-8")
        normaliza(bruto, pronto, com_audio=com_audio)
        bruto.unlink(missing_ok=True)
        return pronto
    except Exception as e:   # noqa: BLE001
        log(f"   flow: não deu ({str(e)[:220]}); sigo sem o clipe do Flow")
        return None


def importa_entrada(cfg=None, log=print):
    """vídeos que ele baixou na mão do Flow em <flow>\\entrada\\ → normalizados em <flow>\\cache\\ (plano B sem automação)"""
    pasta = pasta_flow(cfg)
    feitos = []
    for v in sorted((pasta / "entrada").glob("*")):
        if v.suffix.lower() not in (".mp4", ".mov", ".webm", ".m4v"):
            continue
        saida = pasta / "cache" / f"manual_{hashlib.md5(v.read_bytes()[:2_000_000]).hexdigest()[:12]}.mp4"
        try:
            normaliza(v, saida, com_audio=True)
            v.rename(v.with_suffix(v.suffix + ".feito"))
            feitos.append(saida)
            log(f"   flow: {v.name} → {saida.name}")
        except Exception as e:   # noqa: BLE001
            log(f"   flow: {v.name} não deu ({str(e)[:100]})")
    return feitos


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--saude", action="store_true")
    ap.add_argument("--abrir", action="store_true")
    ap.add_argument("--descobrir", action="store_true")
    ap.add_argument("--importar", action="store_true")
    ap.add_argument("--teste", metavar="PROMPT")
    ap.add_argument("--imagem")
    ap.add_argument("--avatar", action="store_true", help="usa o avatar de flow_avatar do config")
    ap.add_argument("--cfg", help="json de configuração (flow_modelo, flow_avatar, flow_projeto_url...)")
    a = ap.parse_args()
    cfg = json.loads(Path(a.cfg).read_text(encoding="utf-8-sig")) if a.cfg else {}
    if a.saude:
        print(json.dumps(saude(cfg), ensure_ascii=False, indent=1))
    elif a.abrir:
        bat = AQUI.parent.parent / "iniciar_chrome_flow.bat"
        if os.name != "nt":
            sys.exit(f"abra no Windows: {bat}")
        subprocess.Popen(["cmd", "/c", str(bat)], creationflags=0x00000008)
        print("abrindo o Chrome do Flow...")
    elif a.descobrir:
        async def _d():
            s = FlowService(cfg)
            try:
                pg = await s.pagina()
                print("marca:", await s.debug(pg, "descobrir"), "→", s.pasta / "flow_debug")
            finally:
                await s.fechar()
        asyncio.run(_d())
    elif a.importar:
        print(f"{len(importa_entrada(cfg))} clipe(s) importado(s)")
    elif a.teste:
        r = gera_clipe(a.teste, a.imagem, cfg.get("flow_avatar") if a.avatar else None, cfg)
        print(f"pronto: {r}" if r else "não deu — veja as mensagens acima e a pasta flow_debug")
    else:
        print(json.dumps(saude(cfg), ensure_ascii=False))


if __name__ == "__main__":
    main()
