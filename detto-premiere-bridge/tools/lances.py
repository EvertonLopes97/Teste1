# -*- coding: utf-8 -*-
"""Vídeo dos LANCES para a versão "com lances" (você escolhe qual postar: com ou sem).

    python tools/lances.py <job>/EDIT_PLAN.json [--refazer] [--cookies chrome]

Para cada trecho [LANCE+VO] (ou com linha LANCE: no roteiro):
  1. acha o jogo (os dois times do trecho; um só → o adversário vem dos placares do roteiro);
  2. procura no YouTube os "melhores momentos" desse jogo (título com os dois times, sem live/react) e baixa
     em 720p para <job>/lances/ (fica guardado: rodar de novo não baixa outra vez);
  3. lê a NARRAÇÃO (legenda automática do YouTube; sem ela, transcreve com o faster-whisper) e acha o lance
     pelo nome do jogador que VOCÊ cita no trecho ("Gabigol ... bate forte" → narrador grita "gol ... Gabigol");
  4. o lance entra na hora em que você fala o nome, cortado no tamanho que cabe até o próximo assunto.

Resultado: <job>/lances.json (corrija "ini"/"fim" em segundos do vídeo baixado, ou "video", e rode o render de
novo) e <job>/lances_conferir.jpg (3 quadros de cada lance; vermelho = não achei).

No roteiro (opcional):
  LANCE: https://youtu.be/XXXX 1:23-1:31     → esse vídeo, esse trecho
  LANCE: E:/lances/gol.mp4 0:05-0:12         → arquivo seu
  LANCE: sem                                  → esse trecho fica sem vídeo de lance
O YouTube às vezes pede "confirme que não é robô": usa os cookies do seu navegador (--cookies chrome/edge/firefox;
sem a opção, tenta chrome, edge e firefox sozinho). yt-dlp velho também falha: é atualizado sozinho uma vez.
"""
import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

T = Path(__file__).resolve().parent
TIMES = json.loads((T / "roteiro" / "times.json").read_text(encoding="utf-8"))["times"]
ELENCOS = T / "banco" / "elencos"

RUIM = r"\b(ao vivo|live|react|reacao|reagindo|analise|pos[- ]jogo|coletiva|entrevista|feminino|sub[- ]?\d\d|bastidores|torcida canta|narracao radio|efootball|pes|fifa|fc ?2\d|simulacao)\b"
BOM = r"\b(melhores momentos|gols|highlights|compacto|resumo)\b"
PARADA = {"gol", "gols", "bola", "time", "jogo", "area", "lance", "santos", "silva", "souza", "junior", "neto", "filho"}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def parecido(a, b):
    if a == b:
        return True
    return len(a) >= 5 and len(b) >= 5 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.84


def seg_tempo(txt):
    if not txt:
        return None
    v = 0.0
    for x in str(txt).replace(",", ".").split(":"):
        v = v * 60 + float(x)
    return v


def time_por_sigla(sigla):
    return next((t for t in TIMES if t["sigla"] == sigla), None)


def termos_dos_times(times):
    """palavras que são nome de time (não servem para achar jogador: "Santos" é time)"""
    out = set()
    for t in times:
        tt = time_por_sigla(t.get("sigla")) or t
        for x in [tt.get("nome", "")] + list(tt.get("apelidos", [])):
            out.update(norm(x).split())
    return out


def jogadores_do_jogo(times, pessoas):
    """[(nome, [termos])] dos elencos dos dois times + quem está no roteiro"""
    out = list(pessoas)  # quem está no roteiro primeiro (nome como você escreve)
    for t in times:
        tt = time_por_sigla(t.get("sigla")) or {}
        f = ELENCOS / f"{tt.get('sofa') or t.get('sofa')}.json"
        if f.exists():
            for p in json.loads(f.read_text(encoding="utf-8")):
                out.append(p["name"])
    vistos, lista = set(), []
    proibidos = termos_dos_times(times) | PARADA
    for nome in out:
        if nome in vistos:
            continue
        vistos.add(nome)
        partes = [w for w in norm(nome).split() if len(w) >= 4 and w not in proibidos]
        if not partes:
            continue
        # sobrenome (último) e, para nome de uma palavra só (Hulk, Gabigol), ele mesmo
        primeiro = len(partes) == 1 or len(partes[0]) >= (5 if nome in pessoas else 6)
        termos = list(dict.fromkeys([partes[-1]] + ([partes[0]] if primeiro else [])))
        lista.append((nome, termos))
    return lista


