# -*- coding: utf-8 -*-
"""CONFERÊNCIA DO EPISÓDIO — roda ANTES de entregar o vídeo.

Confere três coisas e, onde dá, CORRIGE sozinho antes de montar de novo:

  1. NARRAÇÃO escrita para a voz: número em algarismo, símbolo, sigla, abreviação, hora com "h" — tudo que faz a
     voz falar errado. Esses casos são reescritos por extenso (o mesmo `pronuncia` do canal) e o roteiro é corrigido.
  2. O QUE A VOZ FALOU × o que o roteiro pedia: alinha a transcrição com o texto e mede quanto bateu. Pouca
     semelhança = a voz comeu ou trocou palavras, e o episódio é marcado para refazer a voz.
  3. IMAGEM, cena a cena: um quadro de cada cena; quadro quase preto ou chapado (sem nada desenhado) vira problema,
     e a cena é clareada (escuro → noite) para a remontagem.

Sai `<job>\\conferencia.txt` (o que foi visto e o que foi corrigido) e `<job>\\conferencia.jpg` (um quadro de cada
cena, em folha) — é o que você olha antes de postar.
"""
import re
import subprocess
import unicodedata
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent


def log(m):
    print(m, flush=True)


def _norm(t):
    t = "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", t)


# ------------------------------------------------------------------ 1. a narração está falável?
PROBLEMAS = [
    (r"\d+\s*h\s*\d*", "hora em número (20h30)"),
    (r"R\$\s*\d", "valor em R$"),
    (r"\d+\s*%", "porcentagem"),
    (r"\d+\s*º", "número ordinal (12º)"),
    (r"\b\d+\s*[x×]\s*\d+\b", "placar com x"),
    (r"-\s*\d\b", "número negativo (subsolo -2)"),
    (r"\b[A-ZÀ-Ý]{2,}\b", "sigla em maiúsculas"),
    (r"\b\d[\d.,]*\b", "número em algarismo"),
    (r"[(){}\[\]«»\"]|\.\.\.|—|–", "símbolo que a voz lê errado"),
]


def confere_narracao(rot, corrigir=True, log=log):
    """acha (e corrige) o que faz a voz falar errado. Devolve a lista do que foi encontrado."""
    try:
        import sys

        sys.path.insert(0, str(TOOLS / "canal"))
        import voz as V
    except Exception:
        V = None
    achados = []
    for i, c in enumerate(rot.get("cenas", [])):
        t = str(c.get("narracao", ""))
        for padrao, nome in PROBLEMAS:
            for m in re.finditer(padrao, t):
                trecho = m.group(0).strip()
                if len(trecho) < 2 and not trecho.isdigit():
                    continue
                achados.append((i + 1, nome, trecho))
    if achados and corrigir and V:
        for c in rot.get("cenas", []):
            c["narracao"] = V.pronuncia(str(c.get("narracao", "")))
        rot["narracao"] = " ".join(c.get("narracao", "") for c in rot.get("cenas", []) if c.get("narracao"))
        log(f"conferência: {len(achados)} trecho(s) reescritos para a voz falar certo")
    return achados


# ------------------------------------------------------------------ 2. a voz falou o que estava escrito?
def confere_fala(rot, words):
    """quanto da narração a voz falou igual (0 a 1) e as palavras que saíram diferentes"""
    esperado = [_norm(p) for p in re.findall(r"\w+", " ".join(c.get("narracao", "") for c in rot.get("cenas", [])))]
    falado = [_norm(w.get("w", "")) for w in (words or [])]
    if not esperado or not falado:
        return 1.0, []
    fal = set(falado)
    faltaram = [p for p in esperado if p and p not in fal and len(p) > 3]
    bateu = 1 - len(faltaram) / max(1, len([p for p in esperado if len(p) > 3]))
    return round(max(0.0, bateu), 3), faltaram[:20]


# ------------------------------------------------------------------ 3. as cenas desenharam alguma coisa?
def _quadro(video, t, destino):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.2f}", "-i", str(video), "-frames:v", "1",
                        "-q:v", "4", "-y", str(destino)], capture_output=True, text=True)
    return destino if r.returncode == 0 and Path(destino).exists() else None


