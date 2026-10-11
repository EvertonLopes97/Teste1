# -*- coding: utf-8 -*-
"""Procura uma imagem na internet ATÉ ACHAR e baixa (fotos de jogador, camisas, escudos...).

    python tools/busca_imagem.py "camisa 3 Flamengo 2026" [--exige flamengo,camisa] [--rosto]

Fontes, nesta ordem: Bing Imagens → DuckDuckGo → Wikimedia Commons → Openverse.
Só aceita a imagem quando o título/endereço cita as palavras exigidas (o time, o sobrenome do
jogador); com --rosto, a foto precisa ter UM rosto (YuNet) e é recortada no rosto/ombros.
Cache em tools/banco/web/ (a mesma busca não baixa de novo).
"""
import hashlib
import html
import json
import re
import subprocess
import sys
import unicodedata
import urllib.parse
from pathlib import Path

PONTE = Path(__file__).resolve().parents[1]
CACHE = PONTE / "tools" / "banco" / "web"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
RUIM = re.compile(r"logo|vector|clipart|cartoon|desenho|wallpaper|fifa\s?\d|pes\s?\d|efootball|figurinha|sticker|meme|montagem|png\s?tree", re.I)


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def pegar(url, binario=False, ref=""):
    """GET com cara de navegador (curl_cffi se instalado; senão curl)."""
    try:
        from curl_cffi import requests as cr
        r = cr.get(url, impersonate="chrome", timeout=25, headers={"Referer": ref} if ref else None)
        if r.status_code == 200:
            return r.content if binario else r.text
    except Exception:  # noqa: BLE001
        pass
    cmd = ["curl", "-sSL", "-m", "25", "-A", UA, "-H", "Accept-Language: pt-BR,pt;q=0.9,en;q=0.8"]
    if ref:
        cmd += ["-H", f"Referer: {ref}"]
    r = subprocess.run(cmd + [url], capture_output=True)
    if r.returncode != 0:
        return b"" if binario else ""
    return r.stdout if binario else r.stdout.decode("utf-8", "replace")


def bing(q):
    h = pegar("https://www.bing.com/images/search?form=HDRSC2&first=1&q=" + urllib.parse.quote(q))
    if 'murl' not in (h or ""):
        h = pegar("https://www.bing.com/images/async?first=0&count=35&mmasync=1&q=" + urllib.parse.quote(q))
    out = []
    for m in re.finditer(r'\bm="(\{[^"]+\})"', h or ""):
        try:
            d = json.loads(html.unescape(m.group(1)))
        except json.JSONDecodeError:
            continue
        if d.get("murl"):
            out.append({"url": d["murl"], "titulo": d.get("t", ""), "pagina": d.get("purl", ""), "fonte": "Bing"})
    return out


def duckduckgo(q):
    import time
    res = []
    for tentativa in range(3):  # o DuckDuckGo às vezes recusa quando são muitas buscas seguidas: espera e tenta de novo
        if tentativa:
            time.sleep(3 * tentativa)
        h = pegar("https://duckduckgo.com/?iax=images&ia=images&q=" + urllib.parse.quote(q))
        m = re.search(r'vqd=["\']?([\d-]+)', h or "")
        if not m:
            continue
        j = pegar(f"https://duckduckgo.com/i.js?l=br-pt&o=json&f=,,,,,&p=1&vqd={m.group(1)}&q=" + urllib.parse.quote(q),
                  ref="https://duckduckgo.com/")
        try:
            res = json.loads(j).get("results", [])
        except (json.JSONDecodeError, AttributeError):
            continue
        if res:
            break
    return [{"url": r.get("image", ""), "titulo": r.get("title", ""), "pagina": r.get("url", ""), "fonte": "DuckDuckGo",
             "w": r.get("width", 0), "h": r.get("height", 0)} for r in res if r.get("image")]


def commons(q):
    u = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=20"
         "&prop=imageinfo&iiprop=url|size&iiurlwidth=1200&gsrsearch=" + urllib.parse.quote(q))
    try:
        pages = json.loads(pegar(u) or "{}").get("query", {}).get("pages", {})
    except json.JSONDecodeError:
        return []
    out = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("thumburl") or ii.get("url"):
            out.append({"url": ii.get("thumburl") or ii["url"], "titulo": p.get("title", ""), "pagina": ii.get("descriptionurl", ""),
                        "fonte": "Wikimedia Commons", "w": ii.get("width", 0), "h": ii.get("height", 0)})
    return out


def openverse(q):
    try:
        d = json.loads(pegar("https://api.openverse.org/v1/images/?page_size=20&q=" + urllib.parse.quote(q)) or "{}")
    except json.JSONDecodeError:
        return []
    return [{"url": r["url"], "titulo": r.get("title", ""), "pagina": r.get("foreign_landing_url", ""), "fonte": "Openverse",
             "w": r.get("width", 0), "h": r.get("height", 0)} for r in d.get("results", []) if r.get("url")]


