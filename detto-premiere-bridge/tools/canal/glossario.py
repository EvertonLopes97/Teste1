#!/usr/bin/env python3
"""GLOSSÁRIO DE GTA/GAMES EM PT-BR + CORREÇÃO DE ESCRITA (19/nov, pedido dele: vídeos saindo com "6 estrelas de PROCURA" em
vez de PROCURADO e outros erros de escrita). Duas camadas, porque a IA erra mesmo com instrução:
  1 `bloco()` entra no prompt de TODA IA de texto (roteiro, tradução, documentário, narrado) com os termos certos;
  2 `corrige(texto)` roda DEPOIS da IA e troca por regex os erros conhecidos (tradução literal do inglês, nome próprio errado).
Só troca erro que NUNCA é certo; termo ambíguo fica de fora. Acrescente linhas em `ERROS` quando achar outro."""
import re

# (padrão, troca) — flags: ignorar maiúsculas; a troca mantém a primeira letra maiúscula quando o original tinha
ERROS = [
    # nível de procurado (wanted level) — o erro que ele viu: "6 estrelas de procura"
    (r"\b(estrelas?|n[ií]vel|nível)\s+de\s+procura(?!d)", r"\1 de procurado"),
    (r"\b(estrelas?|n[ií]vel)\s+de\s+(?:busca|persegui[cç][aã]o|desejo|querido|procurada)\b", r"\1 de procurado"),
    (r"\bwanted\s+level\b", "nível de procurado"),
    (r"\bn[ií]vel\s+procurado\b", "nível de procurado"),
    (r"\bn[ií]vel\s+de\s+procura\s+policial\b", "nível de procurado"),
    # nomes próprios traduzidos ou escritos errado
    (r"\bCidade\s+do\s+V[ií]cio\b|\bCidade\s+Vice\b|\bVice[- ]?City\b", "Vice City"),
    (r"\bGrande\s+Roubo\s+(?:de\s+)?Auto(?:m[oó]vel)?\b|\bGrand\s+Theft\s+Autos?\b", "Grand Theft Auto"),
    (r"\bL[uú]cia\s+Caminhos\b|\bLucia\s+Caminho\b|\bLucia\s+Camino\b", "Lucia Caminos"),
    (r"\bJason\s+Duvall?\b|\bJasão\s+Duval\b", "Jason Duval"),
    (r"\bLeon[ií]das\b(?=.{0,40}(?:GTA|Vice|Rockstar|estado|mapa))", "Leonida"),
    (r"\bRock\s+Star(?:\s+Games)?\b", "Rockstar Games"),
    (r"\bTake\s*Two(?:\s+Interactive)?\b", "Take-Two"),
    (r"\bGTA\s*-?\s*(?:6|VI|seis)\b", "GTA 6"),
    (r"\bGTA\s*-?\s*(?:5|V|cinco)\b", "GTA 5"),
    (r"\bLos\s+Santo\b", "Los Santos"),
    (r"\bPlay\s*Station\b", "PlayStation"),
    (r"\bX[- ]?Box\b", "Xbox"),
    (r"\bpre[- ]?load\b|\bpré\s+load\b", "pré-load"),
    (r"\bpr[eé]-?carregamento\s+(?:do\s+)?jogo\b", "pré-load"),
    (r"\btrailler\b|\btreiler\b", "trailer"),
    (r"\bgame\s*play\b|\bgameplei\b", "gameplay"),
    (r"\bopen\s*world\b", "mundo aberto"),
    (r"\bheist\b", "assalto"),
    # duplicação de palavra que a IA e a legenda fazem ("o o jogo", "de de")
    (r"\b([a-zà-ú]+)\s+\1\b(?=[\s,.!?])", r"\1"),
]
_COMP = [(re.compile(a, re.I), b) for a, b in ERROS]


def _troca(m, modelo):
    return modelo


def corrige(texto):
    """→ texto com os erros conhecidos trocados (devolve igual se não achou nada)"""
    if not texto:
        return texto
    out = texto
    for rx, b in _COMP:
        out = rx.sub(b, out)
    # "procurado" no começo de frase continua maiúsculo etc. — nada a fazer; só tira espaço duplo
    return re.sub(r"[ \t]{2,}", " ", out)


def bloco():
    """texto para colar no prompt de qualquer IA de texto do canal"""
    return ("\n\nPORTUGUÊS CERTO (obrigatório — o vídeo é lido por milhares de pessoas, erro de escrita derruba a credibilidade):\n"
            "- Escreva em PORTUGUÊS DO BRASIL correto: ortografia, acentos, concordância e crase. NADA de tradução literal do inglês.\n"
            "- GTA: \"wanted level\" = NÍVEL DE PROCURADO (\"seis estrelas de procurado\", NUNCA \"de procura\" nem \"de busca\"); "
            "\"stars\" = estrelas; \"heist\" = assalto; \"open world\" = mundo aberto; \"pre-load\" = pré-load; \"cops/police\" = polícia.\n"
            "- Nomes que NÃO se traduzem e se escrevem exatamente assim: Vice City, Leonida, Lucia Caminos, Jason Duval, Rockstar Games, "
            "Take-Two, Grand Theft Auto, GTA 6, PlayStation, Xbox, trailer, gameplay.\n"
            "- Releia o texto inteiro antes de responder e corrija qualquer palavra duplicada, trocada ou cortada.\n")
