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
