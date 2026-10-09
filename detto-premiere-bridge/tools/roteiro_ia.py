# -*- coding: utf-8 -*-
"""Escreve o roteiro de edição (formato DETTO) a partir da transcrição, usando o Gemini
(quase de graça) em vez do Claude. O Claude fica só para ajustes.

    python tools/roteiro_ia.py words.json roteiro.txt [--titulo "Cinco camisas"]

Precisa da chave: variável de ambiente GEMINI_API_KEY (crie em https://aistudio.google.com/apikey).
No Windows (uma vez):  setx GEMINI_API_KEY "sua-chave"   e abra outro PowerShell.
Modelo: GEMINI_MODEL (padrão gemini-2.5-flash).
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

REGRAS = """Você é editor de vídeos de futebol do canal @detto.galo (humor, opinião, curiosidades).
Escreva o ROTEIRO DE EDIÇÃO no formato abaixo, em português, a partir da transcrição com tempos.

FORMATO (siga à risca; os tempos são da GRAVAÇÃO, mm:ss):
=====================================================================
 ROTEIRO DE EDIÇÃO — "TÍTULO"
=====================================================================

=====================================================================
 ABERTURA / GANCHO
=====================================================================

[00:00 – 00:08]
FALA: "frase exata da transcrição"
TELA: "TEXTO CURTO EM MAIÚSCULAS" (palavra por palavra)
EFEITO: punch-in em "palavra"

=====================================================================
 BLOCO 1 — NOME DO BLOCO
=====================================================================

[00:08 – 00:19]
FALA: "..."
VISUAL: termos de busca da foto (jogador + clube + ano)
GRÁFICO: PLACA DE PLACAR: TIME A 3 x 1 TIME B • COMPETIÇÃO
SFX: impacto
EFEITO: punch-in em "palavra"

=====================================================================
 CORTES VERTICAIS (9:16) SUGERIDOS
=====================================================================
1. "TEMA": [00:08 – 01:10]. Gancho: "frase do gancho"

=====================================================================
 ERRATA PARA A LEGENDA
=====================================================================
- "palavra ouvida errada" → CORRETA

REGRAS:
- Um trecho [mm:ss – mm:ss] por frase/ideia (5 a 15 s), cobrindo a fala inteira, em ordem, sem buracos.
- FALA = texto exato da transcrição daquele trecho.
- TELA/GRÁFICO só quando a fala cita placar, número, data, nome, ranking ou lista (no máximo 1 a cada ~8 s).
  Tipos de GRÁFICO: PLACA DE PLACAR, CONTADOR, CARD DE ESTATÍSTICA, LINHA DO TEMPO, CARIMBO de data.
- EFEITO: punch-in nas frases de impacto; tremida só em placar, cartão ou gol; zoom lento no suspense.
- VISUAL: termos concretos para achar foto (jogador + clube + ano, estádio, troféu).
- SFX só nos impactos (impacto, whoosh, ding, pop).
- Na chamada para seguir/comentar: TELA: "COMENTA AÍ" + "SEGUIR".
- CORTES VERTICAIS: um por tema (30 a 75 s); o Gancho é a frase de abertura que dá vontade de assistir.
- ERRATA: nomes de jogadores, clubes e competições que a transcrição escreveu errado.
- Responda SÓ com o roteiro, sem comentários.
"""


def falas(words, pausa=0.6):
    """Agrupa as palavras em frases com tempo de início (quebra nas pausas e na pontuação)."""
    linhas, atual, ini = [], [], None
    for k, w in enumerate(words):
        if ini is None:
            ini = w["s"]
        atual.append(w["w"])
        prox = words[k + 1] if k + 1 < len(words) else None
        if prox is None or prox["s"] - w["e"] > pausa or re.search(r"[.!?]$", w["w"]) or len(atual) > 28:
            linhas.append(f"[{int(ini // 60):02d}:{ini % 60:05.2f} – {int(w['e'] // 60):02d}:{w['e'] % 60:05.2f}] {' '.join(atual)}")
            atual, ini = [], None
    return "\n".join(linhas)


def gemini(prompt):
    chave = os.environ.get("GEMINI_API_KEY")
    if not chave:
        raise SystemExit("Falta a chave GEMINI_API_KEY (veja o topo deste arquivo).")
    modelo = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={chave}"
    corpo = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.4}}).encode()
    req = urllib.request.Request(url, data=corpo, headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read())
    return r["candidates"][0]["content"]["parts"][0]["text"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("words")
    p.add_argument("saida")
    p.add_argument("--titulo", default="")
    a = p.parse_args()
    words = json.loads(Path(a.words).read_text(encoding="utf-8"))
    prompt = REGRAS + (f"\nTítulo sugerido: {a.titulo}\n" if a.titulo else "") + "\nTRANSCRIÇÃO:\n" + falas(words)
    texto = gemini(prompt).strip()
    texto = re.sub(r"^```\w*\n|\n```$", "", texto)
    Path(a.saida).write_text(texto + "\n", encoding="utf-8")
    print(f"Roteiro: {a.saida} ({texto.count('FALA:')} trechos)")


if __name__ == "__main__":
    sys.exit(main())
