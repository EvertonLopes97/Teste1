# -*- coding: utf-8 -*-
"""Banco PRONTO de fotos e escudos (como no bot): todos os jogadores dos times de
tools/roteiro/times.json, sem fundo, em tools/banco/jogadores/<id>.webp + escudos.

    python tools/banco_fotos.py            (baixa só o que falta; ~2 min por time novo)
    python tools/banco_fotos.py --tudo     (refaz os elencos: janela de transferências)

Depois disso a edição não precisa de internet para as fotos (o jogadores.py usa o banco).
Se o SofaScore bloquear o seu PC (403): pip install curl_cffi, ou peça para o Claude atualizar
o banco e dê git pull.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jogadores as J  # noqa: E402


def main():
    tudo = "--tudo" in sys.argv
    if tudo:
        for f in (J.BANCO / "elencos").glob("*.json"):
            f.unlink()
    (J.BANCO / "jogadores").mkdir(parents=True, exist_ok=True)
    indice = {}
    novos = falhas = 0
    for t in J.TIMES:
        J.escudo(t)
        lista = J.elenco(t["sofa"])
        itens = []
        for p in lista:
            dst = J.BANCO / "jogadores" / f"{p['id']}.webp"
            if not dst.exists():
                if J.baixar_foto(p["id"], dst):
                    novos += 1
                else:
                    falhas += 1
                time.sleep(0.15)
            itens.append({**p, "foto": dst.name if dst.exists() else ""})
        indice[t["sigla"]] = itens
        print(f"{t['sigla']}: {sum(1 for x in itens if x['foto'])}/{len(itens)} fotos")
    (J.BANCO / "jogadores" / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Banco pronto: {novos} fotos novas, {falhas} sem foto no SofaScore → {J.BANCO}")
    for a in sorted(J.AVISOS)[:5]:
        print(f"  aviso: {a}")


if __name__ == "__main__":
    main()
