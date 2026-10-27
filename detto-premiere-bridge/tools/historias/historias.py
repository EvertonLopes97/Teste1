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
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "reels"))
sys.path.insert(0, str(TOOLS / "canal"))

CONFIG_PADRAO = {
    "contas": ["instagram:detto.historias"],  # para onde o episódio vai (mesma fila do painel)
    "por_dia": 1,
    "duracao_s": 80,              # os virais ficam entre 65 e 90 s
    "palavras_min": 170,          # ritmo da narração medido nos virais
    "voz_voicestudio": "",        # perfil de voz no VoiceStudio; vazio = acha a SUA voz pelo nome (everton/detto)
    "instrucao_voz": "",          # como a voz deve falar; vazio = o padrão (pt-BR claro, sem sotaque de Portugal)
    "voicestudio": "",
    "velocidade_voz": 1.0,
    "marca": "",                  # @ que aparece no rodapé do vídeo
    "fps": 30,
    "auto_postar": True,
}

SERIE_PADRAO = {
    "nome": "",
    "tema": "",
    "contexto": "",   # o que VOCÊ escreve sobre a história: vale para todos os episódios
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
CENARIOS = ["cidade", "predio", "quarto", "janela", "banheiro", "corredor", "rua", "laje", "garagem", "escadaria",
            "mercado", "escuro"]
LUZES = ["dia", "tarde", "noite", "escuro", "chuva", "alerta"]
POSES = ["parado", "olhando", "carregando", "segurando", "andando", "correndo", "agachado", "batendo", "apontando",
         "assustado", "pensando"]
OBJETOS = ["balde", "banheira", "vela", "celular", "porta", "caixa", "moto", "carro", "mochila", "escada", "torneira",
           "relogio", "garrafa", "interruptor", "elevador", "gerador", "lampada"]
MOVIMENTOS = ["zoom", "afasta", "direita", "esquerda", "sobe", "desce"]
CARAS = ["", "serio", "bravo", "assustado", "feliz"]
PLANOS = ["geral", "medio", "close"]
ROUPAS = ["moletom", "camisa", "jaleco", "uniforme", "terno", "pijama", "regata", "capuz"]
# efeitos sonoros (da pasta de sons dele, tools/biblioteca_sons.py). Sem a pasta catalogada, o som é SINTETIZADO
# pelo próprio FFmpeg (`som_sintetico`) — o episódio nunca sai mudo.
SFX = {"batida": "soco", "porta": "porta", "passos": "passos", "relogio": "relogio", "susto": "boom",
       "trovao": "trovao", "whoosh": "whoosh", "tensao": "riser", "agua": "agua", "click": "click",
       "alerta": "ding", "glitch": "glitch", "mensagem": "ding", "sirene": "sirene", "vidro": "vidro",
       "motor": "motor"}
# quando não há arquivo da categoria, o sintetizado mais parecido
PARECIDO = {"porta": "soco", "passos": "tick", "relogio": "tick", "trovao": "boom", "agua": "pop",
            "sirene": "riser", "vidro": "glitch", "motor": "boom"}
# como sintetizar cada categoria quando não há arquivo na pasta dele (filtro lavfi + duração)
SINTETICO = {
    "ding": ("sine=frequency=880:duration=0.45,volume=0.9", 0.45),
    "tick": ("sine=frequency=1600:duration=0.07", 0.07),
    "boom": ("sine=frequency=62:duration=0.9", 0.9),
    "soco": ("sine=frequency=150:duration=0.3", 0.3),
    "pop": ("sine=frequency=520:duration=0.14", 0.14),
    "click": ("anoisesrc=color=white:duration=0.05:amplitude=0.5", 0.05),
    "whoosh": ("anoisesrc=color=brown:duration=0.6:amplitude=0.6", 0.6),
    "riser": ("sine=frequency=180:duration=1.4", 1.4),
    "glitch": ("anoisesrc=color=violet:duration=0.25:amplitude=0.5", 0.25),
}


def prompt_episodio(serie, cfg, n, resultado="", rumo=""):
    pers = "; ".join(f"{p.get('nome')} ({p.get('quem', '')})" for p in serie.get("personagens", [])) or "crie 1 ou 2, de nome simples"
    antes = serie.get("episodios", [])[-3:]
    resumo = "\n".join(f"- Ep {e['n']}: {e.get('resumo', '')} → escolha: {e.get('escolha', {}).get('pergunta', '')}" for e in antes) or "(este é o primeiro)"
    palavras = int(cfg["duracao_s"] * cfg["palavras_min"] / 60)
    abertura = (f'ABRA pelo resultado da votação: "{resultado}". Uma frase, e siga a história por esse caminho.'
                if resultado else "ABRA pelo gancho (não existe votação anterior).")
    if rumo:
        abertura += f"\n\nO QUE ACONTECE NESTE EPISÓDIO (mandado por quem faz o canal — vale mais que tudo, siga à risca): {rumo}"
    ctx = (serie.get("contexto") or "").strip()
    if ctx:
        abertura += ("\n\nCONTEXTO DA SÉRIE (escrito por quem faz o canal; vale para TODOS os episódios, respeite "
                     f"cada detalhe — nomes, lugares, regras, tom):\n{ctx}")
    base = (serie.get("_roteiro_base") or "").strip()
    if base:
        abertura += ("\n\nUSE ESTE ROTEIRO COMO BASE (foi ajustado à mão): siga a estrutura, o tom e as cenas dele, "
                     f"mudando só o que o episódio novo pede.\n{base[:6000]}")
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

COMO ESCREVER A NARRAÇÃO (a voz LÊ exatamente o que você escrever, então o texto já sai pronto para falar):
  - números SEMPRE por extenso: "cento e oitenta litros", "doze horas", "o décimo segundo andar", "oito quilômetros";
  - horas por extenso no texto falado ("sete e dez da manhã"), mesmo que o campo "relogio" da cena mostre "07:10";
  - nada de siglas, símbolos (%, °, R$, x), abreviações, parênteses, aspas, travessões ou reticências;
  - frases curtas, de no máximo 18 palavras, terminadas em ponto — é o que mantém o ritmo de narração.

TAMANHO: cerca de {palavras} palavras de narração no total ({cfg['duracao_s']} s falados).
De 14 a 18 cenas, cada uma com 1 ou 2 frases de narração (4 a 6 s).

VOCÊ TAMBÉM DIRIGE A EDIÇÃO. Cada cena é um desenho feito por código (não existe foto nem filmagem), e você escolhe
o enquadramento, o movimento, a roupa do personagem e o efeito sonoro. Três regras de direção, que são o que separa
um vídeo chato de um viral:
  A) UMA EM CADA TRÊS CENAS NÃO TEM PESSOA. É a regra mais importante: o personagem em todas as cenas deixa o vídeo
     igual do começo ao fim. Essas cenas de apoio são "plano":"close" com "pessoas":[] e UM objeto grande no meio
     ("s" entre 1.8 e 2.4) com o "foco" nele — o celular na hora da mensagem, a torneira, o relógio, o balde. E nunca
     mais de 2 cenas seguidas no mesmo "plano": alterne geral, médio e close.
  B) PONHA O PERSONAGEM FAZENDO A COISA. Se a narração diz que ele enche o balde, a cena tem o balde "enchendo" e a
     pessoa com pose "agachado"/"carregando". Cena com a pessoa parada no meio do nada é cena perdida.
  C) EFEITO SONORO NA PALAVRA CERTA. Em pelo menos 6 cenas ponha "sfx" e "sfx_palavra": a palavra EXATA da narração
     daquela cena em que o som deve estourar (ex.: sfx "mensagem" com sfx_palavra "celular"). Sem a palavra o som
     entra no começo da cena, que é pior.

