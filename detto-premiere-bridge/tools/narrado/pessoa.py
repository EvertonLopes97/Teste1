#!/usr/bin/env python3
"""OS CLIPES CERTOS PARA O VÍDEO NARRADO (06/nov) — o assunto TEM de aparecer, e o corte é o do vídeo.

O QUE ESTAVA ERRADO (visto nos dois mp4 que ele mandou, quadro a quadro):
  1. 13 dos primeiros 30 pedaços eram de UM programa de TV/podcast (duas pessoas falando, tarja e
     letreiro do próprio programa) — repetido pedaço após pedaço. Não era o CR7.
  2. o resto era a final da Euro 2016 inteira, o CR7 em 2 planos. A busca era "cr7 aposentadoria" e
     qualquer vídeo de seleção servia.
  3. o corte era em blocos fixos de 2,2 s do vídeo-fonte, atravessando as trocas de plano: meio
     lance, troca de câmera no meio do pedaço, corte no meio de um movimento.

O QUE FAZ AGORA:
  · RECONHECE O ROSTO DO ASSUNTO (SFace, do próprio OpenCV): baixa fotos da pessoa, tira a "impressão
    do rosto" e confere em cada plano. Plano com a pessoa = `sujeito`; jogo/torcida sem rosto
    nenhum = `contexto`; outra pessoa em close ou duas pessoas conversando = jogado fora.
  · CORTA NAS TROCAS DE PLANO REAIS (detecção de cena do ffmpeg): cada clipe é UM plano inteiro do
    vídeo-fonte, nunca um pedaço que atravessa duas câmeras.
  · NO MÁXIMO 5 PLANOS DE CADA VÍDEO-FONTE e nunca dois seguidos do mesmo: acabou o programa repetido.
  · O TÍTULO do vídeo-fonte tem de citar o assunto e não pode ser react/podcast/debate/ao vivo.
  · a linha do tempo começa SEMPRE no assunto e mantém ~2 de cada 3 planos com ele.
"""
import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
for _p in (TOOLS, TOOLS / "reels", TOOLS / "shop"):
    sys.path.insert(0, str(_p))

SFACE_URL = "https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx"
SFACE_URL2 = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
LIMIAR = 0.363            # o limiar de cosseno que o próprio OpenCV recomenda para o SFace
MAX_POR_FONTE = 5
MIN_PLANO_S, MAX_PLANO_S = 1.4, 2.8
FORA_TITULO = ("react", "reação", "reacao", "reagindo", "podcast", "comenta", "ao vivo", "live",
               "debate", "mesa redonda", "resenha", "programa", "análise", "analise", "opinião", "opiniao",
               "cortes", "jogo completo", "full match", "vs ", " x ", "papo", "bate papo")


def log(m):
    print(m, flush=True)


def norm(t):
    t = unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


# ------------------------------------------------------------------ o rosto
def modelo_sface(log=log):
    """o arquivo do SFace (37 MB). Baixa uma vez para a raiz do projeto; sem internet devolve None."""
    m = PONTE / "sface.onnx"
    if m.exists() and m.stat().st_size > 30_000_000:
        return m
    for url in (SFACE_URL, SFACE_URL2):
        try:
            log("   baixando o modelo de reconhecimento de rosto (37 MB, só esta vez)...")
            with urllib.request.urlopen(url, timeout=180) as r:
                dado = r.read()
            if len(dado) > 30_000_000:
                m.write_bytes(dado)
                return m
        except Exception as e:  # noqa: BLE001
            log(f"   não baixou de {url.split('/')[2]} ({str(e)[:80]})")
    return None


