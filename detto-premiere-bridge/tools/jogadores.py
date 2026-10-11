# -*- coding: utf-8 -*-
"""Fotos dos jogadores e escudos dos times citados no roteiro, CONFERIDOS.

    python tools/jogadores.py <job>/EDIT_PLAN.json        → <job>/jogadores.json

Regras (para nunca aparecer foto de outra pessoa):
  - o jogador é procurado no ELENCO ATUAL do time dele no SofaScore (não numa busca geral);
  - só entra a foto quando o nome bate com UM jogador do elenco; na dúvida, fica sem foto
    (o card mostra as iniciais) e o nome vai para a lista "sem_foto" do relatório;
  - jogadores do Galo usam as fotos oficiais do site (tools/galo/banco/elenco), sem fundo;
  - escudos pelo id do time (tools/roteiro/times.json).
Tudo fica guardado em tools/banco (baixa uma vez só).
"""
import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

PONTE = Path(__file__).resolve().parents[1]
BANCO = PONTE / "tools" / "banco"
TIMES = json.loads((PONTE / "tools" / "roteiro" / "times.json").read_text(encoding="utf-8"))["times"]
GALO = PONTE / "tools" / "galo" / "banco" / "elenco"
UA = "Mozilla/5.0"
API = "https://api.sofascore.com/api/v1"
IMG = "https://api.sofascore.app/api/v1"


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def slug(s):
    return norm(s).replace(" ", "-")


HEAD = ["-H", "Referer: https://www.sofascore.com/", "-H", "Origin: https://www.sofascore.com", "-H", "Accept: application/json"]
AVISOS = set()


def get_json(url):
    # com o curl_cffi instalado (pip install curl_cffi) a conexão parece a do Chrome e o SofaScore não bloqueia
    try:
        from curl_cffi import requests as cr
        r = cr.get(url, impersonate="chrome", timeout=25, headers={"Referer": "https://www.sofascore.com/"})
        if r.status_code == 200:
            return r.json()
        AVISOS.add(f"SofaScore respondeu {r.status_code} em {url.split('/api/v1/')[-1].split('?')[0]}")
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001
        AVISOS.add(f"curl_cffi: {e}")
    # bytes → UTF-8 (no Windows o texto do subprocess viria em cp1252 e estragaria os acentos)
    r = subprocess.run(["curl", "-sS", "-m", "25", "-A", UA, *HEAD, "-w", "\n%{http_code}", url], capture_output=True)
    corpo, _, cod = r.stdout.decode("utf-8", "replace").rpartition("\n")
    if cod.strip() != "200":
        AVISOS.add(f"SofaScore respondeu {cod.strip() or r.returncode} em {url.split('/api/v1/')[-1].split('?')[0]}")
    try:
        return json.loads(corpo or "{}")
    except json.JSONDecodeError:
        return {}


def baixar(url, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["curl", "-sSfL", "-m", "40", "-A", UA, "-o", str(destino), url], capture_output=True)
    return r.returncode == 0 and destino.exists() and destino.stat().st_size > 500


def elenco(team_id):
    """Elenco atual do time (cache de 3 dias)."""
    f = BANCO / "elencos" / f"{team_id}.json"
    if f.exists() and time.time() - f.stat().st_mtime < 3 * 86400:
        return json.loads(f.read_text(encoding="utf-8"))
    # dois endereços do SofaScore (site e app): se um bloquear, tenta o outro
    d = {}
    for base in (API, IMG):
        d = get_json(f"{base}/team/{team_id}/players")
        if d.get("players"):
            break
    lst = [{"id": p["player"]["id"], "name": p["player"].get("name", ""), "short": p["player"].get("shortName", ""),
            "pos": p["player"].get("position", "")} for p in d.get("players", []) if p.get("player")]
    if lst:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(lst, ensure_ascii=False), encoding="utf-8")
        return lst
    # SofaScore bloqueou (403): usa o elenco guardado no projeto (vem no git pull), mesmo antigo
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return lst


def pela_busca(nome, team_id):
    """Plano B (quando o elenco não vem): busca do SofaScore, só aceita jogador DESSE time."""
    import urllib.parse
    d = {}
    for base in (API, IMG):
        d = get_json(f"{base}/search/all?q=" + urllib.parse.quote(nome))
        if d.get("results"):
            break
    lst = [{"id": e["id"], "name": e.get("name", ""), "short": e.get("shortName", ""), "pos": e.get("position", "")}
           for x in d.get("results", []) if x.get("type") == "player"
           for e in [x.get("entity") or {}] if (e.get("team") or {}).get("id") == team_id]
    return casar(nome, lst)


