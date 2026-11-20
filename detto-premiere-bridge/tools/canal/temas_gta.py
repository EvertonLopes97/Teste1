#!/usr/bin/env python3
"""TEMAS DE GTA 6 (20/nov, pedido dele): "pesquise em fóruns, sites ou próprios vídeos e crie os temas".

De onde vêm os temas (tudo no PC dele, com a internet dele):
  1. OS LINKS QUE ELE MANDA (`<pasta do canal>\\temas_links.txt`, ou o campo do painel): TikTok/YouTube/Instagram. O yt-dlp lê título,
     descrição, hashtags, curtidas/visualizações e, se der, a FALA do vídeo (whisper); a IA descobre o ASSUNTO e o JEITO que fez o
     vídeo bombar (gancho, tamanho) e gera temas PARECIDOS — nunca copia a fala.
  2. FÓRUNS: Reddit (r/GTA6, r/GrandTheftAutoVI) — os posts que mais subiram.
  3. SITES: Google Notícias (pt e en) sobre GTA 6, Rockstar Games.
  4. VÍDEOS: títulos recentes do YouTube sobre GTA 6, com visualizações.

Saída: `<pasta>\\temas_gta.json` = fila de temas {tema, tipo "curto"|"longo", gancho, rumor, origem, usado}. Os shorts e o documentário
pegam o próximo da fila (`proximo`). RUMOR vira o tema com a palavra RUMOR (o roteiro é obrigado a chamar de rumor).

    python tools\\canal\\temas_gta.py --pasta E:\\DETTO\\canal_gta6 [--n 12] [--links "https://vt.tiktok.com/..."]
"""
import argparse
import datetime as dt
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
for _p in (AQUI, TOOLS, TOOLS / "reels"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
REDDITS = ("GTA6", "GrandTheftAutoVI")
NOTICIAS = ("https://news.google.com/rss/search?q=GTA+6&hl=pt-BR&gl=BR&ceid=BR:pt-419",
            "https://news.google.com/rss/search?q=GTA+VI+Rockstar&hl=en-US&gl=US&ceid=US:en")
BUSCAS_YT = ("gta 6 novidades", "gta 6 trailer detalhes", "gta 6 vazamento", "gta 6 mapa")


CATEGORIAS_DIVERTIDAS = ("curiosidade", "engracado", "desafio", "easter_egg", "comparacao", "bug")


def log(m):
    print(m, flush=True)


def _le(f, padrao):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return padrao


def _grava(f, d):
    Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _http(url, prazo=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/xml,*/*"})
    with urllib.request.urlopen(req, timeout=prazo) as r:
        return r.read().decode("utf-8", "replace")


# ------------------------------------------------------------------ 1) fóruns, sites, vídeos
def reddit():
    out = []
    for sub in REDDITS:
        for modo in ("hot", "top&t=day"):
            try:
                d = json.loads(_http(f"https://www.reddit.com/r/{sub}/{modo.split('&')[0]}.json?limit=30" + ("&t=day" if "top" in modo else "")))
                for c in d["data"]["children"]:
                    x = c["data"]
                    if x.get("stickied") or x.get("over_18"):
                        continue
                    out.append({"origem": f"reddit r/{sub}", "texto": x.get("title", ""), "peso": int(x.get("score", 0)),
                                "extra": (x.get("selftext") or "")[:300]})
                break
            except Exception as e:   # noqa: BLE001
                log(f"   reddit r/{sub} {modo.split('&')[0]}: {str(e)[:80]}")
    return out


def noticias():
    out = []
    for url in NOTICIAS:
        try:
            xml = _http(url)
        except Exception as e:   # noqa: BLE001
            log(f"   google notícias: {str(e)[:80]}")
            continue
        for it in re.findall(r"<item>(.*?)</item>", xml, re.S)[:25]:
            t = re.search(r"<title>(.*?)</title>", it, re.S)
            if t:
                tt = re.sub(r"<!\[CDATA\[|\]\]>", "", t.group(1)).strip()
                out.append({"origem": "notícia", "texto": tt, "peso": 0, "extra": ""})
    return out


def youtube():
    from reels import ytdlp
    out = []
    for q in BUSCAS_YT:
        try:
            r = ytdlp(["--flat-playlist", "--dump-json", "--playlist-end", "12", "https://www.youtube.com/results?search_query="
                       + urllib.parse.quote(q) + "&sp=CAI%253D"])
        except Exception as e:   # noqa: BLE001
            log(f"   youtube '{q}': {str(e)[:80]}")
            continue
        for ln in (r.stdout or "").splitlines():
            try:
                v = json.loads(ln)
            except ValueError:
                continue
            if v.get("title"):
                out.append({"origem": f"youtube {v.get('channel') or ''}".strip(), "texto": v["title"],
                            "peso": int(v.get("view_count") or 0) // 1000, "extra": ""})
    return out


# ------------------------------------------------------------------ 2) os links que ele manda
def analisa_links(links, pasta, falar=True):
    """título, descrição, hashtags, números e (se der) a fala de cada link. Link que não abre é dito em voz alta, não escondido."""
    from reels import ytdlp
    out = []
    for url in links:
        try:
            r = ytdlp(["--skip-download", "--dump-json", url], timeout=120)
            info = json.loads((r.stdout or "").strip().splitlines()[-1])
        except Exception as e:   # noqa: BLE001
            log(f"   ⚠ link não abriu ({url}): {str(e)[:100]}")
            out.append({"origem": "link seu (NÃO abriu)", "texto": url, "peso": 0, "extra": ""})
            continue
        fala = ""
        if falar:
            try:
                from reels import baixa
                from transcrever import transcrever
                arq, _ = baixa(url, Path(pasta) / "temas_links_tmp", timeout=300)
                if arq:
                    ps = transcrever(str(arq), "base", "cpu", idioma=None)
                    ps = ps[0] if isinstance(ps, tuple) else ps
                    fala = " ".join(p["w"] for p in ps)[:1500]
                    Path(arq).unlink(missing_ok=True)
            except Exception as e:   # noqa: BLE001
                log(f"   sem a fala de {url}: {str(e)[:80]}")
        out.append({"origem": "link seu", "texto": (info.get("title") or info.get("description") or url)[:200], "peso": 9999,
                    "extra": f"descrição: {(info.get('description') or '')[:300]} | hashtags: {' '.join(info.get('tags') or [])[:150]} | "
                             f"{info.get('view_count', '?')} views, {info.get('like_count', '?')} curtidas, {int(info.get('duration') or 0)} s"
                             + (f" | FALA: {fala}" if fala else "")})
        log(f"   link lido: {out[-1]['texto'][:80]}")
    return out


# ------------------------------------------------------------------ 3) a IA transforma tudo em temas
PEDIDO = """Você é o pauteiro de um canal brasileiro de GTA 6 (YouTube longo + shorts/reels/TikTok). Hoje é {hoje}.
Abaixo há o que está em alta (links que o dono mandou — o que mais importa —, fóruns, notícias e vídeos). Crie {n} TEMAS de vídeo.

REGRAS:
- Só tema que tenha base no material abaixo ou no que a Rockstar já mostrou/confirmou. NUNCA invente fato, vazamento ou número.
- Se a base é boato/fórum/vazamento: "rumor": true (o roteiro vai chamar de rumor). Confirmado/mostrado em trailer: false.
- Os links do dono mandam no ESTILO: copie o TIPO de assunto e o jeito do gancho, NÃO a fala nem o texto do vídeo deles.
- MISTURA DE CATEGORIAS ("categoria"): no máximo 1 em cada 4 temas pode ser "guia" (como pegar X). O resto tem de ser CURIOSIDADE e
  DIVERSÃO, que é o que o dono quer: "curiosidade" (detalhe estranho/escondido do jogo), "engracado" (situação absurda, bug, NPC), 
  "desafio" (alguém fez algo maluco, ex.: "o cara malhou a Lucia até ela virar o Ramon Dino"), "easter_egg", "comparacao" (GTA 6 x GTA 5/vida real),
  "rumor" (boato marcado), "noticia". Exemplos do tom que ele ama: "malhou a Lucia até virar o Ramon Dino", "o que acontece se você
  ficar parado na frente do tubarão", "o NPC que odeia o Jason". Humor brasileiro, gancho que faz rir ou dizer 'não acredito'.
  Só use situação que apareça no material ou que seja possível no jogo; NUNCA diga que aconteceu algo que não está no material.
- "tipo": "curto" (short de 30-55 s, UM fato forte) ou "longo" (documentário de 12+ min, assunto que rende capítulos).
  Faça cerca de 3 curtos para cada longo.
- "gancho": a PRIMEIRA frase falada (até 12 palavras), forte, com pergunta ou número, sem "fala galera".
- "tema": a frase de assunto (até 110 letras), em português do Brasil, com o fato concreto. Termos certos: "nível de procurado"
  (nunca "estrelas de procura"), Vice City, Leonida, Lucia Caminos, Jason Duval, Rockstar Games.
- Não repita o que já foi feito: {usados}

MATERIAL:
{material}

Responda SÓ JSON: {{"temas":[{{"tema":"...","categoria":"curiosidade","tipo":"curto","gancho":"...","rumor":false,"origem":"onde viu (reddit/notícia/link seu...)"}}]}}"""


def gera_temas(material, n, usados):
    from reels import gemini_json
    mat = "\n".join(f"- [{m['origem']}] {m['texto']}" + (f" ({m['extra']})" if m.get("extra") else "") for m in material)[:14000]
    d = gemini_json([{"text": PEDIDO.format(hoje=dt.date.today().strftime("%d/%m/%Y"), n=n, usados="; ".join(usados[-30:]) or "nada",
                                            material=mat)}], temperatura=0.85) or {}
    out = []
    try:
        import glossario as G
    except Exception:   # noqa: BLE001
        G = None
    for t in d.get("temas") or []:
        if not isinstance(t, dict) or not str(t.get("tema", "")).strip():
            continue
        tema = str(t["tema"]).strip()
        out.append({"tema": G.corrige(tema) if G else tema, "tipo": "longo" if t.get("tipo") == "longo" else "curto",
                    "gancho": G.corrige(str(t.get("gancho", ""))) if G else str(t.get("gancho", "")),
                    "rumor": bool(t.get("rumor")), "categoria": str(t.get("categoria") or "curiosidade")[:20], "origem": str(t.get("origem", ""))[:40], "usado": False,
                    "criado": dt.date.today().isoformat()})
    return out


def atualiza(pasta, n=12, links=None, log=log):
    """pesquisa tudo e põe temas novos na fila. Devolve quantos entraram."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    arq_links = pasta / "temas_links.txt"
    novos = [l.strip() for l in (links or []) if l.strip().startswith("http")]
    if novos:
        ja = arq_links.read_text(encoding="utf-8").splitlines() if arq_links.exists() else []
        arq_links.write_text("\n".join(ja + [l for l in novos if l not in ja]) + "\n", encoding="utf-8")
    todos = [l.strip() for l in arq_links.read_text(encoding="utf-8").splitlines() if l.strip().startswith("http")] if arq_links.exists() else []
    lidos = _le(pasta / "temas_links_lidos.json", {})
    pend = [l for l in todos if l not in lidos]
    log(f"temas: {len(pend)} link(s) seu(s) novo(s) para ler")
    material = list(analisa_links(pend, pasta))
    for l in pend:     # marca como lido mesmo se não abriu (senão tenta de novo toda hora)
        lidos[l] = dt.date.today().isoformat()
    _grava(pasta / "temas_links_lidos.json", lidos)
    for nome, fn in (("reddit", reddit), ("notícias", noticias), ("youtube", youtube)):
        try:
            r = fn()
            log(f"temas: {nome}: {len(r)} item(ns)")
            material += sorted(r, key=lambda x: -x["peso"])[:25]
        except Exception as e:   # noqa: BLE001
            log(f"temas: {nome} falhou ({str(e)[:80]})")
    material = [m for m in material if m["texto"].strip()]
    if not material:
        log("temas: nada de material (sem internet?)")
        return 0
    fila = _le(pasta / "temas_gta.json", [])
    usados = [t["tema"] for t in fila]
    novos_t = gera_temas(material, n, usados)
    vistos = {re.sub(r"\W+", "", t["tema"].lower())[:50] for t in fila}
    add = [t for t in novos_t if re.sub(r"\W+", "", t["tema"].lower())[:50] not in vistos]
    corte = (dt.date.today() - dt.timedelta(days=10)).isoformat()
    fila = [t for t in fila if not (t.get("usado") and t.get("criado", "") < corte)] + add
    _grava(pasta / "temas_gta.json", fila)
    log(f"temas: {len(add)} tema(s) novo(s) na fila ({sum(1 for t in fila if not t['usado'])} esperando)")
    return len(add)


def proximo(pasta, tipo="curto", log=log, atualizar=True):
    """o próximo tema da fila (do tipo), já marcado como usado. Fila vazia → pesquisa de novo (no máx. 1x por hora)."""
    pasta = Path(pasta)
    f = pasta / "temas_gta.json"
    for tentativa in range(2):
        fila = _le(f, [])
        for t in fila:
            if not t.get("usado") and t.get("tipo") == tipo:
                t["usado"] = True
                _grava(f, fila)
                pre = "RUMOR (ainda NÃO confirmado pela Rockstar; diga que é rumor): " if t.get("rumor") else ""
                cat = str(t.get("categoria") or "")
                if cat in CATEGORIAS_DIVERTIDAS and not t.get("rumor"):
                    pre = "CURIOSIDADE (" + cat + "): "
                log(f"tema da fila ({t.get('origem')}): {t['tema']}")
                return pre + t["tema"] + (f". Comece a narração assim: \"{t['gancho']}\"" if t.get("gancho") else "")
        marca = pasta / ".temas_pesquisou"
        recente = marca.exists() and (dt.datetime.now().timestamp() - marca.stat().st_mtime) < 3600
        if tentativa or recente or not atualizar:
            break
        marca.write_text(dt.datetime.now().isoformat(), encoding="utf-8")
        try:
            atualiza(pasta, log=log)
        except Exception as e:   # noqa: BLE001
            log(f"temas: a pesquisa falhou ({str(e)[:100]})")
            break
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", required=True)
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--links", default="", help="links (TikTok/YouTube/Instagram), um por linha ou separados por espaço")
    a = ap.parse_args()
    atualiza(a.pasta, a.n, re.findall(r"https?://\S+", a.links))


if __name__ == "__main__":
    main()