class Rostos:
    """detecta (YuNet) e reconhece (SFace) rostos num quadro"""

    def __init__(self, log=log):
        import cv2
        os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
        self.cv2 = cv2
        self.yunet = PONTE / "yunet.onnx"
        self.det = None
        self.rec = None
        self.pode_detectar = self.yunet.exists()
        sf = modelo_sface(log)
        if sf and hasattr(cv2, "FaceRecognizerSF"):
            try:
                self.rec = cv2.FaceRecognizerSF.create(str(sf), "")
            except Exception as e:  # noqa: BLE001
                log(f"   o OpenCV não abriu o SFace ({str(e)[:80]})")
        self.refs = []

    @property
    def reconhece(self):
        return self.rec is not None and self.pode_detectar

    def faces(self, img):
        if not self.pode_detectar:
            return []
        h, w = img.shape[:2]
        if self.det is None:
            self.det = self.cv2.FaceDetectorYN.create(str(self.yunet), "", (w, h), 0.75)
        self.det.setInputSize((w, h))
        _, fs = self.det.detect(img)
        return [] if fs is None else list(fs)

    def vetor(self, img, face):
        al = self.rec.alignCrop(img, face)
        return self.rec.feature(al)

    def aprende(self, img):
        """guarda o rosto de uma foto de referência (só vale foto com UM rosto)"""
        if not self.reconhece:
            return False
        fs = self.faces(img)
        if len(fs) != 1:
            return False
        self.refs.append(self.vetor(img, fs[0]))
        return True

    def e_o_assunto(self, img, face):
        if not self.refs:
            return False
        v = self.vetor(img, face)
        return max(self.rec.match(r, v, self.cv2.FaceRecognizerSF_FR_COSINE) for r in self.refs) >= LIMIAR


def referencias(nome, pasta, rostos, log=log, quer=4):
    """baixa fotos da pessoa e ensina o rosto dela ao reconhecedor"""
    import cv2
    from busca_imagem import buscar

    toks = [t for t in norm(nome).split() if len(t) >= 3]
    if not toks or not rostos.reconhece:
        return 0
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    feitas = 0
    for i, q in enumerate((nome, f"{nome} rosto", f"{nome} jogador", f"{nome} entrevista", f"{nome} 2025")):
        if feitas >= quer:
            break
        try:
            r = buscar(q, exige=toks[-1:], rosto=True, destino=pasta / f"ref{i}.jpg", minimo=300,
                       log=lambda *_: None, prazo=40)
        except Exception as e:  # noqa: BLE001
            log(f"   foto de referência falhou ({str(e)[:80]})")
            continue
        if not r:
            continue
        img = cv2.imread(r["file"])
        if img is not None and rostos.aprende(img):
            feitas += 1
    log(f"   rosto de \"{nome}\" aprendido com {feitas} foto(s)")
    return feitas


# ------------------------------------------------------------------ os planos do vídeo-fonte
def trocas_de_plano(fonte, limite=0.28):
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(fonte), "-an",
                        "-vf", f"select='gt(scene,{limite})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=300)
    return [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr or "")]


