# -*- coding: utf-8 -*-
"""Notas dos jogadores de um jogo, SEM depender do SofaScore (que dá 403 no PC do Everton).

Ordem: banco do repositório (tools/galo/banco/notas/*.json, vem no git pull) → FotMob (responde) → SofaScore.

Gravar um jogo no banco (rode aqui no Claude e faça push, ou no PC se o FotMob responder):

    python tools\\galo\\notas.py "Flamengo Atletico Mineiro" --time "Atlético Mineiro"
    python tools\\galo\\notas.py --listar

Formato do arquivo: {"jogo", "quando", "placar": {...}, "notas": [[nota, nome, apelido], ...]} —
`notas` já ordenada da PIOR para a MELHOR, igual o SofaScore devolvia.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent))
import galo  # noqa: E402

PASTA = galo.BANCO / "notas"
UA = "Mozilla/5.0"
FOTMOB_DIA = "https://www.fotmob.com/api/data/matches?date={}"
FOTMOB_JOGO = "https://www.fotmob.com/api/data/matchDetails?matchId={}"


def _json(url, referer="https://www.fotmob.com/"):
    try:
        from curl_cffi import requests as cr
        r = cr.get(url, impersonate="chrome", timeout=30, headers={"Referer": referer})
        if r.status_code == 200:
            return r.json()
    except Exception:  # noqa: BLE001 — sem curl_cffi ou falhou: tenta o curl
        pass
    r = subprocess.run(["curl", "-sS", "-m", "30", "-A", UA, "-H", f"Referer: {referer}", url],
                       capture_output=True)
    try:
        return json.loads(r.stdout.decode("utf-8", "replace") or "{}")
    except json.JSONDecodeError:
        return {}


def _times_da_busca(busca):
    """"Flamengo Atletico Mineiro" -> os pedaços que precisam aparecer nos nomes dos times"""
    return [p for p in galo.slug(busca).split("-") if len(p) > 3]


def _bate(nome_time, pedacos):
    s = galo.slug(nome_time)
    return any(p in s or s in p for p in pedacos)


def _e_o_jogo(casa, fora, pedacos):
    """os DOIS times da busca aparecem? ("Atletico Mineiro" bate com "Atlético-MG" por "atletico";
    exigir todos os pedaços derrubava o jogo, porque "mineiro" não está no nome curto)"""
    if len(pedacos) < 2:
        return False
    usados = set()
    for lado in (casa, fora):
        achou = next((p for p in pedacos if p not in usados and _bate(lado, [p])), None)
        if not achou:
            return False
        usados.add(achou)
    return True


# ============================================================ banco (do git)

def do_banco(busca, time):
    """jogo já gravado em tools/galo/banco/notas (o jeito que funciona no PC dele, sem internet nenhuma)"""
    pedacos = _times_da_busca(busca)
    alvo = galo.slug(time)[:6]
    achados = []
    for f in sorted(PASTA.glob("*.json")) if PASTA.exists() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pl = d.get("placar") or {}
        casa = f"{pl.get('casa', '')} {d.get('jogo', '')}"
        fora = f"{pl.get('fora', '')} {d.get('jogo', '')}"
        if pedacos and not _e_o_jogo(casa, fora, pedacos):
            continue
        if alvo and alvo not in galo.slug(d.get("time", "")):
            continue
        achados.append((d.get("quando", ""), f, d))
    if not achados:
        return None
    _, f, d = max(achados)
    notas = sorted(tuple(n) for n in d.get("notas") or [])
    print(f"Notas do banco: {f.name} ({d.get('jogo')}, {d.get('quando')}) — {len(notas)} jogador(es).")
    return d.get("placar"), notas


# ================================================================== FotMob

def acha_no_fotmob(busca, dias=12):
    """varre os últimos dias do calendário do FotMob até achar o jogo (ele não tem busca por texto aberta)"""
    pedacos = _times_da_busca(busca)
    if len(pedacos) < 2:
        return None
    hoje = dt.date.today()
    for d in range(dias):
        dia = hoje - dt.timedelta(days=d)
        for L in (_json(FOTMOB_DIA.format(dia.strftime("%Y%m%d"))).get("leagues") or []):
            for m in L.get("matches") or []:
                if _e_o_jogo(m.get("home", {}).get("name", ""), m.get("away", {}).get("name", ""), pedacos):
                    return m["id"], L.get("name", ""), dia
    return None


def do_fotmob(busca, time):
    achado = acha_no_fotmob(busca)
    if not achado:
        return None
    mid, liga, dia = achado
    d = _json(FOTMOB_JOGO.format(mid))
    lu = (d.get("content") or {}).get("lineup") or {}
    if not lu.get("homeTeam"):
        return None
    alvo = galo.slug(time)[:6]
    lado = "homeTeam" if _bate(lu["homeTeam"].get("name", ""), [alvo]) else "awayTeam"
    notas = []
    for grupo in ("starters", "subs"):
        for p in lu[lado].get(grupo) or []:
            r = (p.get("performance") or {}).get("rating")
            if r:
                nome = p.get("name") or ""
                notas.append((round(float(r), 1), nome, p.get("shortName") or nome.split()[-1]))
    g = d.get("general") or {}
    st = (d.get("header") or {}).get("status") or {}
    placar = {"competicao": (liga or g.get("leagueName") or "").replace("Série A", "Brasileirão"),
              "quando": dia.strftime("%d/%m"), "status": "Encerrado",
              "casa": lu["homeTeam"].get("name", ""), "fora": lu["awayTeam"].get("name", ""),
              "gols_casa": (st.get("scoreStr") or "x").split("-")[0].strip(),
              "gols_fora": (st.get("scoreStr") or "x").split("-")[-1].strip()}
    print(f"Notas do FotMob: {placar['casa']} x {placar['fora']} ({dia:%d/%m}) — {len(notas)} jogador(es).")
    return placar, sorted(notas)


# ==================================================================== gravar

def grava(busca, time, placar, notas, nome=None):
    PASTA.mkdir(parents=True, exist_ok=True)
    nome = nome or galo.slug(f"{placar.get('casa', '')}-{placar.get('fora', '')}-{dt.date.today():%Y-%m-%d}")
    f = PASTA / f"{nome}.json"
    f.write_text(json.dumps({
        "jogo": busca, "time": time, "quando": dt.date.today().isoformat(),
        "placar": placar, "notas": [list(n) for n in notas]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return f


def main():
    p = argparse.ArgumentParser()
    p.add_argument("jogo", nargs="?", help='ex.: "Flamengo Atletico Mineiro"')
    p.add_argument("--time", default="Atlético Mineiro")
    p.add_argument("--nome", help="nome do arquivo no banco (padrão: times + data)")
    p.add_argument("--listar", action="store_true")
    a = p.parse_args()
    if a.listar or not a.jogo:
        for f in sorted(PASTA.glob("*.json")) if PASTA.exists() else []:
            d = json.loads(f.read_text(encoding="utf-8"))
            print(f"{f.name}: {d.get('jogo')} — {d.get('quando')} — {len(d.get('notas') or [])} jogador(es)")
        return
    r = do_fotmob(a.jogo, a.time)
    if not r:
        raise SystemExit(f"Não achei o jogo no FotMob: {a.jogo}")
    placar, notas = r
    f = grava(a.jogo, a.time, placar, notas, a.nome)
    for n, nome, _ in notas:
        print(f"  {n:>4}  {nome}")
    print(f"\n-> {f}")


if __name__ == "__main__":
    main()