FONTES = [bing, duckduckgo, commons, openverse]


def um_rosto(img):
    """Recorte de rosto+ombros quando há exatamente um rosto; senão None."""
    import cv2
    modelo = PONTE / "yunet.onnx"
    if not modelo.exists():
        return img
    h, w = img.shape[:2]
    det = cv2.FaceDetectorYN.create(str(modelo), "", (w, h), 0.7)
    _, faces = det.detect(img)
    if faces is None or len(faces) != 1:
        return None
    x, y, fw, fh = faces[0][:4]
    if fw < 40:
        return None
    lado = int(fw * 2.6)
    cx, cy = x + fw / 2, y + fh * 0.75
    x0, y0 = int(max(0, cx - lado / 2)), int(max(0, cy - lado * 0.42))
    x1, y1 = int(min(w, x0 + lado)), int(min(h, y0 + lado))
    return img[y0:y1, x0:x1]


KIT_SITES = re.compile(r"footballkitarchive|todosobrecamisetas|mantosdofutebol|maquinadoesporte|footyheadlines|netshoes|centauro|"
                       r"lojavirtual|loja|store|shop|adidas|nike|puma|umbro|newbalance|kappa|volt|diadora|joma", re.I)
FALSO = re.compile(r"concept|conceito|fan ?made|\bvaza\w*|vazament|leak|fifakitcreator|kitdls|rumor|suposta|poss[ií]vel|esbo[cç]o|revelad|mockup|retro|replica antiga|"
                   r"\barte\b|vetor|vector|estampa|kit creator|pesmaster|brech[oó]|usad[ao]|f[oó]rum|enjoei|mercado ?livre|olx|"
                   r"pes ?20|fifa ?2\d|dream league|dls", re.I)
OUTRO_MODELO = re.compile(r"feminin|infantil|kids|women|torcedor? pro|regata|polo|treino|training|goleiro|goalkeeper", re.I)


def pontua(c, prefere, kit, evita=()):
    t = norm(f"{c['titulo']} {c['pagina']} {urllib.parse.unquote(c['url'])}")
    s = sum(2 for p in prefere if p and re.search(rf"\b{re.escape(p)}", t))
    s -= sum(5 for e in evita if e and re.search(rf"\b{re.escape(e)}", t))  # outra temporada
    if kit and KIT_SITES.search(f"{c['pagina']} {c['url']}"):
        s += 4
    if FALSO.search(f"{c['titulo']} {c['pagina']}"):
        s -= 8
    if kit and OUTRO_MODELO.search(f"{c['titulo']} {c['pagina']}"):
        s -= 3  # camisa feminina/infantil/treino/goleiro: só se não tiver a de jogo
    w, h = c.get("w") or 0, c.get("h") or 0
    if w and h and min(w, h) >= 600:
        s += 1
    return s


# faixas HSV (OpenCV: H 0-180) da cor principal da camisa citada no roteiro
FAIXAS = {
    "laranja": [((5, 120, 120), (22, 255, 255))],
    "amarel": [((20, 90, 110), (35, 255, 255))],
    "dourad": [((15, 60, 90), (35, 255, 255))],
    "verde": [((36, 60, 40), (90, 255, 255))],
    "azul": [((88, 70, 50), (130, 255, 255))],
    "celeste": [((85, 40, 90), (115, 255, 255))],
    "vermelh": [((0, 110, 70), (8, 255, 255)), ((165, 110, 70), (180, 255, 255))],
    "vinho": [((0, 70, 25), (10, 255, 150)), ((158, 70, 25), (180, 255, 150))],
    "grena": [((0, 70, 25), (10, 255, 150)), ((158, 70, 25), (180, 255, 150))],
    "rox": [((130, 60, 40), (158, 255, 255))],
    "ros": [((150, 40, 120), (175, 255, 255))],
    "pret": [((0, 0, 0), (180, 255, 60))],
    "branc": [((0, 0, 170), (180, 45, 255))],
    "off white": [((0, 0, 160), (180, 60, 255))],
    "creme": [((0, 0, 160), (180, 70, 255))],
    "bege": [((5, 20, 120), (30, 110, 255))],
    "cinza": [((0, 0, 70), (180, 35, 185))],
}


def cor_principal(tema):
    """Primeira cor citada (a da camisa no roteiro), como chave de FAIXAS."""
    for t in tema:
        t = norm(t)
        for k in FAIXAS:
            if t.startswith(k) or (k == "celeste" and "celeste" in t):
                return "celeste" if "celeste" in t else k
    return None


