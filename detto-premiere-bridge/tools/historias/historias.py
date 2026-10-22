# -*- coding: utf-8 -*-
"""HISTÓRIAS EM SÉRIE — reels de história com o público escolhendo a continuação (o formato que viralizou em out/2026:
Histórias com Kaio, Manual do Benji, Tio do Fim, Insólito).

    python tools\\historias\\historias.py                      → faz o próximo episódio de cada série ligada
    python tools\\historias\\historias.py --serie apocalipse   → só essa
    python tools\\historias\\historias.py --novo "apocalipse zumbi em BH" --conta detto.historias
    python tools\\historias\\historias.py --apurar             → só lê os votos dos episódios já postados

COMO O FORMATO FUNCIONA (medido nos virais):
  60-90 s · ilustração chapada desenhada por código (mesmo visual em toda a série) · narração 150-190 palavras/min ·
  legenda grande em caixa alta com a palavra-chave colorida · relógio/contador na tela · troca de cena a cada 4-6 s.
  Narrativa: gancho em 2ª pessoa → promessa com risco → personagem + hora → REGRAS NUMERADAS com razão técnica de
  verdade (é o que faz salvar/compartilhar) → detalhe doméstico brasileiro → cliffhanger → ESCOLHA A/B.
  O episódio seguinte abre com o resultado ("84% mandaram o Lucas pro mercadinho") — é esse laço que faz crescer.

PASTAS (E:\\DETTO\\historias ou --pasta):
  config.json              geral (contas, voz, quantos por dia)
  series\\<nome>\\serie.json   o mundo, os personagens, as regras e os episódios já feitos
  series\\<nome>\\ep_NN\\       roteiro.json, voz.wav, words.json, episodio.mp4, post.txt
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "reels"))
sys.path.insert(0, str(TOOLS / "canal"))

CONFIG_PADRAO = {
    "contas": ["instagram:detto.historias"],  # para onde o episódio vai (mesma fila do painel)
    "por_dia": 1,
    "duracao_s": 80,              # os virais ficam entre 65 e 90 s
    "palavras_min": 170,          # ritmo da narração medido nos virais
    "voz_voicestudio": "",        # perfil de voz no VoiceStudio; vazio = a voz padrão dele
    "voicestudio": "",
    "velocidade_voz": 1.0,
    "marca": "",                  # @ que aparece no rodapé do vídeo
    "fps": 30,
    "auto_postar": True,
}

SERIE_PADRAO = {
    "nome": "",
    "tema": "",
    "mundo": "",
    "personagens": [],
    "conta": "",
    "ligada": True,
    "episodios": [],
}


def log(m):
    print(m, flush=True)


def pasta_padrao():
    if os.name == "nt" and Path("E:/").exists():
        return Path("E:/DETTO/historias")
    return Path.home() / "DETTO" / "historias"


def le_json(f, padrao=None):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return padrao


def grava_json(f, d):
    Path(f).parent.mkdir(parents=True, exist_ok=True)
    Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def slug(s, n=40):
    import unicodedata
    s = "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:n] or "historia"


# ------------------------------------------------------------------ 1. o roteiro (IA)
CENARIOS = ["cidade", "predio", "quarto", "janela", "banheiro", "corredor", "rua", "laje", "garagem", "mercado", "escuro"]
LUZES = ["dia", "tarde", "noite", "escuro", "chuva", "alerta"]
POSES = ["parado", "olhando", "carregando", "andando", "correndo", "agachado", "batendo", "apontando"]
OBJETOS = ["balde", "banheira", "vela", "celular", "porta", "caixa", "moto", "carro", "mochila", "escada", "torneira"]
MOVIMENTOS = ["zoom", "afasta", "direita", "esquerda", "sobe", "desce"]


def prompt_episodio(serie, cfg, n, resultado="", rumo=""):
    pers = "; ".join(f"{p.get('nome')} ({p.get('quem', '')})" for p in serie.get("personagens", [])) or "crie 1 ou 2, de nome simples"
    antes = serie.get("episodios", [])[-3:]
    resumo = "\n".join(f"- Ep {e['n']}: {e.get('resumo', '')} → escolha: {e.get('escolha', {}).get('pergunta', '')}" for e in antes) or "(este é o primeiro)"
    palavras = int(cfg["duracao_s"] * cfg["palavras_min"] / 60)
    abertura = (f'ABRA pelo resultado da votação: "{resultado}". Uma frase, e siga a história por esse caminho.'
                if resultado else "ABRA pelo gancho (não existe votação anterior).")
    if rumo:
        abertura += f"\n\nO QUE ACONTECE NESTE EPISÓDIO (mandado por quem faz o canal — vale mais que tudo, siga à risca): {rumo}"
    return f"""Você escreve REELS DE HISTÓRIA EM SÉRIE em português do Brasil, no formato que viralizou no Instagram