def confere_imagem(video, rot, pasta, corrigir=True, log=log):
    """um quadro no MEIO de cada cena; quase preto ou chapado = cena vazia (e a cena é clareada para a remontagem)"""
    try:
        from PIL import Image, ImageStat
    except Exception:
        return [], None
    tmp = Path(pasta) / "tmp_conf"
    tmp.mkdir(parents=True, exist_ok=True)
    ruins, quadros = [], []
    ini = 0.0
    for i, c in enumerate(rot.get("cenas", [])):
        fim = float(c.get("ate") or (ini + 4))
        f = _quadro(video, (ini + fim) / 2, tmp / f"c{i:02d}.jpg")
        ini = fim
        if not f:
            continue
        quadros.append((i, f, c))
        im = Image.open(f).convert("L")
        st = ImageStat.Stat(im)
        media, desvio = st.mean[0], st.stddev[0]
        if media < 12:
            ruins.append((i + 1, f"cena quase preta (brilho {media:.0f})"))
            if corrigir and c.get("luz") == "escuro":
                c["luz"] = "noite"
                c.pop("escurece", None)
        elif desvio < 10:
            ruins.append((i + 1, f"cena chapada, sem nada desenhado (variação {desvio:.0f})"))
            if corrigir and not c.get("pessoas") and not c.get("objetos"):
                c["plano"] = "geral"
    folha = _folha(quadros, Path(pasta) / "conferencia.jpg", log)
    for f in tmp.glob("*.jpg"):
        f.unlink(missing_ok=True)
    return ruins, folha


def _folha(quadros, saida, log=log):
    """a folha com um quadro de cada cena (o que você olha antes de postar)"""
    if not quadros:
        return None
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    cols = 6
    lin = (len(quadros) + cols - 1) // cols
    w, h = 220, 391
    folha = Image.new("RGB", (cols * w, lin * (h + 26)), (18, 20, 24))
    d = ImageDraw.Draw(folha)
    for n, (i, f, c) in enumerate(quadros):
        try:
            im = Image.open(f).convert("RGB").resize((w, h))
        except Exception:
            continue
        x, y = (n % cols) * w, (n // cols) * (h + 26)
        folha.paste(im, (x, y))
        txt = f"{i + 1}. {str(c.get('narracao', ''))[:34]}"
        d.text((x + 5, y + h + 6), txt, fill=(226, 226, 226))
    folha.save(saida, quality=88)
    log(f"conferência: folha das cenas em {saida}")
    return saida


# ------------------------------------------------------------------ tudo junto
def confere(job, rot, words, video, log=log, corrigir=True):
    """roda as três conferências e grava o relatório. Devolve (precisa_refazer, relatorio)."""
    job = Path(job)
    linhas = [f"CONFERÊNCIA — {rot.get('titulo', '')}", ""]
    narr = confere_narracao(rot, corrigir, log)
    linhas.append(f"1) NARRAÇÃO PARA A VOZ: {len(narr)} trecho(s) que a voz leria errado"
                  + (" — reescritos" if narr and corrigir else ""))
    for n, nome, trecho in narr[:14]:
        linhas.append(f"   cena {n}: {nome} → \"{trecho}\"")

    bateu, faltaram = confere_fala(rot, words)
    linhas += ["", f"2) A VOZ FALOU O QUE ESTAVA ESCRITO: {bateu * 100:.0f}%"]
    if faltaram:
        linhas.append("   palavras que não saíram: " + ", ".join(faltaram))

    ruins, folha = ([], None)
    if video and Path(video).exists():
        ruins, folha = confere_imagem(video, rot, job, corrigir, log)
    linhas += ["", f"3) IMAGEM: {len(ruins)} cena(s) com problema"]
    for n, p in ruins:
        linhas.append(f"   cena {n}: {p}")
    if folha:
        linhas += ["", f"folha das cenas: {folha}"]

    # refaz quando a voz comeu muita coisa (abaixo de 85%) ou quando cena ficou vazia e foi corrigida
    refazer = bateu < 0.85 or bool(ruins and corrigir)
    linhas += ["", "RESULTADO: " + ("corrigido — monto de novo antes de entregar" if refazer else "tudo certo")]
    (job / "conferencia.txt").write_text("\n".join(linhas), encoding="utf-8")
    log(f"conferência: voz {bateu * 100:.0f}% · {len(narr)} ajuste(s) de pronúncia · {len(ruins)} cena(s) ruim(ns)")
    return refazer, "\n".join(linhas)