def casar(nome, lista):
    """Jogador do elenco com esse nome. Só devolve quando não há ambiguidade."""
    alvo = norm(nome)
    toks = alvo.split()
    exatos = [p for p in lista if norm(p["name"]) == alvo or norm(p["short"]) == alvo]
    if len(exatos) == 1:
        return exatos[0]
    if len(exatos) > 1:
        return None
    if len(toks) > 1:
        # todos os pedaços do nome aparecem no nome do elenco ("Alex Telles" → "Alex Telles")
        c = [p for p in lista if all(t in norm(p["name"]).split() for t in toks)]
        if len(c) == 1:
            return c[0]
        # sobrenome + inicial ("T. Pérez" → "Tomás Pérez")
        c = [p for p in lista if norm(p["name"]).split()[-1:] == toks[-1:] and norm(p["name"])[:1] == toks[0][:1]]
        if len(c) == 1:
            return c[0]
        # apelido + sobrenome ("Flaco López" → José Manuel López): o sobrenome é único no elenco
        c = [p for p in lista if norm(p["name"]).split()[-1:] == toks[-1:]]
        return c[0] if len(c) == 1 else None
    # nome de uma palavra ("Ronaldo", "Matheuzinho"): precisa ser o nome usado (curto) ou o único com essa palavra
    c = [p for p in lista if toks[0] in norm(p["name"]).split() or toks[0] in norm(p["short"]).replace(".", " ").split()]
    return c[0] if len(c) == 1 else None


