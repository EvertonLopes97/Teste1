# -*- coding: utf-8 -*-
"""Aba EDIÇÃO do painel: você manda a gravação + o roteiro pela tela e o PC roda o tools/editar.py.

Pasta (padrão E:\\DETTO\\edicao): cada edição é uma pasta "AAAA-MM-DD HHMM título\\" com
  <título>.mp4 (a gravação), <título>.txt (o seu roteiro), imagens\\ (fotos que você mandou: Vasco.jpg ...),
  <título>_job\\ (o que o editar.py faz: horizontal.mp4, vertical_*.mp4, thumbs, conferência) e painel.json (situação).
Uma edição por vez (placa de vídeo); as outras esperam na fila.
"""
import datetime as dt
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ED = None
TRAVA = threading.Lock()
PROC = {"id": None, "p": None}

ETAPAS = [  # (texto no registro, nome da etapa) — a última que aparecer é a atual
    ("transcrever.py", "Transcrevendo a fala"), ("facetrack.py", "Achando o rosto"), ("roteiro_ia.py", "Gemini escrevendo o roteiro"),
    ("roteiro-to-plan.js", "Alinhando o roteiro com a fala"), ("jogadores.py", "Buscando fotos e imagens"),
    ("lances.py", "Buscando os lances"), ("horizontal.mp4", "Render horizontal (YouTube)"), ("conferir.py", "Conferindo cor e volume"),
    ("vertical_completo.mp4", "Render vertical completo"), ("--cut", "Cortes 9:16"), ("thumb.py", "Fazendo as thumbs"),
    ("Pronto:", "Pronto"),
    # react / galo / vertical
    ("react.py", "Montando o react"), ("passagem.py", "Lendo seus gestos e montando o elenco"), ("vertical916.py", "Fazendo o 9:16"),
    # vlog
    ("1/5 cor", "Convertendo a cor (HDR → SDR)"), ("2/5 ouvindo", "Ouvindo e olhando os clipes"), ("3/5 roteiro", "Montando o roteiro do vlog"),
    ("4/5 montando", "Cortando e montando o vlog"), ("5/5 trilha", "Colocando a trilha"),
]

TIPOS = {  # tipo de edição → arquivos que precisa
    "roteiro": {"nome": "Vídeo com roteiro", "arquivos": ["video"]},
    "reels": {"nome": "Reels com roteiro (9:16)", "arquivos": ["video"]},
    "react": {"nome": "DETTO REAGE", "arquivos": ["video", "tela", "original"]},
    "galo": {"nome": "Galo — elenco passando", "arquivos": ["video"]},
    "vertical": {"nome": "Vertical de vídeo pronto", "arquivos": ["video"]},
    "vlog": {"nome": "Vlog", "arquivos": []},
}
DRIVE = None  # pasta do Google Drive para computador (painel → Configurações)
NOME_ARQ = {"video": "a gravação", "tela": "a gravação da tela", "original": "o vídeo original"}


def pasta_padrao():
    if os.name == "nt" and Path("E:/").exists():
        return Path("E:/DETTO/edicao")
    return Path.home() / "DETTO" / "edicao"


def slug(s, n=50):
    s = unicodedata.normalize("NFC", str(s or "")).strip()
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s[:n].strip() or "video"


def le(f, padrao):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def grava(f, d):
    Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def pasta_de(i):
    p = (ED / slug(i, 120)).resolve()
    if p.parent != ED.resolve() or not p.exists():
        raise ValueError("edição não encontrada")
    return p


def info(p):
    return le(p / "painel.json", {})


def muda_info(p, **kw):
    with TRAVA:
        d = info(p)
        d.update(kw)
        grava(p / "painel.json", d)
        return d


def video_de(p):
    d = info(p)
    v = p / d.get("video", "")
    return v if d.get("video") and v.exists() else None


def job_de(p):
    v = video_de(p)
    return v.with_name(v.stem + "_job") if v else None


def tam_pasta(p):
    t = 0
    for r, _, fs in os.walk(p):
        for f in fs:
            try:
                t += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass
    return t