def tem_cor(img, cor, minimo=0.10):
    """A camisa tem a cor do roteiro? Fração de pixels da cor no miolo da imagem (onde fica a camisa)."""
    import cv2
    import numpy as np
    h, w = img.shape[:2]
    miolo = img[int(h * 0.15):int(h * 0.85), int(w * 0.2):int(w * 0.8)]
    # fundo de foto de loja (branco/cinza liso) não conta: tira os pixels da cor da borda
    borda = np.concatenate([img[:4].reshape(-1, 3), img[-4:].reshape(-1, 3), img[:, :4].reshape(-1, 3), img[:, -4:].reshape(-1, 3)])
    fundo = np.median(borda, axis=0)
    liso = float(np.mean(np.abs(borda.astype(int) - fundo).sum(1) < 40)) > 0.6
    util = np.ones(miolo.shape[:2], bool)
    if liso:
        util = np.abs(miolo.astype(int) - fundo).sum(2) > 40
    if util.mean() < 0.05:
        return False
    hsv = cv2.cvtColor(miolo, cv2.COLOR_BGR2HSV)
    m = np.zeros(hsv.shape[:2], np.uint8)
    for lo, hi in FAIXAS[cor]:
        m |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
    return float((m > 0)[util].mean()) >= minimo


def anos_no(texto):
    """Anos citados: 2026, 2025/26, 2025-2026, 25/26, 25-26, 22/23 (temporada com dois dígitos)."""
    anos = {int(y) for y in re.findall(r"(?<!\d)(20\d\d)(?!\d)", texto)}
    for a, b in re.findall(r"(?<![\d/.-])(\d\d)\s?[/-]\s?(\d\d)(?![\d/.-])", texto):
        a, b = int(a), int(b)
        if 10 <= a <= 40 and b == (a + 1) % 100:
            anos |= {2000 + a, 2000 + b}
    return anos


MARCAS = re.compile(r"\b(adidas|nike|puma|umbro|new balance|kappa|volt|diadora|joma|reebok|le coq|penalty|lupo|topper|mizuno|under armour|hummel|castore|macron)\b", re.I)
CORES = re.compile(r"^(azul celeste|azul|celeste|laranja|pret[ao]|verde esmeralda|verde|vermelh[ao]|amarel[ao]|branc[ao]|vinho|dourad[ao]|off white|bege|ros[ao]|rox[ao]|cinza|grena|prata|creme|marrom)$")
NAO_KIT = re.compile(r"goleiro|goalkeeper|\bgk\b|treino|training|entrenamiento|pre ?jogo|pre ?match|pre ?partida|pre ?game|aquecimento|warm ?up|"
                     r"\bpolo\b|regata|jaqueta|agasalho|moletom|bermuda|calcao|shorts|meiao|chuteira|bola", re.I)