ONDE A PESSOA ESTÁ: quando a história se passa num andar, use cenario "predio" com "andar": 12 e "andares": 15 —
o desenho marca a janela daquele andar com seta e o rótulo "12º ANDAR". Use isso toda vez que o andar for citado.

Peças de cada cena:
  cenario: {', '.join(CENARIOS)}
  luz: {', '.join(LUZES)}
  movimento: {', '.join(MOVIMENTOS)} · plano: {', '.join(PLANOS)} · foco: {{"x":0..1,"y":0..1}} (para onde a câmera fecha)
  andar / andares: só no cenario "predio"
  pessoas: [{{"quem":"<NOME do personagem>","x":0..1,"y":0.70,"alt":640,"pose":"{'|'.join(POSES)}",
             "cara":"serio|bravo|assustado|feliz","falando":true,"olhando":1 ou -1,"x2":0..1 (para onde ele anda)}}]
     **"quem" é obrigatório sempre que alguém aparece** — é por ele que o desenho sabe a cara, o cabelo e a roupa
     daquele personagem, iguais em todos os episódios. Use exatamente os nomes dos PERSONAGENS listados acima; se
     entrar alguém novo (o porteiro, a vizinha), dê um nome e use o mesmo nome em todas as cenas dele.
     NÃO escolha roupa nem cor: isso é do elenco da série.
  objetos: [{{"tipo":"{'|'.join(OBJETOS)}","x":0..1,"y":0.66,"s":1.5}}]
     celular aceita "extra":"TEXTO DO ALERTA" e "alerta":true (pisca) · balde/banheira aceitam "enchendo":true ·
     torneira aceita "seca":true/"jorrando":true · porta aceita "batendo":true/"aberta":true
  gatos: [{{"x":0..1,"y":0.68,"alt":150}}] · silhuetas: [{{"x":0..1,"y":0.76,"alt":420,"x2":0..1}}] (a multidão)
  chuva/fumaca/tremor/escurece/clarao: true/false
  relogio: "03:47" · selo: "ALERTA" · contador: "58:50" + contador_sub: "ATÉ A ENERGIA CAIR"
  onomatopeia: "TRRRUM!" + ono_x/ono_y (0..1)
  sfx: {' | '.join(sorted(SFX))} + sfx_palavra: "<palavra da narração desta cena>"