_ETAPA_CACHE = {}


def registro(p, n=40):
    """últimas linhas do registro da edição + a etapa atual (a última que apareceu)"""
    f = p / "painel_log.txt"
    if not f.exists():
        return [], ""
    st = f.stat()
    with open(f, "rb") as fh:
        fh.seek(max(0, st.st_size - 24000))
        txt = fh.read().decode("utf-8", "replace")
    linhas = [l.rstrip() for l in re.split(r"[\r\n]+", txt) if l.strip()]
    chave_c = (st.st_size, st.st_mtime)
    guardado = _ETAPA_CACHE.get(str(f))
    etapa = guardado[1] if guardado and guardado[0] == chave_c else None
    if etapa is None:
        # só as linhas de comando (">> ...") e o "Pronto:" decidem a etapa
        etapa, pos = "", -1
        with open(f, encoding="utf-8", errors="replace") as fh:
            marcos = [l for l in fh if l.startswith(">>") or l.startswith("Pronto:") or " começando: " in l or re.match(r"^\d/5 ", l)]
        for idx, l in enumerate(marcos):
            for chave, nome in ETAPAS:
                if chave in l and idx >= pos:
                    pos, etapa = idx, nome
        _ETAPA_CACHE[str(f)] = (chave_c, etapa)
    return linhas[-n:], etapa


