#!/usr/bin/env python3
"""DOCUMENTÁRIO DIÁRIO DO GTA 6 (10/nov, pedido dele): "pelo menos um vídeo por dia do GTA 6 como um
documentário, explicando algo, mostrando algo ou projetando algo… nenhum horizontal com menos de 12 min".

POR QUE ISTO E NÃO O canal.py: o canal.py monta notícia da IMPRENSA com a fala dele entre os trechos; num dia sem
notícia ele não tem material para 12 min (e os formatos "documentario"/"cartoes" saíam com 4–6 min). Aqui o vídeo
é ELE narrando do começo ao fim (a voz do perfil detto) e a tela mostra TRAILER/GAMEPLAY do que está sendo dito —
não depende de ninguém ter postado notícia hoje.

O QUE FOI MEDIDO e entra aqui: 12–18 min rende 1,3x no nicho (5 canais) → alvo 14 min, piso 12 que NADA fura;
número no título 2,0x no canal do tamanho dele (Dulebio); "vazou"/"..."/"!!" pioram. Thumb: thumb/gta6.py.

    python tools\\narrado\\documentario.py --pasta E:\\DETTO\\canal_gta6 [--assunto "..."] [--minutos 14] [--nao-postar]

Saída: <pasta>\\prontos\\<data> - <título>\\video.mp4 + thumb_1.jpg + post.json (o painel aprova/posta como os outros).
"""
import argparse
import datetime as dt
import json
import random
import re
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
for p in (AQUI, TOOLS, TOOLS / "canal", TOOLS / "thumb", TOOLS / "yt", TOOLS / "reels"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import narrado as N  # noqa: E402

DW, DH = 1920, 1080
PALAVRAS_MIN_DOC = 165        # narração de documentário é mais calma que o short (190)
TIPOS = ("EXPLICAR", "MOSTRAR", "PROJETAR")


def log(m):
    N.log(m)


def le(f, padrao):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return padrao


def ia(pedido, temp=0.75):
    from reels import gemini_json
    return gemini_json([{"text": pedido}], temperatura=temp) or {}


REGRAS_DOC = """Você escreve um DOCUMENTÁRIO narrado para o YouTube sobre GTA 6, em português do Brasil, na voz de um
criador brasileiro (1ª pessoa, próximo, empolgado sem gritar). Ele narra o vídeo inteiro; na tela passam trailer e
gameplay do que está sendo dito.

COMO PRENDER (é isso que decide se o vídeo viraliza):
- Os primeiros 30 segundos são TUDO: comece pela pergunta/promessa mais forte do vídeo, com um NÚMERO ou detalhe
  concreto. Sem "olá", sem "fala galera", sem apresentar o canal.
- Prometa no começo o que a pessoa vai ganhar ficando até o fim e só entregue a peça principal no último capítulo.
- Cada capítulo termina abrindo o próximo ("e é aí que entra o detalhe que quase ninguém viu...").
- Frases curtas, uma ideia por frase, ritmo de conversa. Nada de enrolação nem de repetir o que já disse.
- Peça inscrição UMA vez, no meio, ligada a um benefício ("se você quer ver o mapa completo no dia 19...").
- Termine com uma pergunta que faça a pessoa comentar.

VERDADE (inegociável): use só o que foi mostrado nos trailers, no site oficial da Rockstar ou anunciado. Rumor e
vazamento são chamados de rumor. PROJEÇÃO é permitida, mas dita como projeção ("o que eu acho que vai acontecer").
Nunca invente número, data, preço ou fala.
Títulos: com NÚMERO concreto quando houver; sem "vazou"; não termine com "..." nem "!!"."""


def contexto(pasta, cfg):
    hist = le(pasta / "historico.json", {})
    lim = (dt.date.today() - dt.timedelta(days=4)).isoformat()
    noticias = [f"- {t.get('manchete', '')}: {t.get('resumo', '')}" for t in (hist.get("trechos") or [])
                if str(t.get("data", "")) >= lim and t.get("manchete")][-25:]
    titulos = [str(t.get("titulo", "")) for t in (hist.get("titulos") or [])][-10:]
    linhas = []
    if cfg.get("lancamento"):
        try:
            faltam = (dt.date.fromisoformat(cfg["lancamento"]) - dt.date.today()).days
            linhas.append(f"HOJE FALTAM {faltam} DIAS para o lançamento ({cfg['lancamento']}).")
        except ValueError:
            pass
    if noticias:
        linhas.append("NOTÍCIAS DOS ÚLTIMOS DIAS (coletadas pelo canal):\n" + "\n".join(noticias))
    if titulos:
        linhas.append("TÍTULOS QUE O CANAL JÁ USOU (não repita o mesmo fato):\n" + "\n".join(titulos))
    return "\n\n".join(linhas)


def esboco(assunto, tipo, minutos, ctx, usados):
    pedido = (f"{REGRAS_DOC}\n\n{ctx}\n\nTIPO DE HOJE: {tipo} (EXPLICAR = como algo funciona; MOSTRAR = percorrer o que "
              f"foi mostrado; PROJETAR = o que dá para esperar, com base no que já se sabe).\n"
              + (f"ASSUNTO: {assunto}\n" if assunto else
                 f"Escolha você o ASSUNTO mais clicável de hoje (não repita estes: {'; '.join(usados[-20:]) or 'nenhum'}).\n")
              + f"O vídeo tem {minutos} minutos: divida em 6 a 8 capítulos.\n"
              'Responda SÓ JSON: {"assunto":"...","titulo":"<até 90 letras, MAIÚSCULAS>","thumb_texto":"<2 a 4 palavras, '
              'com número se houver, SEM repetir o título>","thumb_destaque":"<1 a 2 palavras do thumb_texto>",'
              '"descricao":"<3 frases>","tags":["..."],"capitulos":[{"titulo":"<curto>","resumo":"<o que o capítulo '
              'conta>","buscas":["<termo do YouTube que acha trailer/gameplay DAQUILO, sempre com GTA 6>"]}]}')
    d = ia(pedido)
    caps = [c for c in (d.get("capitulos") or []) if isinstance(c, dict) and c.get("titulo")]
    if len(caps) < 4:
        raise RuntimeError("a IA não devolveu o esboço do documentário (sem IA de texto respondendo?)")
    d["capitulos"] = caps[:8]
    return d


def texto_capitulo(esb, k, palavras, extra=""):
    caps = esb["capitulos"]
    c = caps[k]
    lista = "\n".join(f"{i + 1}. {x['titulo']} — {x.get('resumo', '')}" for i, x in enumerate(caps))
    papel = ("É o PRIMEIRO capítulo: abre o vídeo com o gancho." if k == 0 else
             "É o ÚLTIMO capítulo: entrega a peça principal e termina com a pergunta para comentar." if k == len(caps) - 1
             else "Capítulo do meio: termine abrindo o próximo." + (" Peça a inscrição aqui, uma vez." if k == len(caps) // 2 else ""))
    pedido = (f"{REGRAS_DOC}\n\nDOCUMENTÁRIO: {esb['titulo']}\nCAPÍTULOS:\n{lista}\n\nEscreva SÓ a narração do capítulo "
              f"{k + 1} (\"{c['titulo']}\": {c.get('resumo', '')}). {papel} {extra}\nTem de ter cerca de {palavras} palavras "
              "(não menos). Números por extenso não são obrigatórios.\n"
              'Responda SÓ JSON: {"narracao":"..."}')
    melhor = ""
    for _ in range(3):
        t = re.sub(r"\s+", " ", str(ia(pedido).get("narracao") or "")).strip()
        if len(t.split()) > len(melhor.split()):
            melhor = t
        if len(melhor.split()) >= palavras * 0.85:
            break
        pedido += f"\n\nATENÇÃO: a versão anterior tinha {len(t.split())} palavras; precisa de pelo menos {palavras}."
    if len(melhor.split()) < 40:
        raise RuntimeError(f"a IA não escreveu o capítulo {k + 1}")
    return melhor


def cartela_capitulo(n, titulo, saida):
    """etiqueta do capítulo, embaixo à esquerda (4,5 s) — o espectador sabe onde está e o que vem"""
    from PIL import Image, ImageDraw, ImageFont
    fb = N.FONTES / "Inter-ExtraBold.otf"
    f1 = ImageFont.truetype(str(fb), 34) if fb.exists() else ImageFont.load_default()
    f2 = ImageFont.truetype(str(fb), 62) if fb.exists() else ImageFont.load_default()
    t2 = titulo.upper()[:48]
    img = Image.new("RGBA", (DW, 230), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    larg = int(max(d.textlength(t2, font=f2), 300) + 80)
    d.rounded_rectangle([50, 40, 50 + larg, 210], 18, fill=(10, 10, 14, 215))
    d.rectangle([50, 40, 62, 210], fill=(255, 212, 0, 255))
    d.text((90, 56), f"CAPÍTULO {n}", font=f1, fill=(255, 212, 0, 255))
    d.text((90, 104), t2, font=f2, fill=(255, 255, 255, 255))
    img.save(saida)
    return saida


def fim_da_primeira_frase(palavras, minimo=8.0):
    for p in palavras:
        if p["e"] >= minimo and p["w"].rstrip().endswith((".", "?", "!")):
            return p["e"] + 0.15
    return 15.0


def faz(pasta, cfg, assunto="", minutos=14, postar=True, teste=False):
    pasta = Path(pasta)
    cfg_voz = {**le(N.raiz() / "narrado" / "config.json", {}), **{k: v for k, v in cfg.items() if k in ("voz_narrado", "velocidade_voz")}}
    usados_f = pasta / "documentarios_usados.json"
    usados = le(usados_f, [])
    tipo = TIPOS[dt.date.today().toordinal() % 3]
    piso = float(cfg.get("min_minutos_video", 12)) * 60
    if teste:
        minutos, piso = 2, 60
    log(f"DOCUMENTÁRIO GTA 6: tipo {tipo}, alvo {minutos} min (mínimo {piso / 60:.0f})")
    esb = esboco(assunto, tipo, minutos, contexto(pasta, cfg), usados)
    log(f"   título: {esb.get('titulo')} · {len(esb['capitulos'])} capítulos")
    tmp = pasta / "tmp_doc"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    alvo_pal = int(minutos * PALAVRAS_MIN_DOC / len(esb["capitulos"]))
    caps, total = [], 0.0
    k = 0
    while k < len(esb["capitulos"]):
        c = esb["capitulos"][k]
        texto = texto_capitulo(esb, k, alvo_pal)
        wav = tmp / f"voz_{k:02d}.wav"
        N.narra(texto, wav, cfg_voz, log)
        d = N.dur(wav)
        total += d
        caps.append({"titulo": c["titulo"], "buscas": c.get("buscas") or [], "texto": texto, "wav": wav, "dur": d})
        log(f"   capítulo {k + 1}: {d / 60:.1f} min ({len(texto.split())} palavras) — total {total / 60:.1f} min")
        k += 1
        # FALTOU TEMPO? (a voz dele a 1,25x come o texto): um capítulo a mais, até 2 vezes
        if k == len(esb["capitulos"]) and total < piso + 20 and len(esb["capitulos"]) < 10:
            log(f"   {total / 60:.1f} min é menos que o mínimo; acrescento um capítulo")
            esb["capitulos"].insert(k - 1, {"titulo": "O que ainda não sabemos", "resumo":
                                            "as perguntas em aberto e o que dá para projetar a partir do que já foi mostrado",
                                            "buscas": ["GTA 6 trailer detalhes", "GTA 6 gameplay análise"]})
            ultimo = caps.pop()          # o último capítulo (com a pergunta final) volta para o fim
            total -= ultimo["dur"]
            k -= 1
    if total < piso:
        raise RuntimeError(f"NÃO RODEI: o documentário deu só {total / 60:.1f} min (mínimo {piso / 60:.0f}). Nada foi postado.")

    # ---- imagem: trailer/gameplay do que cada capítulo fala (1920x1080)
    N.W, N.H_TOPO = DW, DH
    todos = []
    pecas = []
    for i, c in enumerate(caps):
        tc = tmp / f"cap{i:02d}"
        tc.mkdir()
        rot = {"sujeito": "GTA 6", "apelidos": ["GTA VI", "Grand Theft Auto VI", "Grand Theft Auto 6"],
               "buscas": [b if "gta" in N.norm(b) else f"GTA 6 {b}" for b in c["buscas"][:3]]
               + ["GTA 6 trailer 4K", "GTA 6 gameplay"], "sujeito_pessoa": False}
        try:
            clipes = N.pool_de_clipes(rot, c["dur"], tmp / "clipes", log)
        except Exception as e:  # noqa: BLE001
            log(f"   capítulo {i + 1}: clipes falharam ({str(e)[:100]})")
            clipes = []
        if not clipes and todos:
            log(f"   capítulo {i + 1}: sem clipe próprio; uso os dos outros capítulos")
            clipes = random.sample(todos, len(todos))
        if not clipes:
            raise RuntimeError("não consegui nenhum clipe de GTA 6 (o YouTube barrou o download? confira o login)")
        todos += clipes
        seq, s = [], 0.0
        while s < c["dur"] + 1:
            p = clipes[len(seq) % len(clipes)]
            seq.append(p)
            s += p["dur"]
        vis = N.esteira(seq, c["dur"], tc, log)
        png = cartela_capitulo(i + 1, c["titulo"], tc / "cartela.png")
        saida = tmp / f"peca_{i:02d}.mp4"
        N.roda(["ffmpeg", "-v", "error", "-i", str(vis), "-i", str(c["wav"]), "-i", str(png), "-filter_complex",
                "[0:v][2:v]overlay=0:H-h-40:enable='lt(t,4.5)'[v];[1:a]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]",
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                "-r", str(N.FPS), "-c:a", "aac", "-b:a", "192k", "-t", f"{c['dur']:.3f}", "-y", str(saida)], f"capítulo {i + 1}")
        pecas.append(saida)
    lista = tmp / "pecas.txt"
    lista.write_text("".join(f"file '{p.as_posix()}'\n" for p in pecas), encoding="utf-8")
    bruto = tmp / "doc.mp4"
    N.roda(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", "-movflags", "+faststart",
            "-y", str(bruto)], "emenda dos capítulos")

    # ---- capítulos do YouTube + vinheta depois do gancho
    marcas, t, faixas_thumb = [], 0.0, []
    for c in caps:
        marcas.append((t, c["titulo"]))
        d_ = N.dur(tmp / f"peca_{len(marcas) - 1:02d}.mp4")
        faixas_thumb.append((t + 5.0, t + max(5.5, d_ - 0.5)))   # longe da etiqueta "CAPÍTULO N"
        t += d_
    final = bruto
    try:
        import vinheta
        import capitulos as CAP
        p1 = N.tempos_das_palavras(caps[0]["wav"], caps[0]["texto"], log)
        em = min(fim_da_primeira_frase(p1), 40.0)
        antes = N.dur(bruto)
        com = vinheta.abre(bruto, canal=cfg.get("vinheta_canal", "gta6"), cfg=cfg, saida=tmp / "doc_vinheta.mp4", log=log, em=em)
        if com and Path(com).exists() and Path(com) != bruto:
            final = Path(com)
            dv = N.dur(final) - antes
            marcas = CAP.desloca(marcas, em, dv)
            faixas_thumb = [(a + dv, b + dv) if a >= em else (a, b) for a, b in faixas_thumb]
        caps_yt = CAP.de_marcas(marcas, N.dur(final), primeiro=caps[0]["titulo"])
    except Exception as e:  # noqa: BLE001
        log(f"   vinheta/capítulos: {str(e)[:120]}")
        caps_yt = []

    # ---- pronto
    titulo = str(esb.get("titulo") or esb.get("assunto") or "GTA 6").strip()[:95]
    pronto = pasta / "prontos" / f"{dt.datetime.now():%Y-%m-%d_%H%M} - {N.slug(titulo, 50)}"
    pronto.mkdir(parents=True, exist_ok=True)
    shutil.move(str(final), pronto / "video.mp4")
    th = None
    try:
        from gta6 import thumb_gta6
        feitas = thumb_gta6(pronto / "thumbs", pronto / "video.mp4", faixas_thumb,
                            esb.get("thumb_texto") or titulo[:30], esb.get("thumb_destaque", ""), log=log)
        if feitas:
            th = pronto / "thumb_1.jpg"
            shutil.copyfile(feitas[0], th)
    except Exception as e:  # noqa: BLE001
        log(f"   thumb falhou ({str(e)[:120]})")
    try:
        import capitulos as CAP
        bloco = CAP.texto(caps_yt)
    except Exception:  # noqa: BLE001
        bloco = ""
    descricao = (str(esb.get("descricao") or "").strip() + ("\n\n" + bloco if bloco else "")
                 + "\n\nImagens: trailers oficiais da Rockstar Games e gameplays públicas, usadas para comentário e análise."
                 + ("\n\n" + cfg["assinatura"] if cfg.get("assinatura") else ""))
    post = {"titulo": titulo, "descricao": descricao, "tags": [str(x) for x in (esb.get("tags") or [])][:15],
            "video": "video.mp4", "thumb": th.name if th else "", "thumb_variante": "gta6", "shorts": [],
            "status": "aguardando", "criado": dt.datetime.now().isoformat(timespec="seconds"),
            "formato": "documentario_narrado", "capitulos": caps_yt, "duracao_min": round(N.dur(pronto / "video.mp4") / 60, 1)}
    import comum
    comum.grava(pronto / "post.json", post)
    usados.append(esb.get("assunto") or titulo)
    usados_f.write_text(json.dumps(usados[-100:], ensure_ascii=False), encoding="utf-8")
    hist_f = pasta / "historico.json"
    hist = le(hist_f, {})
    if isinstance(hist, dict):
        hist.setdefault("titulos", []).append({"quando": dt.datetime.now().isoformat(timespec="minutes"), "titulo": titulo,
                                               "texto": " ".join(c["texto"] for c in caps)[:1500]})
        hist_f.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
    (pasta / "documentario_feito.txt").write_text(dt.date.today().isoformat(), encoding="utf-8")
    log(f"PRONTO: {titulo} — {post['duracao_min']} min → {pronto}")
    shutil.rmtree(tmp, ignore_errors=True)
    if postar and cfg.get("auto_postar") and not teste:
        try:
            comum.publica(pasta, pronto, cfg, log, categoria="20")
        except Exception as e:  # noqa: BLE001
            log(f"   postagem falhou ({str(e)[:160]}); fica aguardando no painel")
    return pronto


def main():
    ap = argparse.ArgumentParser(description="documentário narrado diário do GTA 6 (12+ min)")
    ap.add_argument("--pasta", required=True)
    ap.add_argument("--assunto", default="")
    ap.add_argument("--minutos", type=float, default=0)
    ap.add_argument("--nao-postar", action="store_true")
    ap.add_argument("--teste", action="store_true", help="2 min, sem postar (para conferir o caminho todo)")
    a = ap.parse_args()
    pasta = Path(a.pasta)
    cfg = le(pasta / "config.json", {})
    N.LOG_F = pasta / "documentario.log"
    minutos = a.minutos or float(cfg.get("doc_minutos", 14))
    try:
        faz(pasta, cfg, a.assunto, minutos, postar=not a.nao_postar, teste=a.teste)
    except Exception as e:  # noqa: BLE001
        log(f"NÃO RODEI: {str(e)[:300]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
