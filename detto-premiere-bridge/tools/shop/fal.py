#!/usr/bin/env python3
"""MODELOS ABERTOS (Wan, LatentSync, CatVTON...) RODANDO NA NUVEM DO fal.ai — 13/nov, pedido dele ("IA de código aberto,
chinesa ou não, para vídeo, lipsync e troca de roupa"). A RTX 3050 de 4 GB dele não roda esses modelos (Wan 2.2 pede 8–24 GB,
LatentSync 8–18 GB, CatVTON ~8 GB); no fal.ai o MESMO modelo aberto roda numa placa deles e a cobrança é por uso.

Chave: `FAL_KEY` (ambiente) ou `fal_chave` no config. Fila: POST https://queue.fal.run/<modelo> → status_url → response_url.
NÃO conferido com chave de verdade: os nomes dos campos vêm das páginas públicas do fal.ai lidas em 13/nov
(fal-ai/wan-i2v e fal-ai/cat-vton conferidos; fal-ai/latentsync NÃO consegui abrir — se o nome do campo for outro, o erro aparece no registro).
"""
import json
import os
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
MODELOS = {   # padrões; cada um pode ser trocado no config (`fal_modelo_video`, `fal_modelo_lipsync`, `fal_modelo_roupa`)
    "video": "fal-ai/wan-i2v",        # Wan 2.1/2.2 (Alibaba, aberto): imagem → vídeo
    "lipsync": "fal-ai/latentsync",   # LatentSync (ByteDance, Apache-2.0): vídeo seu + áudio → boca sincronizada
    "roupa": "fal-ai/cat-vton",       # CatVTON: pessoa + roupa → pessoa vestindo (LICENÇA NÃO COMERCIAL)
}


def poe_chave(cfg):
    if not os.environ.get("FAL_KEY") and str((cfg or {}).get("fal_chave") or "").strip():
        os.environ["FAL_KEY"] = str(cfg["fal_chave"]).strip()


def tem_chave():
    return bool(os.environ.get("FAL_KEY"))


def _json(url, corpo=None, prazo=60):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method="POST" if dados else "GET",
                                 headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json",
                                          "Authorization": f"Key {os.environ['FAL_KEY']}"})
    try:
        with urllib.request.urlopen(req, timeout=prazo) as r:
            return json.loads(r.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"fal.ai {e.code}: {e.read().decode('utf-8', 'replace')[:220]}") from e


def roda(modelo, entrada, prazo=900, log=print):
    """envia, espera e devolve o JSON do resultado (ex.: {"video": {"url": ...}})"""
    modelo = modelo.strip("/")
    r = _json(f"https://queue.fal.run/{modelo}", entrada)
    st = r.get("status_url") or (f"https://queue.fal.run/{modelo}/requests/{r['request_id']}/status" if r.get("request_id") else "")
    res = r.get("response_url") or (f"https://queue.fal.run/{modelo}/requests/{r['request_id']}" if r.get("request_id") else "")
    if not st:
        raise RuntimeError(f"o fal.ai não devolveu o pedido ({str(r)[:160]})")
    t0 = time.time()
    while time.time() - t0 < prazo:
        time.sleep(5)
        s = _json(st)
        if s.get("status") == "COMPLETED":
            return _json(res)
        if s.get("status") in ("FAILED", "ERROR", "CANCELLED"):
            raise RuntimeError(f"a geração terminou em {s.get('status')} {str(s.get('error') or s.get('logs') or '')[:160]}")
    raise RuntimeError(f"passou de {prazo // 60} min sem resposta")
