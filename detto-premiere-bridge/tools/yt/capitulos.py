# -*- coding: utf-8 -*-
"""CAPÍTULOS do YouTube — a barrinha dividida por assunto embaixo do vídeo.

Por que vale: um vídeo de 16-25 min com 3 notícias é uma parede lisa. Com capítulos, quem só quer a
notícia do reforço PULA para ela em vez de fechar o vídeo — e o YouTube mostra os títulos deles na
busca. É retenção e é SEO, de graça, sem mexer no vídeo.

REGRAS DO YOUTUBE, conferidas aqui em vez de supostas (um bloco que erra qualquer uma delas
simplesmente NÃO vira capítulo, e sem aviso):
  1. a lista começa em 00:00
  2. no mínimo 3 capítulos
  3. cada capítulo com 10 segundos ou mais
  4. em ordem crescente

Duas portas de entrada:
  `de_marcas`      — o canal.py SABE onde cada notícia começa (ele mesmo emendou as peças) e qual é a
                     manchete dela. Capítulo com o nome certo, no segundo certo. É o caminho bom.
  `de_transcricao` — para vídeo gravado por ele (editar.py), onde não existe essa estrutura: acha as
                     viradas pelas PAUSAS e pela troca de vocabulário, e dá um título de rascunho com
                     as palavras mais repetidas do trecho. É rascunho, não resumo.

A ideia de achar a virada pela pausa + troca de vocabulário vem do youtube-agent-skill
(github.com/Jakeschincariol/youtube-agent-skill, MIT). A implementação aqui é própria e em
português: as listas de palavras-de-apoio do original são em inglês e não servem para nada no
roteiro dele.
"""
from __future__ import annotations

import re
import unicodedata

MIN_S = 10.0        # o mínimo do YouTube
MIN_CAPS = 3        # o mínimo do YouTube
MAX_TITULO = 100    # o YouTube corta o título do capítulo por volta daí

# palavras que não dizem o assunto de nada (para o título de rascunho)
APOIO = set("""a o as os um uma uns umas de do da dos das em no na nos nas por pelo pela para com sem
sob sobre entre ao aos à às e ou mas que se como quando onde porque pois já não sim muito mais menos
também só ainda então aí lá ele ela eles elas eu tu você vocês nós a gente meu minha seu sua nosso
nossa isso isto esse essa este esta aquilo aquele aquela ser estar ter haver fazer ir vir dar ver
dizer falar ficar poder querer vai vou foi era tem tinha está estão são foram seria pode podia acho
olha cara gente galera bom bem agora hoje ontem amanhã aqui ali assim tudo nada nunca sempre coisa
pessoal vamos vai dar deu tá né pra pro""".split())


