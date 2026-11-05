# -*- coding: utf-8 -*-
"""Peças comuns dos canais automáticos (notícias e vlogs): o "pronto" de cada vídeo e a postagem no YouTube.

Cada vídeo montado fica em <canal>\\prontos\\<data - título>\\ com:
  video.mp4, thumb_1.jpg (se tiver), short_1.mp4, short_2.mp4 ... e post.json:
  {"titulo", "descricao", "tags", "video", "thumb", "shorts": [{"arquivo", "titulo"}], "status": aguardando|postando|postado|erro|descartado,
   "youtube", "shorts_youtube": [...], "erro"}
"Postar sozinho" desligado = fica "aguardando" até você aprovar no painel (aba Canais) ou rodar --postar <pasta>.
"""
import datetime as dt
import json
from pathlib import Path


def le(f, padrao=None):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def grava(f, d):
    Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def prontos(pasta):
    """os prontos do canal, mais novos primeiro"""
    out = []
    for p in sorted((Path(pasta) / "prontos").glob("*/post.json"), key=lambda f: f.parent.name, reverse=True):
        d = le(p, {})
        if d:
            out.append((p.parent, d))
    return out


def publica(pasta, pronto, cfg, log=print, sintetico=True, categoria="17"):
    """sobe o vídeo e agenda os Shorts (um a cada horas_entre_shorts, a partir de agora). Devolve o post.json."""
    import youtube_up

    pronto = Path(pronto)
    post = le(pronto / "post.json", {})
    if not post:
        raise RuntimeError(f"sem post.json em {pronto}")
    post["status"] = "postando"
    post.pop("erro", None)
    grava(pronto / "post.json", post)
    try:
        if not post.get("youtube"):
            log(f"postando no YouTube: {post['titulo']}")
            th = pronto / post["thumb"] if post.get("thumb") else None
            vid = youtube_up.posta(pasta, pronto / post["video"], post["titulo"], post["descricao"], post.get("tags", []), th,
                                   cfg.get("privacidade", "public"), sintetico=sintetico, log=log, categoria=categoria)
            post["youtube"] = f"https://youtu.be/{vid}"
            grava(pronto / "post.json", post)
            log(f"POSTADO: {post['youtube']}")
        if post.get("comentario") and not post.get("comentou") and post.get("youtube"):
            try:
                youtube_up.comenta(pasta, post["youtube"].rsplit("/", 1)[-1], post["comentario"])
                post["comentou"] = True
                grava(pronto / "post.json", post)
                log("créditos comentados no vídeo (para FIXAR: YouTube Studio → Comentários → ⋮ → Fixar)")
            except Exception as e:
                msg = str(e)
                if "insufficient" in msg.lower() or "403" in msg:
                    log("não consegui comentar os créditos: falta a permissão de comentar — refaça o login do canal no painel "
                        "(aba Canais) uma vez; os créditos estão na descrição")
                else:
                    log(f"não consegui comentar os créditos ({msg[:150]}); estão na descrição")
        feitos = post.setdefault("shorts_youtube", [])
        agora = dt.datetime.now(dt.timezone.utc)
        passo = float(cfg.get("horas_entre_shorts", 3))
        for i, s in enumerate(post.get("shorts", [])):
            if i < len(feitos) and feitos[i]:
                continue
            quando = (agora + dt.timedelta(hours=passo * (len([x for x in feitos if x]) + 1))).replace(microsecond=0)
            titulo = (s.get("titulo") or post["titulo"])[:88].rstrip() + " #shorts"
            desc = f"{s.get('descricao') or post['titulo']}\n\nVídeo completo: {post['youtube']}\n\n#shorts"
            vid = youtube_up.posta(pasta, pronto / s["arquivo"], titulo, desc, post.get("tags", [])[:10], None,
                                   cfg.get("privacidade", "public"), publicar_em=quando.isoformat().replace("+00:00", "Z"),
                                   sintetico=sintetico, log=log, categoria=categoria)
            feitos.append(f"https://youtube.com/shorts/{vid}")
            grava(pronto / "post.json", post)
            log(f"SHORT agendado para {quando.astimezone():%d/%m %H:%M}: https://youtube.com/shorts/{vid}")
        post["status"] = "postado"
        post["postado_em"] = dt.datetime.now().isoformat(timespec="seconds")
    except BaseException as e:
        post["status"] = "erro"
        post["erro"] = str(e)[:400]
        grava(pronto / "post.json", post)
        raise
    grava(pronto / "post.json", post)
    return post