def alvos_do_trecho(palavras, S, E, jogadores):
    """quem você cita no trecho, na ordem, com a hora (timeline)"""
    achados = []
    for w in palavras:
        if not (S - 0.2 <= w["s"] < E):
            continue
        t = norm(w["w"]).replace(" ", "")
        if len(t) < 4:
            continue
        for nome, termos in jogadores:
            if any(parecido(t, k) for k in termos):
                # mesmo jogador (nome igual ou mesmo sobrenome) ou citado colado no anterior ("Gabigol recebe do
                # Coutinho" = um lance só, o do primeiro)
                if not any(a["nome"] == nome or set(a["termos"]) & set(termos) or w["s"] - a["t"] < 1.8 for a in achados):
                    achados.append({"nome": nome, "termos": termos, "t": w["s"]})
                break
    return achados


# ------------------------------------------------------------------ YouTube
def ytdlp(args, cookies=None):
    base = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--no-playlist"]
    if shutil.which("node"):
        base += ["--js-runtimes", "node"]
    if cookies:
        base += ["--cookies-from-browser", cookies]
    r = subprocess.run(base + args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 and "js-runtimes" in (r.stderr or "") and "no such option" in (r.stderr or "").lower():
        base = [x for x in base if x not in ("--js-runtimes", "node")]
        r = subprocess.run(base + args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r


_atualizado = False


def atualiza_ytdlp():
    global _atualizado
    if _atualizado:
        return
    _atualizado = True
    print("lances: atualizando o yt-dlp (o YouTube muda e versão velha falha)...", flush=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp"], capture_output=True)


def procura_video(times, ano, log=print, gols=None):
    nomes = [time_por_sigla(t["sigla"]) or t for t in times]
    q = f"{nomes[0]['nome']} x {nomes[1]['nome']} melhores momentos {ano}" if len(nomes) > 1 else f"{nomes[0]['nome']} gols melhores momentos {ano}"
    r = ytdlp(["--flat-playlist", "--dump-json", f"ytsearch12:{q}"])
    if r.returncode != 0 and not r.stdout:
        atualiza_ytdlp()
        r = ytdlp(["--flat-playlist", "--dump-json", f"ytsearch12:{q}"])
    cands = []
    for linha in (r.stdout or "").splitlines():
        try:
            v = json.loads(linha)
        except ValueError:
            continue
        tit = norm(v.get("title", ""))
        dur = v.get("duration") or 0
        pts = 0
        for n in nomes:
            aps = [norm(x) for x in [n.get("nome", "")] + list(n.get("apelidos", []))] + [norm(n.get("sigla", ""))]
            if any(a and re.search(rf"\b{re.escape(a)}\b", tit) for a in aps):
                pts += 6
            else:
                pts -= 8
        if re.search(BOM, tit):
            pts += 3
        if re.search(RUIM, tit):
            pts -= 12
        if 90 <= dur <= 1500:
            pts += 2 + (1 if dur <= 900 else 0)
        elif dur:
            pts -= 4
        if gols and re.search(rf"\b({gols[0]}\s*x?\s*-?\s*{gols[1]}|{gols[1]}\s*x?\s*-?\s*{gols[0]})\b", tit):
            pts += 5
        # outro campeonato com os mesmos times (a rodada é do Brasileirão; o placar certo compensa)
        if re.search(r"\b(sul ?americana|sudamericana|libertadores|copa do brasil|campeonato mineiro|paulistao|carioca|gauchao|baiano)\b", tit):
            pts -= 3
        anos = re.findall(r"\b20\d\d\b", tit)
        if anos:
            pts += 2 if str(ano) in anos else -6
        cands.append((pts, v.get("id"), v.get("title", ""), dur))
    cands.sort(reverse=True)
    for c in cands[:3]:
        log(f"   {c[0]:+3d}  {c[2]}  ({c[3] or '?'} s)")
    bom = [c for c in cands if c[0] >= 8]
    return ({"id": bom[0][1], "titulo": bom[0][2], "url": f"https://www.youtube.com/watch?v={bom[0][1]}"} if bom else None), q


def baixa(url, pasta, cookies=None, log=print):
    """baixa em 720p + legenda automática (pt). Devolve o caminho do mp4 ou None."""
    pasta.mkdir(parents=True, exist_ok=True)
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{6,})", url)
    vid = m.group(1) if m else re.sub(r"\W+", "_", url)[-40:]
    pronto = next(iter(sorted(pasta.glob(f"{vid}.mp4"))), None)
    if pronto and pronto.stat().st_size > 100_000:
        return pronto
    args = ["-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]/b", "--merge-output-format", "mp4",
            "--write-auto-subs", "--write-subs", "--sub-langs", "pt.*,pt", "--sub-format", "json3",
            "-o", str(pasta / f"{vid}.%(ext)s"), url]
    tentativas = [cookies] if cookies else [None, "chrome", "edge", "firefox"]
    for k, ck in enumerate(tentativas):
        r = ytdlp(args, ck)
        f = pasta / f"{vid}.mp4"
        if f.exists() and f.stat().st_size > 100_000:
            return f
        erro = (r.stderr or "").strip().splitlines()[-1:] or [""]
        log(f"   não baixou{' (cookies do ' + ck + ')' if ck else ''}: {erro[0][:160]}")
        if k == 0:
            atualiza_ytdlp()
            r = ytdlp(args, ck)
            if f.exists() and f.stat().st_size > 100_000:
                return f
    return None


def narracao(video, log=print):
    """palavras da narração [{w, s, e}]: legenda do YouTube (json3) ou faster-whisper (guardado ao lado)"""
    cache = video.with_suffix(".narracao.json")
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    palavras = []
    for sub in sorted(video.parent.glob(video.stem + ".pt*.json3")):
        d = json.loads(sub.read_text(encoding="utf-8"))
        for ev in d.get("events", []):
            t0 = ev.get("tStartMs", 0) / 1000
            for s in ev.get("segs") or []:
                txt = (s.get("utf8") or "").strip()
                if txt:
                    ts = t0 + s.get("tOffsetMs", 0) / 1000
                    palavras += [{"w": x, "s": round(ts, 2), "e": round(ts + 0.4, 2)} for x in txt.split()]
        if palavras:
            log("   narração: legenda do YouTube")
            break
    if not palavras:
        log("   narração: transcrevendo (faster-whisper)...")
        sys.path.insert(0, str(T))
        try:
            from transcrever import dlls_nvidia, transcrever

            dlls_nvidia()
            try:
                palavras = transcrever(str(video), "small", "cuda")
            except Exception:
                palavras = transcrever(str(video), "small", "cpu")
            print()
        except Exception as e:
            log(f"   não consegui transcrever: {e}")
    cache.write_text(json.dumps(palavras, ensure_ascii=False), encoding="utf-8")
    return palavras


GRITO = re.compile(r"^go+l+|^gola[cç]o|^golaco")


def acha_lance(narr, alvo, evento, usados=()):
    """momento do lance (s no vídeo baixado) pelo nome narrado; perto do grito de gol quando é gol"""
    hits = [w["s"] for w in narr if any(parecido(norm(w["w"]).replace(" ", ""), k) for k in alvo["termos"])]
    hits = [h for h in hits if not any(abs(h - u) < 3 for u in usados)]
    if not hits:
        return None
    h = hits[0]
    if evento in ("gol", ""):
        # o grito de gol mais perto do nome (o narrador fala o nome logo antes ou logo depois do grito)
        gritos = [w["s"] for w in narr if GRITO.match(norm(w["w"])) and h - 9 <= w["s"] <= h + 7 and not any(abs(w["s"] - u) < 3 for u in usados)]
        if gritos:
            return {"momento": min(gritos, key=lambda g: abs(g - h)), "como": f"narração: \"{alvo['termos'][0]}\" + grito de gol"}
    if evento == "pênalti":
        pen = [w["s"] for w in narr if norm(w["w"]).startswith("penalt") and h - 15 <= w["s"] <= h + 15]
        if pen:
            return {"momento": max(h, min(pen)) + 2, "como": f"narração: \"{alvo['termos'][0]}\" + pênalti"}
    return {"momento": h, "como": f"narração: \"{alvo['termos'][0]}\""}


def duracao(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def foto_do_lance(jogador, times, evento, ano, log=print):
    """plano B: foto do lance na internet ("Gabigol gol Santos Atlético 2026"); o nome tem que estar no título"""
    try:
        sys.path.insert(0, str(T))
        from busca_imagem import buscar
    except Exception:
        return None
    nomes = " ".join((time_por_sigla(t["sigla"]) or t)["nome"] for t in times)
    sobrenome = [w for w in norm(jogador).split() if len(w) >= 4][-1:] if jogador else []
    q = f"{jogador} {evento or 'lance'} {nomes} {ano}".strip()
    try:
        r = buscar(q, sobrenome, log=lambda m: None, prazo=60)
    except Exception as e:
        log(f"   foto: {e}")
        return None
    return r and r.get("file")


def folha(job, lances):
    """lances_conferir.jpg: 3 quadros de cada lance (início, meio, fim)"""
    import cv2
    import numpy as np

    linhas = []
    for L in lances:
        th = []
        for k in (0.1, 0.5, 0.9):
            img = None
            if L.get("foto") and Path(L["foto"]).exists():
                img = cv2.imread(L["foto"])
            elif L.get("video") and Path(L["video"]).exists():
                t = L["ini"] + (L["fim"] - L["ini"]) * k
                r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", L["video"], "-frames:v", "1", "-vf", "scale=360:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True)
                if r.stdout:
                    img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                img = np.full((202, 360, 3), (40, 40, 160), np.uint8)
            img = cv2.resize(img, (360, 202))
            th.append(img)
        faixa = np.full((40, 1080, 3), 25, np.uint8)
        txt = f"{L['t']:.1f}s  {L.get('jogador') or L.get('evento') or ''}  [{L.get('como', '')}]  {Path(L.get('video') or L.get('foto') or '-').name} {L.get('ini', 0):.1f}-{L.get('fim', 0):.1f}"
        cv2.putText(faixa, norm(txt)[:110], (8, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255) if L.get("video") or L.get("foto") else (80, 80, 255), 1, cv2.LINE_AA)
        linhas.append(np.vstack([faixa, np.hstack(th)]))
    if linhas:
        cv2.imwrite(str(job / "lances_conferir.jpg"), np.vstack(linhas), [cv2.IMWRITE_JPEG_QUALITY, 85])


def main():
    ap = argparse.ArgumentParser(description="vídeo dos lances para a versão com lances")
    ap.add_argument("plano")
    ap.add_argument("--refazer", action="store_true", help="refaz a escolha dos trechos (o vídeo baixado é reaproveitado)")
    ap.add_argument("--cookies", default=None, help="navegador com o YouTube logado: chrome, edge ou firefox")
    a = ap.parse_args()
    plano_f = Path(a.plano).resolve()
    job = plano_f.parent
    saida = job / "lances.json"
    if saida.exists() and not a.refazer:
        print(f"lances: já existe {saida} (use --refazer para buscar de novo)")
        return
    plano = json.loads(plano_f.read_text(encoding="utf-8"))
    segs = (plano.get("meta") or {}).get("segments") or []
    palavras = sorted([w for c in plano.get("captions", []) for w in c.get("words", [])], key=lambda w: w["s"])
    total = max((c["timeline"] + c["end"] - c["start"] for c in plano.get("cuts", [])), default=0)
    pessoas = []
    jj = job / "jogadores.json"
    if jj.exists():
        pessoas = list(json.loads(jj.read_text(encoding="utf-8")).get("players", {}).keys())
    ano = (re.findall(r"\b20\d\d\b", json.dumps(plano.get("meta", {}).get("title", ""))) or [None])[0] or __import__("datetime").date.today().year
    pasta = job / "lances"
    videos = {}
    lances = []
    for i, s in enumerate(segs):
        pedido = next((c["data"] for c in s.get("comps", []) if c.get("type") == "lance"), None)
        if not pedido or pedido.get("sem"):
            continue
        S = s["start"]
        E = segs[i + 1]["start"] if i + 1 < len(segs) else total
        times = pedido.get("times") or []
        print(f"\nlance {S:.1f}s ({' x '.join(t['nome'] for t in times) or '?'}, {pedido.get('evento') or 'lance'})", flush=True)
        # vídeo: o do roteiro ou o achado no YouTube
        fonte = pedido.get("url") or ""
        if fonte and not re.match(r"https?://", fonte):
            arq = Path(fonte)
            video = arq if arq.exists() else None
            titulo = arq.name
        else:
            chave = fonte or "|".join(sorted(t["sigla"] for t in times))
            if chave not in videos:
                info = {"url": fonte, "titulo": fonte} if fonte else None
                if not info and len(times) >= 1:
                    info, q = procura_video(times, ano, gols=pedido.get("gols"))
                    print(f"   busca: {q}")
                if info:
                    print(f"   vídeo: {info['titulo']}")
                    videos[chave] = (baixa(info["url"], pasta, a.cookies), info["titulo"])
                else:
                    print("   não achei melhores momentos desse jogo")
                    videos[chave] = (None, "")
            video, titulo = videos[chave]
        if not video:
            # sem vídeo: foto do lance de quem você cita (plano B)
            alvos = alvos_do_trecho(palavras, S, E, jogadores_do_jogo(times, pessoas))
            for k, alvo in enumerate(alvos[:3] or [{"nome": "", "t": S + 0.2}]):
                fimslot = alvos[k + 1]["t"] if k + 1 < len(alvos) else E
                foto = foto_do_lance(alvo["nome"], times, pedido.get("evento"), ano)
                dur = min(fimslot - alvo["t"] - 0.1, 5.0)
                if foto and dur >= 2:
                    lances.append({"t": round(alvo["t"] - 0.1, 2), "dur": round(dur, 2), "foto": foto, "jogador": alvo["nome"], "como": "foto (sem vídeo)", "times": [t["sigla"] for t in times], "placar": pedido.get("placar", "")})
                    print(f"   foto do lance: {alvo['nome'] or 'jogo'}")
            if not any(L.get("foto") and L["t"] >= S - 0.2 for L in lances):
                lances.append({"t": S, "dur": 0, "video": "", "evento": pedido.get("evento"), "como": "não achei vídeo nem foto"})
            continue
        vdur = duracao(video)
        # trecho escrito no roteiro: vale ele
        ini_r, fim_r = seg_tempo(pedido.get("inicio")), seg_tempo(pedido.get("fim"))
        if ini_r is not None and fim_r:
            lances.append({"t": S + 0.2, "dur": round(min(fim_r - ini_r, E - S - 0.3), 2), "video": str(video), "ini": ini_r, "fim": fim_r, "titulo": titulo, "como": "roteiro", "times": [t["sigla"] for t in times], "placar": pedido.get("placar", "")})
            continue
        alvos = alvos_do_trecho(palavras, S, E, jogadores_do_jogo(times, pessoas))
        print(f"   você cita: {', '.join(x['nome'] for x in alvos) or 'ninguém do elenco'}")
        narr = narracao(video)
        usados = []
        achou = 0
        for k, alvo in enumerate(alvos):
            r = acha_lance(narr, alvo, pedido.get("evento"), usados)
            if not r:
                print(f"   {alvo['nome']}: não achei na narração")
                continue
            m = r["momento"]
            usados.append(m)
            fimslot = alvos[k + 1]["t"] if k + 1 < len(alvos) else E
            dur = min(fimslot - alvo["t"] - 0.1, 9.0)
            if dur < 2.5:
                continue
            ini = max(0.0, m - 6.0)
            ini = max(ini, m + 2.5 - dur)  # curto: começa mais perto do lance, para o lance caber
            fim = min(vdur, ini + dur)
            lances.append({"t": round(alvo["t"] - 0.1, 2), "dur": round(fim - ini, 2), "video": str(video), "ini": round(ini, 2), "fim": round(fim, 2),
                           "titulo": titulo, "jogador": alvo["nome"], "como": r["como"], "times": [t["sigla"] for t in times], "placar": pedido.get("placar", "")})
            achou += 1
            print(f"   {alvo['nome']}: {ini:.1f}–{fim:.1f}s do vídeo ({r['como']})")
        if not achou:
            # ninguém achado: o primeiro grito de gol (ou o começo do trecho de lances) — confira na folha
            gritos = [w["s"] for w in narr if GRITO.match(norm(w["w"]))]
            if gritos and pedido.get("evento") in ("gol", ""):
                m = gritos[0]
                dur = min(E - S - 0.4, 8.0)
                if dur >= 2.5:
                    lances.append({"t": round(S + 0.2, 2), "dur": round(dur, 2), "video": str(video), "ini": round(max(0, m - dur + 2.5), 2), "fim": round(max(0, m - dur + 2.5) + dur, 2),
                                   "titulo": titulo, "como": "chute: 1º grito de gol (confira)", "times": [t["sigla"] for t in times], "placar": pedido.get("placar", "")})
                    print("   chute: primeiro grito de gol (confira na folha)")
    saida.write_text(json.dumps({"lances": lances}, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        folha(job, lances)
    except Exception as e:  # folha é só conferência
        print(f"(sem folha de conferência: {e})")
    ok = [L for L in lances if (L.get("video") or L.get("foto")) and L.get("dur")]
    print(f"\nlances: {len(ok)} com vídeo → {saida}")
    if (job / "lances_conferir.jpg").exists():
        print(f"confira: {job / 'lances_conferir.jpg'}")


if __name__ == "__main__":
    main()
