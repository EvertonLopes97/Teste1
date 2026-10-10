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
import urllib.error
import urllib.request
from pathlib import Path

REGRAS = """Você é editor de vídeos de futebol do canal @detto.galo (humor, opinião, curiosidades).
Escreva o ROTEIRO DE EDIÇÃO no formato abaixo, em português, a partir da transcrição com tempos.

FORMATO (siga à risca; os tempos são da GRAVAÇÃO, m:ss):
=====================================================================
 ROTEIRO + MAPA DE EDIÇÃO — "TÍTULO"
=====================================================================

=====================================================================
 0. GANCHO (0:00 – 0:20)
=====================================================================

[0:00 – 0:08]  MODO: [CAM]
FALA: "frase exata da transcrição"
TELA: "MELHORES • PIORES • POLÊMICAS"
EFEITO: punch-in em "palavra"

[0:08 – 0:20]  MODO: [CAM+MG]
FALA: "..."
MG: dois cards entram sincronizados com a fala: RONALDO (Bahia) 9,5 → NEYMAR (Santos) 8,3

=====================================================================
 1. NOME DO BLOCO (0:20 – 1:30)
=====================================================================

[0:20 – 0:24]  MODO: [MG+VO]
MG: vinheta "GOLEIROS"

[0:24 – 0:40]  MODO: [MG+VO]
FALA: "Quarta-feira: Inter 2 a 1 Corinthians. Bragantino 1 a 1 Mirassol."
MG: as PLACAS DE PLACAR caem uma por vez, sincronizadas com cada placar falado.

[0:40 – 0:55]  MODO: [CAM]
FALA: "..."
TELA: enquete "ERA VERMELHO? ✅ SIM / ❌ NÃO — COMENTA!"

=====================================================================
 CORTES VERTICAIS (9:16) PRA TIKTOK / REELS / SHORTS
=====================================================================
1. "TEMA" — [0:08 – 1:10]. Gancho na tela: "FRASE DO GANCHO"

MODOS (um por trecho):
- [CAM] só a câmera (opinião, reação, improviso). TELA só para textos curtos, enquete ou chamada.
- [CAM+MG] câmera pequena no canto + gráfico (quando explica um dado).
- [MG+VO] só o gráfico com a voz por baixo (placares, notas, seleção da rodada).

O QUE O MG PODE PEDIR (escreva assim, o editor automático entende):
- cards de jogador: NOME EM MAIÚSCULAS (Time) nota com vírgula. Ex.: "SAVARINO (Fluminense) 10,0 → ERICK (Vitória) 10,0".
  Cartão vermelho: "... e um cartão vermelho carimba em cima" na frase do jogador.
- placares da rodada: "as PLACAS DE PLACAR caem uma por vez" (os jogos vêm da FALA: "Time 2 a 1 Time").
- campinho: "o campo desce ... título "SELEÇÃO DA RODADA"" e a formação, uma linha por setor, do ataque ao goleiro:
  [ NEYMAR 8,3 ]   [ ARTUR 8,2 ]
  [ RONALDO 9,5 ]
- duelo de pontos: "barras de pontos: FLA 61 x PAL 60" (siglas de 3 letras).
- vinheta de bloco: vinheta "NOME".   - aspas: aspas "FRASE" — Autor.
- selos: selo "ANULADO" / "✅ CORRETO".   - tela de VAR: "vira a TELA DE VAR".
- números grandes: VFX: três "10" azuis caem do topo.

REGRAS:
- Um trecho [m:ss – m:ss] por frase/ideia (5 a 15 s), cobrindo a fala inteira, em ordem, sem buracos.
- FALA = texto exato da transcrição daquele trecho.
- Gráfico só quando a fala cita placar, nota, número, nome, ranking ou lista (no máximo 1 a cada ~8 s).
- NUNCA invente nota, placar ou time: use só o que está na fala. Sem a nota na fala, não faça card.
- EFEITO: punch-in nas frases de impacto; zoom lento no suspense.
- Na chamada para seguir/comentar: TELA: "COMENTA AÍ" + botão "SEGUIR".
- CORTES VERTICAIS: um por tema (30 a 75 s), com um gancho forte.
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


API = "https://generativelanguage.googleapis.com/v1beta"


def _chamar(url, corpo=None):
    req = urllib.request.Request(url, data=corpo, headers={"Content-Type": "application/json",
                                                           "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=300).read())
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "ignore")[:400]
        raise RuntimeError(f"Gemini respondeu {e.code}: {detalhe}") from None


def modelos_disponiveis():
    """Modelos que a sua chave pode usar (os 'flash' primeiro: rápidos e baratos)."""
    r = _chamar(f"{API}/models?pageSize=200")
    nomes = [m["name"].split("/", 1)[1] for m in r.get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    flash = [n for n in nomes if "flash" in n and "lite" not in n and "image" not in n and "tts" not in n]
    return sorted(flash, reverse=True) + [n for n in nomes if n not in flash]


def gemini(prompt):
    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("Falta a chave GEMINI_API_KEY (veja o topo deste arquivo).")
    corpo = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.4}}).encode()
    preferido = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
    tentativas = [preferido, "gemini-2.5-flash"]
    for modelo in tentativas + ["__lista__"]:
        if modelo == "__lista__":  # nome antigo/novo: pergunta ao Google quais existem
            disp = modelos_disponiveis()
            if not disp:
                raise SystemExit("A chave não tem acesso a nenhum modelo Gemini. Gere outra em aistudio.google.com/apikey")
            modelo = disp[0]
        try:
            r = _chamar(f"{API}/models/{modelo}:generateContent", corpo)
            print(f"Roteiro feito pelo modelo {modelo}")
            return r["candidates"][0]["content"]["parts"][0]["text"]
        except RuntimeError as e:
            if " 404" in str(e) and modelo in tentativas:
                continue
            if " 400" in str(e) or " 403" in str(e):
                raise SystemExit(f"{e}\nA chave foi recusada: gere outra em https://aistudio.google.com/apikey "
                                 f"(começa com AIza) e rode setx GEMINI_API_KEY de novo.")
            raise SystemExit(str(e))
    raise SystemExit("Nenhum modelo Gemini respondeu.")


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