(Histórias com Kaio, Manual do Benji, Tio do Fim, Insólito): sobrevivência/suspense do dia a dia, com o público
escolhendo a continuação nos comentários.

SÉRIE: {serie.get('nome')} — {serie.get('tema')}
MUNDO/REGRAS: {serie.get('mundo')}
PERSONAGENS: {pers}
EPISÓDIOS ANTERIORES:
{resumo}

ESTE É O EPISÓDIO {n}. {abertura}

A FÓRMULA (siga à risca — foi medida nos vídeos que deram certo):
1. GANCHO em 2ª pessoa ou com o personagem, com uma ordem contra-intuitiva nos 2 primeiros segundos.
   Ex.: "Se o apocalipse começar enquanto você estiver no 14º andar, NÃO DESÇA."
2. PROMESSA COM RISCO logo depois: "você está num dos lugares mais seguros… mas só se não cometer um erro idiota."
3. PERSONAGEM de nome simples + HORA exata ("o alarme toca às 7h10").
4. 3 a 5 AÇÕES/REGRAS, cada uma com a RAZÃO TÉCNICA DE VERDADE e NÚMERO CONCRETO. É o coração do formato:
   "a bomba d'água é elétrica, então ele enche a banheira e os baldes: 180 litros"; "1 litro de água = 1 quilo na
   mochila, então leva 2 litros e um pano para pegar chuva". Nada de número inventado sem lógica.
5. UM DETALHE DOMÉSTICO BRASILEIRO que dê verdade (a gata, o mercadinho, a laje, o grupo do condomínio, o portão).
6. CLIFFHANGER curto e seco na última frase da narração.
7. ESCOLHA A/B: pergunta fechada, as duas opções plausíveis e perigosas, ligada ao cliffhanger.

TAMANHO: cerca de {palavras} palavras de narração no total ({cfg['duracao_s']} s falados).
De 12 a 16 cenas, cada uma com 1 ou 2 frases de narração (4 a 6 s).

Monte cada cena com estas peças (é um desenho feito por código, não existe foto):
  cenario: {', '.join(CENARIOS)}
  luz: {', '.join(LUZES)}
  movimento: {', '.join(MOVIMENTOS)}
  pessoas: [{{"x":0..1,"y":0.66,"alt":430,"pose":"{'|'.join(POSES)}","olhando":1 ou -1}}]   (y=0.66 é o chão; alt 400-470)
  objetos: [{{"tipo":"{'|'.join(OBJETOS)}","x":0..1,"y":0.66,"s":1.5}}]   (celular aceita "extra":"TEXTO DO ALERTA")
  gatos: [{{"x":0..1,"y":0.68,"alt":150}}]
  chuva: true/false · relogio: "03:47" · selo: "ALERTA" · contador: "58:50" + contador_sub: "ATÉ A ENERGIA CAIR"
  onomatopeia: "TRRRUM!" + ono_x/ono_y (0..1)

