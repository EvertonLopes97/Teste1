#!/usr/bin/env python3
"""FATOS ATUAIS (13/nov, "o short falou de jogadores que não estão mais no Galo e do Cuca, que não é mais o técnico").

A IA que escreve as falas tem MEMÓRIA VELHA: quando o texto da notícia é curto e o pedido é "N palavras", ela completa
com o que lembra (técnico antigo, jogador que já saiu). Três defesas, usadas pelo canal.py e pelo narrado.py:

1. `bloco()` — entra em todo pedido de roteiro: a data de hoje, a ordem de NÃO citar técnico/elenco/tabela/nome que
   não esteja no material, e os fatos que ELE escreveu em `<pasta do canal>\\fatos.txt`.
2. `fatos.txt` — texto livre (ex.: "Técnico atual: Fulano") + linhas `NÃO CITAR: Cuca, Beltrano` (quem saiu).
3. `limpa()` — conferência DEPOIS da IA: frase que cita um nome de NÃO CITAR (e o nome não está no material da
   notícia) é retirada, e o registro diz qual.
"""
import datetime as dt
import re
import unicodedata
from pathlib import Path

MODELO = """# FATOS ATUAIS deste canal — a IA lê isto antes de escrever qualquer fala.
# Escreva em texto livre o que é verdade HOJE (uma linha por fato). Linhas com # são comentários.
# Quem saiu do clube vai em linhas "NÃO CITAR:" (nomes separados por vírgula): a frase que citar é cortada,
# a não ser que a própria notícia do dia fale da pessoa.
#
# Técnico atual: <escreva aqui>
# Reforços recentes: <escreva aqui>
NÃO CITAR: Cuca
"""


def _n(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")


def le(pasta, criar=False):
    """→ (fatos em texto, [nomes que não podem ser citados])"""
    if not pasta:
        return "", []
    f = Path(pasta) / "fatos.txt"
    if not f.exists():
        if criar:
            try:
                f.write_text(MODELO, encoding="utf-8")
            except OSError:
                pass
        else:
            return "", []
    try:
        linhas = f.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return "", []
    fatos, fora = [], []
    for ln in linhas:
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        m = re.match(r"(?i)n[ãa]o\s+citar\s*:\s*(.+)", ln)
        if m:
            fora += [x.strip() for x in re.split(r"[,;]", m.group(1)) if len(x.strip()) >= 3]
        else:
            fatos.append(ln)
    return "\n".join(fatos), fora


def bloco(pasta=None):
    fatos, fora = le(pasta)
    hoje = dt.date.today()
    t = (f"\n\nATUALIDADE (obrigatório): hoje é {hoje:%d/%m/%Y}. A sua memória sobre clubes, elencos e técnicos está "
         "DESATUALIZADA. Fale SOMENTE do que está no material acima. É PROIBIDO citar de memória técnico, jogador, "
         "escalação, contratação, saída, lesão, tabela, placar ou data que não esteja escrito no material. Precisa de mais "
         "palavras? Explique, opine e desenvolva o que ESTÁ no material — nunca acrescente fato novo.")
    if fatos:
        t += f"\nFATOS ATUAIS confirmados pelo dono do canal (valem mais que a sua memória):\n{fatos}"
    if fora:
        t += f"\nNÃO CITE (não fazem mais parte do clube, salvo se o material falar deles): {', '.join(fora)}."
    return t


def limpa(texto, pasta=None, material="", log=None):
    """tira as frases que citam um nome de NÃO CITAR que não aparece no material da notícia → (texto, [nomes tirados])"""
    _, fora = le(pasta)
    if not fora or not texto:
        return texto, []
    mat = _n(material)
    proibidos = [x for x in fora if _n(x) not in mat]
    if not proibidos:
        return texto, []
    ficam, tirados = [], []
    for fr in re.split(r"(?<=[.!?…])\s+", str(texto).strip()):
        achou = [x for x in proibidos if re.search(r"\b" + re.escape(_n(x)) + r"\b", _n(fr))]
        if achou:
            tirados += achou
            if log:
                log(f"   ⚠ frase com nome desatualizado ({', '.join(achou)}) tirada: \"{fr[:70]}\"")
            continue
        ficam.append(fr)
    return " ".join(ficam).strip(), sorted(set(tirados))