def duracao(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


def planos(fonte):
    """[(ini, fim)] — cada um é UM plano inteiro entre duas trocas de câmera.

    Vídeo quase sem corte (menos de 3 trocas) cai em blocos fixos, que é o único jeito de usá-lo.
    """
    total = duracao(fonte)
    cortes = [c for c in trocas_de_plano(fonte) if 0.3 < c < total - 0.3]
    if len(cortes) < 3:
        n = int(total // 2.2)
        return [(i * 2.2, (i + 1) * 2.2) for i in range(n)]
    marcas = [0.0] + cortes + [total]
    return [(a, b) for a, b in zip(marcas, marcas[1:]) if b - a >= MIN_PLANO_S]


def quadro(fonte, t, largura=640):
    import cv2
    import numpy as np

    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(fonte), "-frames:v", "1",
                        "-vf", f"scale={largura}:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True, timeout=60)
    if not r.stdout:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)


def classifica(fonte, ini, fim, rostos):
    """'sujeito' | 'contexto' | None (None = jogar fora, com o motivo)"""
    import cv2

    amostras = [ini + 0.35, (ini + fim) / 2, fim - 0.35]
    achou_assunto, grande_outro, muitos = False, False, False
    escuros = 0
    for t in amostras:
        img = quadro(fonte, t)
        if img is None:
            continue
        cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if cinza.mean() < 24 or cinza.std() < 9:
            escuros += 1
            continue
        h, w = img.shape[:2]
        fs = rostos.faces(img)
        grandes = [f for f in fs if (float(f[2]) * float(f[3])) / (w * h) >= 0.02]
        if len(grandes) >= 2:
            muitos = True
        for f in fs:
            area = (float(f[2]) * float(f[3])) / (w * h)
            if area < 0.004:
                continue
            if rostos.reconhece and rostos.refs:
                if rostos.e_o_assunto(img, f):
                    achou_assunto = True
                elif area >= 0.035:
                    grande_outro = True
            elif area >= 0.06:
                grande_outro = True       # sem reconhecedor: close grande vira "talvez outra pessoa"
    if escuros >= 2:
        return None, "tela preta/lisa"
    if achou_assunto:
        return "sujeito", ""
    if muitos:
        return None, "duas pessoas conversando (programa/podcast)"
    if grande_outro:
        return None, "close de outra pessoa"
    return "contexto", ""


# ------------------------------------------------------------------ a busca
def acha_videos(termo, sujeito_tokens, quantos=3, log=log):
    from clipes_web import _ytdlp

    r = _ytdlp(["--flat-playlist", "--dump-json", f"ytsearch{quantos * 4}:{termo}"], timeout=180)
    out = []
    for linha in (r.stdout or "").splitlines():
        try:
            v = json.loads(linha)
        except ValueError:
            continue
        if not isinstance(v, dict) or not v.get("id"):
            continue
        d = v.get("duration") or 0
        tit = v.get("title") or ""
        n = norm(tit)
        if d and not (45 <= d <= 1500):
            continue
        if any(x in f" {n} " or x in tit.lower() for x in FORA_TITULO):
            continue
        if sujeito_tokens and not any(re.search(rf"\b{re.escape(t)}", n) for t in sujeito_tokens):
            continue
        out.append({"id": v["id"], "titulo": tit, "dur": d, "url": f"https://www.youtube.com/watch?v={v['id']}"})
        if len(out) >= quantos:
            break
    return out


_ROSTOS = {}


def _rostos():
    if "r" not in _ROSTOS:
        try:
            _ROSTOS["r"] = Rostos(lambda *a, **k: None)
        except Exception:  # noqa: BLE001
            _ROSTOS["r"] = None
    return _ROSTOS["r"]


def foco_do_plano(fonte, ini, dur):
    """caixa (x0,y0,x1,y1, relativa 0-1) que une os rostos GRANDES do plano; None se não há rosto"""
    r = _rostos()
    if r is None or not r.pode_detectar:
        return None
    caixas = []
    for t in (ini + 0.2, ini + dur / 2, ini + max(0.3, dur - 0.2)):
        try:
            img = quadro(fonte, t)
        except Exception:  # noqa: BLE001
            img = None
        if img is None:
            continue
        h, w = img.shape[:2]
        fs = [f for f in r.faces(img) if (float(f[2]) * float(f[3])) / (w * h) >= 0.004]
        if not fs:
            continue
        maior = max(float(f[2]) * float(f[3]) for f in fs)
        for f in fs:
            if float(f[2]) * float(f[3]) >= maior * 0.4:
                caixas.append((float(f[0]) / w, float(f[1]) / h, (float(f[0]) + float(f[2])) / w,
                               (float(f[1]) + float(f[3])) / h))
    if not caixas:
        return None
    return (min(c[0] for c in caixas), min(c[1] for c in caixas), max(c[2] for c in caixas), max(c[3] for c in caixas))


def filtro_enquadra(foco, larg, alt, fonte_ar):
    """NÃO CORTA A PESSOA: a janela do corte é centrada no rosto; se o rosto não cabe nela, o plano
    inteiro entra com fundo desfocado. Sem rosto, corte central (jogo, torcida)."""
    ta = larg / alt
    if foco is None:
        return f"scale={larg}:{alt}:force_original_aspect_ratio=increase,crop={larg}:{alt},fps=30"
    x0, y0, x1, y1 = foco
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    # largura/altura relativas da janela
    if fonte_ar > ta:
        jan_w, jan_h = ta / fonte_ar, 1.0
    else:
        jan_w, jan_h = 1.0, fonte_ar / ta
    face_w, face_h = x1 - x0, y1 - y0
    if face_w > jan_w * 0.9 or face_h > jan_h * 0.9:
        return (f"split[a][b];[a]scale={larg}:{alt}:force_original_aspect_ratio=increase,crop={larg}:{alt},"
                f"scale={larg // 8}:{alt // 8},scale={larg}:{alt},eq=brightness=-0.1[bg];"
                f"[b]scale={larg}:{alt}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,fps=30")
    # o rosto fica um pouco acima do meio na vertical (sobra espaço para o corpo embaixo)
    cy_alvo = cy + 0.10 * jan_h
    return (f"crop=w='min(iw,ih*{ta:.5f})':h='min(ih,iw/{ta:.5f})':"
            f"x='min(max({cx:.4f}*iw-out_w/2,0),iw-out_w)':y='min(max({cy_alvo:.4f}*ih-out_h/2,0),ih-out_h)',"
            f"scale={larg}:{alt},fps=30")


def corta_plano(fonte, ini, dur, destino, larg, alt):
    ar = None
    try:
        img = quadro(fonte, ini + dur / 2, 320)
        if img is not None:
            ar = img.shape[1] / img.shape[0]
    except Exception:  # noqa: BLE001
        ar = None
    foco = foco_do_plano(fonte, ini, dur) if ar else None
    vf = filtro_enquadra(foco, larg, alt, ar or 16 / 9)
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{ini:.2f}", "-i", str(fonte), "-t", f"{dur:.2f}", "-an"]
    cmd += ["-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]"] if ";" in vf else ["-vf", vf]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(destino)]
    subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return destino.exists() and destino.stat().st_size > 8000