Responda SÓ JSON:
{{"titulo": "<até 60 letras, com o número do episódio>",
 "resumo": "<1 frase do que acontece, para o próximo episódio>",
 "narracao": "<o texto COMPLETO que o narrador fala, seguido, sem marcações>",
 "cenas": [{{"narracao": "<a frase desta cena, copiada da narração>", "cenario": "...", "luz": "...", "movimento": "...",
            "pessoas": [], "objetos": [], "relogio": "", "onomatopeia": ""}}],
 "escolha": {{"pergunta": "<a pergunta fechada>", "a": "<opção A, curta>", "b": "<opção B, curta>"}},
 "legenda_post": "<legenda do post: 2 a 4 linhas + a pergunta + 'Comenta A ou B' + 4 hashtags>"}}"""


def escreve_episodio(serie, cfg, n, resultado="", log=log, rumo=""):
    """a IA escreve o episódio (Gemini → IAs grátis → Claude da assinatura, a mesma cadeia do resto do projeto)"""
    from reels import gemini_json

    g = gemini_json([{"text": prompt_episodio(serie, cfg, n, resultado, rumo)}], temperatura=0.95)
    if not g or not g.get("cenas"):
        raise RuntimeError("nenhuma IA escreveu o episódio (sem GEMINI_API_KEY/IAs grátis/Claude?)")
    g["cenas"] = [limpa_cena(c) for c in g["cenas"]][:18]
    if not g.get("narracao"):
        g["narracao"] = " ".join(c.get("narracao", "") for c in g["cenas"])
    return g


def limpa_cena(c):
    """só deixa passar o que o palco sabe desenhar (a IA às vezes inventa um cenário ou uma pose)"""
    out = {
        "cenario": c.get("cenario") if c.get("cenario") in CENARIOS else "quarto",
        "luz": c.get("luz") if c.get("luz") in LUZES else "noite",
        "movimento": c.get("movimento") if c.get("movimento") in MOVIMENTOS else "zoom",
        "narracao": str(c.get("narracao", "")),
        "semente": abs(hash(str(c.get("narracao", "")))) % 97,
    }
    for k in ("relogio", "selo", "contador", "contador_sub", "onomatopeia"):
        if c.get(k):
            out[k] = str(c[k])[:28]
    for k in ("ono_x", "ono_y"):
        if isinstance(c.get(k), (int, float)):
            out[k] = max(0.02, min(0.95, float(c[k])))
    if c.get("chuva"):
        out["chuva"] = True
    out["pessoas"] = [{"x": max(0.08, min(0.92, float(p.get("x", 0.5)))), "y": float(p.get("y", 0.66)),
                       "alt": max(240, min(520, float(p.get("alt", 430)))),
                       "pose": p.get("pose") if p.get("pose") in POSES else "parado",
                       "olhando": -1 if str(p.get("olhando")) in ("-1", "-1.0") else 1,
                       "cor": p.get("cor") or "#3f6f7a"}
                      for p in (c.get("pessoas") or [])[:3] if isinstance(p, dict)]
    out["objetos"] = [{"tipo": o.get("tipo"), "x": max(0.05, min(0.95, float(o.get("x", 0.5)))),
                       "y": float(o.get("y", 0.66)), "s": max(0.5, min(3.0, float(o.get("s", 1.4)))),
                       **({"extra": str(o.get("extra"))[:18]} if o.get("extra") else {})}
                      for o in (c.get("objetos") or [])[:4] if isinstance(o, dict) and o.get("tipo") in OBJETOS]
    out["gatos"] = [{"x": max(0.05, min(0.95, float(g.get("x", 0.7)))), "y": float(g.get("y", 0.68)),
                     "alt": max(70, min(220, float(g.get("alt", 150))))}
                    for g in (c.get("gatos") or [])[:2] if isinstance(g, dict)]
    return out


# ------------------------------------------------------------------ 2. voz + legendas
def narra(texto, saida, cfg, log=log):
    """a narração na voz do VoiceStudio (ou Fish/Chatterbox, a mesma cadeia do canal de notícias)"""
    import voz as V

    falado = V.pronuncia(texto)
    url = cfg.get("voicestudio") or V.voicestudio_url()
    if V.voicestudio_ligado(url):
        log(f"voz: VoiceStudio ({url})")
        V.voicestudio_fala(falado, saida, cfg.get("voz_voicestudio") or "default", url,
                           velocidade=float(cfg.get("velocidade_voz", 1.0)))
    else:
        chave = os.environ.get("FISH_API_KEY")
        if not chave:
            raise RuntimeError("sem voz: abra o VoiceStudio no PC (ou ponha a FISH_API_KEY)")
        log("voz: Fish Audio (o VoiceStudio está fechado)")
        V.fish_fala(falado, saida, os.environ.get("FISH_VOZ", ""), chave)
    try:
        c = V.sem_pausas(saida)  # tira os silêncios do meio: é o que entrega que é IA
        if c > 0.2:
            log(f"voz: tirei {c:.1f}s de silêncio do meio")
    except Exception as e:
        log(f"voz: não tirei as pausas ({str(e)[:90]})")
    return saida


def dur_wav(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def palavras(wav, log=log):
    """as palavras com tempo (faster-whisper) — as legendas saem do que foi REALMENTE falado"""
    from transcrever import transcrever
    try:
        return transcrever(str(wav), "small", "cuda")
    except Exception:
        return transcrever(str(wav), "small", "cpu")


def encaixa_cenas(rot, words):
    """cada cena termina onde a frase dela termina na narração (assim a imagem acompanha a fala)"""
    if not words:
        return
    import unicodedata

    def norm(t):
        t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9 ]", " ", t).split()

    faladas = [norm(w["w"])[0] if norm(w["w"]) else "" for w in words]
    pos = 0
    for c in rot["cenas"]:
        alvo = norm(c.get("narracao", ""))
        if not alvo:
            continue
        fim = pos
        for p in alvo:  # anda na transcrição enquanto as palavras baterem
            achou = next((k for k in range(fim, min(len(faladas), fim + 14)) if faladas[k] == p), None)
            if achou is not None:
                fim = achou + 1
        if fim > pos:
            c["ate"] = round(words[min(fim, len(words)) - 1]["e"] + 0.12, 2)
            pos = fim


# ------------------------------------------------------------------ 3. votos do episódio anterior
def apura(serie, pasta_base, cfg, log=log):
    """lê os comentários do post anterior e conta A x B (Instagram pela API; o painel já tem o login)"""
    eps = serie.get("episodios", [])
    if not eps or not eps[-1].get("media_id") or eps[-1].get("resultado"):
        return ""
    ep = eps[-1]
    try:
        sys.path.insert(0, str(TOOLS / "postar"))
        import postar as P

        base = P.pasta_padrao()
        cfg_p = P.le_json(base / "config.json", {}) or {}
        conta = (serie.get("conta") or cfg["contas"][0]).split(":")[-1]
        tk = P.ig_token(cfg_p, base, conta)
        if not tk:
            return ""
        import urllib.parse
        d = P.http("GET", f"{P.ig_host(tk)}/{cfg_p['instagram']['versao']}/{ep['media_id']}/comments?"
                   + urllib.parse.urlencode({"fields": "text", "limit": "300", "access_token": tk["token"]}))
        textos = [str(x.get("text", "")).lower() for x in (d.get("data") or [])]
    except Exception as e:
        log(f"votos: não consegui ler os comentários ({str(e)[:120]})")
        return ""
    if not textos:
        return ""
    esc = ep.get("escolha", {})
    pa = pb = 0
    for t in textos:
        tem_a = bool(re.search(r"\ba\b|opcao a|opção a", t)) or (esc.get("a", "x").lower()[:12] in t)
        tem_b = bool(re.search(r"\bb\b|opcao b|opção b", t)) or (esc.get("b", "x").lower()[:12] in t)
        if tem_a and not tem_b:
            pa += 1
        elif tem_b and not tem_a:
            pb += 1
    if pa + pb < 3:
        log(f"votos: só {pa + pb} comentário(s) decidiram — sigo pela opção A")
        pa = max(pa, 1)
    venceu, perc = ("a", pa) if pa >= pb else ("b", pb)
    pct = round(100 * perc / max(1, pa + pb))
    txt = f"{pct}% escolheram: {esc.get(venceu, venceu.upper())}"
    ep["resultado"] = {"a": pa, "b": pb, "venceu": venceu, "texto": txt}
    log(f"votos: A={pa} B={pb} → {txt}")
    return txt


# ------------------------------------------------------------------ 4. um episódio inteiro
def faz_episodio(serie_f, cfg, log=log, venceu="", rumo=""):
    """venceu = "a"/"b" escolhido POR VOCÊ (em vez de contar os comentários); rumo = o que acontece, escrito por você"""
    serie = {**SERIE_PADRAO, **(le_json(serie_f, {}) or {})}
    base = Path(serie_f).parent
    n = len(serie.get("episodios", [])) + 1
    log(f"\n=== {serie.get('nome')} — episódio {n} ===")
    eps = serie.get("episodios", [])
    # o que VOCÊ mandou (no painel ou na linha de comando) vale mais que a apuração automática
    venceu = (venceu or serie.pop("proxima_escolha", "") or "").lower().strip()
    rumo = rumo or serie.pop("proximo_rumo", "") or ""
    if venceu in ("a", "b") and eps:
        esc = eps[-1].get("escolha", {})
        resultado = f"a maioria escolheu: {esc.get(venceu, venceu.upper())}"
        eps[-1]["resultado"] = {"venceu": venceu, "texto": resultado, "por": "você"}
        log(f"continuação escolhida por você: {venceu.upper()} — {esc.get(venceu, '')}")
    else:
        resultado = apura(serie, base, cfg, log)
    if rumo:
        log(f"rumo que você mandou: {rumo[:160]}")
    grava_json(serie_f, serie)

    job = base / f"ep_{n:02d}"
    job.mkdir(parents=True, exist_ok=True)
    rot_f = job / "roteiro.json"
    rot = le_json(rot_f)
    if not rot:
        log("1/4 escrevendo o episódio...")
        rot = escreve_episodio(serie, cfg, n, resultado, log, rumo)
        rot["marca"] = cfg.get("marca") or f"@{(serie.get('conta') or '').split(':')[-1]}"
        grava_json(rot_f, rot)
    log(f"    \"{rot.get('titulo', '')}\" — {len(rot['cenas'])} cenas")

    wav = job / "voz.wav"
    if not wav.exists():
        log("2/4 narrando...")
        narra(rot["narracao"], wav, cfg, log)
    wf = job / "words.json"
    if not wf.exists():
        log("3/4 alinhando as legendas...")
        grava_json(wf, palavras(wav, log))
    words = le_json(wf, [])
    encaixa_cenas(rot, words)
    grava_json(rot_f, rot)

    saida = job / "episodio.mp4"
    if not saida.exists():
        log("4/4 desenhando e montando...")
        dur = (words[-1]["e"] + 0.7) if words else (dur_wav(wav) or cfg["duracao_s"])
        r = subprocess.run(["node", str(AQUI / "render.js"), str(rot_f), "--voz", str(wav), "--words", str(wf),
                            "--out", str(saida), "--work", str(job / "tmp"), "--fps", str(cfg.get("fps", 30)),
                            "--duracao", f"{dur:.2f}", "--marca", rot.get("marca", "")], cwd=str(PONTE))
        if r.returncode != 0 or not saida.exists():
            raise RuntimeError("o render do episódio falhou (veja as mensagens acima)")

    esc = rot.get("escolha", {})
    legenda = rot.get("legenda_post") or f"{rot.get('titulo', '')}\n\n{esc.get('pergunta', '')}\nA: {esc.get('a', '')}\nB: {esc.get('b', '')}\n\nComenta A ou B 👇"
    (job / "post.txt").write_text(legenda, encoding="utf-8")
    serie.setdefault("episodios", []).append({"n": n, "titulo": rot.get("titulo", ""), "resumo": rot.get("resumo", ""),
                                              "escolha": esc, "arquivo": str(saida), "feito": dt.datetime.now().isoformat(timespec="minutes")})
    grava_json(serie_f, serie)
    if cfg.get("auto_postar"):
        enfileira(saida, legenda, serie, cfg, log)
    log(f"pronto: {saida}")
    return saida


def enfileira(video, legenda, serie, cfg, log=log):
    """põe o episódio na fila de postagem do painel (a mesma do resto)"""
    try:
        sys.path.insert(0, str(TOOLS / "postar"))
        import postar as P

        base = P.pasta_padrao()
        destinos = [serie.get("conta")] if serie.get("conta") else list(cfg.get("contas", []))
        nome = f"{dt.date.today():%Y-%m-%d} {slug(serie.get('nome'), 20)} ep{len(serie.get('episodios', [])) + 1:02d}"
        P.enfileira(base, Path(video), [d for d in destinos if d], legenda, nome)
        log(f"na fila: {', '.join(d for d in destinos if d)}")
    except Exception as e:
        log(f"não entrou na fila ({str(e)[:140]}) — o arquivo está pronto, dá para subir pelo painel")


# ------------------------------------------------------------------ 5. séries
def nova_serie(pasta, ideia, conta, cfg, log=log):
    """a IA monta o mundo e os personagens da série a partir de uma ideia sua"""
    from reels import gemini_json

    g = gemini_json([{"text": f"""Monte uma SÉRIE de reels de história (formato "você decide", estilo Histórias com Kaio /
Manual do Benji) a partir desta ideia: "{ideia}".
O mundo precisa de REGRAS CLARAS e verossímeis (é delas que saem as dicas técnicas de cada episódio) e de personagens
simples e brasileiros. Pode ser sobrevivência, mistério, esporte, trabalho — o que a ideia pedir.
Responda SÓ JSON: {{"nome": "<nome curto da série>", "tema": "<1 frase>",
"mundo": "<3 a 5 frases: a situação, as regras duras do mundo e o que é perigoso>",
"personagens": [{{"nome": "<nome simples>", "quem": "<1 linha: idade, o que faz, o que tem de especial>"}}]}}"""}],
                    temperatura=0.95)
    if not g or not g.get("nome"):
        raise RuntimeError("a IA não montou a série")
    s = {**SERIE_PADRAO, **g, "conta": conta or (cfg.get("contas") or [""])[0], "ligada": True, "episodios": []}
    f = Path(pasta) / "series" / slug(g["nome"]) / "serie.json"
    grava_json(f, s)
    log(f"série nova: {g['nome']} → {f}")
    for p in s.get("personagens", []):
        log(f"   {p.get('nome')}: {p.get('quem', '')}")
    return f


def series(pasta):
    return sorted((Path(pasta) / "series").glob("*/serie.json"))


def prepara(pasta):
    pasta = Path(pasta)
    (pasta / "series").mkdir(parents=True, exist_ok=True)
    f = pasta / "config.json"
    if not f.exists():
        grava_json(f, CONFIG_PADRAO)
    return {**CONFIG_PADRAO, **(le_json(f, {}) or {})}


def main():
    ap = argparse.ArgumentParser(description="reels de história em série, com o público escolhendo a continuação")
    ap.add_argument("--pasta", default=str(pasta_padrao()))
    ap.add_argument("--serie", default="", help="só esta série (o nome da pasta)")
    ap.add_argument("--novo", default="", help="cria uma série a partir de uma ideia")
    ap.add_argument("--conta", default="", help="instagram:conta para a série nova")
    ap.add_argument("--apurar", action="store_true", help="só conta os votos dos episódios já postados")
    ap.add_argument("--quantos", type=int, default=0, help="quantos episódios fazer (padrão: o por_dia do config)")
    ap.add_argument("--continuar", choices=["a", "b"], default="", help="a continuação é esta (em vez de contar os comentários)")
    ap.add_argument("--rumo", default="", help='o que acontece neste episódio, escrito por você (ex.: "entra um drone da prefeitura")')
    a = ap.parse_args()
    pasta = Path(a.pasta)
    cfg = prepara(pasta)
    if a.novo:
        nova_serie(pasta, a.novo, a.conta, cfg)
        return
    fs = [f for f in series(pasta) if not a.serie or slug(a.serie) in f.parent.name]
    if not fs:
        log(f"nenhuma série em {pasta / 'series'}. Crie uma:\n"
            f'  python tools\\historias\\historias.py --novo "apocalipse zumbi em BH" --conta instagram:detto.historias')
        return
    feitos = 0
    limite = a.quantos or int(cfg.get("por_dia", 1))
    for f in fs:
        s = le_json(f, {}) or {}
        if not s.get("ligada", True):
            continue
        if a.apurar:
            apura(s, f.parent, cfg)
            grava_json(f, s)
            continue
        if feitos >= limite:
            break
        try:
            faz_episodio(f, cfg, venceu=a.continuar, rumo=a.rumo)
            feitos += 1
        except Exception as e:
            log(f"{f.parent.name}: {str(e)[:300]}")


if __name__ == "__main__":
    main()