Responda SÓ JSON:
{{"titulo": "<até 60 letras, SEM o número do episódio>",
 "resumo": "<1 frase do que acontece, para o próximo episódio>",
 "narracao": "<o texto COMPLETO que o narrador fala, seguido, sem marcações>",
 "figurino": {{"<nome do personagem>": {{"roupa": "...", "cor": "#...", "mochila": true}}}},
 "cenas": [{{"narracao": "<a frase desta cena, copiada da narração>", "cenario": "...", "luz": "...", "movimento": "...",
            "plano": "geral|medio|close", "foco": {{"x":0.5,"y":0.5}}, "pessoas": [], "objetos": [],
            "relogio": "", "onomatopeia": "", "sfx": "", "sfx_palavra": ""}}],
 "escolha": {{"pergunta": "<a pergunta fechada>", "a": "<opção A, curta, até 6 palavras>", "b": "<opção B, curta>"}},
 "capa": {{"titulo": "<2 a 4 palavras em caixa alta para a capa do episódio>"}},
 "legenda_post": "<legenda do post: 2 a 4 linhas + a pergunta + 'Comenta A ou B' + 4 hashtags>"}}"""


def escreve_episodio(serie, cfg, n, resultado="", log=log, rumo=""):
    """a IA escreve o episódio (Gemini → IAs grátis → Claude da assinatura, a mesma cadeia do resto do projeto)"""
    from reels import gemini_json

    g = gemini_json([{"text": prompt_episodio(serie, cfg, n, resultado, rumo)}], temperatura=0.95)
    if not g or not g.get("cenas"):
        raise RuntimeError("nenhuma IA escreveu o episódio (sem GEMINI_API_KEY/IAs grátis/Claude?)")
    g["cenas"] = [limpa_cena(c) for c in g["cenas"]][:20]
    if not g.get("narracao"):
        g["narracao"] = " ".join(c.get("narracao", "") for c in g["cenas"])
    uma_cena_por_frase(g)
    garante_apoio(g)
    garante_sfx(g)
    fecha_com_escolha(g)
    return g


# ------------------------------------------------------------------ o ELENCO (quem é quem na tela)
# O PRINCIPAL é o bonequinho do modelo: cabeça redonda, cabelo de tigela com a faixa clara, moletom verde-acinzentado,
# mochila nas costas e calça azul. Ele nunca muda — é a cara da série.
LOOK_PRINCIPAL = {"corte": "tigela", "cabelo": "#5a3b26", "pele": "#f0d5a8", "roupa": "moletom",
                  "cor": "#4a6b6b", "calca": "#3a5a86", "mochila": True, "barba": "", "oculos": False}
# Os SECUNDÁRIOS têm que ser DIFERENTES do principal e entre si — corte, barba, pele, roupa e cor mudam juntos.
LOOKS_SECUNDARIOS = [
    {"corte": "grisalho", "cabelo": "#6b6b6b", "pele": "#d9b183", "roupa": "uniforme", "cor": "#3f5f86", "calca": "#2c3a4a", "barba": "bigode"},
    {"corte": "rabo", "cabelo": "#2f2a26", "pele": "#c98f5e", "roupa": "camisa", "cor": "#9c4a52", "calca": "#39404d"},
    {"corte": "careca", "cabelo": "#2f2a26", "pele": "#8d5a37", "roupa": "uniforme", "cor": "#4c7a52", "calca": "#2f3a44", "barba": "cheia"},
    {"corte": "cacheado", "cabelo": "#241c16", "pele": "#a8693f", "roupa": "regata", "cor": "#d8a43a", "calca": "#48566b"},
    {"corte": "curto", "cabelo": "#8a6a3a", "pele": "#f0d5a8", "roupa": "jaleco", "cor": "#eef2f3", "calca": "#5a6472", "oculos": True},
    {"corte": "longo", "cabelo": "#45302a", "pele": "#e8c79b", "roupa": "moletom", "cor": "#7a5c86", "calca": "#2f3a44"},
    {"corte": "bone", "cabelo": "#241c16", "pele": "#b87a4a", "roupa": "capuz", "cor": "#c0552f", "calca": "#39404d", "cor_bone": "#1f2630"},
    {"corte": "curto", "cabelo": "#3b2d23", "pele": "#d9b183", "roupa": "terno", "cor": "#2f3540", "calca": "#2a2f38", "barba": "cavanhaque"},
]
TRACOS = ("corte", "cabelo", "pele", "roupa", "cor", "calca", "mochila", "barba", "oculos", "bone", "cor_bone")


def elenco(serie, rot):
    """guarda a APARÊNCIA de cada personagem na série, para ele ser o mesmo em todos os episódios.
    O primeiro personagem (o protagonista) fica com o look do modelo; os outros recebem looks diferentes, sem repetir."""
    el = serie.setdefault("elenco", {})
    pers = [str(p.get("nome", "")).strip() for p in serie.get("personagens", []) if p.get("nome")]
    principal = (serie.get("principal") or (pers[0] if pers else "")).strip()
    # quem aparece nas cenas, na ordem em que entra
    nomes = []
    for c in rot.get("cenas", []):
        for p in c.get("pessoas") or []:
            n = str(p.get("quem", "")).strip()
            if n and n not in nomes:
                nomes.append(n)
    if not principal:
        principal = nomes[0] if nomes else "principal"
    serie["principal"] = principal
    for n in [principal] + [x for x in pers + nomes if x != principal]:
        if n in el:
            continue
        if n == principal:
            el[n] = dict(LOOK_PRINCIPAL)
        else:  # o primeiro look ainda não usado — nunca o do principal
            usados = {(v.get("corte"), v.get("cor")) for v in el.values()}
            livre = next((lk for lk in LOOKS_SECUNDARIOS if (lk["corte"], lk["cor"]) not in usados), None)
            el[n] = dict(livre or LOOKS_SECUNDARIOS[len(el) % len(LOOKS_SECUNDARIOS)])
    return el


def aplica_elenco(serie, rot):
    """põe em cada pessoa da cena os traços do personagem dela (o palco só sabe desenhar, quem sabe quem é quem é aqui)"""
    el = elenco(serie, rot)
    principal = serie.get("principal") or next(iter(el), "")
    for c in rot.get("cenas", []):
        for p in c.get("pessoas") or []:
            if p.get("livre"):  # roteiro mexido à mão: "livre": true manda no visual daquela pessoa
                continue
            nome = str(p.get("quem", "")).strip()
            if not nome:  # cena com uma pessoa só e sem nome = o protagonista
                nome = principal
                p["quem"] = nome
            look = el.get(nome) or el.get(principal) or LOOK_PRINCIPAL
            for k in TRACOS:
                if k in look:
                    p[k] = look[k]
            p["bone"] = look.get("corte") == "bone"
    return rot


# palavra da narração → o objeto que a cena de apoio mostra em close
APOIO = [(("celular", "mensagem", "telefone", "whatsapp", "zap", "aviso", "alerta", "liga"), "celular"),
         (("interruptor", "quadro de luz", "disjuntor", "chave geral"), "interruptor"),
         (("elevador",), "elevador"),
         (("gerador", "motor do predio", "subsolo"), "gerador"),
         (("lâmpada", "lampada", "luz do teto", "luminária", "luminaria"), "lampada"),
         (("porta", "tranca", "fechadura", "corrente"), "porta"),
         (("relógio", "relogio", "hora", "minuto", "segundo", "tempo", "faltam"), "relogio"),
         (("torneira", "água", "agua", "bomba"), "torneira"),
         (("balde", "litro", "litros"), "balde"),
         (("banheira", "banho"), "banheira"),
         (("vela", "luz", "escuro", "lanterna", "lâmpada", "lampada"), "vela"),
         (("garrafa", "térmica", "termica", "bebe", "sede"), "garrafa"),
         (("mochila", "bolsa", "peso", "quilo"), "mochila"),
         (("carro", "rua", "motor"), "carro"),
         (("moto", "entregador"), "moto"),
         (("escada", "degrau", "andar", "subir", "descer"), "escada"),
         (("caixa", "comida", "mercado", "mantimento"), "caixa")]


# palavra da narração → efeito sonoro (e é NELA que o som estoura)
GATILHOS = [
    (("mensagem", "celular", "telefone", "vibra", "aviso", "notificacao", "zap", "whatsapp", "toca"), "mensagem"),
    (("alarme", "sirene", "ambulancia", "policia", "bombeiro"), "sirene"),
    (("porta", "tranca", "fechadura", "corrente", "trinco", "bateu", "batendo"), "porta"),
    (("tiro", "disparo", "estrondo", "explosao", "explode", "grito", "gritou", "susto", "barulho", "baque", "estouro"), "susto"),
    (("trovao", "raio", "tempestade", "relampago"), "trovao"),
    (("passos", "correu", "corre", "correndo", "subiu", "desceu", "escada", "degraus", "pisou"), "passos"),
    (("relogio", "hora", "horas", "minuto", "minutos", "segundos", "contagem", "tempo"), "relogio"),
    (("agua", "torneira", "enche", "encheu", "balde", "banheira", "chuveiro", "litros", "pingando"), "agua"),
    (("luz", "apagou", "apaga", "acendeu", "interruptor", "lampada", "disjuntor", "energia"), "click"),
    (("motor", "carro", "moto", "ronco", "acelera", "acelerou", "freou", "pneu"), "motor"),
    (("vidro", "quebrou", "quebra", "estilhacou", "janela", "estilhaco"), "vidro"),
    (("tela", "sinal", "internet", "desligou", "sumiu", "apagão", "apagao"), "glitch"),
]


def garante_sfx(rot, a_cada=2):
    """O EPISÓDIO NÃO SAI MUDO. A IA esquece de marcar `sfx`, então aqui toda cena sem efeito ganha um, escolhido
    pela PALAVRA da narração (e é nessa palavra que ele estoura). Cena de tensão/tremor/escuro leva o riser."""
    import unicodedata

    def sem_acento(t):
        return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")

    desde = 99
    for c in rot.get("cenas", []):
        if c.get("sfx") in SFX:
            desde = 0
            continue
        desde += 1
        txt = sem_acento(c.get("narracao", ""))
        achou = None
        for palavras, efeito in GATILHOS:
            for p in palavras:
                if re.search(rf"\b{re.escape(p)}\w*", txt):
                    achou = (efeito, p)
                    break
            if achou:
                break
        if not achou and (c.get("tremor") or c.get("clarao")):
            achou = ("susto", "")
        if not achou and (c.get("escurece") or c.get("escolha")):
            achou = ("tensao", "")
        if not achou and desde >= a_cada:   # faz tempo que não tem som: entra um whoosh na virada da cena
            achou = ("whoosh", "")
        if not achou:
            continue
        c["sfx"] = achou[0]
        if achou[1]:
            c["sfx_palavra"] = achou[1]
        desde = 0
    return rot


def uma_cena_por_frase(rot, maximo=26):
    """UMA CENA POR FRASE. A IA escreve 2 ou 3 frases numa cena só e a imagem fica parada enquanto a narração anda
    (o boneco mexendo as perninhas no mesmo lugar). Aqui a cena é partida: cada frase ganha a sua, com plano e
    movimento diferentes — e a segunda vira o CLOSE no que está sendo falado."""
    novas = []
    planos = ["geral", "medio", "close"]
    movs = ["zoom", "direita", "afasta", "esquerda", "sobe", "desce"]
    for c in rot.get("cenas", []):
        txt = str(c.get("narracao", "")).strip()
        frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", txt) if f.strip()]
        # só parte o que é longo de verdade: duas frases curtas cabem numa cena de 4 s
        if c.get("escolha") or len(frases) < 2 or len(txt.split()) < 15 or len(novas) >= maximo:
            novas.append(c)
            continue
        base_plano = planos.index(c.get("plano", "geral")) if c.get("plano") in planos else 0
        for i, f in enumerate(frases):
            n = {**{k: v for k, v in c.items() if k not in ("ate", "_ini")}, "narracao": f,
                 "semente": (int(c.get("semente", 3)) + i * 17) % 97,
                 "plano": planos[(base_plano + i) % 3],
                 "movimento": movs[(movs.index(c.get("movimento", "zoom")) + i * 2) % len(movs)] if c.get("movimento") in movs else movs[i % len(movs)]}
            # a frase seguinte fecha no OBJETO — mas só quando ela fala do objeto, não do personagem
            sobre_pessoa = re.search(r"\b(ele|ela|henrique|lucas|marcos)\b", f.lower()) is not None
            if i and n["plano"] == "close" and not sobre_pessoa:
                obj = (n.get("objetos") or [{}])[0]
                if obj.get("tipo"):
                    n["pessoas"] = []
                    n["objetos"] = [{**obj, "x": 0.5, "s": max(2.0, float(obj.get("s", 1.4)) * 1.5)}]
                    n["foco"] = {"x": 0.5, "y": max(0.2, float(obj.get("y", 0.66)) - 0.12)}
            if i:   # a continuação não repete relógio/selo/onomatopeia da primeira
                for k in ("onomatopeia", "selo", "contador", "contador_sub"):
                    n.pop(k, None)
            novas.append(n)
            if len(novas) >= maximo:
                break
    rot["cenas"] = novas
    return rot


def garante_apoio(rot, minimo=0.3):
    """CENAS DE APOIO (o "B-roll" do formato): a IA tende a pôr o personagem em TODA cena, e o vídeo fica igual do
    começo ao fim. Aqui, toda vez que o boneco aparece em 3 cenas seguidas, a do meio vira um CLOSE no objeto de que
    a narração está falando — sem pessoa. É o corte que dá respiro e faz o vídeo parecer editado."""
    cenas = [c for c in rot.get("cenas", []) if not c.get("escolha")]
    if len(cenas) < 4:
        return rot
    def objeto_da(c):
        txt = str(c.get("narracao", "")).lower()
        for palavras, tipo in APOIO:
            if any(p in txt for p in palavras):
                return tipo
        return "relogio"

    def vira_apoio(c):
        obj = next((o for o in c.get("objetos") or [] if o.get("tipo") in OBJETOS), None)
        if not obj:
            obj = {"tipo": objeto_da(c), "x": 0.5, "y": 0.62, "s": 1.9}
            c["objetos"] = [obj]
        else:
            obj["x"], obj["y"] = 0.5, obj.get("y", 0.62)
            obj["s"] = max(1.6, float(obj.get("s", 1.4)))
        c["pessoas"] = []
        c["plano"] = "close"
        c["foco"] = {"x": 0.5, "y": max(0.25, float(obj.get("y", 0.62)) - 0.12)}
        c["_apoio"] = True

    seguidas = 0
    for c in cenas:
        if c.get("pessoas"):
            seguidas += 1
            if seguidas >= 3:
                vira_apoio(c)
                seguidas = 0
        else:
            seguidas = 0
    # ainda com pouca variação? o close entra nas cenas que já tinham objeto
    faltam = int(len(cenas) * minimo) - sum(1 for c in cenas if not c.get("pessoas"))
    for c in cenas[1:-1]:
        if faltam <= 0:
            break
        if c.get("pessoas") and (c.get("objetos") or []):
            vira_apoio(c)
            faltam -= 1
    return rot


def melhora_roteiro(serie, cfg, rot, log=log):
    """MAIS EDIÇÃO, mesma história: a IA recebe o roteiro pronto e devolve as cenas mais ricas (closes de apoio,
    objetos, onomatopeia, relógio, tremor, movimento variado, efeito sonoro na palavra). A NARRAÇÃO não muda —
    por isso a voz e as legendas já feitas continuam valendo e só o desenho é remontado."""
    from reels import gemini_json

    cenas = [c for c in rot.get("cenas", []) if not c.get("escolha")]
    if not cenas:
        return rot
    atual = [{k: v for k, v in c.items() if not k.startswith("_") and k not in ("semente",)} for c in cenas]
    pers = ", ".join(serie.get("elenco", {})) or "o protagonista"
    g = gemini_json([{"text": f"""Você dirige a EDIÇÃO de um reels de história ilustrado (desenho por código, estilo
Histórias com Kaio). Abaixo está o roteiro COMO ESTÁ. A narração está pronta e NÃO PODE MUDAR — mude só a edição.

