# -*- coding: utf-8 -*-
"""PAINEL DO TIKTOK SHOP (avulso) — a tela do pacote DETTO-SHOP, para o PC do sócio.

    python tools\\shop\\painel_shop.py            → abre http://localhost:8731 no navegador

É só Python (http.server). Não tem canal, postagem, token nem conta de ninguém: mostra as opções do vídeo
(modo, narração, legenda, voz, clipes da internet), recebe o produto (nome, link, lista ou pasta), roda o
`shop.py` e mostra o registro e os vídeos prontos. As chaves das IAs de texto ficam em `chaves.json` na
pasta do pacote (nunca saem do PC) e entram no ambiente do processo — sem `setx`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
PORTA = int(os.environ.get("DETTO_SHOP_PORTA", "8731"))
CHAVES_F = PONTE / "chaves.json"
CHAVES = ("GEMINI_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", "MISTRAL_API_KEY", "OPENROUTER_API_KEY")
VOZES = [("pt-BR-AntonioNeural", "Antônio (masculina)"), ("pt-BR-FranciscaNeural", "Francisca (feminina)"),
         ("pt-BR-ThalitaMultilingualNeural", "Thalita (feminina, jovem)"),
         ("pt-BR-MacerioMultilingualNeural", "Macério (masculina, jovem)")]

# a pasta de trabalho é a `shop\` AO LADO do instalador (o shop.py lê DETTO_SHOP em pasta_padrao)
os.environ.setdefault("DETTO_SHOP", str(PONTE / "shop"))
# o Chromium das cartelas fica dentro do pacote (o INSTALAR põe lá): não depende do perfil do Windows
if (PONTE / "navegador").is_dir():
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(PONTE / "navegador"))
for p in (str(TOOLS / "painel"), str(AQUI), str(TOOLS)):
    if p not in sys.path:
        sys.path.insert(0, p)


def le_chaves():
    try:
        d = json.loads(CHAVES_F.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {k: str(d.get(k) or "").strip() for k in CHAVES}


def aplica_chaves():
    for k, v in le_chaves().items():
        if v:
            os.environ[k] = v
        elif k in os.environ and CHAVES_F.exists():
            os.environ.pop(k, None)


def _tem(prog):
    return bool(shutil.which(prog))


def saude():
    """o que falta para sair vídeo — aparece no topo da tela"""
    falta = []
    if not _tem("ffmpeg"):
        falta.append("ffmpeg não encontrado — rode o INSTALAR.bat de novo")
    if not _tem("node"):
        falta.append("Node.js não encontrado — o vídeo sai SEM as cartelas de texto/preço (rode o INSTALAR.bat)")
    if not any(os.environ.get(k) for k in CHAVES):
        falta.append("nenhuma chave de IA de texto — o roteiro sai no MODELO simples. Ponha a chave grátis do Gemini "
                     "ou do Groq em \"Chaves\" para o roteiro autoral")
    return falta


def estado():
    import shop_painel as SP

    e = SP.estado()
    S = SP._s()
    cfg = S.prepara(SP.pasta())
    e["voz_neural"] = cfg.get("voz_neural") or "pt-BR-AntonioNeural"
    e["velocidade_voz"] = float(cfg.get("velocidade_voz", 1.0))
    e["vozes"] = [{"id": a, "nome": b} for a, b in VOZES]
    e["chaves"] = {k: bool(v) for k, v in le_chaves().items()}
    e["saude"] = saude()
    # os prontos dos últimos dias (o painel grande só mostra os de hoje)
    prontos = []
    raiz = SP.pasta() / "prontos"
    for d in sorted((x for x in raiz.iterdir() if x.is_dir()), reverse=True)[:5] if raiz.is_dir() else []:
        for f in sorted(d.glob("*.mp4"), reverse=True):
            t = f.with_suffix(".txt")
            leg = ""
            if t.exists():
                leg = t.read_text(encoding="utf-8", errors="replace").split("\n---")[0].strip()
            prontos.append({"nome": f.name, "dia": d.name, "legenda": leg})
    e["prontos"] = prontos[:30]
    return e


def acao(nome, d):
    import shop_painel as SP

    S = SP._s()
    base = SP.pasta()
    if nome == "chaves":
        atual = le_chaves()
        for k in CHAVES:
            if k in d:
                atual[k] = str(d[k] or "").strip()
        CHAVES_F.write_text(json.dumps(atual, ensure_ascii=False, indent=1), encoding="utf-8")
        aplica_chaves()
        return {"ok": True}
    if nome == "cfg":
        cfg = S.prepara(base)
        if d.get("voz_neural") in [v for v, _ in VOZES]:
            cfg["voz_neural"] = d["voz_neural"]
        if "velocidade_voz" in d:
            cfg["velocidade_voz"] = max(0.8, min(1.5, float(d["velocidade_voz"])))
        if "duracao" in d:
            d["duracao"] = max(15, min(90, int(float(d["duracao"]))))
        S.grava_json(base / "config.json", cfg)
        d.pop("postar", None)          # neste pacote a postagem fica desligada
        return SP.acao("shop_cfg", d)
    if nome == "fazer":
        aplica_chaves()
        link = str(d.get("link") or "").strip()
        if link:   # "link | nome | preço": o nome salva o link de vitrine (a página do Shop barra robô)
            extra = [str(d.get(k) or "").strip() for k in ("nome_do_link", "preco")]
            if extra[0]:
                link = " | ".join([link, extra[0]] + ([extra[1]] if extra[1] else []))
            d = {**d, "link": link, "nome": ""}
        d["nao_postar"] = True
        return SP.acao("shop_fazer", d)
    if nome == "links":
        return SP.acao("shop_links", d)
    if nome == "parar":
        return SP.acao("shop_parar", d)
    if nome == "abrir_pasta":
        alvo = base / ("produtos" if d.get("qual") == "produtos" else "prontos")
        alvo.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(alvo))   # noqa: S606
            else:
                subprocess.Popen(["xdg-open", str(alvo)])
        except OSError as e:
            return {"ok": False, "erro": str(e)[:120]}
        return {"ok": True}
    return {"ok": False, "erro": f"ação desconhecida: {nome}"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):   # silencioso
        pass

    def _manda(self, corpo, tipo="application/json; charset=utf-8", cod=200):
        if not isinstance(corpo, bytes):
            corpo = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(cod)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path in ("/", "/index.html"):
                return self._manda((AQUI / "painel_shop.html").read_bytes(), "text/html; charset=utf-8")
            if u.path == "/api/estado":
                return self._manda(estado())
            if u.path == "/video":
                import shop_painel as SP

                q = parse_qs(u.query)
                f = SP.arquivo((q.get("nome") or [""])[0], (q.get("dia") or [""])[0])
                if not f:
                    return self._manda({"erro": "não achei"}, cod=404)
                return self._arquivo(f, baixar=bool(q.get("baixar")))
        except Exception as e:   # noqa: BLE001
            return self._manda({"ok": False, "erro": str(e)[:300]}, cod=500)
        self._manda({"erro": "?"}, cod=404)

    def _arquivo(self, f, baixar=False):
        tam = f.stat().st_size
        ini, fim = 0, tam - 1
        faixa = self.headers.get("Range")
        if faixa and faixa.startswith("bytes="):
            a, _, b = faixa[6:].partition("-")
            ini = int(a or 0)
            fim = min(tam - 1, int(b)) if b else tam - 1
        self.send_response(206 if faixa else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fim - ini + 1))
        if faixa:
            self.send_header("Content-Range", f"bytes {ini}-{fim}/{tam}")
        if baixar:
            self.send_header("Content-Disposition", "attachment")
        self.end_headers()
        with open(f, "rb") as g:
            g.seek(ini)
            falta = fim - ini + 1
            while falta > 0:
                bloco = g.read(min(1 << 16, falta))
                if not bloco:
                    break
                try:
                    self.wfile.write(bloco)
                except OSError:
                    break
                falta -= len(bloco)

    def do_POST(self):
        u = urlparse(self.path)
        # só a própria tela pode mandar ação (outro site aberto no navegador não)
        origem = self.headers.get("Origin") or ""
        if origem and urlparse(origem).hostname not in ("localhost", "127.0.0.1"):
            return self._manda({"ok": False, "erro": "origem recusada"}, cod=403)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            d = json.loads(self.rfile.read(n) or b"{}")
            if u.path.startswith("/api/"):
                return self._manda(acao(u.path[5:], d))
        except Exception as e:   # noqa: BLE001
            return self._manda({"ok": False, "erro": str(e)[:300]}, cod=500)
        self._manda({"erro": "?"}, cod=404)


def main():
    aplica_chaves()
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORTA), H)
    except OSError:
        print(f"O painel já está aberto: http://localhost:{PORTA}")
        webbrowser.open(f"http://localhost:{PORTA}")
        return 0
    print(f"PAINEL DO TIKTOK SHOP em http://localhost:{PORTA}  (deixe esta janela aberta; Ctrl+C fecha)")
    if "--sem-navegador" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(f"http://localhost:{PORTA}")).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
