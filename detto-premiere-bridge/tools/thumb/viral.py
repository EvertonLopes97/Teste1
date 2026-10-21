# -*- coding: utf-8 -*-
"""THUMB VIRAL de qualquer vídeo: VOCÊ (sua melhor reação, recortado com contorno) + UM QUADRO DO VÍDEO (o lance, a
notícia, o lugar, o jogo) + O ASSUNTO em texto gigante (2–4 palavras, uma em destaque) + selo/escudo/jogador.

    python tools\\thumb\\viral.py --rosto "gravacao.mp4" --quadro "video_final.mp4" --assunto "Hulk volta ao Galo" \\
        [--texto "HULK VOLTOU" --destaque HULK --selo URGENTE --extra jogador.png --estilo noticia|futebol|vlog|gameplay]

Usado por: editar.py (thumb.py), canal de notícias (canal.py) e canal Everton Lopes (canal_vlog.py).
- Rosto: os quadros com a reação mais forte (MediaPipe) dos vídeos em --rosto; sem rosto neles → a sua FOTO PADRÃO
  (DETTO_FOTO, ou <DETTO>\\marca\\eu.jpg / <DETTO>\\thumb_rosto\\*.jpg). Recorte falhou → recorte quadrado no rosto.
- Quadro: o mais NÍTIDO e colorido do vídeo (ou das faixas de tempo dadas), sem quadro preto/borrado.
- Texto: --texto; senão a IA (Gemini → IAs grátis → Claude, só texto) escreve a partir do assunto; senão o próprio assunto.
- Desenho: Chromium (viral.js, 3 versões); se falhar, um desenho mais simples pelo Python (nunca fica sem thumb).
Saída: <saida>\\thumb_1.jpg … thumb_3.jpg (1280x720, < 2 MB) + thumbs.jpg (todas juntas para comparar).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
FONTES = PONTE / "fonts"
VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv", ".avi", ".mts", ".webm"}
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}

ESTILOS = {
    # cor de destaque, cor da luz, selo padrão
    "noticia": {"cor": "#FFD400", "luz": "rgba(255,59,59,.8)", "selo": "URGENTE", "selo_cor": "#E6282D"},
    "futebol": {"cor": "#FFE600", "luz": "rgba(182,255,59,.7)", "selo": "", "selo_cor": "#E6282D"},
    "vlog": {"cor": "#C8FF3D", "luz": "rgba(255,200,120,.55)", "selo": "", "selo_cor": "#111111"},
    "gameplay": {"cor": "#C8FF3D", "luz": "rgba(150,90,255,.85)", "selo": "GAMEPLAY", "selo_cor": "#965AFF"},
}


def log(m):
    print(m, flush=True)


def duracao(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return 0.0


def _filtro_cor(video):
    sys.path.insert(0, str(TOOLS))
    try:
        from cor import filtro_cor  # HDR do iPhone → SDR

        return filtro_cor(str(video)) or ""
    except Exception:
        return ""


def _extrai(video, t, saida, altura=1080):
    cor = _filtro_cor(video)
    vf = (f"{cor}," if cor else "") + f"scale=-2:'min({altura},ih)'"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t):.2f}", "-i", str(video), "-frames:v", "1", "-vf", vf,
                    "-q:v", "2", str(saida)], capture_output=True)
    return Path(saida) if Path(saida).exists() and Path(saida).stat().st_size > 2000 else None


# ------------------------------------------------------------------ você
def foto_padrao():
    """a sua foto para quando o vídeo não tem o seu rosto (vlog só de paisagem, notícia sem máscara)"""
    cand = []
    if os.environ.get("DETTO_FOTO"):
        cand.append(Path(os.environ["DETTO_FOTO"]))
    raizes = [Path("E:/DETTO")] if os.name == "nt" else []
    raizes.append(Path.home() / "DETTO")
    for r in raizes:
        cand += sorted((r / "marca").glob("eu.*")) + sorted((r / "thumb_rosto").glob("*"))
    return [p for p in cand if p.exists() and p.suffix.lower() in IMG_EXT]


def reacoes_de(videos, saida, n=3, log=log):
    """as n reações mais fortes somando todos os vídeos (cada uma copiada para a pasta de saída)"""
    sys.path.insert(0, str(AQUI))
    from thumb import reacoes

    todas = []
    for k, v in enumerate(videos):
        try:
            for nota, t, f in reacoes(v, n):
                dest = Path(saida) / f"_reacao_{k}_{int(t * 10)}.jpg"
                shutil.copyfile(f, dest)
                todas.append((nota, v, t, dest))
        except Exception as e:
            log(f"thumb: rosto em {Path(v).name}: {str(e)[:120]}")
    todas.sort(key=lambda x: -x[0])
    return todas[:n]


_YUNET = {}


def _caixa_rosto(img):
    """o maior rosto (x, y, w, h) em pixels, ou None"""
    import cv2
    h, w = img.shape[:2]
    try:
        if (w, h) not in _YUNET:
            _YUNET[(w, h)] = cv2.FaceDetectorYN.create(str(PONTE / "yunet.onnx"), "", (w, h), 0.6)
        _, f = _YUNET[(w, h)].detect(img)
        fs = [tuple(int(v) for v in x[:4]) for x in (f if f is not None else [])]
    except Exception:
        c = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        fs = [tuple(x) for x in c.detectMultiScale(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 1.1, 6)]
    return max(fs, key=lambda q: q[2] * q[3]) if fs else None


def recorta_voce(quadro, saida):
    """você recortado em PNG transparente (recorte do 'texto atrás'); se o recorte falhar ou sair ruim, um corte
    quadrado em volta do rosto (o desenho põe moldura branca)"""
    import cv2
    import numpy as np
    # BUSTO: thumb precisa do rosto GRANDE — corta da cabeça até o peito antes de recortar (gravação em pé, 9:16)
    img0 = cv2.imread(str(quadro))
    c = _caixa_rosto(img0) if img0 is not None else None
    if c:
        h0, w0 = img0.shape[:2]
        x, y, fw, fh = c
        cx = x + fw / 2
        y0, y1 = int(max(0, y - 0.9 * fh)), int(min(h0, y + fh * 3.4))
        x0, x1 = int(max(0, cx - 2.1 * fh)), int(min(w0, cx + 2.1 * fh))
        if (y1 - y0) < h0 * 0.95 or (x1 - x0) < w0 * 0.95:
            quadro = Path(saida).with_name(Path(saida).stem + "_busto.jpg")
            cv2.imwrite(str(quadro), img0[y0:y1, x0:x1], [cv2.IMWRITE_JPEG_QUALITY, 95])
    try:
        sys.path.insert(0, str(AQUI))
        from thumb import recorte

        recorte(quadro, saida)
        a = cv2.imread(str(saida), cv2.IMREAD_UNCHANGED)
        if a is not None and a.shape[2] == 4 and (a[:, :, 3] > 128).mean() > 0.08:
            return saida, True
    except Exception as e:
        log(f"thumb: recorte falhou ({str(e)[:100]}) — uso o rosto em quadro")
    img = cv2.imread(str(quadro))
    c = _caixa_rosto(img)
    h, w = img.shape[:2]
    if c:
        x, y, fw, fh = c
        lado = int(fh * 2.6)
        cx, cy = x + fw // 2, y + int(fh * 0.75)
        x0, y0 = max(0, cx - lado // 2), max(0, cy - lado // 2)
        img = img[y0: min(h, y0 + lado), x0: min(w, x0 + lado)]
    rgba = np.dstack([img, np.full(img.shape[:2], 255, np.uint8)])
    cv2.imwrite(str(saida), rgba)
    return saida, False


# ------------------------------------------------------------------ quadro do vídeo
def melhores_quadros(video, faixas=None, n=3, sem_rosto_grande=False):
    """os n quadros mais bonitos (nítido + colorido + bem exposto), espaçados; faixas = [(ini, fim)] onde procurar"""
    import cv2
    import numpy as np
    d = duracao(video)
    if not faixas:
        faixas = [(min(2.0, d * 0.05), max(0.5, d - 1.0))]
    tempos = []
    total = sum(max(0.0, b - a) for a, b in faixas) or 1.0
    for a, b in faixas:
        k = max(2, int(36 * (b - a) / total))
        tempos += [a + (b - a) * (i + 0.5) / k for i in range(k)]
    cor = _filtro_cor(video)
    notas = []
    tmp = Path(os.environ.get("TEMP", "/tmp")) / "detto_thumb_quadros"
    tmp.mkdir(parents=True, exist_ok=True)
    for i, t in enumerate(tempos):
        f = tmp / f"q{i:03d}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf",
                        (f"{cor}," if cor else "") + "scale=480:-2", "-q:v", "4", str(f)], capture_output=True)
        img = cv2.imread(str(f))
        if img is None:
            continue
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        nit = cv2.Laplacian(g, cv2.CV_64F).var()
        b, gg, r = [img[:, :, k].astype(np.float32) for k in range(3)]
        rg, yb = np.abs(r - gg), np.abs(0.5 * (r + gg) - b)
        colorido = np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2)
        luz = g.mean() / 255
        if luz < 0.12 or luz > 0.93 or g.std() < 18:
            continue  # preto, estourado ou liso (transição/vinheta)
        nota = min(1.0, nit / 250) * (0.4 + min(1.0, colorido / 60)) * (1 - abs(luz - 0.5))
        if sem_rosto_grande:
            c = _caixa_rosto(img)
            if c and c[3] > img.shape[0] * 0.45:
                nota *= 0.5
        notas.append((nota, t))
    for f in tmp.glob("q*.jpg"):
        f.unlink(missing_ok=True)
    notas.sort(key=lambda x: -x[0])
    esc = []
    for nota, t in notas:
        if all(abs(t - e) >= max(4.0, d / 20) for e in esc):
            esc.append(t)
        if len(esc) == n:
            break
    return esc or [d * 0.4]


# ------------------------------------------------------------------ texto
def texto_viral(assunto, estilo="futebol", log=log):
    """(texto, destaque, selo): 2–4 palavras que dão vontade de clicar, sem mentir"""
    if not assunto:
        return "OLHA ISSO", "ISSO", ""
    try:
        sys.path.insert(0, str(TOOLS / "reels"))
        from reels import gemini_json

        tipo = {"noticia": "notícias do Atlético-MG (o Galo)", "vlog": "vlog de viagem/dia a dia", "gameplay": "gameplay de videogame"}.get(estilo, "futebol")
        g = gemini_json([{"text": f"""Vídeo do YouTube de {tipo}. Assunto: {assunto[:1500]}
