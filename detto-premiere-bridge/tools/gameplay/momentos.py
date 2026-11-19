# -*- coding: utf-8 -*-
"""OS MOMENTOS FORTES de uma gameplay bruta — morte, vitória, tiroteio, susto, a falha engraçada.

É a peça que não existia. Numa gravação de 2 h de CS ou Project Zomboid não há roteiro nem marcação:
o vídeo só vira vídeo depois que alguém decide QUAIS 15 minutos valem a pena. Isto decide.

Três sinais, somados, e um aprendizado que já custou caro em outras partes do sistema:
**o que vale é o que sai do normal DAQUELE vídeo, não um número fixo.** Um Project Zomboid é quase
todo silencioso e um CS é todo barulhento; limite fixo acharia 300 momentos num e nenhum no outro.
Então cada sinal é medido contra a mediana do próprio vídeo (o mesmo que o `retencao.py` faz com os
paredões).

  VOLUME    pico de áudio do jogo = tiro, grito, música de morte, horda chegando
  MOVIMENTO a tela mudando muito = correndo, perseguição, luta, troca de cena
  A SUA FALA se você comentou enquanto jogava, a palavra que você disse É o momento
            ("morri", "não acredito", "olha isso") — é o sinal mais confiável dos três

Depois o Gemini olha UM quadro de cada momento e diz o que aconteceu, para a narração falar do que
está na tela em vez de encher linguiça. Sem Gemini os momentos continuam valendo (só ficam sem nome).
"""
from __future__ import annotations

import re
import statistics
import unicodedata

# o que você diz quando acontece algo — vale mais que volume e movimento juntos
GRITOS = set("""morri morreu morremos caralho porra puta merda nossa cara eita uai vamo vamos isso
consegui ganhei perdi acabou nao-acredito inacreditavel olha mano gente socorro corre corre-corre
pelamor meudeus deus ferrou fudeu acabo acabou-se tomei levei matei mataram pegou pegaram salvou
salvei quase ultimo ultima recorde sorte azar inacreditavel absurdo""".split())
# palavras que dão ainda mais peso (o ponto alto de verdade)
AUGE = set("morri morreu caralho consegui ganhei inacreditavel absurdo recorde socorro".split())


def _norm(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _z(serie):
    """quanto cada ponto sai do normal DAQUELE vídeo (0 = normal, 1 = bem acima)"""
    vs = [v for v in serie if v is not None]
    if len(vs) < 5:
        return [0.0] * len(serie)
    meio = statistics.median(vs)
    # desvio pela mediana (robusto): um pico gigante não estraga a régua, como a média estragaria
    espalha = statistics.median([abs(v - meio) for v in vs]) or (statistics.pstdev(vs) or 1.0)
    return [max(0.0, (v - meio) / (espalha * 3)) if v is not None else 0.0 for v in serie]


def por_segundo(mov, vol, dur):
    """nota de 0 a ~2 por segundo do vídeo, juntando movimento e volume"""
    n = max(1, int(dur))
    mov = list(mov or [])
    vol = list(vol or [])

    def em(serie, i):
        if not serie:
            return None
        return serie[min(i, len(serie) - 1)]

    zm = _z([em(mov, i) for i in range(n)])
    zv = _z([em(vol, i) for i in range(n)])
    return [round(0.45 * zm[i] + 0.55 * zv[i], 3) for i in range(n)]


def da_fala(palavras):
    """os segundos em que VOCÊ reagiu, pelo que você disse (o sinal mais confiável)"""
    out = {}
    for w in palavras or []:
        if not isinstance(w, dict) or not w.get("w"):
            continue
        p = _norm(re.sub(r"\W", "", w["w"]))
        if p in GRITOS:
            s = int(float(w.get("s") or 0))
            out[s] = max(out.get(s, 0), 1.4 if p in AUGE else 0.9)
    return out


def momentos(mov, vol, dur, palavras=None, quantos=14, min_s=8.0, max_s=45.0, antes=4.0, depois=3.5):
    """devolve [{ini, fim, nota, pelo}] — os melhores pedaços, já com a sobra ANTES e DEPOIS.

    `antes` existe porque o momento forte não começa no pico: começa na SUBIDA (o zumbi aparecendo,
    o inimigo virando a esquina). Cortar no pico entrega o resultado sem a tensão, que é a parte que
    prende. `depois` guarda a reação.
    """
    notas = por_segundo(mov, vol, dur)
    fala = da_fala(palavras)
    for s, peso in fala.items():
        if 0 <= s < len(notas):
            notas[s] = round(notas[s] + peso, 3)
    if not notas:
        return []
    # pico = acima do que é normal NESTE vídeo
    corte = max(0.55, statistics.median(notas) + 0.35)
    picos = [(i, v) for i, v in enumerate(notas) if v >= corte]
    if not picos:
        picos = sorted(enumerate(notas), key=lambda x: -x[1])[:quantos]
    picos.sort(key=lambda x: -x[1])

    brutos = []
    for i, v in picos:
        ini, fim = max(0.0, i - antes), min(float(dur), i + depois)
        if any(not (fim <= b["ini"] or ini >= b["fim"]) for b in brutos):
            continue   # já tem um momento cobrindo esse pedaço
        brutos.append({"ini": ini, "fim": fim, "nota": v, "pelo": "fala" if i in fala else "jogo"})
        if len(brutos) >= quantos * 2:
            break
    brutos.sort(key=lambda m: m["ini"])

    # junta os que ficaram colados (dois picos a 3 s um do outro são UM momento, não dois cortes)
    juntos = []
    for m in brutos:
        if juntos and m["ini"] - juntos[-1]["fim"] <= 3.0 and (m["fim"] - juntos[-1]["ini"]) <= max_s:
            juntos[-1]["fim"] = m["fim"]
            juntos[-1]["nota"] = round(max(juntos[-1]["nota"], m["nota"]), 3)
            if m["pelo"] == "fala":
                juntos[-1]["pelo"] = "fala"
        else:
            juntos.append(dict(m))
    # estica o que ficou curto demais para contar história, e corta o que passou do teto
    for m in juntos:
        if m["fim"] - m["ini"] < min_s:
            falta = min_s - (m["fim"] - m["ini"])
            m["ini"] = max(0.0, m["ini"] - falta * 0.6)
            m["fim"] = min(float(dur), m["fim"] + falta * 0.4)
        if m["fim"] - m["ini"] > max_s:
            m["fim"] = m["ini"] + max_s
    juntos = [m for m in juntos if m["fim"] - m["ini"] >= min_s * 0.7]
    # fala vale mais que jogo: no empate de nota, quem você comentou entra primeiro
    juntos.sort(key=lambda m: (-(m["nota"] + (0.5 if m["pelo"] == "fala" else 0))))
    escolhidos = sorted(juntos[:quantos], key=lambda m: m["ini"])
    for k, m in enumerate(escolhidos):
        m["n"] = k + 1
        m["ini"] = round(m["ini"], 2)
        m["fim"] = round(m["fim"], 2)
    return escolhidos


def fala_no_momento(palavras, ini, fim):
    """o que VOCÊ falou dentro do momento (a narração usa isso para não inventar)"""
    ws = [w["w"] for w in (palavras or [])
          if isinstance(w, dict) and w.get("w") and ini <= float(w.get("s") or 0) <= fim]
    return " ".join(ws)[:400]