def sem_fundo(src, dst, lado=256):
    """Foto do SofaScore (fundo branco) → PNG com o fundo transparente (recorte simples pelas bordas)."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return False
    data = np.frombuffer(Path(src).read_bytes(), np.uint8)
    im = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if im is None:
        return False
    im = cv2.resize(im, (lado, lado), interpolation=cv2.INTER_LANCZOS4)
    h, w = im.shape[:2]
    mask = np.zeros((h + 2, w + 2), np.uint8)
    for x, y in [(0, 0), (w - 1, 0), (0, h // 3), (w - 1, h // 3), (w // 2, 0), (w // 4, 0), (3 * w // 4, 0)]:
        if im[y, x].min() > 225:
            cv2.floodFill(im.copy(), mask, (x, y), 0, (22, 22, 22), (22, 22, 22), cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8))
    alpha = 255 - mask[1:-1, 1:-1]
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    rgba = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = alpha
    ext = Path(dst).suffix.lower() or ".png"
    ok, buf = cv2.imencode(ext, rgba, [cv2.IMWRITE_WEBP_QUALITY, 85] if ext == ".webp" else [])
    if ok:
        Path(dst).write_bytes(buf.tobytes())
    return ok


def baixar_foto(pid, dst):
    """Foto do jogador no SofaScore → sem o fundo branco → dst (.webp)."""
    tmp = Path(dst).with_suffix(".orig")
    if baixar(f"{IMG}/player/{pid}/image", tmp):
        if not sem_fundo(tmp, dst):
            tmp.replace(dst)
    if tmp.exists():
        tmp.unlink()
    return Path(dst).exists()


def foto_galo(nome):
    alvos = {slug(nome)}
    if " " in nome:
        alvos.add(slug(nome.split()[-1]))
    for p in sorted(GALO.glob("*.*")):
        if p.stem in alvos:
            return p
    return None


def escudo(t):
    dst = BANCO / "escudos" / f"{t['sigla']}.png"
    if not dst.exists():
        tmp = dst.with_suffix(".webp")
        if baixar(f"{IMG}/team/{t['sofa']}/image", tmp):
            try:
                import cv2
                im = cv2.imdecode(__import__("numpy").frombuffer(tmp.read_bytes(), "uint8"), cv2.IMREAD_UNCHANGED)
                cv2.imwrite(str(dst), im)
                tmp.unlink()
            except Exception:
                tmp.rename(dst)
    return str(dst) if dst.exists() else ""


def main():
    if len(sys.argv) < 2:
        raise SystemExit("uso: python tools/jogadores.py <EDIT_PLAN.json> [saida.json]")
    plano = Path(sys.argv[1])
    saida = Path(sys.argv[2]) if len(sys.argv) > 2 else plano.with_name("jogadores.json")
    plan = json.loads(plano.read_text(encoding="utf-8"))
    pessoas = (plan.get("meta") or {}).get("people") or []
    # times citados nos componentes (placares, duelo)
    siglas = {p["sigla"] for p in pessoas if p.get("sigla")}
    for s in (plan.get("meta") or {}).get("segments") or []:
        for c in s.get("comps") or []:
            d = c.get("data") or {}
            for it in d.get("items") or []:
                siglas.add(it.get("sigla"))
            for g in d.get("groups") or []:
                for m in g.get("games") or []:
                    siglas.update([m.get("siglaA"), m.get("siglaB")])
            siglas.update([d.get("siglaA"), d.get("siglaB"), (d.get("a") or {}).get("sigla") if isinstance(d.get("a"), dict) else None,
                           (d.get("b") or {}).get("sigla") if isinstance(d.get("b"), dict) else None])
    siglas.discard(None)
    siglas.discard("")
    out = {"players": {}, "teams": {}, "sem_foto": []}
    for sg in sorted(siglas):
        t = next((x for x in TIMES if x["sigla"] == sg), None)
        if t:
            out["teams"][sg] = {"nome": t["nome"], "crest": escudo(t)}
    from busca_imagem import buscar

    def na_internet(nome, time_nome):
        """Não achou no banco nem no SofaScore: procura na internet até achar (foto com UM rosto)."""
        sobrenome = norm(nome).split()[-1]
        for q in ([f"{nome} {time_nome}", f"{nome} {time_nome} jogador", f"{nome} futebol"] if time_nome else [f"{nome} futebol", f"{nome} técnico"]):
            r = buscar(q, [sobrenome], rosto=True, log=lambda m: None)
            if r:
                return r
        return None

    for p in pessoas:
        nome = p["name"]
        t = next((x for x in TIMES if x["sigla"] == p.get("sigla")), None)
        dst = None
        j = None
        if t and t["sigla"] == "CAM":
            f = foto_galo(nome)
            if f:
                out["players"][nome] = {"photo": str(f), "fonte": "site do Atlético"}
                continue
        if t:
            lista = elenco(t["sofa"])
            j = casar(nome, lista) if lista else None
            if not j:
                j = pela_busca(nome, t["sofa"])
        if j:
            # banco pronto (vem no git pull): tools/banco/jogadores/<id>.webp — sem internet
            dst = BANCO / "jogadores" / f"{j['id']}.webp"
            if not dst.exists() and dst.with_suffix(".png").exists():
                dst = dst.with_suffix(".png")
            if not dst.exists():
                baixar_foto(j["id"], dst)
                time.sleep(0.2)
        if dst is not None and dst.exists():
            out["players"][nome] = {"photo": str(dst), "fonte": f"SofaScore: {j['name']} ({t['nome']})"}
            continue
        r = na_internet(nome, t["nome"] if t else "")
        if r:
            out["players"][nome] = {"photo": r["file"], "fonte": f"internet ({r['fonte']}): {r['titulo'][:70]}"}
        else:
            out["sem_foto"].append(f"{nome} ({t['nome'] if t else 'sem time'}: não achei nem na internet)")

    # fotos pedidas no roteiro (camisas, VISUAL): procura na internet até achar
    out["imagens"] = {}
    for s in (plan.get("meta") or {}).get("segments") or []:
        for c in s.get("comps") or []:
            if c.get("type") != "fotos":
                continue
            for it in c["data"].get("items", []):
                q = it.get("query", "")
                if not q or q in out["imagens"]:
                    continue
                # até achar: a busca do roteiro, sem o ano, em inglês (sites de camisas) e sem o ano de novo
                ingles = q.replace("terceira camisa", "third kit").replace("segunda camisa", "away kit").replace("camisa", "home kit")
                sem_ano = lambda x: re.sub(r"\s*\b20\d\d\b", "", x).strip()  # noqa: E731
                r = None
                for v in dict.fromkeys([q, sem_ano(q), ingles, sem_ano(ingles)]):
                    r = buscar(v, it.get("exige") or [], log=lambda m: None)
                    if r:
                        break
                if r:
                    out["imagens"][q] = r
                else:
                    out["sem_foto"].append(f"imagem: {q} (não achei)")
    saida.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(pessoas)
    print(f"Fotos conferidas: {len(out['players'])}/{n} jogadores, {sum(1 for x in out['teams'].values() if x['crest'])}/{len(out['teams'])} escudos"
          + (f", {len(out['imagens'])} imagens da internet" if out["imagens"] else ""))
    for s in out["sem_foto"]:
        print(f"  sem foto: {s}")
    for a in sorted(AVISOS)[:5]:
        print(f"  aviso: {a}")
    print(f"→ {saida}")


if __name__ == "__main__":
    main()
