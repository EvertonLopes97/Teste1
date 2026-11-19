#!/usr/bin/env python3
"""IA PAGA QUE DÁ MOVIMENTO À FOTO DO PRODUTO (12/nov, pedido dele: "quero o Higgsfield e o Seedance, com uma chave
para ligar ou desligar") — imagem→vídeo, 720p, 9:16.

A foto REAL do produto é a referência; a IA só cria o movimento (texto→vídeo inventa rótulo e derruba conta de
afiliado). Cada clipe CUSTA dinheiro na conta dele, então:
  - vem DESLIGADO (`"ia_video": "desligado"` no config do shop; painel: chave "Movimento por IA");
  - no máximo `ia_video_max` clipes por vídeo (padrão 1) de `ia_video_s` segundos (padrão 5);
  - o que já foi gerado fica guardado em `<shop>\\ia_video\\` pela foto + pedido: nunca paga duas vezes pelo mesmo.

SEEDANCE (muapi.ai, `SEEDANCE_API_KEY`): POST /api/v1/seedance-v2.0-i2v {prompt, images_list, aspect_ratio 9:16,
  resolution 720p, duration 5, quality high} → GET /predictions/<id>/result (documentado em muapi.ai/playground).
HIGGSFIELD (`HF_API_KEY_ID` + `HF_API_KEY_SECRET`): sobe a foto (files/generate-upload-url), POST
  https://api.higgsfield.ai/<modelo> {image_url, prompt, duration, aspect_ratio, resolution} → status_url → video.url.
  O caminho do modelo vem de `higgsfield_modelo` (padrão higgsfield-ai/dop/standard; o catálogo fica em
  console.higgsfield.ai — se o modelo dele for outro, é só trocar essa chave).

NÃO conferido com chave de verdade (não tenho conta): os dois caminhos seguem a documentação pública lida em 12/nov.
Erro de qualquer tipo = devolve o que conseguiu (ou nada) e o vídeo segue com as fotos/clipes normais.
"""
import hashlib
import json
import mimetypes
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
PEDIDO = ("The product from @image1 in real use, handheld UGC style. Slow smooth camera push-in with slight natural hand "
          "movement and soft daylight. The product keeps EXACTLY the same shape, colors, label and text as the photo. "
          "No new text, no logos added, no faces, realistic, sharp focus on the product.")
PROVEDORES = {"seedance": "Seedance (muapi.ai)", "higgsfield": "Higgsfield", "fal": "Wan aberto (fal.ai)"}


def provedor(cfg):
    p = str(cfg.get("ia_video") or "desligado").lower()
    return p if p in PROVEDORES else ""


def poe_chaves(cfg):
    """as chaves podem vir do ambiente (painel avulso: chaves.json) ou do config do shop (painel principal)"""
    if not os.environ.get("FAL_KEY") and str(cfg.get("fal_chave") or "").strip():
        os.environ["FAL_KEY"] = str(cfg["fal_chave"]).strip()
    for env, k in (("SEEDANCE_API_KEY", "seedance_chave"), ("HF_API_KEY_ID", "hf_id"), ("HF_API_KEY_SECRET", "hf_segredo")):
        if not os.environ.get(env) and str(cfg.get(k) or "").strip():
            os.environ[env] = str(cfg[k]).strip()


def tem_chave(p):
    if p == "seedance":
        return bool(os.environ.get("SEEDANCE_API_KEY"))
    if p == "higgsfield":
        return bool(os.environ.get("HF_API_KEY_ID") and os.environ.get("HF_API_KEY_SECRET"))
    if p == "fal":
        return bool(os.environ.get("FAL_KEY"))
    return False


def _json(url, corpo=None, cab=None, metodo=None, prazo=60):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method=metodo or ("POST" if dados else "GET"),
                                 headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json", **(cab or {})})
    try:
        with urllib.request.urlopen(req, timeout=prazo) as r:
            return json.loads(r.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} {e.read().decode('utf-8', 'replace')[:200]}") from e