def saidas(p):
    rel = lambda f: str(f.relative_to(p)).replace("\\", "/")  # noqa: E731
    if info(p).get("tipo", "roteiro") not in ("roteiro", "reels"):
        pasta = p / "saidas"
        vids = [{"rel": rel(f), "nome": f.name, "tam": f.stat().st_size, "quando": dt.datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m %H:%M")}
                for f in sorted(pasta.glob("*.mp4")) if not f.name.startswith("vlog_")] if pasta.exists() else []
        imgs = [{"rel": rel(f), "nome": f.name} for f in sorted(pasta.glob("*.jpg"))] if pasta.exists() else []
        th = pasta / "thumbs"
        if th.exists():  # thumbs virais (react/vlog)
            imgs += [{"rel": rel(f), "nome": f.name} for f in [th / "thumbs.jpg"] + sorted(th.glob("thumb_*.jpg")) if f.exists()]
        return {"videos": vids, "imagens": imgs, "textos": {}}
    job = job_de(p)
    if not job or not job.exists():
        return {"videos": [], "imagens": [], "textos": {}}
    ordem = lambda f: (0 if f.stem.startswith("reels") else 0 if f.stem.startswith("horizontal")  # noqa: E731
                       else 1 if f.stem.startswith("vertical_completo") else 2, f.name)
    vids = [{"rel": rel(f), "nome": f.name, "tam": f.stat().st_size, "quando": dt.datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m %H:%M")}
            for f in sorted(job.glob("*.mp4"), key=ordem)]
    imgs = []
    for nome in ("thumbs/thumbs.jpg", "conferencia.jpg", "imagens_conferir.jpg", "lances_conferir.jpg"):
        if (job / nome).exists():
            imgs.append({"rel": rel(job / nome), "nome": nome.split("/")[-1]})
    imgs += [{"rel": rel(f), "nome": f.name} for f in sorted((job / "thumbs").glob("thumb_*.jpg"))] if (job / "thumbs").exists() else []
    textos = {}
    for nome in ("conferencia.txt", "ajustes.txt"):
        if (job / nome).exists():
            textos[nome] = (job / nome).read_text(encoding="utf-8", errors="replace")[:6000]
    return {"videos": vids, "imagens": imgs, "textos": textos}


def lista():
    if not ED.exists():
        return []
    out = []
    for p in sorted((x for x in ED.iterdir() if x.is_dir() and (x / "painel.json").exists()), key=lambda x: x.name, reverse=True):
        d = info(p)
        reg, etapa = registro(p) if d.get("status") in ("editando", "erro", "pronto", "interrompido", "cancelado") else ([], "")
        img_n = len([f for f in (p / "imagens").glob("*") if f.suffix.lower() in IMG_EXT]) if (p / "imagens").exists() else 0
        dur = None
        if d.get("inicio"):
            fim = d.get("fim") or time.time()
            dur = int(fim - d["inicio"])
        out.append({
            "id": p.name, "titulo": d.get("titulo") or p.name, "status": d.get("status", "rascunho"), "opcoes": d.get("opcoes", {}),
            "tipo": d.get("tipo", "roteiro"), "tipo_nome": TIPOS.get(d.get("tipo", "roteiro"), {}).get("nome", ""), "extra": d.get("extra", {}),
            "video": d.get("video", ""), "roteiro": (p / "roteiro_enviado.txt").exists() or bool(job_de(p) and (job_de(p) / "roteiro.txt").exists()),
            "imagens": img_n, "criado": d.get("criado", ""), "duracao": dur, "etapa": etapa, "registro": reg if d.get("status") != "pronto" else reg[-8:],
            "erro": d.get("erro", ""), "tam": tam_pasta(p), "saidas": saidas(p) if d.get("status") in ("pronto", "erro", "interrompido", "cancelado", "editando") else None,
            "na_frente": sum(1 for q in ED.iterdir() if q.is_dir() and info(q).get("status") == "na_fila" and info(q).get("pedido", 0) < d.get("pedido", 0))
            if d.get("status") == "na_fila" else 0,
        })
    return out


def novo(d):
    ED.mkdir(parents=True, exist_ok=True)
    titulo = slug(d.get("titulo") or "video")
    nome = f"{dt.datetime.now():%Y-%m-%d %H%M} {titulo}"
    p = ED / nome
    i = 2
    while p.exists():
        p = ED / f"{nome} {i}"
        i += 1
    p.mkdir()
    (p / "imagens").mkdir()
    op = d.get("opcoes") or {}
    opcoes = {"teste": bool(op.get("teste")), "sem_lances": bool(op.get("sem_lances")), "sem_thumbs": bool(op.get("sem_thumbs")),
              "sem_verticais": bool(op.get("sem_verticais")), "fps": 30 if str(op.get("fps")) == "30" else 60,
              "sfx": str(op.get("sfx") or "0.3"), "postar": [x for x in op.get("postar", []) if re.fullmatch(r"(instagram|tiktok):[\w.]+", x)]}
    tipo = d.get("tipo") if d.get("tipo") in TIPOS else "roteiro"
    ex = d.get("extra") or {}
    extra = {"jogo": str(ex.get("jogo", ""))[:120], "time": str(ex.get("time") or "Atlético Mineiro")[:60], "com_placar": bool(ex.get("com_placar")),
             "formato": "vertical" if ex.get("formato") == "vertical" else "horizontal", "faixa": str(ex.get("faixa", ""))[:120],
             "grafico": ex.get("grafico") if ex.get("grafico") in ("pip", "tela", "dividido") else "pip",
             "partes": max(0, min(180, int(float(ex.get("partes") or 0)))),
             "pasta": str(ex.get("pasta") or "")[:400], "estilo": str(ex.get("estilo") or "")[:300],
             "duracao": max(1.0, min(60.0, float(ex.get("duracao") or 10))), "legendas": ex.get("legendas") if ex.get("legendas") in (True, False) else None}
    grava(p / "painel.json", {"titulo": titulo, "tipo": tipo, "extra": extra, "status": "rascunho",
                              "criado": dt.datetime.now().strftime("%d/%m %H:%M"), "opcoes": opcoes})
    if str(d.get("roteiro_texto") or "").strip():
        (p / "roteiro_enviado.txt").write_text(d["roteiro_texto"].strip() + "\n", encoding="utf-8")
    return {"id": p.name}


def recebe(h, q):
    """arquivos da edição: tipo=video (a gravação), roteiro (.txt) ou imagem (vai para imagens\\ com o nome que tem)"""
    p = pasta_de(q.get("id", ""))
    tipo = q.get("tipo")
    nome = Path(slug(q.get("nome", "arquivo"), 120)).name
    ext = Path(nome).suffix.lower()
    if tipo in ("video", "tela", "original"):
        if ext not in VIDEO_EXT:
            raise ValueError(f"{NOME_ARQ[tipo]} precisa ser vídeo (.mp4, .mov ...)")
        alvo = p / (f"{info(p).get('titulo', 'video')}{ext}" if tipo == "video" else f"{tipo}{ext}")
    elif tipo == "roteiro":
        if ext not in (".txt", ".md", ".docx"):
            raise ValueError("roteiro: mande .txt (ou .docx)")
        alvo = p / ("roteiro_enviado" + ext)
    elif tipo == "clipe":  # vlog: vários clipes enviados pela tela
        if ext not in VIDEO_EXT:
            raise ValueError("clipe: só vídeo (.mp4, .mov ...)")
        (p / "clipes").mkdir(exist_ok=True)
        alvo = p / "clipes" / nome
    elif tipo == "imagem":
        if ext not in IMG_EXT:
            raise ValueError("imagem: .jpg, .png ou .webp")
        alvo = p / "imagens" / nome
    else:
        raise ValueError("tipo?")
    tam = int(h.headers.get("Content-Length") or 0)
    tmp = alvo.with_name(alvo.name + ".parte")
    with open(tmp, "wb") as f:
        falta = tam
        while falta > 0:
            b = h.rfile.read(min(4 * 1024 * 1024, falta))
            if not b:
                break
            f.write(b)
            falta -= len(b)
    if falta > 0:
        tmp.unlink(missing_ok=True)
        raise ValueError("envio interrompido")
    os.replace(tmp, alvo)
    if tipo == "roteiro" and ext == ".docx":
        _docx_para_txt(alvo)
    if tipo in ("video", "tela", "original"):
        muda_info(p, **{tipo: alvo.name})
    return {"ok": True}


def _docx_para_txt(f):
    """roteiro em Word → texto (parágrafos)"""
    import zipfile
    from xml.etree import ElementTree as ET
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(f) as z:
        raiz = ET.fromstring(z.read("word/document.xml"))
    linhas = ["".join(t.text or "" for t in par.iter(ns + "t")) for par in raiz.iter(ns + "p")]
    f.with_suffix(".txt").write_text("\n".join(linhas).strip() + "\n", encoding="utf-8")
    f.unlink()


def de_caminho(d):
    """a gravação já está no PC: liga o arquivo (mesmo disco = não ocupa espaço de novo) ou copia"""
    p = pasta_de(d.get("id", ""))
    campo = d.get("campo") if d.get("campo") in ("video", "tela", "original") else "video"
    orig = Path(str(d.get("caminho", "")).strip().strip('"'))
    if not orig.is_file() or orig.suffix.lower() not in VIDEO_EXT:
        raise ValueError(f"não achei {NOME_ARQ[campo]}: {orig}")
    alvo = p / (f"{info(p).get('titulo', 'video')}{orig.suffix.lower()}" if campo == "video" else f"{campo}{orig.suffix.lower()}")
    alvo.unlink(missing_ok=True)
    try:
        os.link(orig, alvo)
    except OSError:
        shutil.copyfile(orig, alvo)
    muda_info(p, **{campo: alvo.name})
    if campo == "video":
        junto_do_video(p, orig)
    return {"ok": True}


def junto_do_video(p, orig):
    """vídeo pelo caminho (ex.: a pasta do Drive "rodada 31"): pega também o roteiro (.txt/.docx) e a pasta imagens\\
    que estão ao lado dele — antes só ia o vídeo e o editar.py pedia o roteiro ao Gemini"""
    pasta = orig.parent
    if not any((p / f"roteiro_enviado{e}").exists() for e in (".txt", ".md")):
        cands = [orig.with_suffix(e) for e in (".txt", ".docx", ".md")] + [orig.with_name(orig.stem + "_roteiro.txt")]
        outros = sorted((f for f in pasta.iterdir() if f.is_file() and f.suffix.lower() in (".txt", ".docx", ".md")
                         and not f.name.lower().startswith(("leia-me", "leiame", "~$"))), key=lambda f: -f.stat().st_mtime)
        rot = next((c for c in cands if c.is_file()), None) or (outros[0] if outros else None)
        if rot:
            alvo = p / ("roteiro_enviado" + rot.suffix.lower())
            shutil.copyfile(rot, alvo)
            if alvo.suffix == ".docx":
                _docx_para_txt(alvo)
            muda_info(p, roteiro_de=str(rot))
    imgs = pasta / "imagens"
    if imgs.is_dir():
        (p / "imagens").mkdir(exist_ok=True)
        for f in imgs.iterdir():
            if f.is_file() and f.suffix.lower() in IMG_EXT and not (p / "imagens" / f.name).exists():
                shutil.copyfile(f, p / "imagens" / f.name)


def prepara_roteiro(p):
    """o roteiro mandado vira <título>.txt ao lado da gravação (o editar.py acha sozinho)"""
    env = p / "roteiro_enviado.txt"
    v = video_de(p)
    if env.exists() and v:
        alvo = v.with_suffix(".txt")
        if not alvo.exists() or alvo.read_bytes() != env.read_bytes():
            shutil.copyfile(env, alvo)


def pasta_vlog(p):
    """os clipes do vlog: a pasta escolhida (Google Drive) ou os enviados pela tela"""
    ex = info(p).get("extra", {})
    if ex.get("pasta") and Path(ex["pasta"]).is_dir():
        return Path(ex["pasta"])
    if (p / "clipes").is_dir():
        return p / "clipes"
    return None


def drive_raiz():
    """onde está o Google Drive para computador (a pasta configurada no painel ou a padrão)"""
    cands = [DRIVE] if DRIVE else []
    for letra in "GHIJKFE":
        for nome in ("Meu Drive", "My Drive"):
            cands.append(f"{letra}:/{nome}")
    cands += [str(Path.home() / "Google Drive"), str(Path.home() / "Meu Drive")]
    for c in cands:
        if c and Path(c).is_dir():
            return Path(c)
    return None


def drive_pastas(d=None):
    """pastas com vídeos dentro do Drive (até 3 níveis), mais recentes primeiro — para escolher o vlog"""
    raiz = drive_raiz()
    if not raiz:
        return {"raiz": "", "pastas": []}
    base = raiz / "DETTO" / "vlogs" if (raiz / "DETTO" / "vlogs").is_dir() else raiz
    out = []
    for prof in range(3):
        for p in (base.glob("/".join(["*"] * (prof + 1)))):
            try:
                if p.is_dir() and not p.name.startswith("."):
                    vids = [f for f in p.iterdir() if f.suffix.lower() in VIDEO_EXT]
                    if vids:
                        out.append({"pasta": str(p), "nome": str(p.relative_to(raiz)), "n": len(vids),
                                    "quando": max(f.stat().st_mtime for f in vids)})
            except OSError:
                continue
        if len(out) > 80:
            break
    out.sort(key=lambda x: -x["quando"])
    return {"raiz": str(raiz), "base": str(base), "pastas": out[:60]}


def iniciar(d):
    p = pasta_de(d.get("id", ""))
    dd = info(p)
    for campo in TIPOS.get(dd.get("tipo", "roteiro"), TIPOS["roteiro"])["arquivos"]:
        if not dd.get(campo) or not (p / dd[campo]).exists():
            raise ValueError(f"falta {NOME_ARQ[campo]}")
    if dd.get("tipo") == "vlog":
        pasta = pasta_vlog(p)
        if not pasta or not any(f.suffix.lower() in VIDEO_EXT for f in pasta.iterdir()):
            raise ValueError("vlog: escolha a pasta do Drive com os clipes ou envie os clipes")
    if info(p).get("status") == "editando":
        raise ValueError("já está editando")
    muda_info(p, status="na_fila", pedido=time.time(), erro="", inicio=None, fim=None)
    return {"ok": True}


def roteiro(d):
    """o roteiro atual: o do job (o que o editar.py usou, com seus ajustes) ou o que você mandou"""
    p = pasta_de(d.get("id", ""))
    job = job_de(p)
    for f in ([job / "roteiro.txt"] if job else []) + [p / "roteiro_enviado.txt"]:
        if f.exists():
            return {"texto": f.read_text(encoding="utf-8", errors="replace"), "de": "job" if f.parent == job else "enviado"}
    return {"texto": "", "de": ""}


def refazer(d):
    """salva o roteiro ajustado e edita de novo (transcrição e rosto são reaproveitados)"""
    p = pasta_de(d.get("id", ""))
    if "texto" in d and str(d["texto"]).strip():
        txt = str(d["texto"]).replace("\r\n", "\n").strip() + "\n"
        job = job_de(p)
        if job:
            job.mkdir(exist_ok=True)
            (job / "roteiro.txt").write_text(txt, encoding="utf-8")
            # o editar.py só troca o roteiro do job se o da pasta for mais novo: o da pasta fica igual
            v = video_de(p)
            if v and v.with_suffix(".txt").exists():
                v.with_suffix(".txt").write_text(txt, encoding="utf-8")
                os.utime(job / "roteiro.txt", None)
        (p / "roteiro_enviado.txt").write_text(txt, encoding="utf-8")
    if "extra" in d:
        ex = info(p).get("extra", {})
        ex.update({k: v for k, v in d["extra"].items() if k in ("jogo", "time", "com_placar", "formato", "faixa", "grafico", "partes",
                                                                 "estilo", "duracao", "legendas")})
        muda_info(p, extra=ex)
    if "plano" in d:  # vlog: refazer com o mesmo plano (ou do zero)
        muda_info(p, refazer_plano=bool(d["plano"]))
    if d.get("refazer_gestos"):
        v = video_de(p)
        if v:
            Path(str(v) + ".roteiro.json").unlink(missing_ok=True)
    if "opcoes" in d:
        op = info(p).get("opcoes", {})
        op.update({k: v for k, v in d["opcoes"].items() if k in ("teste", "sem_lances", "sem_thumbs", "sem_verticais", "fps", "sfx")})
        muda_info(p, opcoes=op)
    return iniciar({"id": p.name})


def cancelar(d):
    p = pasta_de(d.get("id", ""))
    if PROC["id"] == p.name and PROC["p"] and PROC["p"].poll() is None:
        mata(PROC["p"])
    st = info(p).get("status")
    if st in ("na_fila", "editando"):
        muda_info(p, status="cancelado", fim=time.time())
    return {"ok": True}


def mata(proc):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        proc.kill()


def apagar(d):
    p = pasta_de(d.get("id", ""))
    cancelar(d)
    time.sleep(0.5)
    shutil.rmtree(p, ignore_errors=True)
    return {"ok": True}


def arquivo(i, rel):
    p = pasta_de(i)
    f = (p / rel).resolve()
    if p not in f.parents or not f.is_file():
        raise ValueError("arquivo?")
    return f


def comando(p):
    d = info(p)
    op = d.get("opcoes", {})
    ex = d.get("extra", {})
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        exe = exe.with_name("python.exe")
    tipo = d.get("tipo", "roteiro")
    if tipo != "roteiro":
        (p / "saidas").mkdir(exist_ok=True)
        titulo = d.get("titulo", "video")
    if tipo == "react":
        cfg = {"camera": str(p / d["video"]), "tela": str(p / d["tela"]), "original": str(p / d["original"]),
               "titulo": ex.get("faixa") or titulo, "formato": ex.get("formato", "horizontal"), "mascote": "", "patrocinio": "",
               "offset_camera": None, "saida": str(p / "saidas" / f"{titulo} react{' vertical' if ex.get('formato') == 'vertical' else ''}.mp4")}
        grava(p / "react.json", cfg)
        return [str(exe), "-u", str(TOOLS / "react" / "react.py"), str(p / "react.json")]
    if tipo == "galo":
        cfg = {"video": str(p / d["video"]), "time": ex.get("time") or "Atlético Mineiro", "com_placar": bool(ex.get("com_placar")),
               "saida": str(p / "saidas" / f"{titulo} galo.mp4"), "trabalho": str(p / "galo_tmp")}
        if ex.get("jogo"):
            cfg["jogo"] = ex["jogo"]
        grava(p / "jogo.json", cfg)
        return [str(exe), "-u", str(TOOLS / "galo" / "passagem.py"), str(p / "jogo.json")]
    if tipo == "vlog":
        cmd = [str(exe), "-u", str(TOOLS / "vlog" / "vlog.py"), str(pasta_vlog(p)), "--saida", str(p / "saidas"), "--titulo", titulo,
               "--formato", ex.get("formato", "horizontal"), "--duracao", str(ex.get("duracao") or 10)]
        if ex.get("estilo"):
            cmd += ["--estilo", ex["estilo"]]
        if ex.get("legendas") is not None:
            cmd += ["--legendas", "1" if ex["legendas"] else "0"]
        if d.get("refazer_plano") and (p / "saidas" / "plano.json").exists():
            cmd.append("--refazer")
        return cmd
    if tipo == "vertical":
        cmd = [str(exe), "-u", str(TOOLS / "vertical916.py"), str(p / d["video"]), str(p / "saidas" / f"{titulo} 9x16.mp4"),
               "--grafico", ex.get("grafico", "pip")]
        if ex.get("partes"):
            cmd += ["--partes", str(ex["partes"])]
        return cmd
    cmd = [str(exe), "-u", str(TOOLS / "editar.py"), str(video_de(p)), "--titulo", d.get("titulo", ""), "--fps", str(op.get("fps", 60))]
    if tipo == "reels":   # o vídeo inteiro vira UM reels 9:16, com o gancho na tela
        cmd.append("--reels")
    if op.get("canal") in ("galo", "noticias", "vlog", "sem"):
        cmd += ["--canal", op["canal"]]
    for chave, flag in (("teste", "--teste"), ("sem_lances", "--sem-lances"), ("sem_thumbs", "--sem-thumbs"), ("sem_verticais", "--sem-verticais")):
        if op.get(chave):
            cmd.append(flag)
    if op.get("sfx") not in (None, "", "0.3"):
        cmd += ["--sfx", str(op["sfx"])]
    return cmd


def proximo_da_fila():
    if not ED.exists():
        return None
    fila = [p for p in ED.iterdir() if p.is_dir() and info(p).get("status") == "na_fila"]
    return min(fila, key=lambda p: info(p).get("pedido", 0)) if fila else None


def thumbs_depois(p, log=print):
    """react e vlog (horizontais, YouTube): thumbs virais — você + quadro do vídeo + assunto — em saidas\\thumbs\\
    (roda separado, não segura a próxima edição)"""
    d = info(p)
    tipo, ex = d.get("tipo", "roteiro"), d.get("extra", {}) or {}
    if tipo not in ("react", "vlog") or ex.get("formato") == "vertical":
        return
    pasta = p / "saidas"
    vids = sorted([f for f in pasta.glob("*.mp4") if not f.name.startswith("vlog_")], key=lambda f: -f.stat().st_size) if pasta.exists() else []
    if not vids:
        return
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        exe = exe.with_name("python.exe")
    if tipo == "react":
        rosto, quadro, estilo = [str(p / d["video"])], str(p / d["original"]), "futebol"
    else:
        pv = pasta_vlog(p)
        clipes = sorted(f for f in pv.rglob("*") if f.suffix.lower() in (".mp4", ".mov", ".m4v")) if pv else []
        rosto, quadro = [str(c) for c in clipes[:: max(1, len(clipes) // 6)][:6]] + [str(vids[0])], str(vids[0])
        estilo = "gameplay" if re.search(r"gameplay|game|jogando|fifa|ea fc|efootball", d.get("titulo", "").lower()) else "vlog"
    cmd = [str(exe), "-u", str(TOOLS / "thumb" / "viral.py"), "--rosto", *rosto, "--quadro", quadro, "--assunto",
           ex.get("faixa") or d.get("titulo", ""), "--estilo", estilo, "--saida", str(pasta / "thumbs")]
    logf = open(p / "painel_log.txt", "a", encoding="utf-8")
    logf.write(f"\n{dt.datetime.now():%d/%m %H:%M} thumbs: fazendo as thumbs virais...\n")
    logf.flush()
    extra = {"creationflags": 0x08000000} if os.name == "nt" else {}
    subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, cwd=str(PONTE),
                     env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}, **extra)
    log(f"edição {p.name}: fazendo as thumbs")


# linhas do registro que NÃO explicam nada (barra de progresso do ffmpeg, avisos soltos)
_RUIDO = re.compile(r"^(frame=|size=|\[|Press \[q\]|\s*$|Aviso:)", re.I)
_ERRO = re.compile(r"erro|error|exception|traceback|not found|no such|falh|não achei|não consegui|sys\.exit|"
                   r"espaço|space left|permission|recusad|invalid|inválid", re.I)


def motivo_do_erro(p, codigo):
    """o POR QUÊ, tirado do registro do job — o painel só dizia "veja o registro" e você ficava sem saber"""
    f = Path(p) / "painel_log.txt"
    try:
        linhas = [l.strip() for l in f.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    except OSError:
        linhas = []
    uteis = [l for l in linhas[-120:] if not _RUIDO.match(l)]
    achou = [l for l in uteis if _ERRO.search(l)]
    motivo = (achou[-1] if achou else (uteis[-1] if uteis else ""))[:300]
    return (f"a edição parou (código {codigo})" + (f": {motivo}" if motivo else " — veja o registro"))


OCUPADO = lambda: False  # noqa: E731  (o painel troca: um canal montando = a próxima edição espera)


def laco(log=print, ao_terminar=None):
    """roda as edições da fila, uma por vez"""
    # o painel foi fechado no meio de uma edição: ela fica "interrompida" (botão Refazer)
    if ED.exists():
        for p in ED.iterdir():
            if p.is_dir() and info(p).get("status") == "editando":
                muda_info(p, status="interrompido", erro="o painel/PC foi desligado no meio da edição")
    while True:
        try:
            pr = PROC["p"]
            if pr is not None and pr.poll() is not None:
                p = ED / PROC["id"]
                if p.exists() and info(p).get("status") == "editando":
                    ok = pr.returncode == 0
                    muda_info(p, status="pronto" if ok else "erro", fim=time.time(),
                              erro="" if ok else motivo_do_erro(p, pr.returncode))
                    shutil.rmtree(p / "galo_tmp", ignore_errors=True)
                    log(f"edição {p.name}: {'PRONTA' if ok else 'ERRO'}")
                    if ok:
                        try:
                            thumbs_depois(p, log)
                        except Exception as e:
                            log(f"edição {p.name}: thumbs não saíram ({e})")
                    if ok and ao_terminar:
                        try:
                            ao_terminar(p)
                        except Exception as e:
                            log(f"edição {p.name}: não entrou na fila de postagem ({e})")
                PROC.update(id=None, p=None)
            if PROC["p"] is None and not OCUPADO():
                p = proximo_da_fila()
                if p:
                    prepara_roteiro(p)
                    logf = open(p / "painel_log.txt", "w", encoding="utf-8")
                    logf.write(f"{dt.datetime.now():%d/%m %H:%M} começando: {' '.join(comando(p))}\n")
                    logf.flush()
                    extra = {"creationflags": 0x08000000 | 0x00000200} if os.name == "nt" else {"start_new_session": True}
                    PROC.update(id=p.name, p=subprocess.Popen(comando(p), stdout=logf, stderr=subprocess.STDOUT, cwd=str(PONTE),
                                                              env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}, **extra))
                    muda_info(p, status="editando", inicio=time.time(), fim=None)
                    log(f"edição {p.name}: começou")
        except Exception as e:
            log(f"edição: erro no laço ({e})")
        time.sleep(3)