O QUE MELHORAR, cena a cena:
1. CENAS DE APOIO: pelo menos 1 em cada 3 cenas sem pessoa ("pessoas": []), em "plano":"close", com UM objeto grande
   ("s" de 1.8 a 2.4) e "foco" nele — o objeto de que a narração está falando naquele momento.
2. VARIAR O PLANO e o MOVIMENTO: nunca 2 cenas seguidas iguais. Alterne geral/medio/close e zoom/afasta/direita/
   esquerda/sobe/desce.
3. EFEITO SONORO em quase toda cena: "sfx" + "sfx_palavra" (a palavra EXATA da narração daquela cena em que o som
   estoura). Efeitos: {' | '.join(sorted(SFX))}.
4. VIDA NA CENA: onomatopeia ("TRRRUM!", "PLIM!") com ono_x/ono_y, relogio ("20:14"), selo ("ALERTA"), contador,
   tremor/escurece/clarao/chuva/fumaca onde a história pede, objetos com estado (celular "alerta", balde "enchendo",
   porta "batendo", torneira "seca").
5. O CENÁRIO tem que casar com a frase: se a narração fala da rua, cenario "rua"; do prédio, "predio" com "andar"
   (o número do andar citado) e "andares"; da escada, "escadaria".
6. Pessoas: só "quem" (o nome: {pers}), "pose", "cara", "falando", "x"/"y"/"alt"/"x2". NÃO escolha roupa nem cor.