def _baixa(url, destino):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as r, open(destino, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    if destino.stat().st_size < 50000:
        raise RuntimeError("o vídeo gerado veio vazio")
    return destino


def _link_publico(foto):
    """a muapi só aceita URL: a foto do produto sobe para o Catbox (o mesmo que o postar usa)"""
    lim = uuid.uuid4().hex
    dados = Path(foto).read_bytes()
    tipo = mimetypes.guess_type(str(foto))[0] or "image/jpeg"
    corpo = (f"--{lim}\r\nContent-Disposition: form-data; name=\"reqtype\"\r\n\r\nfileupload\r\n"
             f"--{lim}\r\nContent-Disposition: form-data; name=\"fileToUpload\"; filename=\"foto{Path(foto).suffix or '.jpg'}\"\r\n"
             f"Content-Type: {tipo}\r\n\r\n").encode() + dados + f"\r\n--{lim}--\r\n".encode()
    req = urllib.request.Request("https://catbox.moe/user/api.php", data=corpo,
                                 headers={"User-Agent": UA, "Content-Type": f"multipart/form-data; boundary={lim}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        url = r.read().decode().strip()
    if not url.startswith("http"):
        raise RuntimeError(f"não consegui hospedar a foto ({url[:80]})")
    return url


def _espera(pega, prazo, log):
    """pergunta de 5 em 5 s até terminar; `pega()` devolve (estado, url, erro)"""
    t0 = time.time()
    while time.time() - t0 < prazo:
        time.sleep(5)
        estado, url, erro = pega()
        if url:
            return url
        if estado in ("failed", "cancelled", "canceled", "nsfw"):
            raise RuntimeError(f"a geração terminou em '{estado}' {str(erro or '')[:160]}")
    raise RuntimeError(f"passou de {prazo // 60} min sem resposta")


def _seedance(foto, pedido, seg, cfg, log):
    cab = {"x-api-key": os.environ["SEEDANCE_API_KEY"]}
    base = "https://api.muapi.ai/api/v1"
    seg = min((5, 10, 15), key=lambda x: abs(x - seg))
    r = _json(f"{base}/{cfg.get('seedance_modelo') or 'seedance-v2.0-i2v'}",
              {"prompt": pedido, "images_list": [_link_publico(foto)], "aspect_ratio": "9:16",
               "resolution": str(cfg.get("ia_video_resolucao") or "720p"), "duration": seg,
               "quality": str(cfg.get("ia_video_qualidade") or "high")}, cab)
    rid = r.get("request_id") or r.get("id")
    if not rid:
        raise RuntimeError(f"a muapi não devolveu o pedido ({str(r)[:160]})")

    def pega():
        s = _json(f"{base}/predictions/{rid}/result", cab=cab)
        saidas = s.get("outputs") or []
        return s.get("status"), (saidas[0] if s.get("status") == "completed" and saidas else ""), s.get("error")
    return _espera(pega, int(cfg.get("ia_video_prazo_s", 600)), log)


def _higgsfield(foto, pedido, seg, cfg, log):
    cab = {"Authorization": f"Key {os.environ['HF_API_KEY_ID']}:{os.environ['HF_API_KEY_SECRET']}"}
    api = "https://api.higgsfield.ai"
    tipo = mimetypes.guess_type(str(foto))[0] or "image/jpeg"
    up = _json(f"{api}/files/generate-upload-url", {"content_type": tipo}, cab)
    req = urllib.request.Request(up["upload_url"], data=Path(foto).read_bytes(), method="PUT",
                                 headers={**(up.get("upload_headers") or {"Content-Type": tipo})})
    urllib.request.urlopen(req, timeout=180).read()
    modelo = str(cfg.get("higgsfield_modelo") or "higgsfield-ai/dop/standard").strip("/")
    r = _json(f"{api}/{modelo}", {"image_url": up["public_url"], "prompt": pedido.replace("@image1", "the photo"),
                                  "duration": 5 if seg <= 7 else 10, "aspect_ratio": "9:16",
                                  "resolution": str(cfg.get("ia_video_resolucao") or "720p")}, cab)
    st = r.get("status_url") or (f"{api}/requests/{r['request_id']}/status" if r.get("request_id") else "")
    if not st:
        raise RuntimeError(f"o Higgsfield não devolveu o pedido ({str(r)[:160]})")

    def pega():
        s = _json(st, cab=cab)
        return s.get("status"), ((s.get("video") or {}).get("url") or "") if s.get("status") == "completed" else "", s.get("error")
    return _espera(pega, int(cfg.get("ia_video_prazo_s", 600)), log)


def _fal(foto, pedido, seg, cfg, log):
    """Wan (modelo ABERTO da Alibaba) rodando no fal.ai: a foto vai embutida (data URI), sem hospedar em lugar nenhum"""
    import base64
    import fal
    tipo = mimetypes.guess_type(str(foto))[0] or "image/jpeg"
    uri = f"data:{tipo};base64," + base64.b64encode(Path(foto).read_bytes()).decode()
    entrada = {"prompt": pedido.replace("@image1", "the photo"), "image_url": uri, "aspect_ratio": "9:16",
               "resolution": str(cfg.get("ia_video_resolucao") or "720p"), "num_frames": 81}
    r = fal.roda(str(cfg.get("fal_modelo_video") or fal.MODELOS["video"]), entrada, int(cfg.get("ia_video_prazo_s", 900)), log)
    url = (r.get("video") or {}).get("url")
    if not url:
        raise RuntimeError(f"o fal.ai não devolveu vídeo ({str(r)[:160]})")
    return url


def gera(fotos, nome, base, cfg, log=print):
    """→ lista de clipes .mp4 em 1080x1920 (pode vir vazia). `fotos` = fotos REAIS do produto."""
    p = provedor(cfg)
    if not p or not fotos:
        return []
    poe_chaves(cfg)
    if not tem_chave(p):
        log(f"   movimento por IA ({PROVEDORES[p]}): ligado, mas sem a chave — cole no painel (Chaves). Sigo sem ele.")
        return []
    quantos = max(1, min(4, int(cfg.get("ia_video_max", 1))))
    seg = int(cfg.get("ia_video_s", 5))
    pedido = str(cfg.get("ia_video_pedido") or PEDIDO)
    if nome:
        pedido += f" Product: {nome}."
    pasta = Path(base) / "ia_video"
    pasta.mkdir(parents=True, exist_ok=True)
    feitos = []
    for foto in list(fotos)[:quantos]:
        try:
            marca = hashlib.md5(Path(foto).read_bytes() + f"{p}|{seg}|{pedido}".encode()).hexdigest()[:16]
            pronto = pasta / f"{p}_{marca}.mp4"
            if pronto.exists() and pronto.stat().st_size > 50000:
                log(f"   movimento por IA: já tinha este clipe guardado ({pronto.name}) — não paga de novo")
                feitos.append(str(pronto))
                continue
            log(f"   movimento por IA ({PROVEDORES[p]}, {seg}s, 720p): gerando a partir de {Path(foto).name} — isto é PAGO")
            t0 = time.time()
            url = {"seedance": _seedance, "higgsfield": _higgsfield, "fal": _fal}[p](foto, pedido, seg, cfg, log)
            bruto = _baixa(url, pasta / f"{p}_{marca}_bruto.mp4")
            # no padrão dos outros clipes do Shop: 1080x1920, 30 fps, sem som
            r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(bruto), "-an", "-vf",
                                "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,fps=30,unsharp=5:5:0.6",
                                "-c:v", "libx264", "-crf", "17", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-y", str(pronto)])
            bruto.unlink(missing_ok=True)
            if r.returncode != 0 or not pronto.exists():
                raise RuntimeError("o ffmpeg não leu o vídeo gerado")
            log(f"   movimento por IA: clipe pronto em {time.time() - t0:.0f}s")
            feitos.append(str(pronto))
        except Exception as e:   # noqa: BLE001
            log(f"   movimento por IA: não deu nesta foto ({str(e)[:200]}); sigo com o que tenho")
    return feitos
