# -*- coding: utf-8 -*-
"""PASTA DE EFEITOS SONOROS — baixa do myinstants.com e monta a biblioteca das histórias.

    python tools\\historias\\sons_web.py                     → completa todas as categorias (4 sons em cada)
    python tools\\historias\\sons_web.py --quantos 8         → 8 por categoria
    python tools\\historias\\sons_web.py --categoria ding    → só essa
    python tools\\historias\\sons_web.py --listar            → o que já tem na pasta

Os arquivos ficam em `<DETTO>\\historias\\sons\\<categoria>\\` e o `historias.py` usa daí (antes da pasta de efeitos
do PC e antes do som sintetizado). O que já está baixado não baixa de novo.

Os sons vêm de uma biblioteca pública de efeitos enviados por usuários: ótimos para whoosh, clique, impacto e
suspense. Se um dia um vídeo for monetizado, vale conferir a origem do efeito antes.
"""
import argparse
import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

SITE = "https://www.myinstants.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# categoria (a que o roteiro pede) → o que procurar no site, na ordem
CATEGORIAS = {
    "ding": ["notificação mensagem", "som de notificação", "sino aviso"],
    "tick": ["tic tac relógio", "click curto"],
    "relogio": ["tic tac relógio", "relógio contagem"],
    "passos": ["passos andando", "passos correndo"],
    "boom": ["impacto grave", "boom cinematográfico", "impacto suspense"],
    "soco": ["soco impacto", "batida forte"],
    "porta": ["porta batendo", "porta fechando"],
    "pop": ["pop", "bolha pop"],
    "click": ["click interruptor", "clique botão"],
    "whoosh": ["whoosh transição", "transição swoosh"],
    "riser": ["suspense tensão", "riser cinematográfico"],
    "glitch": ["glitch", "erro digital"],
    "trovao": ["trovão", "raio trovão"],
    "agua": ["água pingando", "torneira água"],
    "sirene": ["sirene", "alarme"],
    "vidro": ["vidro quebrando", "estilhaço vidro"],
    "motor": ["motor carro", "carro acelerando"],
}


def log(m):
    print(m, flush=True)


def pasta_padrao():
    import os

    if os.name == "nt" and Path("E:/").exists():
        return Path("E:/DETTO/historias/sons")
    return Path.home() / "DETTO" / "historias" / "sons"


def _abre(url, binario=False, espera=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=espera) as r:
        d = r.read()
    return d if binario else d.decode("utf-8", "replace")


def busca(termo, quantos=12):
    """os efeitos da busca: (nome, endereço do mp3)"""
    try:
        html = _abre(f"{SITE}/pt/search/?name={urllib.parse.quote(termo)}")
    except Exception as e:
        log(f"   busca \"{termo}\": {str(e)[:90]}")
        return []
    out, vistos = [], set()
    # cada botão do site tem o play('/media/sounds/x.mp3') e, logo depois, o nome do efeito
    for m in re.finditer(r"play\('(/media/sounds/[^']+\.mp3)'", html):
        url = m.group(1)
        if url in vistos:
            continue
        vistos.add(url)
        nome = re.sub(r"[^\w\s-]", "", urllib.parse.unquote(Path(url).stem).replace("-", " ")).strip()[:48]
        out.append((nome or "efeito", SITE + url))
        if len(out) >= quantos:
            break
    return out


def dur(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def baixa_categoria(cat, pasta, quantos=4, log=log):
    """completa a categoria até `quantos` efeitos BONS (0,2 a 8 s, que o FFmpeg lê)"""
    destino = Path(pasta) / cat
    destino.mkdir(parents=True, exist_ok=True)
    ja = {f.stem.lower() for f in destino.glob("*.mp3")}
    falta = quantos - len(ja)
    if falta <= 0:
        return 0
    novos = 0
    for termo in CATEGORIAS.get(cat, [cat]):
        if novos >= falta:
            break
        for nome, url in busca(termo, quantos=14):
            if novos >= falta:
                break
            chave = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")[:40] or "efeito"
            if chave in ja:
                continue
            alvo = destino / f"{chave}.mp3"
            try:
                dados = _abre(url, binario=True)
            except Exception:
                continue
            if len(dados) < 1500 or len(dados) > 3_000_000:
                continue
            alvo.write_bytes(dados)
            d = dur(alvo)
            if not (0.2 <= d <= 8.0):   # efeito de vídeo é curto; música inteira não serve
                alvo.unlink(missing_ok=True)
                continue
            ja.add(chave)
            novos += 1
            log(f"   {cat}: {chave} ({d:.1f}s)")
    return novos


def arquivo(cat, i=0, pasta=None):
    """um efeito dessa categoria (rodando entre os que tem) — a mesma cara do biblioteca_sons.arquivo"""
    d = Path(pasta or pasta_padrao()) / cat
    fs = sorted(d.glob("*.mp3"))
    return str(fs[i % len(fs)]) if fs else None


def inventario(pasta=None):
    p = Path(pasta or pasta_padrao())
    return {c: len(list((p / c).glob("*.mp3"))) for c in CATEGORIAS}


def main():
    ap = argparse.ArgumentParser(description="baixa efeitos sonoros e monta a pasta das histórias")
    ap.add_argument("--pasta", default=str(pasta_padrao()))
    ap.add_argument("--quantos", type=int, default=4, help="quantos efeitos por categoria")
    ap.add_argument("--categoria", default="", help="só esta categoria")
    ap.add_argument("--listar", action="store_true")
    a = ap.parse_args()
    pasta = Path(a.pasta)
    if a.listar:
        inv = inventario(pasta)
        log(f"pasta: {pasta}")
        for c, n in sorted(inv.items()):
            log(f"  {c:9} {n} efeito(s)")
        log(f"total: {sum(inv.values())}")
        return
    cats = [a.categoria] if a.categoria else list(CATEGORIAS)
    total = 0
    for c in cats:
        if c not in CATEGORIAS:
            log(f"categoria desconhecida: {c} (tem: {', '.join(CATEGORIAS)})")
            continue
        total += baixa_categoria(c, pasta, a.quantos)
    inv = inventario(pasta)
    log(f"\n{total} efeito(s) novo(s). A pasta tem {sum(inv.values())} em {len(CATEGORIAS)} categorias: {pasta}")
    (pasta / "sons.json").write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