def _norm(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _palavras(t):
    return [w for w in re.findall(r"[a-záàâãéêíóôõúüç']{4,}", (t or "").lower())]


def mmss(s):
    s = max(0, int(round(float(s))))
    h, m, g = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{g:02d}" if h else f"{m}:{g:02d}"


# o que CONTINUA em caixa alta quando a manchete é rebaixada (sigla, canal, competição)
SIGLAS = set("""mg sp rj rs mt ms go ba pe ce pr sc df am pa cbf caf fifa var saf var tv af ge espn
tnt sbt band gta vi gb ps5 ps4 ia ai mvp otd uefa conmebol stjd cas ufc nba nfl dvd pc xbox hd 4k
8k fps rp npc dlc""".split())
# palavras pequenas que ficam minúsculas no meio do título
MIUDAS = set("""de do da dos das e ou em no na nos nas a o as os um uma por pelo pela pelos pelas para
com sem ao aos à às que se""".split())


def _titulo_limpo(t, n=MAX_TITULO):
    """a manchete vem em CAIXA ALTA (é feita para a faixa do vídeo). Na lista de capítulos, caixa alta
    GRITA e o YouTube mostra isso na busca — então rebaixo, mas sem estragar sigla nem nome de canal:
    "GLOBO ESPORTE MG" tem que virar "Globo Esporte MG", não "Globo esporte mg"."""
    t = re.sub(r"\s+", " ", str(t or "").strip()).strip(" -–—•|")
    letras = [c for c in t if c.isalpha()]
    if letras and len(t) > 12 and all(c.isupper() for c in letras):
        saiu = []
        for i, p in enumerate(t.split(" ")):
            nu = _norm(re.sub(r"\W", "", p))
            if nu in SIGLAS or (len(nu) <= 3 and not nu.isalpha()):
                saiu.append(p)                      # sigla fica como está
            elif i and nu in MIUDAS:
                saiu.append(p.lower())
            else:
                saiu.append(p[:1] + p[1:].lower())  # Palavra
        t = " ".join(saiu)
    return t[:n].rstrip(" ,.;:-") or "Trecho"


def arruma(marcas, dur_total, primeiro="Resumo de hoje"):
    """recebe [(segundo, título), ...] e devolve a lista que o YouTube ACEITA.

    - ordena, força o 00:00, junta o que ficou com menos de 10 s no capítulo anterior
      (juntar é melhor que descartar: a notícia não desaparece da lista, ela só compartilha o capítulo)
    - devolve [] quando não dá para fazer 3 capítulos válidos, em vez de devolver um bloco que o
      YouTube ignora em silêncio
    """
    dur_total = float(dur_total or 0)
    itens = []
    for s, t in marcas or []:
        try:
            s = float(s)
        except (TypeError, ValueError):
            continue
        if s < 0 or (dur_total and s > dur_total - MIN_S):
            continue
        itens.append([s, _titulo_limpo(t)])
    itens.sort(key=lambda x: x[0])
    # o primeiro capítulo é obrigatoriamente 00:00
    if not itens or itens[0][0] > 0.5:
        itens.insert(0, [0.0, _titulo_limpo(primeiro)])
    else:
        itens[0][0] = 0.0
    # junta os curtos: quem começa menos de 10 s depois do anterior não pode existir
    caps = []
    for s, t in itens:
        if caps and s - caps[-1][0] < MIN_S:
            continue
        caps.append([s, t])
    if dur_total and caps and dur_total - caps[-1][0] < MIN_S:
        caps.pop()
    if len(caps) < MIN_CAPS:
        return []
    return [{"s": round(s, 2), "tempo": mmss(s), "titulo": t} for s, t in caps]


def texto(caps):
    """o bloco para colar na descrição (é assim que o YouTube lê os capítulos: uma linha por capítulo)"""
    if not caps:
        return ""
    return "\n".join(f"{c['tempo']} {c['titulo']}" for c in caps)


def de_marcas(marcas, dur_total, primeiro="Resumo de hoje"):
    """o caminho bom: o programa já sabe o segundo e o nome de cada bloco"""
    return arruma(marcas, dur_total, primeiro)


def desloca(marcas, a_partir_de, quanto):
    """a vinheta entra no MEIO do vídeo (depois da chamada) e empurra tudo o que vem depois dela.

    Sem isto, todo capítulo depois da abertura ficaria ~3 s adiantado — e um capítulo adiantado é
    pior que nenhum, porque cai no fim da notícia anterior.
    """
    quanto = float(quanto or 0)
    if quanto <= 0:
        return list(marcas or [])
    return [(s + quanto, t) if float(s) >= float(a_partir_de) - 0.01 else (s, t) for s, t in (marcas or [])]


def de_transcricao(palavras, dur_total=None, alvo=7, primeiro="Começo"):
    """vídeo gravado por ele: acha as viradas pelas PAUSAS e pela troca de assunto.

    `palavras` = a lista do transcrever.py ({"w","s","e"}). O título sai das palavras mais repetidas
    do trecho — é rascunho para ele reescrever, não um resumo.
    """
    ws = [w for w in (palavras or []) if isinstance(w, dict) and w.get("w")]
    if len(ws) < 40:
        return []
    fim = float(ws[-1].get("e") or 0)
    dur_total = float(dur_total or fim)
    # frases pelas pausas
    frases, atual = [], None
    for w in ws:
        s, e = float(w.get("s") or 0), float(w.get("e") or 0)
        if atual and s - atual[1] > 0.6:
            frases.append(atual)
            atual = None
        if atual is None:
            atual = [s, e, [w["w"]]]
        else:
            atual[1] = e
            atual[2].append(w["w"])
    if atual:
        frases.append(atual)
    if len(frases) < 6:
        return []
    # nota de cada emenda: pausa longa + vocabulário que mudou
    cand = []
    for i in range(1, len(frases)):
        pausa = frases[i][0] - frases[i - 1][1]
        antes = set(_palavras(" ".join(" ".join(f[2]) for f in frases[max(0, i - 12):i]))) - APOIO
        depois = set(_palavras(" ".join(" ".join(f[2]) for f in frases[i:i + 12]))) - APOIO
        virada = 1 - len(antes & depois) / len(antes | depois) if (antes | depois) else 0
        cand.append((pausa * 1.6 + virada * 3.2, frases[i][0], i))
    cand.sort(reverse=True)
    cortes = [0.0]
    for _, t, _ in cand:
        if len(cortes) >= max(MIN_CAPS, int(alvo)):
            break
        if all(abs(t - c) >= max(MIN_S, dur_total / 40) for c in cortes) and dur_total - t >= MIN_S:
            cortes.append(t)
    cortes.sort()
    marcas = []
    for n, t in enumerate(cortes):
        ate = cortes[n + 1] if n + 1 < len(cortes) else dur_total
        txt = " ".join(" ".join(f[2]) for f in frases if f[0] >= t and f[1] <= ate)
        cont = {}
        for w in _palavras(txt):
            if w not in APOIO:
                cont[w] = cont.get(w, 0) + 1
        top = sorted(cont, key=lambda w: (-cont[w], w))[:3]
        marcas.append((t, " ".join(w.capitalize() for w in top) if top else "Trecho"))
    if marcas:
        marcas[0] = (0.0, _titulo_limpo(primeiro))
    return arruma(marcas, dur_total, primeiro)
