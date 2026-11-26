#!/usr/bin/env python3
"""O QUE FAZER COM CADA VIRAL QUE CAIU NA PASTA (06/nov, pedido dele).

O catcher (viral.py) já acha o vídeo que está explodindo e baixa. Faltava a DECISÃO: este aqui é para
REAGIR, para COPIAR o formato, ou só para NARRAR como notícia? Era ele quem olhava um por um.

Agora a IA olha 4 quadros + a fala do vídeo e responde uma das três, com o motivo — e cada resposta
LEVA O VÍDEO PARA O LUGAR CERTO do sistema, que já existe:
  reagir  → fica em videos_para_react\\ (é a entrada do react.py)
  copiar  → o link vai para o links.txt dos reels (o reels.py no modo TROCA refaz com a cara dele)
  narrar  → o assunto vai para pautas_virais.txt (o canal de notícias lê) e serve ao tools\\narrado

Uso:
    python tools\\viral\\decide.py                 # decide tudo que está na pasta e ainda não foi decidido
    python tools\\viral\\decide.py --arquivo x.mp4 # um só
    python tools\\viral\\decide.py --so-dizer      # decide e escreve, mas não mexe em nada
"""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent
for _p in (TOOLS, TOOLS / "reels", TOOLS / "viral"):
    sys.path.insert(0, str(_p))

REGRAS = """Você olha um vídeo curto que está VIRALIZANDO agora e diz o que um criador brasileiro de
futebol/humor (@detto.galo) deve fazer com ele. Só existem três respostas:

"reagir"  — tem algo acontecendo que rende comentário: declaração, polêmica, lance, gafe, reviravolta.
            O valor está em VER a cena e ouvir a opinião dele por cima.
"copiar"  — é um MEME de formato: uma pessoa fazendo/falando algo no começo e depois um corte para
            outra coisa (lance, cena, reação). O valor está no FORMATO, que ele refaz com a cara dele.
"narrar"  — é notícia/informação. O vídeo em si é fraco (print, texto na tela, locução genérica), mas o
            ASSUNTO é bom. Vale virar vídeo narrado, não react.

Regras duras:
- Se aparecer criança, crime sexual, suicídio, feminicídio ou corpo/violência explícita: responda
  "nenhum". Ele não traz esses assuntos.
- Se não der para dizer o que é com o que você está vendo, responda "nenhum" em vez de chutar.

Responda SÓ este JSON:
{"o_que":"reagir|copiar|narrar|nenhum","motivo":"uma frase curta","gancho":"a frase que ele falaria nos 2 primeiros segundos"}"""


def log(m):
    print(m, flush=True)


def norm(t):
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


def quadros(video, quantos=4, destino=None):
    """alguns quadros espalhados: é o que a IA precisa para dizer o que é"""
    destino = Path(destino or Path(video).parent / "_quadros")
    destino.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True)
    try:
        total = float((r.stdout or "0").strip())
    except ValueError:
        total = 0.0
    if total <= 0:
        return []
    out = []
    for k in range(quantos):
        t = total * (k + 0.5) / quantos
        f = destino / f"{Path(video).stem}_{k}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                        "-vf", "scale=480:-2", "-y", str(f)], capture_output=True, timeout=120)
        if f.exists():
            out.append(f)
    return out


def fala(video, segundos=60):
    """a transcrição do começo (o faster-whisper já é usado no resto do sistema)"""
    try:
        sys.path.insert(0, str(TOOLS))
        from transcrever import transcrever
        pedaco = Path(video).with_suffix(".corte.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-t", str(segundos), "-i", str(video),
                        "-ar", "16000", "-ac", "1", "-y", str(pedaco)], capture_output=True, timeout=180)
        if not pedaco.exists():
            return ""
        ps = transcrever(pedaco, "base", "cpu", idioma=None)
        pedaco.unlink(missing_ok=True)
        if isinstance(ps, tuple):
            ps = ps[0]
        return " ".join(p.get("w", "") for p in (ps or []))[:1200]
    except Exception as e:
        log(f"   (sem transcrição: {str(e)[:90]})")
        return ""


