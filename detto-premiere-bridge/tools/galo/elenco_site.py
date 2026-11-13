# -*- coding: utf-8 -*-
"""Baixa as fotos oficiais do elenco (site do Atlético), tira o fundo e salva em banco/elenco/<nome>.webp.

    python tools/galo/elenco_site.py            (pula quem já está no banco)
    python tools/galo/elenco_site.py --tudo     (refaz todos)

A lista fica em tools/galo/elenco.json: [nome, número, posição, URL da foto do site].
Jogador novo: abra https://atletico.com.br/atleta/<nome>/, copie o endereço da foto e acrescente na lista.
"""
import io
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import galo  # noqa: E402


def main():
    from rembg import new_session, remove
    sessao = new_session("isnet-general-use")
    tudo = "--tudo" in sys.argv
    for nome, num, pos, url in json.loads((AQUI / "elenco.json").read_text(encoding="utf-8")):
        dest = galo.BANCO / "elenco" / f"{galo.slug(nome)}.webp"
        if dest.exists() and not tudo:
            continue
        r = subprocess.run(["curl", "-sSfL", "-m", "60", "-A", "Mozilla/5.0", url], capture_output=True)
        if r.returncode:
            print(f"  ! {nome}: não baixou ({url})")
            continue
        img = remove(Image.open(io.BytesIO(r.stdout)).convert("RGB"), session=sessao, post_process_mask=True)
        img = img.crop(img.getbbox())
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.thumbnail((900, 1100))
        img.save(dest, quality=92, method=6)
        print(f"  {nome} ok")


if __name__ == "__main__":
    main()
