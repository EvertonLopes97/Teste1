# -*- coding: utf-8 -*-
"""RETENÇÃO — onde o público ABANDONA os SEUS vídeos, e o que você estava falando ali.

É a peça que faltava no sistema. Hoje ele mede os CONCORRENTES (o que viraliza nos nichos, 30/out) e
nunca mede os vídeos dele — então todo acerto e todo erro dos vídeos que ele publica passa em branco.

Pega o arquivo no YouTube Studio:
   Analytics → escolha o vídeo → Engajamento → o gráfico "Retenção do público" → ícone de baixar →
   "Retenção do público". Vem um CSV com duas colunas: a posição no vídeo e quantos % ainda estão
   assistindo.

   python tools\\yt\\retencao.py "retencao.csv" --duracao 980
   python tools\\yt\\retencao.py "retencao.csv" --duracao 980 --words "<job>\\words.json"
   python tools\\yt\\retencao.py "retencao.csv" --capitulos "<pronto>\\post.json"

Três problemas DIFERENTES, com três consertos diferentes — é por isso que saem separados:

  VAZAMENTO NO GANCHO  quanto você perdeu nos primeiros 30 s. Conserta-se na PRIMEIRA FRASE.
  PAREDÕES             quedas secas: um momento certo em que as pessoas foram embora. Conserta-se
                       cortando AQUELE trecho.
  ESCORREGA            a sangria lenta e constante do meio. Não é conteúdo, é RITMO: corta-se o
                       meio, não se reescreve.

Com `--words` (a transcrição que o sistema já gera) ou `--capitulos` (o post.json do canal), cada
paredão vem com O QUE ESTAVA SENDO DITO ali — é a única versão deste relatório em que dá para agir
sem ficar arrastando a linha do tempo procurando.

A separação gancho/paredão/escorrega vem do youtube-agent-skill
(github.com/Jakeschincariol/youtube-agent-skill, MIT); aqui o relatório é em português, lê a
transcrição e os capítulos do próprio sistema, e as faixas de "saudável" são por DURAÇÃO do vídeo
(um vídeo de 20 min não perde no gancho como um Short).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def le_csv(caminho):
    """duas colunas de número: posição e % assistindo. O Studio muda o cabeçalho e o separador
    conforme o idioma da conta, então eu não confio em nome de coluna — pego os números."""
    linhas = []
    texto = Path(caminho).read_text(encoding="utf-8-sig", errors="replace")
    sep = ";" if texto.count(";") > texto.count(",") else ","
    for r in csv.reader(texto.splitlines(), delimiter=sep):
        nums = []
        for c in r:
            c = c.strip().replace("%", "").replace('"', "")
            if sep == ";":
                c = c.replace(".", "").replace(",", ".")   # 1.234,5 → 1234.5
            try:
                nums.append(float(c))
            except ValueError:
                pass
        if len(nums) >= 2:
            linhas.append((nums[0], nums[1]))
    return linhas


def palavras_de(arquivo):
    """aceita o words.json do transcrever.py (lista) e o do canal.py ({"palavras": [...]})"""
    try:
        d = json.loads(Path(arquivo).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(d, dict):
        d = d.get("palavras") or []
    return [w for w in d if isinstance(w, dict) and w.get("w")]


def capitulos_de(arquivo):
    """os capítulos do post.json — dizem em que NOTÍCIA caiu o paredão"""
    try:
        d = json.loads(Path(arquivo).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    caps = d.get("capitulos") if isinstance(d, dict) else None
    return [c for c in (caps or []) if isinstance(c, dict) and "s" in c]


def _frase_em(ws, t, folga=4.0):
    return " ".join(w["w"] for w in ws if float(w.get("s") or 0) <= t + folga and float(w.get("e") or 0) >= t - folga)


def _capitulo_em(caps, t):
    atual = ""
    for c in caps:
        if float(c["s"]) <= t:
            atual = c.get("titulo", "")
        else:
            break
    return atual


def analisa(linhas, duracao=None, ws=None, caps=None):
    if len(linhas) < 8:
        raise ValueError("não consegui ler nem 8 pontos nesse CSV — é o arquivo da RETENÇÃO DO PÚBLICO?")
    xs = [a for a, _ in linhas]
    ys = [b for _, b in linhas]
    dur = float(duracao) if duracao else None
    # O EIXO É % OU SEGUNDO? Num vídeo de até ~100 s os dois são IDÊNTICOS (33 s e 33% dão o mesmo
    # número) — e confundir isso jogava o paredão de um Short dentro da janela do gancho e o fazia
    # desaparecer do relatório. Com a duração na mão dá para decidir: se o último ponto bate com a
    # duração, o eixo é em SEGUNDOS.
    em_pct = max(xs) <= 100.5
    if dur and em_pct and abs(max(xs) - dur) <= max(3.0, dur * 0.1):
        em_pct = False

    def seg(x):
        return x / 100.0 * dur if (em_pct and dur) else x

    inicio = ys[0] or 100.0
    # os primeiros 30 s. Sem a duração e com eixo em %, 10% é o palpite — e eu digo isso no relatório.
    corte = 30.0 if not em_pct else (30.0 / dur * 100 if dur else 10.0)
    no_gancho = min([y for x, y in linhas if x <= corte] or [inicio])
    vazamento = inicio - no_gancho
    # O STUDIO MANDA ~100 PONTOS DO VÍDEO INTEIRO: num vídeo de 16 min cada ponto é ~10 s, então os
    # primeiros 30 s são 3 pontos. Dizer "gancho saudável" com 3 pontos é chutar — eu aviso em vez de
    # dar um veredito falso.
    pontos_gancho = sum(1 for x, _ in linhas if x <= corte)

    quedas = []
    for i in range(1, len(linhas)):
        caiu = ys[i - 1] - ys[i]
        vao = (xs[i] - xs[i - 1]) or 1
        quedas.append((caiu / vao, xs[i - 1], caiu))
    # PAREDÃO é queda FORA DO NORMAL daquele vídeo, não queda acima de um número fixo: num vídeo que
    # escorrega 1%/ponto, uma queda de 1,1% é o próprio escorrega — listar isso enche o relatório de
    # ruído e esconde o paredão de verdade.
    ordenadas = sorted(c for _, _, c in quedas)
    tipica = ordenadas[len(ordenadas) // 2] if ordenadas else 0.0
    minimo = max(1.5, tipica * 2.5)
    paredoes = []
    for _, x0, caiu in sorted(quedas, reverse=True)[:6]:
        if caiu < minimo or x0 <= corte:   # o gancho é o item 1; aqui são os momentos DEPOIS dele
            continue
        t = seg(x0) if (not em_pct or dur) else None
        paredoes.append({"x": round(x0, 2), "segundo": round(t, 1) if t is not None else None, "caiu": round(caiu, 2),
                         "falando": _frase_em(ws or [], t)[:150] if (ws and t is not None) else "",
                         "capitulo": _capitulo_em(caps or [], t) if (caps and t is not None) else ""})
    meio = [c for c, x0, _ in quedas if x0 > corte]
    escorrega = sum(meio) / len(meio) if meio else 0.0

    # QUANTO É NORMAL depende da duração: um vídeo de 20 min não perde no gancho como um Short
    limite = 25.0
    if dur:
        limite = 18.0 if dur <= 90 else 25.0 if dur <= 600 else 32.0
    return {"pontos": len(linhas), "inicio": round(inicio, 1), "fim": round(ys[-1], 1),
            "vazamento": round(vazamento, 1), "limite_saudavel": limite, "em_pct": em_pct, "duracao": dur,
            "pontos_gancho": pontos_gancho, "queda_tipica": round(tipica, 2), "minimo_paredao": round(minimo, 2),
            "paredoes": paredoes, "escorrega": round(escorrega, 3)}


def relatorio(r, nome=""):
    L = []
    L.append(f"\nRETENÇÃO — {nome}" if nome else "\nRETENÇÃO")
    L.append(f"{r['pontos']} pontos · começa em {r['inicio']:.0f}% e termina em {r['fim']:.0f}%"
             + (f" · vídeo de {r['duracao'] / 60:.0f} min" if r.get("duracao") else ""))
    if r["em_pct"] and not r.get("duracao"):
        L.append("(o CSV veio em % do vídeo e você não passou --duracao: os tempos abaixo são aproximados)")

    v, lim = r["vazamento"], r["limite_saudavel"]
    # cada ponto do arquivo vale quantos segundos? Acima de ~5 s por ponto, 30 s são 5 ou 6 pontos e o
    # gancho não aparece no gráfico — não dá veredito em cima disso.
    seg_por_ponto = (r["duracao"] / r["pontos"]) if (r.get("duracao") and r.get("pontos")) else 0
    poucos = r.get("pontos_gancho", 99) < 6 or seg_por_ponto > 5
    como = "POUCOS PONTOS" if poucos else "SAUDÁVEL" if v < lim else "VAZANDO" if v < lim * 1.6 else "GRAVE"
    L.append(f"\n1) GANCHO — perdeu {v:.1f}% nos primeiros 30 s   [{como}]")
    if poucos:
        L.append(f"   Só {r['pontos_gancho']} ponto(s) do arquivo caem nos primeiros 30 s — o Studio manda ~100 pontos do")
        L.append("   vídeo INTEIRO, então num vídeo longo o gancho fica grosseiro e eu não dou veredito.")
        L.append("   Para medir o gancho de verdade: Analytics → Conteúdo → \"Os primeiros 30 segundos\" no Studio.")
    else:
        L.append(f"   até {lim:.0f}% é normal para um vídeo deste tamanho.")
    if v >= lim and not poucos:
        L.append("   Conserto: a PRIMEIRA FRASE. Nada mais importa enquanto isso vazar — nem thumb, nem título.")
        L.append("   No canal: é o 'abertura' do roteiro (o resumo + CTA). Comece pelo fato, não por 'fala galera'.")
    elif not poucos:
        L.append("   O gancho está de pé. Olhe os paredões abaixo.")

    L.append(f"\n2) PAREDÕES — os momentos em que as pessoas FORAM EMBORA"
             f"   (queda normal deste vídeo: {r.get('queda_tipica', 0):.2f}%; "
             f"só conto paredão acima de {r.get('minimo_paredao', 1.5):.2f}%)")
    if not r["paredoes"]:
        L.append("   nenhuma queda fora do normal — a perda toda é escorrega (item 3), não momento.")
    for p in r["paredoes"]:
        if p["segundo"] is None:
            onde = f"{p['x']}%"
        else:
            s = int(p["segundo"])
            onde = f"{s}s ({s // 60}:{s % 60:02d})"   # // e não arredondamento: 413 s é 6:53, não 7min52
        L.append(f"   -{p['caiu']:4.1f}%  em {onde}" + (f"   · capítulo: {p['capitulo']}" if p["capitulo"] else ""))
        if p["falando"]:
            L.append(f'            você estava dizendo: "{p["falando"]}"')
    if r["paredoes"]:
        L.append("   Conserto: CORTE esse trecho no próximo vídeo. Paredão quase sempre é trecho de imprensa longo")
        L.append("   demais sem a sua fala no meio, ou uma notícia que não interessava.")

    L.append(f"\n3) ESCORREGA — {r['escorrega']:.3f}% por ponto no meio do vídeo")
    L.append("   Escorrega parelho é RITMO, não conteúdo: encurte o vídeo e os trechos, não reescreva o texto.")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="onde o público abandona os seus vídeos (CSV do YouTube Studio)")
    ap.add_argument("csv", help="o arquivo baixado em Analytics → Engajamento → Retenção do público")
    ap.add_argument("--duracao", type=float, default=None, help="duração do vídeo em SEGUNDOS (deixa os tempos exatos)")
    ap.add_argument("--words", default=None, help="words.json da transcrição: diz o que você estava falando em cada queda")
    ap.add_argument("--capitulos", default=None, help="post.json do canal: diz em que notícia caiu")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not Path(a.csv).exists():
        print(f"não achei {a.csv}")
        return 1
    ws = palavras_de(a.words) if a.words else []
    caps = capitulos_de(a.capitulos) if a.capitulos else []
    dur = a.duracao
    if not dur and ws:
        dur = max(float(w.get("e") or 0) for w in ws)   # a transcrição já diz quanto o vídeo tem
    try:
        r = analisa(le_csv(a.csv), dur, ws, caps)
    except ValueError as e:
        print(f"{e}")
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else relatorio(r, Path(a.csv).name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
