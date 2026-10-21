# -*- coding: utf-8 -*-
"""CANAL DE VLOGS automático: você sobe os clipes no Google Drive → o editor de vlog monta → vídeo longo + Shorts → YouTube.

    python tools\\canal\\canal_vlog.py              → uma rodada: procura vlogs novos na pasta do Drive e monta
    python tools\\canal\\canal_vlog.py --login      → liga o canal de vlogs no YouTube (uma vez)
    python tools\\canal\\canal_vlog.py --postar "<pasta do pronto>"   → posta um que estava esperando aprovação
    python tools\\canal\\canal_vlog.py --pasta "D:\\canal_vlogs"

COMO USAR: no Drive, dentro de  Meu Drive\\DETTO\\canal_vlogs\\  crie uma pasta por vlog (ex.: "Viagem BH") e suba
os clipes nela. Quando a pasta fica 20 min sem arquivo novo (upload terminou), a rodada monta o vlog.
Opcional: um info.txt na pasta do vlog com linhas  titulo: ...  estilo: ...  duracao: 12
"Postar sozinho" (auto_postar) desligado = fica esperando você aprovar no painel (aba Canais).

PASTA DO CANAL (padrão E:\\DETTO\\canal_vlogs): config.json, token.json (login do YouTube deste canal),
prontos\\<data - vlog>\\ (video.mp4, thumb, short_1.mp4..., post.json, edicao\\ = o trabalho do editor de vlog),
historico.json (vlogs já feitos). A credencial do Google (client_secret.json) pode ficar em E:\\DETTO\\youtube\\
(vale para os dois canais).
"""
import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
PONTE = TOOLS.parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(TOOLS))
import comum  # noqa: E402

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv", ".avi", ".mts"}
TEMP_EXT = {".tmp", ".part", ".partial", ".crdownload", ".download"}

CONFIG_PADRAO = {
    "drive": "",  # a pasta dos vlogs no Drive; vazio = <Meu Drive>\DETTO\canal_vlogs
    "nome_canal": "EVERTON LOPES",  # o canal de vlogs, gameplays e outros vídeos
    "assinatura": ("🎬 EVERTON LOPES — vlogs, gameplays e o meu dia a dia (futebol, viagens, resenha).\n"
                   "🔔 Inscreva-se e ative o sininho.\n⚽ Notícias do Galo: DETTO GALO NOTÍCIAS\n📲 Instagram e TikTok: @detto.galo"),
    "estilo": "cinematográfico, estilo AM3NIC (cortes secos, nome dos lugares, notas curtas em minúsculas)",
    "duracao": 10,
    "auto_postar": False,  # False = espera você aprovar no painel; True = posta sozinho
    "shorts": 2,
    "short_s": 58,
    "horas_entre_shorts": 3,
    "privacidade": "public",
    "espera_min": 20,  # minutos sem arquivo novo na pasta = upload terminou
    "tags_padrao": ["everton lopes", "vlog", "detto", "dettogalo"],
}


def log(m):
    print(m, flush=True)


def pasta_padrao():
    if os.name == "nt" and Path("E:/").exists():
        return Path("E:/DETTO/canal_vlogs")
    return Path.home() / "DETTO" / "canal_vlogs"


def prepara(pasta):
    (pasta / "prontos").mkdir(parents=True, exist_ok=True)
    f = pasta / "config.json"
    if not f.exists():
        comum.grava(f, CONFIG_PADRAO)
    cfg = dict(CONFIG_PADRAO)
    cfg.update(comum.le(f, {}) or {})
    if "Afreim" in str(cfg.get("estilo", "")):  # o padrão antigo → o estilo que ele escolheu (19/out: AM3NIC)
        cfg["estilo"] = CONFIG_PADRAO["estilo"]
    if not cfg.get("nome_canal"):
        cfg["nome_canal"] = CONFIG_PADRAO["nome_canal"]  # 20/out: canal EVERTON LOPES (vlogs + gameplays)
    return cfg


