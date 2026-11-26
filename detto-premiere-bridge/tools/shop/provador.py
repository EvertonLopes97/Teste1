#!/usr/bin/env python3
"""TROCA DE ROUPA (virtual try-on, 13/nov): foto sua + foto da peça → você vestindo a peça (CatVTON, modelo aberto, no fal.ai).
  python tools\\shop\\provador.py --pessoa eu.jpg --roupa camisa.jpg [--tipo upper|lower|overall] [--saida pronto.jpg]
Chave: FAL_KEY ou `fal_chave` no config do shop. PAGO por uso.
ATENÇÃO — LICENÇA: o CatVTON é CC BY-NC-SA 4.0 (NÃO comercial) e o fal.ai o marca "research only". Para anúncio de produto
(TikTok Shop) isso é área cinzenta: use por sua conta e risco ou troque por outro modelo em `fal_modelo_roupa` (ex.: Leffa, MIT).
Não conferido com chave real."""
import argparse
import base64
import mimetypes
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fal  # noqa: E402
import ia_video  # noqa: E402


def _uri(f):
    return f"data:{mimetypes.guess_type(str(f))[0] or 'image/jpeg'};base64," + base64.b64encode(Path(f).read_bytes()).decode()


def veste(pessoa, roupa, saida, tipo="upper", cfg=None, log=print):
    """devolve Path da foto com a roupa trocada, ou None (nunca derruba quem chamou)"""
    cfg = cfg or {}
    fal.poe_chave(cfg)
    if not fal.tem_chave():
        log("   troca de roupa: falta a chave do fal.ai (FAL_KEY ou fal_chave)")
        return None
    try:
        r = fal.roda(str(cfg.get("fal_modelo_roupa") or fal.MODELOS["roupa"]),
                     {"human_image_url": _uri(pessoa), "garment_image_url": _uri(roupa), "cloth_type": tipo,
                      "image_size": "portrait_16_9"}, 600, log)
        url = (r.get("image") or {}).get("url")
        if not url:
            raise RuntimeError(f"sem imagem na resposta ({str(r)[:120]})")
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": ia_video.UA})
        Path(saida).write_bytes(urllib.request.urlopen(req, timeout=120).read())
        return Path(saida)
    except Exception as e:   # noqa: BLE001
        log(f"   troca de roupa falhou: {str(e)[:200]}")
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pessoa", required=True)
    ap.add_argument("--roupa", required=True)
    ap.add_argument("--tipo", default="upper", choices=["upper", "lower", "overall", "inner", "outer"])
    ap.add_argument("--saida")
    a = ap.parse_args()
    s = Path(a.saida or Path(a.pessoa).with_name(Path(a.pessoa).stem + "_vestido.jpg"))
    r = veste(a.pessoa, a.roupa, s, a.tipo, {"fal_chave": os.environ.get("FAL_KEY", "")})
    print(f"pronto: {r}" if r else "não deu — veja a mensagem acima")


if __name__ == "__main__":
    main()