Escreva o TEXTO DA THUMB: 2 a 4 palavras em MAIÚSCULAS que dão vontade de clicar (curiosidade, choque, polêmica), SEM mentir
e sem repetir o título inteiro. Use nome de jogador/time/lugar se for o centro do assunto. Diga a palavra a destacar e um selo
curto opcional (ex.: URGENTE, OFICIAL, POLÊMICA, VAZOU, AO VIVO NÃO; vazio se não combinar).
Responda SÓ JSON: {{"texto": "...", "destaque": "...", "selo": "..."}}"""}], temperatura=0.9)
        if g and g.get("texto"):
            return str(g["texto"]).upper()[:40], str(g.get("destaque") or "").upper(), str(g.get("selo") or "").upper()[:14]
    except Exception as e:
        log(f"thumb: IA do texto não respondeu ({str(e)[:100]})")
    # sem IA: as primeiras palavras do assunto (nome de arquivo tipo IMG_1853 não serve)
    palavras = re.sub(r"[^A-Za-zÀ-ÿ0-9 ]", " ", re.sub(r"\b(IMG|VID|DSC|MVI|PXL)[_ -]?\d+\w*", " ", assunto, flags=re.I)).upper().split()
    palavras = [p for p in palavras if len(p) > 2 and not p.isdigit()][:4]
    if not palavras:
        palavras = {"vlog": ["OLHA", "ESSE", "LUGAR"], "gameplay": ["OLHA", "ESSA", "JOGADA"], "noticia": ["NOTÍCIA", "DO", "GALO"]}.get(estilo, ["OLHA", "ISSO"])
    return " ".join(palavras), max(palavras, key=len), ""


# ------------------------------------------------------------------ desenho
def desenha_pil(spec, saida):
    """desenho reserva (sem Chromium): quadro do vídeo de fundo, você à direita, texto à esquerda"""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
    W, H = 1280, 720
    q = Image.open(spec["quadro"]).convert("RGB")
    s = max(W / q.width, H / q.height)
    q = q.resize((int(q.width * s) + 1, int(q.height * s) + 1)).crop((0, 0, W, H))
    img = ImageEnhance.Brightness(q.filter(ImageFilter.GaussianBlur(3))).enhance(0.55)
    v = Image.open(spec["voce"]).convert("RGBA")
    alt = 700
    v = v.resize((max(1, int(v.width * alt / v.height)), alt))
    if not spec.get("voce_recortado"):
        borda = Image.new("RGBA", (v.width + 16, v.height + 16), (255, 255, 255, 255))
        borda.paste(v, (8, 8))
        v = borda
    img.paste(v, (W - v.width + 10, H - v.height + 10), v)
    d = ImageDraw.Draw(img)
    palavras = spec["texto"].split()
    linhas = [" ".join(palavras[: (len(palavras) + 1) // 2]), " ".join(palavras[(len(palavras) + 1) // 2:])]
    y = 60
    for ln in [x for x in linhas if x]:
        t = 170
        while t > 50 and d.textlength(ln, font=ImageFont.truetype(str(FONTES / "Anton-Regular.ttf"), t)) > 720:
            t -= 6
        f = ImageFont.truetype(str(FONTES / "Anton-Regular.ttf"), t)
        x = 40
        for w in ln.split():
            cor = spec["cor"] if w.strip(".,!?") == spec.get("destaque") else "#FFFFFF"
            d.text((x, y), w, font=f, fill=cor, stroke_width=9, stroke_fill="#000000")
            x += d.textlength(w + " ", font=f)
        y += int(t * 1.05)
    if spec.get("selo"):
        f = ImageFont.truetype(str(FONTES / "Anton-Regular.ttf"), 50)
        lw = d.textlength(spec["selo"], font=f)
        d.rectangle((40, H - 110, 40 + lw + 40, H - 40), fill=spec.get("selo_cor", "#E6282D"))
        d.text((60, H - 105), spec["selo"], font=f, fill="#FFFFFF")
    img.save(saida, quality=90)
    return saida


def thumb_viral(saida, assunto="", texto="", destaque="", selo=None, rosto_de=(), quadro_de=None, faixas=None, extras=(),
                estilo="futebol", marca="", n=3, log=log):
    """faz as thumbs e devolve a lista de JPGs (a 1ª é a principal). Nunca levanta erro: no pior caso, 1 thumb simples."""
    out = Path(saida)
    out.mkdir(parents=True, exist_ok=True)
    est = ESTILOS.get(estilo, ESTILOS["futebol"])
    if texto:
        texto, destaque = texto.upper(), (destaque or "").upper()
        selo = est["selo"] if selo is None else selo
    else:
        texto, destaque, selo_ia = texto_viral(assunto, estilo, log)
        selo = selo if selo is not None else (selo_ia or est["selo"])
    log(f"thumb: \"{texto}\" (destaque {destaque or '-'}{', selo ' + selo if selo else ''})")
    # 1) você
    rostos = [Path(v) for v in rosto_de if v and Path(v).exists()]
    vids = [v for v in rostos if v.suffix.lower() in VIDEO_EXT]
    fotos = [v for v in rostos if v.suffix.lower() in IMG_EXT]
    voces = []
    if vids:
        log("thumb: procurando as suas melhores reações...")
        for nota, v, t, f in reacoes_de(vids, out, n):
            grande = _extrai(v, t, out / f"_voce_{len(voces)}.jpg") or f  # quadro em resolução cheia para o recorte
            png, ok = recorta_voce(grande, out / f"voce_{len(voces) + 1}.png")
            voces.append({"png": str(png), "recortado": ok})
            log(f"   reação em {Path(v).name} {t:.1f}s (nota {nota:.2f}){'' if ok else ' — sem recorte, vai em quadro'}")
    if not voces:
        for fo in fotos + foto_padrao():
            png, ok = recorta_voce(fo, out / f"voce_{len(voces) + 1}.png")
            voces.append({"png": str(png), "recortado": ok})
            if len(voces) >= n:
                break
        if voces:
            log("thumb: sem rosto no vídeo — usei a sua foto padrão")
        else:
            log("thumb: sem rosto no vídeo e sem foto padrão (ponha uma foto sua em E:\\DETTO\\marca\\eu.jpg)")
    # 2) quadro do vídeo
    quadros = []
    fonte_q = Path(quadro_de) if quadro_de and Path(quadro_de).exists() else (vids[0] if vids else None)
    if fonte_q and fonte_q.suffix.lower() in IMG_EXT:
        quadros = [str(fonte_q)]
    elif fonte_q:
        for k, t in enumerate(melhores_quadros(fonte_q, faixas, n, sem_rosto_grande=bool(voces))):
            q = _extrai(fonte_q, t, out / f"quadro_{k + 1}.jpg")
            if q:
                quadros.append(str(q))
    if not quadros and voces:
        quadros = [voces[0]["png"]]
    if not quadros:
        log("thumb: sem vídeo para tirar o quadro")
        return []
    spec = {"texto": texto, "destaque": destaque, "selo": selo, "selo_cor": est["selo_cor"], "cor": est["cor"], "luz": est["luz"],
            "estilo": estilo, "marca": marca, "voces": voces, "quadros": quadros,
            "extras": [str(e) for e in extras if e and Path(e).exists()][:2], "saida": str(out), "fontes": str(FONTES), "n": n}
    (out / "thumbs.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in range(n):
        (out / f"thumb_{k + 1}.jpg").unlink(missing_ok=True)  # nunca fica a thumb de uma rodada antiga
    try:
        r = subprocess.run(["node", str(AQUI / "viral.js"), str(out / "thumbs.json")], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
        erro = "" if r.returncode == 0 else ((r.stderr or r.stdout or "").strip().splitlines() or ["?"])[-1][:160]
    except (OSError, subprocess.SubprocessError) as e:
        erro = str(e)[:160]
    feitas = [out / f"thumb_{k + 1}.jpg" for k in range(n) if (out / f"thumb_{k + 1}.jpg").exists()]
    if erro or not feitas:
        log(f"thumb: desenho no Chromium falhou ({erro or 'sem arquivo'}) — faço a simples")
        feitas = []
        for k in range(min(n, max(len(voces), 1))):
            vk = voces[k % len(voces)] if voces else {"png": quadros[0], "recortado": False}
            try:
                feitas.append(desenha_pil({**spec, "quadro": quadros[k % len(quadros)], "voce": vk["png"], "voce_recortado": vk["recortado"]},
                                          out / f"thumb_{k + 1}.jpg"))
            except Exception as e:
                log(f"thumb: desenho simples falhou ({str(e)[:120]})")
    for f in list(out.glob("_*.jpg")) + list(out.glob("*_busto.jpg")):
        f.unlink(missing_ok=True)
    log(f"thumb: {len(feitas)} pronta(s) em {out}")
    return [Path(f) for f in feitas]


def main():
    ap = argparse.ArgumentParser(description="thumb viral: você + quadro do vídeo + assunto")
    ap.add_argument("--rosto", nargs="*", default=[], help="vídeos/fotos onde está o seu rosto")
    ap.add_argument("--quadro", default="", help="o vídeo (ou imagem) de onde sai o quadro do assunto")
    ap.add_argument("--faixa", nargs="*", default=[], help="onde procurar o quadro: 12.5-40 (segundos)")
    ap.add_argument("--assunto", default="")
    ap.add_argument("--texto", default="")
    ap.add_argument("--destaque", default="")
    ap.add_argument("--selo", default=None)
    ap.add_argument("--extra", nargs="*", default=[], help="jogador/escudo (PNG)")
    ap.add_argument("--estilo", default="futebol", choices=list(ESTILOS))
    ap.add_argument("--marca", default="")
    ap.add_argument("--saida", required=True)
    a = ap.parse_args()
    faixas = [tuple(float(x) for x in f.split("-")) for f in a.faixa] or None
    feitas = thumb_viral(a.saida, a.assunto, a.texto, a.destaque, a.selo, a.rosto, a.quadro or None, faixas, a.extra, a.estilo, a.marca)
    sys.exit(0 if feitas else 1)


if __name__ == "__main__":
    main()
    os._exit(0)