def raiz_drive(cfg):
    """a pasta onde ficam as pastas dos vlogs"""
    if cfg.get("drive"):
        return Path(cfg["drive"])
    if os.environ.get("DETTO_DRIVE") and Path(os.environ["DETTO_DRIVE"]).is_dir():
        return Path(os.environ["DETTO_DRIVE"]) / "DETTO" / "canal_vlogs"
    sys.path.insert(0, str(TOOLS / "painel"))
    try:
        from edicao import drive_raiz

        r = drive_raiz()
    except Exception:
        r = None
    return (r / "DETTO" / "canal_vlogs") if r else None


def vlogs_novos(cfg, hist):
    """pastas do Drive com vídeos, ainda não feitas e paradas há espera_min (o upload terminou)"""
    raiz = raiz_drive(cfg)
    if not raiz:
        log("Google Drive não encontrado: instale o Google Drive para computador ou ponha o caminho em config.json → \"drive\"")
        return []
    raiz.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(raiz.iterdir()):
        if not p.is_dir() or p.name.startswith(".") or p.name in hist["feitos"]:
            continue
        arqs = [f for f in p.iterdir() if f.is_file()]
        vids = [f for f in arqs if f.suffix.lower() in VIDEO_EXT and not f.stem.endswith(" SDR")]
        if not vids:
            continue
        if any(f.suffix.lower() in TEMP_EXT or f.name.startswith("~") for f in arqs):
            log(f"{p.name}: ainda subindo")
            continue
        parado = (time.time() - max(f.stat().st_mtime for f in arqs)) / 60
        if parado < float(cfg.get("espera_min", 20)):
            log(f"{p.name}: {len(vids)} clipes, último chegou há {parado:.0f} min — espero {cfg.get('espera_min', 20)} min sem novidade")
            continue
        out.append(p)
    return out


def info_txt(p):
    """info.txt opcional na pasta do vlog: titulo / estilo / duracao"""
    d = {}
    f = p / "info.txt"
    if f.exists():
        for l in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*(titulo|título|estilo|duracao|duração)\s*:\s*(.+)", l, re.I)
            if m:
                d[m.group(1).lower().replace("í", "i").replace("çã", "ca")] = m.group(2).strip()
    return d


