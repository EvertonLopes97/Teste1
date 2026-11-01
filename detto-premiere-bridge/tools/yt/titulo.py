# -*- coding: utf-8 -*-
"""TÍTULO + THUMB conferidos antes de subir — em português e com as regras MEDIDAS dos nichos dele.

O par título+thumb é UMA coisa, não duas. O erro mais comum é a thumb repetir a palavra do título:
metade da área de clique gasta dizendo o mesmo. Isso é o que esta conferência procura primeiro.

POR QUE NÃO USEI O ORIGINAL: o `title.py` do youtube-agent-skill (MIT) procura "amazing",
"incredible", "insane" e trata "the/a/of" como palavra vazia. No título dele, em português, ele
aprovaria "OLHA O QUE A RENATA FAN FALOU" (nenhuma palavra vaga EM INGLÊS) e reprovaria títulos bons.
Então a ideia é dele; as listas, os limites e o peso são daqui — e as regras de nicho vêm da medição
de 30/out (150 vídeos do Galo, 96 de GTA 6), não de palpite.

   python tools\\yt\\titulo.py --titulo "..." --thumb "PLANTÃO" --nicho galo
   python tools\\yt\\titulo.py titulos.txt --nicho gta6        (um por linha, ranqueados)
   python tools\\yt\\titulo.py --titulo "..." --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

CORTE_PC, CORTE_CELULAR, LIMITE = 60, 40, 100

# vago em PORTUGUÊS — promete sem dizer nada
VAGAS = set("""absurdo absurda incrivel inacreditavel surreal chocante bombastico impressionante
historico inedito exclusivo urgente polemica polemico monstruoso gigante enorme melhor pior maior
tudo tudao segredo misterio revelacao definitivo completo total surpreendente assustador insano
louco doido impensavel""".split())
# palavras que não carregam assunto (para medir se o começo do título diz algo)
VAZIAS = set("""a o as os um uma uns umas de do da dos das em no na nos nas por pelo pela para com
sem sob sobre entre ao aos à às e ou mas que se como quando onde porque pois ja nao sim muito mais
menos tambem so ainda entao ai la ele ela eles elas eu voce isso isto esse essa este esta aquele
aquela ser estar ter haver fazer ir vir dar ver dizer falar ficar poder querer vai vou foi era tem
tinha esta estao sao foram seria pode olha veja agora hoje""".split())

# ---------------------------------------------------------------- regras MEDIDAS (30/out)
NICHOS = {
    "galo": {
        "nome": "Galo",
        # jornalista famoso no título: 1,36x — a maior alavanca medida
        "ganha": [(r"\b(renata fan|denilson|neto|mauro cezar|craque neto|benja|jorge nicola|venê|vene casagrande|"
                   r"nicola|andre henning|paulo vinicius coelho|pvc)\b", 1.36, "jornalista famoso no título"),
                  (r"\b(refor[çc]o|contrata|contrata[çc][ãa]o|mercado|assina|chega(?:ndo)?|fechado)\b", 1.22, "reforço/mercado"),
                  (r"\b(globo esporte|jogo aberto|os donos da bola|seleção sportv|sportv|band minas|itatiaia|"
                   r"alterosa|espn|cortes tnt|tnt sports)\b", 1.18, "nome do programa no título"),
                  (r"\?", 1.14, "pergunta no título"),
                  (r" / ", 1.11, "título em duas partes")],
        # arbitragem rende MENOS (0,89x)
        "perde": [(r"\b(arbitragem|[áa]rbitro|roubo|roubada|var|p[êe]nalti n[ãa]o marcado)\b", 0.89,
                   "arbitragem/VAR rende 0,89x no seu nicho — não construa o título nisso")],
        "duracao_boa": (16, 25),
    },
    "gta6": {
        "nome": "GTA 6",
        # no GTA o título quase não muda nada; o que MUDA é o que PIORA
        "ganha": [(r"#gta6", 1.04, "#gta6 no título")],
        "perde": [(r"\b(vazou|vazamento|leak|leaked)\b", 0.90, '"vazou/vazamento" rende 0,90x — chame de "nova informação"'),
                  (r"\.\.\.\s*$", 0.90, 'terminar com "..." rende 0,90x')],
        "duracao_boa": (12, 18),
    },
}


def _norm(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _palavras(t):
    return re.findall(r"[a-z0-9']+", _norm(t))


def confere(titulo, thumb=None, nicho=None, duracao_min=None):
    t = re.sub(r"\s+", " ", str(titulo or "").strip())
    n = len(t)
    problemas, bons = [], []

    # ---- tamanho
    if n > LIMITE:
        problemas.append(("tamanho", f"{n} letras — o YouTube corta em {LIMITE}; o fim do título não existe", 3))
    elif n > CORTE_PC:
        problemas.append(("tamanho", f"{n} letras — a busca no PC corta perto de {CORTE_PC}", 1))
    else:
        bons.append(f"{n} letras, cabe no corte de {CORTE_PC} do PC")
    if n > CORTE_CELULAR:
        inicio = t[:CORTE_CELULAR].rsplit(" ", 1)[0]
        problemas.append(("celular", f'no celular aparece mais ou menos "{inicio}…" — confira se o ASSUNTO sobrevive', 1))

    # ---- caixa alta: ELE escreve o título todo em caixa alta DE PROPÓSITO (e os concorrentes medidos
    # também). Reclamar disso em todo vídeo é ruído. O sinal de spam é caixa alta MISTURADA — umas
    # palavras gritando dentro de um título normal.
    pal = [w for w in t.split() if len(w) > 2 and any(c.isalpha() for c in w)]
    gritos = [w for w in pal if w.isupper()]
    # sem tolerância: UMA palavra em caixa mista já é título misto ("URGENTE! O Galo ACABOU de...")
    tudo_caixa = bool(pal) and len(gritos) == len(pal)
    if tudo_caixa:
        bons.append("título todo em caixa alta (o padrão do seu canal e dos concorrentes)")
    elif len(gritos) > 3:
        problemas.append(("grito", f"{len(gritos)} palavras gritando dentro de um título normal — lê-se como spam", 2))
    elif gritos:
        bons.append(f"{len(gritos)} palavra(s) em caixa alta para dar ênfase")

    # ---- vago x concreto
    v = sorted({w for w in _palavras(t) if w in VAGAS})
    if v:
        problemas.append(("vago", f"{', '.join(v)} — troque por um NOME, um NÚMERO ou uma DATA", 2))
    nums = [x.rstrip(".,") for x in re.findall(r"\d[\d.,]*%?", t)]
    if nums:
        bons.append(f"tem número concreto ({', '.join(nums[:3])})")
    # NOME PRÓPRIO: num título todo em CAIXA ALTA, a inicial maiúscula não diz nada — toda palavra
    # pareceria nome próprio ("ESPORTE, MG:, DIRETORES"). Aí eu procuro os nomes que o nicho CONHECE.
    if tudo_caixa:
        nomes = []
        for padrao, _, porque in (NICHOS.get(nicho or "") or {}).get("ganha", []):
            if "jornalista" not in porque and "programa" not in porque:
                continue
            m = re.search(padrao, t, re.I)
            if m:
                nomes.append(m.group(0))
    else:
        nomes = [w for w in t.split()[1:] if w[:1].isupper() and _norm(re.sub(r"\W", "", w)) not in VAZIAS and len(w) > 2]
    if nomes:
        bons.append(f"cita nome próprio ({', '.join(nomes[:3])})")
    if not nums and not nomes:
        problemas.append(("sem-ancora", "não tem número, data nem nome próprio conhecido — é o conserto mais confiável "
                                        "que existe", 3))

    # ---- o começo do título diz algo?
    comeco = [w for w in _palavras(t)[:3] if w not in VAZIAS]
    if not comeco:
        problemas.append(("comeco-vazio", "as 3 primeiras palavras são de enchimento — puxe o assunto para a frente", 2))

    # ---- o par com a thumb (o motivo de isto existir)
    if thumb:
        pt = {w for w in _palavras(t) if w not in VAZIAS}
        ph = {w for w in _palavras(thumb) if w not in VAZIAS}
        juntas = pt & ph
        if juntas:
            problemas.append(("repetida", f"a thumb repete o título em: {', '.join(sorted(juntas))} — "
                                          "a thumb tem que dizer o que o título NÃO diz", 3))
        else:
            bons.append("thumb e título dizem coisas diferentes")
        pw = _palavras(thumb)
        if len(pw) > 4:
            problemas.append(("thumb-longa", f"{len(pw)} palavras na thumb — no tamanho do feed, 3 é o teto", 2))

    # ---- regras medidas do nicho
    nic = NICHOS.get(nicho or "")
    alavanca = 1.0
    if nic:
        for padrao, peso, porque in nic["ganha"]:
            if re.search(padrao, t, re.I):
                alavanca *= peso
                bons.append(f"{porque} (medido: {peso:.2f}x)")
        for padrao, peso, porque in nic["perde"]:
            if re.search(padrao, t, re.I):
                alavanca *= peso
                problemas.append(("nicho", porque, 2))
        if duracao_min:
            a, b = nic["duracao_boa"]
            if a <= duracao_min <= b:
                bons.append(f"duração de {duracao_min:.0f} min está na faixa que rende mais ({a}-{b} min)")
            else:
                problemas.append(("duracao", f"{duracao_min:.0f} min — no seu nicho a faixa que rende mais é {a}-{b} min", 1))

    # os pontos bons não APAGAM uma reclamação: com problema em aberto a nota não chega a 100, senão o
    # relatório diz "100/100" com dois ✗ na tela e ninguém olha mais para os ✗
    base = 100 - 9 * sum(p[2] for p in problemas)
    nota = max(0, min(99 if problemas else 100, base + min(20, 4 * len(bons))))
    return {"titulo": t, "letras": n, "nota": nota, "alavanca": round(alavanca, 3),
            "problemas": [{"tipo": a, "diz": b, "peso": c} for a, b, c in problemas], "bons": bons,
            "nicho": nic["nome"] if nic else ""}


def texto(r):
    L = [f'\n  "{r["titulo"]}"', f"  {r['letras']} letras · nota {r['nota']}/100"
         + (f" · alavanca medida {r['alavanca']:.2f}x ({r['nicho']})" if r["nicho"] and r["alavanca"] != 1 else "")]
    for p in sorted(r["problemas"], key=lambda x: -x["peso"]):
        L.append(f"    ✗ {p['tipo']:<13} {p['diz']}")
    for b in r["bons"]:
        L.append(f"    ✔               {b}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="confere título + thumb antes de subir (regras medidas dos nichos dele)")
    ap.add_argument("arquivo", nargs="?", help="arquivo com um título por linha")
    ap.add_argument("--titulo")
    ap.add_argument("--thumb", help="o texto que está ESCRITO na thumb")
    ap.add_argument("--nicho", choices=sorted(NICHOS), help="galo | gta6 (aplica as regras medidas)")
    ap.add_argument("--duracao-min", type=float, default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.titulo:
        linhas = [a.titulo]
    elif a.arquivo and Path(a.arquivo).exists():
        linhas = [l for l in Path(a.arquivo).read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        ap.print_help()
        return 1
    rs = sorted((confere(t, a.thumb, a.nicho, a.duracao_min) for t in linhas), key=lambda r: -r["nota"])
    if a.json:
        print(json.dumps(rs, ensure_ascii=False, indent=1))
    else:
        for r in rs:
            print(texto(r))
        if len(rs) > 1:
            print(f"\n  melhor: {rs[0]['titulo']}  (nota {rs[0]['nota']})\n")
        else:
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