def confere_postados(pasta, cfg=None, horas=72, log=print):
    """O VÍDEO FOI AO AR OU FOI BLOQUEADO? (05/nov)

    Ele descobriu na mão que os vídeos estavam sendo DERRUBADOS depois de postados — e que o único que
    escapou foi justamente o que não tinha imagem de imprensa nenhuma. Isso é direito autoral, e o sistema
    não fazia a menor ideia: para ele, "postado" era o fim da história.

    Agora, depois de postar, eu pergunto ao YouTube como o vídeo está. A API responde em
    `status.rejectionReason` se foi `copyright`/`claim` (reclamação) ou `duplicate` (o mesmo vídeo já
    estava no canal) — os dois casos que aconteceram com ele no mesmo dia.

    E mais importante que avisar: eu ANOTO DE QUAIS FONTES era aquele vídeo. Depois de alguns bloqueios dá
    para ver qual canal-fonte sempre derruba o vídeo, e aí é só tirar da lista. Isso é medir em vez de
    adivinhar — do mesmo jeito que o resto do sistema."""
    import datetime as dt

    import youtube_up

    pasta = Path(pasta)
    hist = le(pasta / "historico.json", {}) or {}
    bloqueios = hist.setdefault("bloqueios", {})   # fonte -> quantas vezes derrubou
    limite = dt.datetime.now() - dt.timedelta(hours=horas)
    mudou, achados = False, []
    for pr, post in prontos(pasta):
        if post.get("status") != "postado" or not post.get("youtube"):
            continue
        if post.get("yt_conferido_em"):
            # já conferido: só reconfere o que ainda é recente (a reclamação chega HORAS depois)
            try:
                if dt.datetime.fromisoformat(post["yt_conferido_em"]) > dt.datetime.now() - dt.timedelta(hours=6):
                    continue
            except ValueError:
                pass
        try:
            # o canal.py grava "criado"; o publica() grava "postado_em"
            quando = dt.datetime.fromisoformat(post.get("postado_em") or post.get("criado") or "")
            if quando < limite:
                continue       # vídeo velho: a janela de reclamação já passou, não gasto cota
        except (ValueError, TypeError):
            pass
        vid = post["youtube"].rsplit("/", 1)[-1]
        try:
            s = youtube_up.situacao(pasta, vid)
        except Exception as e:   # noqa: BLE001
            log(f"   não consegui conferir {vid}: {str(e)[:110]}")
            continue
        post["yt_estado"] = s["estado"]
        post["yt_motivo"] = s["motivo"]
        post["yt_bloqueado"] = s["bloqueado"]
        post["yt_conferido_em"] = dt.datetime.now().isoformat(timespec="minutes")
        grava(pr / "post.json", post)
        mudou = True
        if s["bloqueado"]:
            fontes = sorted({t.get("fonte", "") for t in (post.get("trechos") or []) if t.get("fonte")})
            for f in fontes:
                bloqueios[f] = int(bloqueios.get(f, 0)) + 1
            achados.append({"titulo": post.get("titulo", ""), "link": post["youtube"],
                            "motivo": s["motivo"] or s["estado"], "fontes": fontes})
            log(f"⛔ BLOQUEADO: {post.get('titulo', '')[:60]} — {s['motivo'] or s['estado']}"
                + (f" · imagens de: {', '.join(fontes)}" if fontes else ""))
    if mudou:
        hist["bloqueios"] = bloqueios
        grava(pasta / "historico.json", hist)
    if bloqueios:
        pior = sorted(bloqueios.items(), key=lambda x: -x[1])[:3]
        if any(n >= 2 for _, n in pior):
            log("   fontes que mais derrubam o vídeo: "
                + ", ".join(f"{f} ({n}x)" for f, n in pior if n >= 2)
                + " — pense em tirar da lista de fontes")
    return achados