def pool(sujeito, apelidos, buscas, total_s, pasta, larg, alt, log=log, e_pessoa=True, min_fontes=3):
    """devolve [{arq, dur, tipo, fonte}] na ORDEM em que devem entrar na tela"""
    from clipes_web import baixa_trecho

    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    rostos = Rostos(log)
    refs = referencias(sujeito, pasta / "refs", rostos, log) if e_pessoa and sujeito else 0
    if e_pessoa and not refs:
        log("   AVISO: não consegui o rosto de referência — vou filtrar por título e por close, sem "
            "confirmar o rosto. Confira o vídeo.")
    toks = [t for t in norm(f"{sujeito} {' '.join(apelidos)}").split() if len(t) >= 3]

    por_fonte, ja = {}, set()
    precisa_s = total_s * 1.5
    for termo in buscas:
        if sum(p["dur"] for ps in por_fonte.values() for p in ps) >= precisa_s and len(por_fonte) >= min_fontes:
            break
        log(f"   procurando: {termo}")
        try:
            vids = acha_videos(termo, toks, quantos=2, log=log)
        except Exception as e:  # noqa: BLE001
            log(f"   busca falhou ({str(e)[:90]})")
            continue
        for v in vids:
            if v["id"] in ja or len(por_fonte) >= 7:
                continue
            ja.add(v["id"])
            bruto = pasta / f"{v['id']}.mp4"
            ini = min(60, max(4, (v["dur"] or 200) * 0.06))
            log(f"   baixando: {v['titulo'][:62]}")
            r = baixa_trecho(v["url"], bruto, ini=ini, dur=100)
            if not isinstance(r, Path):
                log(f"   não baixou ({str(r)[:100]})")
                continue
            achados, motivos = [], {}
            for (a, b) in planos(bruto):
                tipo, motivo = classifica(bruto, a, b, rostos)
                if not tipo:
                    motivos[motivo] = motivos.get(motivo, 0) + 1
                    continue
                achados.append((a, b, tipo))
            sujs = [x for x in achados if x[2] == "sujeito"]
            ctxs = [x for x in achados if x[2] == "contexto"]
            # prefere os planos COM o assunto e limita cada vídeo-fonte
            escolhidos = (sujs[:MAX_POR_FONTE] + ctxs[:max(0, MAX_POR_FONTE - len(sujs[:MAX_POR_FONTE]))])
            escolhidos.sort()
            lista = []
            for k, (a, b, tipo) in enumerate(escolhidos):
                d = min(MAX_PLANO_S, b - a - 0.12)
                alvo = pasta / f"{v['id'][:6]}_{k:02d}_{tipo}.mp4"
                if corta_plano(bruto, a + 0.06, d, alvo, larg, alt):
                    lista.append({"arq": alvo, "dur": d, "tipo": tipo, "fonte": v["id"]})
            por_fonte[v["id"]] = lista
            bruto.unlink(missing_ok=True)
            log(f"   {len(lista)} plano(s) bons ({sum(1 for x in lista if x['tipo'] == 'sujeito')} com o assunto)"
                + (f"; descartei: {', '.join(f'{n}× {m}' for m, n in motivos.items())}" if motivos else ""))
    return ordena(por_fonte, total_s, refs > 0, log)