Peças que o desenho conhece:
  cenario: {', '.join(CENARIOS)} · luz: {', '.join(LUZES)} · movimento: {', '.join(MOVIMENTOS)} · plano: {', '.join(PLANOS)}
  pose: {', '.join(POSES)} · objetos: {', '.join(OBJETOS)}

ROTEIRO ATUAL ({len(cenas)} cenas, na ordem):
{json.dumps(atual, ensure_ascii=False)[:14000]}

Responda SÓ JSON com as MESMAS {len(cenas)} cenas, na mesma ordem e com a MESMA "narracao" de cada uma:
{{"cenas": [{{"narracao": "<igual>", "cenario": "...", "luz": "...", "plano": "...", "movimento": "...",
  "foco": {{"x":0.5,"y":0.5}}, "andar": 0, "andares": 0, "pessoas": [], "objetos": [], "gatos": [], "silhuetas": [],
  "relogio": "", "selo": "", "onomatopeia": "", "ono_x": 0.6, "ono_y": 0.3,
  "sfx": "", "sfx_palavra": "", "tremor": false, "escurece": false, "clarao": false, "chuva": false, "fumaca": false}}]}}"""}],
                    temperatura=0.8)
    novas = (g or {}).get("cenas") or []
    if len(novas) < max(2, len(cenas) - 2):
        log(f"mais edição: a IA devolveu {len(novas)} cena(s) de {len(cenas)} — fica o roteiro de antes")
        return rot
    saida = []
    for i, c in enumerate(cenas):
        nova = limpa_cena({**novas[i], "narracao": c.get("narracao", "")}) if i < len(novas) else c
        for k in ("ate", "_ini"):   # os tempos já alinhados com a voz continuam valendo
            if c.get(k) is not None:
                nova[k] = c[k]
        saida.append(nova)
    rot["cenas"] = saida + [c for c in rot.get("cenas", []) if c.get("escolha")]
    uma_cena_por_frase(rot)
    garante_apoio(rot)
    garante_sfx(rot)
    apoio = sum(1 for c in rot["cenas"] if not c.get("pessoas") and not c.get("escolha"))
    log(f"mais edição: {len(saida)} cenas refeitas, {apoio} de apoio (close sem pessoa), "
        f"{sum(1 for c in rot['cenas'] if c.get('sfx'))} com efeito sonoro")
    return rot


def fecha_com_escolha(rot):
    """TODO episódio termina na cartela A/B — é ela que traz o comentário (e o episódio seguinte).
    A pergunta entra na narração (o narrador lê) e vira a última cena, com os dois cards na tela."""
    e = rot.get("escolha") or {}
    a, b = str(e.get("a", "")).strip(), str(e.get("b", "")).strip()
    if not (a and b):
        return rot
    if any(c.get("escolha") for c in rot.get("cenas", [])):
        return rot
    perg = str(e.get("pergunta", "")).strip() or "O que ele faz agora?"
    fala = f"{perg} Comenta A, {a.rstrip('.')}. Ou B, {b.rstrip('.')}."
    rot["narracao"] = (rot.get("narracao", "").rstrip() + " " + fala).strip()
    ultima = (rot.get("cenas") or [{}])[-1]
    rot.setdefault("cenas", []).append({
        "cenario": ultima.get("cenario", "escuro"), "luz": ultima.get("luz", "escuro"),
        "movimento": "zoom", "plano": "geral", "narracao": fala, "semente": 7,
        "escolha": {"pergunta": perg, "a": a, "b": b},
        "pessoas": [], "objetos": [], "gatos": [], "silhuetas": [],
        "sfx": "tensao", "sfx_palavra": "comenta",
    })
    return rot


def limpa_cena(c):
    """só deixa passar o que o palco sabe desenhar (a IA às vezes inventa um cenário ou uma pose)"""
    out = {
        "cenario": c.get("cenario") if c.get("cenario") in CENARIOS else "quarto",
        "luz": c.get("luz") if c.get("luz") in LUZES else "noite",
        "movimento": c.get("movimento") if c.get("movimento") in MOVIMENTOS else "zoom",
        "plano": c.get("plano") if c.get("plano") in PLANOS else "geral",
        "narracao": str(c.get("narracao", "")),
        "semente": abs(hash(str(c.get("narracao", "")))) % 97,
    }
    f = c.get("foco")
    if isinstance(f, dict):
        out["foco"] = {"x": max(0.0, min(1.0, float(f.get("x", 0.5)))), "y": max(0.0, min(1.0, float(f.get("y", 0.5))))}
    for k in ("andar", "andares"):  # o andar da história, marcado no desenho do prédio
        try:
            if c.get(k) is not None:
                out[k] = max(1, min(24, int(c[k])))
        except (TypeError, ValueError):
            pass
    if c.get("sfx") in SFX:
        out["sfx"] = c["sfx"]
        if c.get("sfx_palavra"):
            out["sfx_palavra"] = str(c["sfx_palavra"])[:30]
    for k in ("fumaca", "chuva", "tremor", "escurece", "clarao"):
        if c.get(k):
            out[k] = True
    for k in ("relogio", "selo", "contador", "contador_sub", "onomatopeia"):
        if c.get(k):
            out[k] = str(c[k])[:28]
    for k in ("ono_x", "ono_y"):
        if isinstance(c.get(k), (int, float)):
            out[k] = max(0.02, min(0.95, float(c[k])))
    if c.get("chuva"):
        out["chuva"] = True
    out["pessoas"] = [{"x": max(0.06, min(0.94, float(p.get("x", 0.5)))), "y": float(p.get("y", 0.70)),
                       **({"x2": max(0.06, min(0.94, float(p["x2"])))} if p.get("x2") is not None else {}),
                       "alt": max(380, min(760, float(p.get("alt", 640)))),
                       "pose": p.get("pose") if p.get("pose") in POSES else "parado",
                       "cara": p.get("cara") if p.get("cara") in CARAS else "",
                       "falando": bool(p.get("falando")),
                       "olhando": -1 if str(p.get("olhando")) in ("-1", "-1.0") else 1,
                       "roupa": p.get("roupa") if p.get("roupa") in ROUPAS else "moletom",
                       **({"quem": str(p["quem"])[:40]} if p.get("quem") else {}),
                       **({"livre": True} if p.get("livre") else {}),
                       **{k: True for k in ("mochila", "bone", "colete", "lanterna") if p.get(k)},
                       "cor": p.get("cor") or "#4a6b6b"}
                      for p in (c.get("pessoas") or [])[:3] if isinstance(p, dict)]
    out["silhuetas"] = [{"x": max(-0.05, min(1.05, float(g.get("x", 0.3)))), "y": float(g.get("y", 0.76)),
                         **({"x2": max(-0.05, min(1.05, float(g["x2"])))} if g.get("x2") is not None else {}),
                         "alt": max(200, min(560, float(g.get("alt", 420))))}
                        for g in (c.get("silhuetas") or [])[:5] if isinstance(g, dict)]
    out["objetos"] = [{"tipo": o.get("tipo"), "x": max(0.05, min(0.95, float(o.get("x", 0.5)))),
                       "y": float(o.get("y", 0.66)), "s": max(0.5, min(3.0, float(o.get("s", 1.4)))),
                       **({"extra": str(o.get("extra"))[:44]} if o.get("extra") else {}),
                       **{k: True for k in ("enchendo", "jorrando", "seca", "batendo", "aberta", "alerta",
                                            "travado", "apagado", "subindo") if o.get(k)}}
                      for o in (c.get("objetos") or [])[:4] if isinstance(o, dict) and o.get("tipo") in OBJETOS]
    out["gatos"] = [{"x": max(0.05, min(0.95, float(g.get("x", 0.7)))), "y": float(g.get("y", 0.70)),
                     "alt": max(90, min(260, float(g.get("alt", 170))))}
                    for g in (c.get("gatos") or [])[:2] if isinstance(g, dict)]
    # o plano manda no tamanho: num close a câmera já aproxima, então a pessoa desenhada tem que ser menor
    teto = {"close": 500, "medio": 620}.get(out["plano"], 720)
    for p in out["pessoas"]:
        p["alt"] = min(p["alt"], teto)
    e = c.get("escolha")
    if isinstance(e, dict) and e.get("a") and e.get("b"):
        out["escolha"] = {"pergunta": str(e.get("pergunta", ""))[:90], "a": str(e["a"])[:60], "b": str(e["b"])[:60]}
    return out


# ------------------------------------------------------------------ 2. voz + legendas
def narra(texto, saida, cfg, log=log):
    """a narração na voz do VoiceStudio (ou Fish/Chatterbox, a mesma cadeia do canal de notícias)"""
    import voz as V

    falado = V.pronuncia(texto)
    url = cfg.get("voicestudio") or V.voicestudio_url()
    if V.voicestudio_pronto(url):
        voz_id, voz_nome = V.voicestudio_escolhe(url, cfg.get("voz_voicestudio"), log)
        log(f"voz: VoiceStudio ({url}) — voz \"{voz_nome}\"")
        V.voicestudio_fala(falado, saida, voz_id, url, velocidade=float(cfg.get("velocidade_voz", 1.0)),
                           instrucao=cfg.get("instrucao_voz") or V.INSTRUCAO_PADRAO)
    else:
        chave = os.environ.get("FISH_API_KEY")
        if not chave:
            raise RuntimeError("sem voz: cadastre a sua voz clonada no VoiceStudio (sem nenhuma voz ele sorteia "
                               "uma qualquer) ou ponha a FISH_API_KEY")
        log("voz: Fish Audio (o VoiceStudio está fechado ou sem voz cadastrada)")
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
    """cada cena termina onde a frase dela termina na narração (assim a imagem acompanha a fala).

    A voz nem sempre fala igualzinho ao roteiro (número por extenso, palavra trocada). Quando a cena não casa com a
    transcrição, ela não fica sem hora: o tempo é repartido entre as cenas vizinhas que casaram, na proporção do
    tamanho da fala de cada uma. É isso que mantém imagem e narração juntas do começo ao fim."""
    if not words:
        return
    import unicodedata

    def norm(t):
        t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9 ]", " ", t).split()

    faladas = [norm(w["w"])[0] if norm(w["w"]) else "" for w in words]
    cenas = rot["cenas"]
    # a fala do roteiro, palavra a palavra, sabendo de que cena cada palavra é
    roteiro, de_quem = [], []
    for i, c in enumerate(cenas):
        c.pop("ate", None)
        for p in norm(c.get("narracao", "")):
            roteiro.append(p)
            de_quem.append(i)
    if not roteiro:
        return

    # ALINHAMENTO GLOBAL (o mesmo jeito do roteiro × transcrição dos vídeos dele): programação dinâmica, aceitando
    # palavra trocada, falada a mais ou comida. É isso que faz a imagem virar na hora certa mesmo quando a voz não
    # falou igualzinho ao roteiro.
    n, m = len(roteiro), len(faladas)
    INF = float("inf")
    # custo: 0 se a palavra é a mesma, 0.4 se é parecida (mesmo começo), 1 se é outra; 0.9 por pular
    d = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        d[i][0] = i * 0.9
    for j in range(1, m + 1):
        d[0][j] = j * 0.9
    for i in range(1, n + 1):
        a = roteiro[i - 1]
        li = d[i]
        lp = d[i - 1]
        for j in range(1, m + 1):
            b = faladas[j - 1]
            troca = 0.0 if a == b else (0.4 if a[:4] and a[:4] == b[:4] else 1.0)
            li[j] = min(lp[j - 1] + troca, lp[j] + 0.9, li[j - 1] + 0.9)
    # volta pelo caminho mais barato: para cada palavra do roteiro, em que palavra falada ela caiu
    onde = [None] * n
    i, j = n, m
    while i > 0 and j > 0:
        a, b = roteiro[i - 1], faladas[j - 1]
        troca = 0.0 if a == b else (0.4 if a[:4] and a[:4] == b[:4] else 1.0)
        if abs(d[i][j] - (d[i - 1][j - 1] + troca)) < 1e-9:
            onde[i - 1] = j - 1
            i -= 1
            j -= 1
        elif abs(d[i][j] - (d[i - 1][j] + 0.9)) < 1e-9:
            i -= 1
        else:
            j -= 1

    # cada cena termina onde caiu a ÚLTIMA palavra dela
    ult = {}
    for k, w in enumerate(onde):
        if w is not None:
            ult[de_quem[k]] = w
    fim_total = round(words[-1]["e"] + 0.5, 2)
    anterior = 0.0
    for i, c in enumerate(cenas):
        w = ult.get(i)
        if w is None:
            continue
        t = round(float(words[w]["e"]) + 0.1, 2)
        if t > anterior + 0.4:  # nunca para trás nem cena de meio segundo
            c["ate"] = t
            anterior = t
    # cena sem âncora (fala comida): divide o espaço entre as vizinhas pelo tamanho da fala
    ini, i = 0.0, 0
    tam = [max(1, len(norm(c.get("narracao", "")))) for c in cenas]
    while i < len(cenas):
        if cenas[i].get("ate"):
            ini = cenas[i]["ate"]
            i += 1
            continue
        j = i
        while j < len(cenas) and not cenas[j].get("ate"):
            j += 1
        prox = cenas[j]["ate"] if j < len(cenas) else fim_total
        vao = max(0.6, prox - ini)
        peso = sum(tam[k] for k in range(i, j)) or 1
        t = ini
        for k in range(i, j):
            t += vao * tam[k] / peso
            cenas[k]["ate"] = round(min(t, prox), 2)
        ini = prox
        i = j
    cenas[-1]["ate"] = max(float(cenas[-1].get("ate") or 0), fim_total)


def som_sintetico(cat, destino):
    """gera o efeito pelo próprio FFmpeg quando não há arquivo na pasta dele — assim o episódio NUNCA sai mudo"""
    filtro, dur = SINTETICO.get(cat) or SINTETICO.get(PARECIDO.get(cat, ""), SINTETICO["pop"])
    env = f"afade=t=out:st={max(0.02, dur * 0.35):.2f}:d={max(0.03, dur * 0.65):.2f}"
    if cat == "riser":  # tensão: a frequência sobe
        env = f"asetrate=48000*1.0,atempo=1.0,{env}"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", filtro,
                        "-af", f"{env},aformat=channel_layouts=stereo,aresample=48000", str(destino)],
                       capture_output=True, text=True)
    return destino if r.returncode == 0 and Path(destino).exists() else None


def marca_sfx(rot, words):
    """a HORA de cada efeito: na palavra que a cena mandou (`sfx_palavra`), procurada na transcrição dentro da
    janela daquela cena. É isso que faz o som estourar junto com "o celular vibra", e não no começo da cena."""
    import unicodedata

    def norm(t):
        t = "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9]", "", t)

    faladas = [(norm(w.get("w", "")), float(w.get("s", 0))) for w in (words or [])]
    marcas = []
    for c in rot.get("cenas", []):
        if c.get("sfx") not in SFX:
            continue
        ini = float(c.get("_ini", 0))
        fim = float(c.get("ate") or (ini + 6))
        t = ini + 0.15
        alvo = norm(c.get("sfx_palavra", ""))
        if alvo:
            achou = next((s for p, s in faladas if p == alvo and ini - 0.3 <= s <= fim + 0.3), None)
            if achou is None:  # a voz pode ter falado diferente: aceita começo igual
                achou = next((s for p, s in faladas if alvo and p.startswith(alvo[:5]) and ini - 0.3 <= s <= fim + 0.3), None)
            if achou is not None:
                t = max(0.0, achou - 0.06)
        marcas.append((round(t, 2), SFX[c["sfx"]]))
    return sorted(marcas)


def sons(video, rot, saida, log=log, words=None):
    """mistura os efeitos sonoros nos tempos CERTOS (a palavra da narração), ~16 dB abaixo da voz.
    Usa a pasta de sons dele; sem ela, o som é sintetizado pelo FFmpeg."""
    sys.path.insert(0, str(TOOLS))
    from ffcompat import filtro_complexo

    import sons_web

    try:
        from biblioteca_sons import arquivo as arq_dele
    except Exception:
        arq_dele = None

    def acha(cat, i):
        """1) a pasta de efeitos das histórias (baixada do site) · 2) a pasta de efeitos do PC · 3) o sintetizado"""
        f = sons_web.arquivo(cat, i)
        if not f and PARECIDO.get(cat):
            f = sons_web.arquivo(PARECIDO[cat], i)
        if not f and arq_dele:
            try:
                f = arq_dele(PARECIDO.get(cat, cat), i)
            except Exception:
                f = None
        return f
    marcas = marca_sfx(rot, words)
    if not marcas:
        return video
    tmp = Path(saida).parent / "sfx_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    entradas, partes, usados, n = [], [], {}, 0
    for t, cat in marcas[:16]:
        f = acha(cat, usados.get(cat, 0))
        if not f:
            f = som_sintetico(cat, tmp / f"{cat}_{usados.get(cat, 0)}.wav")
        usados[cat] = usados.get(cat, 0) + 1
        if not f:
            continue
        n += 1
        entradas += ["-i", str(f)]
        partes.append(f"[{n}:a]atrim=0:1.8,afade=t=out:st=1.3:d=0.5,aresample=48000,aformat=channel_layouts=stereo,"
                      f"loudnorm=I=-30:TP=-6,adelay={int(max(0, t) * 1000)}|{int(max(0, t) * 1000)}[s{n}]")
    if not n:
        log("sfx: não consegui nenhum som")
        return video
    # o vídeo pode estar sem áudio (render sem narração): aí mistura só os efeitos
    tem_audio = bool(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                                     "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout.strip())
    mix = "".join(f"[s{i}]" for i in range(1, n + 1))
    # com narração, o tamanho é o dela (duration=first); sem narração, vale o efeito mais longo
    grafo = ";".join(partes) + (f";[0:a]{mix}amix=inputs={n + 1}:normalize=0:duration=first" if tem_audio
                                else f";{mix}amix=inputs={n}:normalize=0:duration=longest") \
        + ",loudnorm=I=-14:TP=-1.5[a]"
    g = Path(saida).parent / "grafo_sfx.txt"
    g.write_text(grafo, encoding="utf-8")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), *entradas, *filtro_complexo(str(g)),
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(saida)],
                       capture_output=True, text=True)
    g.unlink(missing_ok=True)
    if r.returncode != 0 or not Path(saida).exists():
        log(f"sfx: não entraram ({(r.stderr or '')[-160:]})")
        return video
    log(f"sfx: {n} efeito(s) sonoro(s), na palavra de cada cena")
    return saida


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
def faz_episodio(serie_f, cfg, log=log, venceu="", rumo="", base="", refazer=0, melhorar=0):
    """venceu = "a"/"b" escolhido POR VOCÊ (em vez de contar os comentários); rumo = o que acontece, escrito por você;
    base = um roteiro anterior (texto) para a IA seguir; refazer = N refaz o episódio N com o roteiro.json que está lá"""
    serie = {**SERIE_PADRAO, **(le_json(serie_f, {}) or {})}
    pasta_serie = Path(serie_f).parent
    n = int(melhorar or refazer) if (melhorar or refazer) else len(serie.get("episodios", [])) + 1
    if refazer:  # refazer = apaga voz, legendas e vídeo; o roteiro.json (que você editou) fica
        job0 = pasta_serie / f"ep_{n:02d}"
        for f0 in ("voz.wav", "words.json", "episodio.mp4", "episodio_sfx.mp4"):
            (job0 / f0).unlink(missing_ok=True)
        log(f"refazendo o episódio {n} com o roteiro que está em {job0 / 'roteiro.json'}")
    elif melhorar:  # mais edição: a narração (e a voz) continua a mesma, só o desenho é remontado
        job0 = pasta_serie / f"ep_{n:02d}"
        for f0 in ("episodio.mp4", "episodio_sfx.mp4"):
            (job0 / f0).unlink(missing_ok=True)
        log(f"pedindo mais edição à IA para o episódio {n} (a narração e a voz continuam as mesmas)")
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
        resultado = apura(serie, pasta_serie, cfg, log)
    if rumo:
        log(f"rumo que você mandou: {rumo[:160]}")
    grava_json(serie_f, serie)

    job = pasta_serie / f"ep_{n:02d}"
    job.mkdir(parents=True, exist_ok=True)
    rot_f = job / "roteiro.json"
    rot = le_json(rot_f)
    if not rot:
        log("1/4 escrevendo o episódio...")
        rot = escreve_episodio({**serie, "_roteiro_base": base} if base else serie, cfg, n, resultado, log, rumo)
        rot["marca"] = cfg.get("marca") or f"@{(serie.get('conta') or '').split(':')[-1]}"
        grava_json(rot_f, rot)
    else:
        if melhorar:
            melhora_roteiro(serie, cfg, rot, log)
        garante_sfx(rot)        # roteiro editado à mão também não sai mudo
        fecha_com_escolha(rot)  # e sem a cartela A/B ganha a dela
        grava_json(rot_f, rot)
    aplica_elenco(serie, rot)      # cada personagem com a MESMA cara de sempre (o principal é o do modelo)
    grava_json(serie_f, serie)
    grava_json(rot_f, rot)
    log(f"    \"{rot.get('titulo', '')}\" — {len(rot['cenas'])} cenas"
        + (f" — elenco: {', '.join(serie.get('elenco', {}))}" if serie.get("elenco") else ""))

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
    t0 = 0.0
    for c in rot["cenas"]:  # a hora em que cada cena começa (o efeito sonoro entra aí)
        c["_ini"] = round(t0, 2)
        t0 = float(c.get("ate") or (t0 + 5))
    grava_json(rot_f, rot)

    saida = job / "episodio.mp4"

    def monta_video():
        dur = (words[-1]["e"] + 0.7) if words else (dur_wav(wav) or cfg["duracao_s"])
        r = subprocess.run(["node", str(AQUI / "render.js"), str(rot_f), "--voz", str(wav), "--words", str(wf),
                            "--out", str(saida), "--work", str(job / "tmp"), "--fps", str(cfg.get("fps", 30)),
                            "--duracao", f"{dur:.2f}", "--marca", rot.get("marca", "")], cwd=str(PONTE))
        if r.returncode != 0 or not saida.exists():
            raise RuntimeError("o render do episódio falhou (veja as mensagens acima)")

    if not saida.exists():
        log("4/5 desenhando e montando...")
        monta_video()

    # CONFERÊNCIA antes de entregar: pronúncia, o que a voz falou e cada cena desenhada.
    # Achou problema que dá para corrigir → corrige e MONTA DE NOVO (uma vez).
    log("5/5 conferindo antes de entregar...")
    try:
        import confere as CF

        refazer, _ = CF.confere(job, rot, words, saida, log)
        if refazer:
            grava_json(rot_f, rot)
            if any(c.get("narracao") for c in rot["cenas"]) and not wav.exists():
                narra(rot["narracao"], wav, cfg, log)
            saida.unlink(missing_ok=True)
            monta_video()
            CF.confere(job, rot, words, saida, log, corrigir=False)
    except Exception as e:
        log(f"conferência: não rodou ({str(e)[:140]})")

    # efeitos sonoros, cada um na palavra que a cena marcou
    com_sfx = job / "episodio_sfx.mp4"
    if not com_sfx.exists() and any(c.get("sfx") for c in rot.get("cenas", [])):
        v = sons(saida, rot, com_sfx, log, words)
        if Path(v) == com_sfx and com_sfx.exists():
            saida.unlink(missing_ok=True)
            com_sfx.replace(saida)

    # capa do episódio (a grade do perfil) — sai junto, sempre
    try:
        import capa as CAPA

        CAPA.capa_episodio(serie, rot, n, job / "capa.jpg", log=log)
    except Exception as e:
        log(f"capa: não saiu ({str(e)[:120]})")
    esc = rot.get("escolha", {})
    legenda = rot.get("legenda_post") or f"{rot.get('titulo', '')}\n\n{esc.get('pergunta', '')}\nA: {esc.get('a', '')}\nB: {esc.get('b', '')}\n\nComenta A ou B 👇"
    (job / "post.txt").write_text(legenda, encoding="utf-8")
    reg = {"n": n, "titulo": rot.get("titulo", ""), "resumo": rot.get("resumo", ""), "escolha": esc,
           "arquivo": str(saida), "feito": dt.datetime.now().isoformat(timespec="minutes")}
    eps_l = serie.setdefault("episodios", [])
    antigo = next((i for i, e in enumerate(eps_l) if e.get("n") == n), None)
    if antigo is None:
        eps_l.append(reg)
    else:  # refazer: atualiza o episódio em vez de criar outro (e guarda o resultado da votação dele)
        eps_l[antigo] = {**eps_l[antigo], **reg}
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
def apaga_serie(pasta, nome):
    """apaga a série inteira (os testes que não servem mais) — pasta, episódios e vídeos"""
    import shutil

    alvo = Path(pasta) / "series" / nome
    if not (alvo / "serie.json").exists():
        alvo = next((f.parent for f in series(pasta) if slug(nome) in f.parent.name), None)
    if not alvo or not alvo.exists():
        return f"não achei a série \"{nome}\""
    s = le_json(alvo / "serie.json", {}) or {}
    shutil.rmtree(alvo, ignore_errors=True)
    return f"apaguei a série \"{s.get('nome', alvo.name)}\" ({alvo})"


def nova_serie(pasta, ideia, conta, cfg, log=log, contexto=""):
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
    s = {**SERIE_PADRAO, **g, "conta": conta or (cfg.get("contas") or [""])[0], "ligada": True, "episodios": [],
         "contexto": contexto or ideia}
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
    ap.add_argument("--contexto", default="", help="grava o contexto da série (vale para todos os episódios)")
    ap.add_argument("--base-roteiro", default="", help="arquivo com um roteiro anterior para a IA seguir")
    ap.add_argument("--refazer", type=int, default=0, help="refaz o episódio N com o roteiro.json que está na pasta dele")
    ap.add_argument("--melhorar", type=int, default=0, help="pede MAIS EDIÇÃO à IA no episódio N (a narração e a voz continuam as mesmas)")
    ap.add_argument("--apagar", action="store_true", help="APAGA a série (com --serie); pede o nome exato da pasta")
    a = ap.parse_args()
    pasta = Path(a.pasta)
    cfg = prepara(pasta)
    if a.novo:
        nova_serie(pasta, a.novo, a.conta, cfg, contexto=a.contexto)
        return
    if a.apagar:
        if not a.serie:
            log("diga qual série apagar: --serie <pasta> --apagar")
            return
        log(apaga_serie(pasta, a.serie))
        return
    if a.contexto and a.serie:
        f = pasta / "series" / slug(a.serie) / "serie.json"
        f = f if f.exists() else next((x for x in series(pasta) if slug(a.serie) in x.parent.name), None)
        if not f:
            log("não achei essa série")
            return
        s = le_json(f, {}) or {}
        s["contexto"] = a.contexto
        grava_json(f, s)
        log(f"contexto gravado em {f}")
        return
    base_rot = ""
    if a.base_roteiro and Path(a.base_roteiro).exists():
        base_rot = Path(a.base_roteiro).read_text(encoding="utf-8-sig")[:8000]
        log(f"seguindo o roteiro base: {a.base_roteiro}")
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
            faz_episodio(f, cfg, venceu=a.continuar, rumo=a.rumo, base=base_rot, refazer=a.refazer, melhorar=a.melhorar)
            feitos += 1
        except Exception as e:
            log(f"{f.parent.name}: {str(e)[:300]}")


if __name__ == "__main__":
    main()
