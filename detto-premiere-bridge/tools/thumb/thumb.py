# -*- coding: utf-8 -*-
"""THUMBS virais do vídeo: VOCÊ (melhor reação, recortado do peito para cima) + UM QUADRO DO VÍDEO + O ASSUNTO.

    python tools\\thumb\\thumb.py "<video ou pasta do job>" [--texto "VIRADA NO FIM" --destaque VIRADA] [--jogador "Hulk"]
        [--quadro "video_final.mp4"] [--estilo futebol|noticia|vlog|gameplay] [--selo URGENTE] [--saida pasta]

Quem desenha é o viral.py (3 versões; se o Chromium falhar, uma simples — nunca fica sem thumb). Aqui ficam as peças:
reacoes() = os quadros com a sua reação mais forte (MediaPipe Face Landmarker; olhando para a câmera, sem piscar) e
recorte() = você em PNG transparente. Quadro do assunto: o horizontal.mp4 do job (gráficos, lances, fotos).
Saída: <job>\\thumbs\\thumb_1.jpg … thumb_3.jpg (1280x720) + thumbs.jpg (todas lado a lado).
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
MODELOS = TOOLS / "motion" / "modelos"
ROSTO_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"


def baixa_modelo(nome, url):
    f = MODELOS / nome
    if not f.exists():
        MODELOS.mkdir(parents=True, exist_ok=True)
        print(f"thumb: baixando {nome} (uma vez só)...", flush=True)
        urllib.request.urlretrieve(url, f)
    return f


def duracao(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def quadros(video, passo=0.5, maximo=900):
    """(t, imagem BGR) a cada `passo` s (cor SDR, como no render)"""
    sys.path.insert(0, str(TOOLS))
    try:
        from cor import filtro_cor  # HDR do iPhone → SDR

        cor = filtro_cor(str(video))
    except Exception:
        cor = ""
    d = duracao(video)
    passo = max(passo, d / maximo)
    vf = f"fps={1 / passo:.4f}" + (f",{cor}" if cor else "") + ",scale=-2:720"
    tmp = Path(os.environ.get("TEMP", "/tmp")) / "detto_thumb_q"
    tmp.mkdir(parents=True, exist_ok=True)
    for f in tmp.glob("*.jpg"):
        f.unlink()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", vf, "-q:v", "2", str(tmp / "%05d.jpg")], check=True)
    for i, f in enumerate(sorted(tmp.glob("*.jpg"))):
        yield i * passo, f


def reacoes(video, n=4):
    """os n quadros com a reação mais forte (espaçados ≥ 4 s)"""
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    det = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(baixa_modelo("face_landmarker.task", ROSTO_URL))),
        output_face_blendshapes=True, num_faces=1))
    notas = []
    for t, f in quadros(video):
        img = cv2.imread(str(f))
        if img is None:
            continue
        r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))))
        if not r.face_blendshapes:
            continue
        b = {c.category_name: c.score for c in r.face_blendshapes[0]}
        pts = np.array([(p.x, p.y) for p in r.face_landmarks[0]])
        larg = pts[:, 0].max() - pts[:, 0].min()
        cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        x0, x1 = int(pts[:, 0].min() * img.shape[1]), int(pts[:, 0].max() * img.shape[1])
        y0, y1 = int(pts[:, 1].min() * img.shape[0]), int(pts[:, 1].max() * img.shape[0])
        nitido = cv2.Laplacian(cinza[max(0, y0):y1, max(0, x0):x1], cv2.CV_64F).var() if x1 > x0 and y1 > y0 else 0
        expressao = (1.4 * b.get("jawOpen", 0) + b.get("eyeWideLeft", 0) + b.get("eyeWideRight", 0) + 1.2 * b.get("browInnerUp", 0)
                     + 0.6 * (b.get("browOuterUpLeft", 0) + b.get("browOuterUpRight", 0)) + 0.5 * (b.get("mouthSmileLeft", 0) + b.get("mouthSmileRight", 0))
                     + 0.5 * (b.get("mouthFunnel", 0) + b.get("mouthPucker", 0)))
        piscando = (b.get("eyeBlinkLeft", 0) + b.get("eyeBlinkRight", 0)) / 2 > 0.45
        olhando_baixo = (b.get("eyeLookDownLeft", 0) + b.get("eyeLookDownRight", 0)) / 2 > 0.4  # thumb: olhando para a câmera
        nota = (expressao * (0.6 + 0.4 * min(1, nitido / 120)) * (0.2 if piscando else 1) * (0.5 if larg < 0.08 else 1)
                * (0.45 if olhando_baixo else 1))
        notas.append((nota, t, f))
    notas.sort(key=lambda x: -x[0])
    escolhidos = []
    for nota, t, f in notas:
        if all(abs(t - e[1]) >= 4 for e in escolhidos):
            escolhidos.append((nota, t, f))
        if len(escolhidos) == n:
            break
    return escolhidos


def recorte(img_f, saida):
    """você recortado (PNG transparente) com o modelo completo de recorte"""
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    sys.path.insert(0, str(TOOLS / "motion"))
    from recorte import modelo

    arq, multi = modelo()
    seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(base_options=BaseOptions(model_asset_path=str(arq)), output_confidence_masks=True))
    img = cv2.imread(str(img_f))
    r = seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))))
    m = (1 - r.confidence_masks[0].numpy_view()) if multi else r.confidence_masks[0].numpy_view()
    m = cv2.resize(np.asarray(m, np.float32).squeeze(), (img.shape[1], img.shape[0]))
    guia = getattr(getattr(cv2, "ximgproc", None), "guidedFilter", None)
    m = guia(img, m, 8, 1e-4) if guia else cv2.GaussianBlur(m, (5, 5), 0)
    a = (np.clip((m - 0.3) / 0.4, 0, 1) * 255).astype(np.uint8)
    # só a maior mancha (tira pedaços soltos do fundo)
    n, lab, st, _ = cv2.connectedComponentsWithStats((a > 128).astype(np.uint8))
    if n > 2:
        maior = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        a[cv2.dilate((lab == maior).astype(np.uint8), np.ones((15, 15), np.uint8)) == 0] = 0
    ys, xs = np.where(a > 20)
    rgba = np.dstack([img, a])
    if len(xs):
        rgba = rgba[max(0, ys.min() - 10):, max(0, xs.min() - 10):xs.max() + 10]
    cv2.imwrite(str(saida), rgba)
    return saida


def texto_curto(titulo):
    """2–4 palavras de impacto para a thumb (Gemini); sem chave: o começo do título"""
    if os.environ.get("GEMINI_API_KEY") and titulo:
        sys.path.insert(0, str(TOOLS))
        try:
            from roteiro_ia import API, _chamar

            corpo = json.dumps({"contents": [{"parts": [{"text": f"Título de vídeo de futebol: {titulo!r}. Escreva o TEXTO DA THUMB do YouTube: 2 a 4 palavras "
                                                                  "em MAIÚSCULAS, chocantes/curiosas, sem repetir o título inteiro. E diga qual palavra destacar. "
                                                                  "Responda JSON {\"texto\": \"...\", \"destaque\": \"...\"}"}]}],
                                "generationConfig": {"temperature": 0.9, "responseMimeType": "application/json"}}).encode()
            r = _chamar(f"{API}/models/{os.environ.get('GEMINI_MODEL', 'gemini-flash-latest')}:generateContent", corpo)
            d = json.loads(r["candidates"][0]["content"]["parts"][0]["text"])
            return d.get("texto", "").upper(), d.get("destaque", "").upper()
        except Exception as e:
            print(f"thumb: Gemini não respondeu ({str(e)[:100]})")
    palavras = re.sub(r"[^\wÀ-ÿ ]", " ", titulo or "").upper().split()
    return " ".join(palavras[:4]) or "VOCÊ NÃO VAI ACREDITAR", (palavras[-1] if palavras else "")


def fundo_ia(tema, saida):
    """fundo de estádio gerado pelo Gemini (imagem); None se a chave/modelo não deixar"""
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    sys.path.insert(0, str(TOOLS))
    from roteiro_ia import API, _chamar

    corpo = json.dumps({"contents": [{"parts": [{"text": f"Fundo para thumbnail de YouTube de futebol, 16:9, sem pessoas em primeiro plano e sem texto: "
                                                          f"estádio lotado à noite, refletores, fumaça e luz dramática, cores fortes. Tema: {tema}"}]}],
                        "generationConfig": {"responseModalities": ["IMAGE"]}}).encode()
    for modelo in [os.environ.get("GEMINI_IMG_MODEL", "gemini-2.5-flash-image"), "gemini-2.0-flash-preview-image-generation"]:
        try:
            r = _chamar(f"{API}/models/{modelo}:generateContent", corpo)
            for p in r["candidates"][0]["content"]["parts"]:
                if "inlineData" in p or "inline_data" in p:
                    d = p.get("inlineData") or p.get("inline_data")
                    Path(saida).write_bytes(base64.b64decode(d["data"]))
                    return saida
        except Exception as e:
            print(f"thumb: fundo IA ({modelo}) não saiu: {str(e)[:120]}")
    return None


def main():
    """thumbs do vídeo editado (editar.py) ou de qualquer vídeo: VOCÊ + QUADRO DO VÍDEO + ASSUNTO (viral.py)"""
    ap = argparse.ArgumentParser(description="thumbs virais do vídeo")
    ap.add_argument("alvo", help="o vídeo (gravação) ou a pasta do job")
    ap.add_argument("--texto", default="")
    ap.add_argument("--destaque", default="", help="palavra do texto em destaque")
    ap.add_argument("--selo", default=None, help="selo (URGENTE, POLÊMICA...); vazio = sem")
    ap.add_argument("--jogador", default="", help="jogador na thumb (foto do jogadores.json do job)")
    ap.add_argument("--quadro", default="", help="vídeo de onde sai o quadro do assunto (padrão: o horizontal.mp4 do job)")
    ap.add_argument("--estilo", default="futebol", help="futebol | noticia | vlog | gameplay")
    ap.add_argument("--marca", default="")
    ap.add_argument("--saida", default="")
    ap.add_argument("--fundo-ia", action="store_true", help="(antigo, ignorado)")
    a = ap.parse_args()
    sys.path.insert(0, str(AQUI))
    from viral import thumb_viral

    alvo = Path(a.alvo).resolve()
    job, video = (alvo, None) if alvo.is_dir() else (alvo.with_name(alvo.stem + "_job"), alvo)
    plano = {}
    if (job / "EDIT_PLAN.json").exists():
        plano = json.loads((job / "EDIT_PLAN.json").read_text(encoding="utf-8"))
        if not video:
            video = Path(((plano.get("media") or [{}])[0]).get("path", ""))
    if not video or not video.exists():
        sys.exit("Passe o vídeo da gravação (ou a pasta do job com o EDIT_PLAN.json).")
    out = Path(a.saida) if a.saida else (job if job.exists() else video.parent) / "thumbs"
    titulo = ((plano.get("meta") or {}).get("title") or plano.get("name") or video.stem)
    # o assunto: título + o começo do que é falado (para a IA achar as 2–4 palavras)
    assunto = titulo
    rot = job / "roteiro.txt"
    if rot.exists():
        falas = re.findall(r'FALA:\s*"?([^"\n]+)', rot.read_text(encoding="utf-8", errors="replace"))
        assunto += " — " + " ".join(falas[:8])[:900]
    # jogador/escudo: o pedido, senão os primeiros com foto no jogadores.json
    extras = []
    jj = job / "jogadores.json"
    if jj.exists():
        players = json.loads(jj.read_text(encoding="utf-8")).get("players", {})
        nomes = [k for k in players if a.jogador.lower() in k.lower()] if a.jogador else list(players)
        extras = [players[k]["photo"] for k in nomes if players[k].get("photo")][:2]
    quadro = Path(a.quadro) if a.quadro else next((p for p in (job / "horizontal.mp4", job / "horizontal_lances.mp4") if p.exists()), video)
    feitas = thumb_viral(out, assunto, a.texto, a.destaque, a.selo, [video], quadro, None, extras, a.estilo, a.marca)
    if not feitas:
        sys.exit("thumb: não consegui fazer a thumb (veja as mensagens acima)")
    print(f"\nthumbs: {out}  (compare em {out / 'thumbs.jpg'})")


if __name__ == "__main__":
    main()
    os._exit(0)