def decide_um(video, log=log):
    """a resposta da IA para ESTE vídeo"""
    from reels import gemini_json

    qs = quadros(video)
    if not qs:
        return {"o_que": "nenhum", "motivo": "não consegui abrir o vídeo"}
    import base64
    partes = [{"text": REGRAS}]
    for q in qs:
        partes.append({"inline_data": {"mime_type": "image/jpeg",
                                       "data": base64.b64encode(q.read_bytes()).decode()}})
    t = fala(video)
    partes.append({"text": f"\nO QUE SE OUVE NO VÍDEO: {t or '(sem fala)'}"})
    d = gemini_json(partes, temperatura=0.3) or {}
    o = str(d.get("o_que", "")).strip().lower()
    if o not in ("reagir", "copiar", "narrar"):
        o = "nenhum"
    return {"o_que": o, "motivo": (d.get("motivo") or "")[:200], "gancho": (d.get("gancho") or "")[:200]}


def aplica(video, r, base, so_dizer=False, link="", log=log):
    """leva o vídeo para o lugar certo do sistema"""
    base = Path(base)
    if so_dizer:
        return
    if r["o_que"] == "copiar" and link:
        try:
            import viral as V
            alvo = Path(V.raiz_midia()) / "reels" / "links.txt"   # `raiz_midia` é do viral.py, não do reels
        except Exception:
            alvo = base.parent / "reels" / "links.txt"
        alvo.parent.mkdir(parents=True, exist_ok=True)
        tinha = alvo.read_text(encoding="utf-8", errors="replace") if alvo.exists() else ""
        if link not in tinha:
            with alvo.open("a", encoding="utf-8") as f:
                f.write(link + "\n")
            log(f"      link no {alvo.name} (o reels.py refaz no modo TROCA)")
    elif r["o_que"] == "narrar":
        arq = base / "pautas_virais.txt"
        assunto = r.get("gancho") or Path(video).stem.replace("_", " ")
        tinha = arq.read_text(encoding="utf-8", errors="replace") if arq.exists() else ""
        if norm(assunto) not in norm(tinha):
            with arq.open("a", encoding="utf-8") as f:
                f.write(assunto + "\n")
            log("      assunto em pautas_virais.txt (canal de notícias + tools\\narrado)")


def rodada(base, so_dizer=False, um=None, log=log):
    base = Path(base)
    pasta = base / "videos_para_react"
    pasta.mkdir(parents=True, exist_ok=True)
    feitos_f = base / "decididos.json"
    feitos = {}
    if feitos_f.exists():
        try:
            feitos = json.loads(feitos_f.read_text(encoding="utf-8-sig"))
        except ValueError:
            feitos = {}
    videos = [Path(um)] if um else sorted(p for p in pasta.iterdir()
                                          if p.suffix.lower() in (".mp4", ".mov", ".webm"))
    n = 0
    for v in videos:
        if not um and v.name in feitos:
            continue
        log(f"   {v.name}")
        try:
            r = decide_um(v, log)
        except Exception as e:
            log(f"      não decidi: {str(e)[:140]}")
            continue
        log(f"      → {r['o_que'].upper()}: {r['motivo']}")
        # o link do vídeo original, quando o catcher anotou num .txt ao lado
        link = ""
        lado = v.with_suffix(".txt")
        if lado.exists():
            m = re.search(r"https?://\S+", lado.read_text(encoding="utf-8", errors="replace"))
            link = m.group(0) if m else ""
        aplica(v, r, base, so_dizer=so_dizer, link=link, log=log)
        v.with_suffix(".decisao.txt").write_text(
            f"{r['o_que'].upper()}\n{r['motivo']}\n\nGANCHO: {r.get('gancho', '')}\n", encoding="utf-8")
        feitos[v.name] = {"o_que": r["o_que"], "quando": dt.datetime.now().isoformat(timespec="minutes")}
        n += 1
    feitos_f.write_text(json.dumps(feitos, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"decididos: {n}")
    return n


def main():
    ap = argparse.ArgumentParser(description="o que fazer com cada viral: reagir, copiar ou narrar")
    ap.add_argument("--pasta", default="")
    ap.add_argument("--arquivo", default="")
    ap.add_argument("--so-dizer", action="store_true", help="decide e escreve, mas não mexe em nada")
    a = ap.parse_args()
    if a.pasta:
        base = Path(a.pasta)
    else:
        import viral as V
        base = V.raiz_midia() / "viral" if hasattr(V, "raiz_midia") else Path.home() / "DETTO" / "viral"
    rodada(base, so_dizer=a.so_dizer, um=a.arquivo or None)


if __name__ == "__main__":
    main()