def roda(cmd, logf):
    """roda um passo mostrando o registro"""
    with open(logf, "a", encoding="utf-8") as g:
        g.write(f"\n{dt.datetime.now():%d/%m %H:%M} {' '.join(str(c) for c in cmd)}\n")
        g.flush()
        p = subprocess.Popen([str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(PONTE),
                             env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
        for linha in iter(p.stdout.readline, b""):
            t = linha.decode("utf-8", "replace")
            g.write(t)
            g.flush()
            print(t, end="", flush=True)
        return p.wait()


def duracao(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def melhores_janelas(video, n, tam):
    """os n trechos de tam segundos com mais "vida" (volume), sem sobrepor; fora o fim (despedida)"""
    import numpy as np

    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-ac", "1", "-ar", "8000", "-f", "f32le", "-"], capture_output=True)
    a = np.frombuffer(r.stdout, np.float32)
    seg = len(a) // 8000
    if seg < tam + 5:
        return [0.0] if seg >= 15 else []
    rms = np.sqrt(np.square(a[: seg * 8000].reshape(seg, 8000)).mean(axis=1) + 1e-9)
    t = int(tam)
    soma = np.convolve(rms, np.ones(t), "valid")
    lim = max(1, len(soma) - 20)
    escolhidos = []
    for i in np.argsort(-soma[:lim]):
        if all(abs(int(i) - j) >= t for j in escolhidos):
            escolhidos.append(int(i))
        if len(escolhidos) >= n:
            break
    return sorted(float(i) for i in escolhidos)


def textos(plano, nome, info, cfg):
    """título, descrição, tags e texto da thumb (Gemini olhando o roteiro do vlog); sem Gemini: o nome da pasta"""
    falas = []
    for s in plano.get("secoes", []):
        for t in s.get("trechos", []):
            if t.get("texto"):
                falas.append(t["texto"])
    base = {"titulo": (info.get("titulo") or plano.get("titulo") or nome)[:95], "descricao": f"{info.get('titulo') or nome}",
            "tags": cfg.get("tags_padrao", []), "thumb_texto": (info.get("titulo") or nome).upper()[:30], "thumb_destaque": ""}
    if not os.environ.get("GEMINI_API_KEY"):
        return base
    sys.path.insert(0, str(TOOLS / "reels"))
    from reels import gemini_json

    g = gemini_json([{"text": f"""Você cuida de um canal de VLOGS no YouTube (estilo AM3NIC: cinematográfico, títulos curiosos tipo "MINHA CASA ESTÁ ABANDONADA?"), do canal "{cfg.get('nome_canal') or 'EVERTON LOPES'}" (vlogs e gameplays do Everton, o @detto.galo).
Vlog: "{info.get('titulo') or plano.get('titulo') or nome}". Partes: {', '.join(s.get('clima', '') for s in plano.get('secoes', []))}.
Textos e falas do vlog: {' | '.join(falas)[:6000]}
Responda SÓ JSON: {{"titulo": "<título chamativo até 90 letras, sem mentir>", "descricao": "<3 a 5 frases>",
"tags": ["<10 a 15 tags>"], "thumb_texto": "<2 a 4 palavras>", "thumb_destaque": "<1 palavra do thumb_texto>",
"shorts": ["<título curto para cada corte, até 60 letras>", "..."]}}"""}], temperatura=0.7)
    if g and g.get("titulo"):
        base.update({k: v for k, v in g.items() if v})
    return base


def monta(vlog, cfg, pasta):
    info = info_txt(vlog)
    pronto = pasta / "prontos" / f"{dt.datetime.now():%Y-%m-%d_%H%M} - {vlog.name}"
    pronto.mkdir(parents=True, exist_ok=True)
    reg = pronto / "registro.txt"
    ed = pronto / "edicao"
    comum.grava(pronto / "post.json", {"titulo": info.get("titulo") or vlog.name, "status": "montando", "origem": str(vlog),
                                       "criado": dt.datetime.now().isoformat(timespec="seconds")})
    log(f"\nVLOG {vlog.name}: montando (registro em {reg})")
    cmd = [sys.executable, TOOLS / "vlog" / "vlog.py", vlog, "--saida", ed, "--formato", "horizontal",
           "--estilo", info.get("estilo") or cfg["estilo"], "--duracao", str(info.get("duracao") or cfg["duracao"])]
    if info.get("titulo"):
        cmd += ["--titulo", info["titulo"]]
    if roda(cmd, reg) != 0 or not (ed / "vlog.mp4").exists():
        comum.grava(pronto / "post.json", {**comum.le(pronto / "post.json", {}), "status": "erro", "erro": "o editor de vlog parou — veja registro.txt"})
        raise RuntimeError("o editor de vlog parou (registro.txt)")
    video = pronto / "video.mp4"
    try:
        os.replace(ed / "vlog.mp4", video)
    except OSError:
        shutil.copyfile(ed / "vlog.mp4", video)
    plano = comum.le(ed / "plano.json", {}) or {}
    tx = textos(plano, vlog.name, info, cfg)
    # thumb: suas melhores reações + texto
    th = ""
    if roda([sys.executable, TOOLS / "thumb" / "thumb.py", video, "--texto", tx.get("thumb_texto", ""), "--destaque", tx.get("thumb_destaque", ""),
             "--saida", pronto / "thumbs"], reg) == 0 and (pronto / "thumbs" / "thumb_1.jpg").exists():
        shutil.copyfile(pronto / "thumbs" / "thumb_1.jpg", pronto / "thumb_1.jpg")
        th = "thumb_1.jpg"
    # Shorts: os trechos com mais vida, em 9:16 com recorte no rosto
    shorts = []
    tam = max(60.0, float(cfg.get("short_s", 62)))  # short nunca abaixo de 60 s
    for k, ini in enumerate(melhores_janelas(video, int(cfg.get("shorts", 0)), tam)):
        corte = pronto / f"corte_{k + 1}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ini:.2f}", "-t", f"{tam:.2f}", "-i", str(video), "-c:v", "libx264", "-crf", "16",
                        "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", str(corte)], check=True)
        sv = pronto / f"short_{k + 1}.mp4"
        if roda([sys.executable, TOOLS / "vertical916.py", corte, sv], reg) == 0 and sv.exists():
            tt = (tx.get("shorts") or [])
            shorts.append({"arquivo": sv.name, "titulo": tt[k] if k < len(tt) else tx["titulo"], "descricao": tx.get("descricao", "")[:200]})
        corte.unlink(missing_ok=True)
    tags = list(dict.fromkeys([t.strip("#") for t in tx.get("tags", [])] + cfg.get("tags_padrao", [])))[:15]
    descricao = tx.get("descricao", "")
    comentario = ""
    cred = Path(video).parent / "creditos_apoio.txt"
    if cred.exists():
        # cenas de apoio da internet (lugares): crédito na descrição e num comentário do canal
        linhas = [l for l in cred.read_text(encoding="utf-8").splitlines() if l.startswith("•")]
        if linhas:
            descricao += "\n\nCenas de apoio:\n" + "\n".join(linhas)
            comentario = "🎥 Créditos das cenas de apoio usadas neste vlog:\n" + "\n".join(linhas)
    if cfg.get("assinatura"):
        descricao += f"\n\n{cfg['assinatura']}"
    post = {"titulo": tx["titulo"], "descricao": descricao, "tags": tags, "video": "video.mp4", "thumb": th, "comentario": comentario,
            "shorts": shorts, "status": "aguardando", "origem": str(vlog), "criado": dt.datetime.now().isoformat(timespec="seconds"),
            "duracao": round(duracao(video))}
    comum.grava(pronto / "post.json", post)
    # disco: os clipes SDR e as partes do editor saem (o vídeo final fica)
    shutil.rmtree(ed / "clipes", ignore_errors=True)
    shutil.rmtree(ed / "partes", ignore_errors=True)
    return pronto


def main():
    ap = argparse.ArgumentParser(description="canal de vlogs automático")
    ap.add_argument("--pasta", default=str(pasta_padrao()))
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--preparar", action="store_true", help="só cria as pastas e o config.json")
    ap.add_argument("--postar", metavar="PASTA_DO_PRONTO")
    ap.add_argument("--nao-postar", action="store_true", help="monta e deixa esperando aprovação mesmo com 'postar sozinho' ligado")
    ap.add_argument("--vlog", help="(teste) monta esta pasta de clipes agora, sem esperar o Drive")
    a = ap.parse_args()
    pasta = Path(a.pasta)
    cfg = prepara(pasta)
    if a.preparar:
        return
    import youtube_up

    if a.login:
        youtube_up.credenciais(pasta, abrir_navegador=True)
        nome, cid = youtube_up.canal_logado(pasta)
        print(f"Ligado ao canal: {nome} ({cid}).")
        return
    if a.postar:
        comum.publica(pasta, Path(a.postar), cfg, log=log, sintetico=False, categoria="22")
        return
    hist = comum.le(pasta / "historico.json", {"feitos": {}}) or {"feitos": {}}
    novos = [Path(a.vlog)] if a.vlog else vlogs_novos(cfg, hist)
    if not novos:
        log("nenhum vlog novo no Drive")
        return
    for vlog in novos[:1]:  # um por rodada (o PC fica livre para o resto)
        hist["feitos"][vlog.name] = {"quando": dt.datetime.now().isoformat(timespec="seconds"), "status": "montando"}
        comum.grava(pasta / "historico.json", hist)
        try:
            pronto = monta(vlog, cfg, pasta)
        except Exception as e:
            hist["feitos"][vlog.name].update(status="erro", erro=str(e)[:300])
            comum.grava(pasta / "historico.json", hist)
            log(f"ERRO: {e}")
            continue
        hist["feitos"][vlog.name].update(status="pronto", pronto=str(pronto))
        comum.grava(pasta / "historico.json", hist)
        if cfg.get("auto_postar") and not a.nao_postar:
            comum.publica(pasta, pronto, cfg, log=log, sintetico=False, categoria="22")
        else:
            log(f"PRONTO, esperando você aprovar (painel → Canais): {pronto}")


if __name__ == "__main__":
    main()