def ordena(por_fonte, total_s, tem_rosto_ref, log=log):
    """linha do tempo: começa no assunto, ~2 de cada 3 planos com ele, nunca dois seguidos do mesmo vídeo"""
    sujs = {f: [p for p in ps if p["tipo"] == "sujeito"] for f, ps in por_fonte.items()}
    ctxs = {f: [p for p in ps if p["tipo"] == "contexto"] for f, ps in por_fonte.items()}
    seq, soma, ultimo, i = [], 0.0, None, 0
    padrao = ["sujeito", "sujeito", "contexto"] if tem_rosto_ref else ["contexto"]

    def tira(pools, quer):
        # a fonte com mais planos sobrando que não seja a do plano anterior
        ordem = sorted(pools, key=lambda f: -len(pools[f]))
        for f in ordem:
            if pools[f] and f != ultimo:
                return pools[f].pop(0)
        for f in ordem:
            if pools[f]:
                return pools[f].pop(0)
        return None

    while soma < total_s + 3:
        quer = padrao[i % len(padrao)]
        outro = "contexto" if quer == "sujeito" else "sujeito"
        p = tira(sujs if quer == "sujeito" else ctxs, quer) or tira(sujs if outro == "sujeito" else ctxs, outro)
        if p is None:
            break
        seq.append(p)
        soma += p["dur"]
        ultimo = p["fonte"]
        i += 1
    if soma < total_s and seq:
        log(f"   faltou material ({soma:.0f}s de {total_s:.0f}s): repito os melhores planos (sujeito primeiro)")
        base = sorted(seq, key=lambda p: p["tipo"] != "sujeito")
        k = 0
        while soma < total_s + 3:
            p = base[k % len(base)]
            if p["fonte"] == ultimo and len(base) > 1:
                k += 1
                continue
            seq.append(p)
            soma += p["dur"]
            ultimo = p["fonte"]
            k += 1
    n_suj = sum(1 for p in seq if p["tipo"] == "sujeito")
    log(f"   linha do tempo: {len(seq)} planos, {n_suj} com o assunto ({100 * n_suj // max(1, len(seq))}%), "
        f"de {len({p['fonte'] for p in seq})} vídeo(s) diferentes")
    return seq