def buscar(q, exige=(), rosto=False, destino=None, minimo=300, log=print, alternativas=(), prefere=(), kit=False, evita=(),
           ano=None, tema=(), nao=(), extras=(), marca=""):
    """Devolve {file, fonte, titulo, pagina} ou None. Junta candidatos das fontes, só aceita os que
    citam TODAS as palavras exigidas (e pelo menos uma de cada grupo de alternativas), e baixa na
    ordem de pontuação (site de camisas, ano/marca/cor citados; "concept"/"fan made" fica de fora)."""
    import cv2
    import numpy as np
    exige = [norm(e) for e in exige if norm(e)]
    alternativas = [[norm(x) for x in g if norm(x)] for g in alternativas if g]
    prefere = [norm(p) for p in prefere if norm(p)]
    evita = [norm(e) for e in evita if norm(e)]
    tema = [norm(t) for t in tema if norm(t)]
    nao = [norm(x) for x in nao if norm(x)]
    frases = [t for t in tema if not CORES.match(t) and not re.fullmatch(r"\d+", t)]
    cor = cor_principal(tema) if kit else None
    buscas = list(dict.fromkeys([q, *extras]))
    chave = hashlib.sha1(f"{buscas}|{','.join(exige)}|{alternativas}|{rosto}|{kit}|{evita}|{ano}|{tema}|{nao}|{marca}".encode()).hexdigest()[:16]
    CACHE.mkdir(parents=True, exist_ok=True)
    meta = CACHE / f"{chave}.json"
    if meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        if Path(m.get("file", "")).exists():
            return m

    def passa(c):
        texto = norm(f"{c['titulo']} {c['pagina']} {urllib.parse.unquote(c['url'])}")
        if exige and not all(re.search(rf"\b{re.escape(e)}", texto) for e in exige):
            return False
        if any(not any(re.search(rf"\b{re.escape(x)}", texto) for x in g) for g in alternativas):
            return False
        if any(re.search(rf"\b{re.escape(x)}\b", texto) for x in nao):
            return False  # outro clube (Inter Miami, Atlético Madrid...)
        if kit and not re.search(r"\b(camis|uniform|kit|jersey|shirt|manto|maglia|trikot|third|iii)", texto):
            return False  # notícia de jogo ("terceira fase da Copinha") não é camisa
        if kit and re.search(r"\b(selecao|copinha|sub ?\d\d|futebol internacional|feminino)\b", texto):
            return False
        if kit and NAO_KIT.search(norm(f"{c['titulo']} {c['pagina']}")):
            return False  # camisa de goleiro/treino/polo: não é a camisa 3 de jogo
        if ano:
            # SÓ a camisa do ano pedido: título/endereço com outro ano (2025, 2024/25, notícia de 2025) fica fora
            anos = anos_no(f"{c['titulo']} {c['pagina']} {c['url']}")
            permitidos = {int(ano), int(ano) + 1} | anos_no(" ".join(tema))  # "MUNDIAL 2006" é tema, não temporada
            if anos and (anos - permitidos):
                return False
            # sem ano nenhum no título/endereço: só vale se citar o nome/inspiração da camisa (ou, sem nome
            # no roteiro, a marca + a cor); "Camisa adidas Fluminense III Verde" sem ano pode ser de 2018
            if not anos:
                if frases:
                    if not any(re.search(rf"\b{re.escape(t)}", texto) for t in frases):
                        return False
                elif not (marca and re.search(rf"\b{re.escape(norm(marca))}", texto) and any(re.search(rf"\b{re.escape(t)}", texto) for t in tema)):
                    return False
        if kit and marca:
            # outra fornecedora no título = outra camisa (o roteiro diz Puma, o anúncio diz adidas)
            outras = {m.lower() for m in MARCAS.findall(norm(f"{c['titulo']} {c['pagina']}"))} - {norm(marca)}
            if outras and not re.search(rf"\b{re.escape(norm(marca))}", texto):
                return False
        return not RUIM.search(c["titulo"] or "") and not (kit and FALSO.search(f"{c['titulo']} {c['pagina']}"))

    # junta os candidatos de TODAS as buscas (nome da camisa, ano, "terceiro uniforme", inglês) e fica com o melhor
    cands, vistos = [], set()
    for busca in buscas:
        for fonte in FONTES:
            try:
                achados = [c for c in fonte(busca)[:100] if c["url"] not in vistos and passa(c)]
            except Exception as e:  # noqa: BLE001
                log(f"  {fonte.__name__}: {e}")
                continue
            vistos.update(c["url"] for c in achados)
            cands += achados
            if len(cands) >= 12:
                break
    pref = [*prefere, *[f for f in frases if f not in prefere]]
    cands.sort(key=lambda c: -(pontua(c, pref, kit, evita) + sum(3 for f in frases if re.search(rf"\b{re.escape(f)}", norm(f"{c['titulo']} {c['pagina']}")))
                               + (3 if ano and int(ano) in anos_no(f"{c['titulo']} {c['pagina']} {c['url']}") else 0)))
    for c in cands[:20]:
        dado = pegar(c["url"], binario=True, ref=c.get("pagina", ""))
        if not dado or len(dado) < 5000:
            continue
        img = cv2.imdecode(np.frombuffer(dado, np.uint8), cv2.IMREAD_COLOR)
        if img is None or min(img.shape[:2]) < minimo:
            continue
        if kit and cor and not tem_cor(img, cor):
            log(f"  cor não bate ({cor}): {c['titulo'][:60]}")
            continue  # o roteiro diz camisa vinho; a foto é de uma camisa branca = outra camisa
        if rosto:
            img = um_rosto(img)
            if img is None or min(img.shape[:2]) < 120:
                continue
        if max(img.shape[:2]) > 1400:
            k = 1400 / max(img.shape[:2])
            img = cv2.resize(img, (int(img.shape[1] * k), int(img.shape[0] * k)), interpolation=cv2.INTER_AREA)
        out = Path(destino) if destino else CACHE / f"{chave}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        ok, buf = cv2.imencode(out.suffix or ".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90] if out.suffix != ".webp" else [cv2.IMWRITE_WEBP_QUALITY, 85])
        if not ok:
            continue
        out.write_bytes(buf.tobytes())
        m = {"file": str(out), "fonte": c["fonte"], "titulo": c["titulo"], "pagina": c["pagina"], "busca": q, "url": c["url"]}
        meta.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        return m
    return None


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("busca")
    ap.add_argument("--exige", default="")
    ap.add_argument("--rosto", action="store_true")
    a = ap.parse_args()
    r = buscar(a.busca, [x for x in a.exige.split(",") if x], a.rosto)
    print(json.dumps(r, ensure_ascii=False, indent=1) if r else "Nada encontrado.")
    sys.exit(0 if r else 1)
