"""ANÁLISE DE CAPAS DOS CONCORRENTES (06/nov): o que a capa tem × quanto o vídeo rendeu.

`python tools\\yt\\analise_capas.py [--nicho galo|games|todos] [--quantos 30] [--saida pasta]`
Para cada canal: lista os últimos vídeos (yt-dlp --flat-playlist, de graça), baixa a MINIATURA, mede o que ela
tem (rosto e tamanho do rosto, quantidade de texto, brilho, cor viva, vermelho/amarelo, borda de contraste) e compara
as views de cada vídeo com a MEDIANA do PRÓPRIO canal (então "canal grande" não conta). No fim diz, por nicho,
qual característica rende mais/menos e escreve `capas_<nicho>.csv`, `capas_<nicho>.txt` e folhas de contato
(as 8 melhores × as 8 piores capas de cada canal) para olhar com o olho.
Não mede o TikTok (não deixa robô listar) nem o Shop (a miniatura do TikTok Shop não é pública).
"""

import argparse
import csv
import json
import statistics
import subprocess
import urllib.request
from pathlib import Path

import cv2
import numpy as np

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent

CANAIS = {
    "galo": ["@JornaldoGalo", "@diariodogalo940", "@galoticiasoficial", "@EUSOUGALO", "@TrincaGalo", "@ETERNOGALONEWS"],
    "games": ["@SaninPlay", "@GameplayRJ", "@WillMacGTA", "@NobertoGamer", "@gigatongames", "@Dulebio",
              "@VOXELOFICIAL", "@BRKsEDU"],
}


def lista(canal, n):
    try:
        r = subprocess.run(["yt-dlp", "--flat-playlist", "--dump-json", "--playlist-end", str(n),
                            f"https://www.youtube.com/{canal}/videos"], capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace")
    except Exception:   # noqa: BLE001
        return []
    out = []
    for l in r.stdout.splitlines():
        try:
            d = json.loads(l)
        except ValueError:
            continue
        if d.get("id") and d.get("view_count") is not None and (d.get("duration") or 0) > 60:
            out.append({"id": d["id"], "titulo": d.get("title") or "", "views": int(d["view_count"]),
                        "dur": d.get("duration") or 0})
    return out


def baixa(vid, pasta):
    f = pasta / f"{vid}.jpg"
    if not f.exists() or f.stat().st_size < 2000:
        for nome in ("maxresdefault", "hqdefault"):
            try:
                dados = urllib.request.urlopen(f"https://i.ytimg.com/vi/{vid}/{nome}.jpg", timeout=30).read()
                if len(dados) > 4000:
                    f.write_bytes(dados)
                    break
            except Exception:   # noqa: BLE001
                continue
    return f if f.exists() else None


def medidas(img, det):
    h, w = img.shape[:2]
    if w > 640:
        img = cv2.resize(img, (640, int(h * 640 / w)))
        h, w = img.shape[:2]
    det.setInputSize((w, h))
    _, rostos = det.detect(img)
    areas = sorted(((float(f[2]) * float(f[3])) / (w * h) for f in (rostos if rostos is not None else [])), reverse=True)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bordas = cv2.Canny(cinza, 120, 240)
    # "texto": bordas fortes concentradas em blocos horizontais (letra grande tem muita borda numa faixa estreita)
    faixas = [bordas[int(h * i / 8):int(h * (i + 1) / 8)].mean() / 255 for i in range(8)]
    h_, s_, v_ = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    vermelho = (((h_ < 8) | (h_ > 172)) & (s_ > 140) & (v_ > 110)).mean()
    amarelo = ((h_ > 18) & (h_ < 34) & (s_ > 140) & (v_ > 150)).mean()
    return {
        "rosto": int(len(areas) > 0 and areas[0] >= 0.012),
        "rosto_area": round(areas[0], 4) if areas else 0.0,
        "rostos": sum(1 for a in areas if a >= 0.006),
        "brilho": round(float(v_.mean()) / 255, 3),
        "cor_viva": round(float((s_ > 120).mean()), 3),
        "vermelho": round(float(vermelho), 3),
        "amarelo": round(float(amarelo), 3),
        "texto": round(float(np.mean(sorted(faixas)[-3:])), 3),
        "contraste": round(float(cinza.std()) / 128, 3),
    }


def do_titulo(t):
    letras = [c for c in t if c.isalpha()]
    return {"pergunta": int("?" in t), "numero": int(any(c.isdigit() for c in t)),
            "maiuscula": int(bool(letras) and sum(c.isupper() for c in letras) / len(letras) > 0.8)}


def folha(itens, destino, titulo):
    if not itens:
        return
    cols, larg, alt = 4, 320, 180
    linhas = (len(itens) + cols - 1) // cols
    tela = np.full((linhas * (alt + 34), cols * larg, 3), 20, np.uint8)
    for k, (arq, rot) in enumerate(itens):
        im = cv2.imread(str(arq))
        if im is None:
            continue
        im = cv2.resize(im, (larg, alt))
        y, x = (k // cols) * (alt + 34), (k % cols) * larg
        tela[y:y + alt, x:x + larg] = im
        cv2.putText(tela, rot[:44], (x + 4, y + alt + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1, cv2.LINE_AA)
    cv2.imwrite(str(destino), tela)


def principais(linhas, chave, corte, nome):
    """razão média (views/mediana do canal) com e sem a característica"""
    com = [r["razao"] for r in linhas if r[chave] >= corte]
    sem = [r["razao"] for r in linhas if r[chave] < corte]
    if len(com) < 5 or len(sem) < 5:
        return None
    return (nome, len(com), statistics.median(com), len(sem), statistics.median(sem))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nicho", default="todos")
    ap.add_argument("--quantos", type=int, default=30)
    ap.add_argument("--novos", type=int, default=7, help="quantos vídeos mais recentes de cada canal ignorar")
    ap.add_argument("--saida", default=str(Path.home() / "analise_capas"))
    a = ap.parse_args()
    saida = Path(a.saida)
    (saida / "miniaturas").mkdir(parents=True, exist_ok=True)
    det = cv2.FaceDetectorYN.create(str(RAIZ / "yunet.onnx"), "", (320, 320), 0.7)
    for nicho, canais in CANAIS.items():
        if a.nicho not in ("todos", nicho):
            continue
        linhas = []
        for c in canais:
            vs = lista(c, a.quantos)
            if len(vs) < 8:
                print(f"{c}: só {len(vs)} vídeos, pulei")
                continue
            # os MAIS NOVOS ainda não tiveram tempo de render (a 1ª análise pôs vídeo de ontem entre as "piores"
            # capas): fora os `--novos` mais recentes de cada canal; a mediana também sai só dos que já maturaram
            vs = vs[a.novos:]
            med = statistics.median(v["views"] for v in vs)
            for v in vs:
                f = baixa(v["id"], saida / "miniaturas")
                img = cv2.imread(str(f)) if f else None
                if img is None:
                    continue
                m = medidas(img, det)
                linhas.append({"canal": c, "id": v["id"], "titulo": v["titulo"], "views": v["views"],
                               "razao": round(v["views"] / max(1, med), 3), "arq": str(f), **m, **do_titulo(v["titulo"])})
            print(f"{c}: {len(vs)} vídeos, mediana {med:,.0f} views")
        if not linhas:
            continue
        with open(saida / f"capas_{nicho}.csv", "w", newline="", encoding="utf-8") as g:
            w = csv.DictWriter(g, fieldnames=list(linhas[0]))
            w.writeheader()
            w.writerows(linhas)
        rel = [f"CAPAS — {nicho} — {len(linhas)} vídeos de {len({r['canal'] for r in linhas})} canais",
               "razão = views do vídeo ÷ mediana do próprio canal (1,00 = normal do canal)", ""]
        testes = [
            principais(linhas, "rosto", 1, "tem rosto grande (≥1,2% da capa)"),
            principais(linhas, "rosto_area", 0.05, "rosto GRANDE (≥5% da capa)"),
            principais(linhas, "rostos", 2, "2 ou mais rostos"),
            principais(linhas, "texto", 0.10, "muito texto/borda forte"),
            principais(linhas, "cor_viva", 0.45, "cores vivas (≥45% saturado)"),
            principais(linhas, "vermelho", 0.03, "tem vermelho forte"),
            principais(linhas, "amarelo", 0.02, "tem amarelo forte"),
            principais(linhas, "brilho", 0.45, "capa clara (brilho ≥0,45)"),
            principais(linhas, "contraste", 0.35, "alto contraste"),
            principais(linhas, "pergunta", 1, "título com PERGUNTA (?)"),
            principais(linhas, "numero", 1, "título com NÚMERO"),
            principais(linhas, "maiuscula", 1, "título todo em CAIXA ALTA"),
        ]
        for t in testes:
            if t:
                nome, n1, m1, n0, m0 = t
                rel.append(f"{nome}: COM = {m1:.2f}x ({n1} vídeos) · SEM = {m0:.2f}x ({n0}) → "
                           f"{'rende MAIS' if m1 > m0 * 1.08 else 'rende MENOS' if m1 < m0 * 0.92 else 'não muda'}")
        rel.append("\nPOR CANAL — com rosto × sem rosto (razão mediana):")
        for c in canais:
            do_canal = [r for r in linhas if r["canal"] == c]
            com = [r["razao"] for r in do_canal if r["rosto"]]
            sem = [r["razao"] for r in do_canal if not r["rosto"]]
            if len(com) >= 3 and len(sem) >= 3:
                rel.append(f"  {c}: com rosto {statistics.median(com):.2f}x ({len(com)}) · sem {statistics.median(sem):.2f}x ({len(sem)})")
        top = sorted(linhas, key=lambda r: -r["razao"])
        rel.append("\nAS 10 MAIORES CAPAS DO NICHO (razão):")
        rel += [f"  {r['razao']:.1f}x · {r['canal']} · rosto={r['rosto']} · {r['titulo'][:70]}" for r in top[:10]]
        (saida / f"capas_{nicho}.txt").write_text("\n".join(rel), encoding="utf-8")
        folha([(r["arq"], f"{r['razao']:.1f}x {r['canal']}") for r in top[:16]], saida / f"melhores_{nicho}.jpg", "melhores")
        folha([(r["arq"], f"{r['razao']:.1f}x {r['canal']}") for r in top[-16:]], saida / f"piores_{nicho}.jpg", "piores")
        print("\n".join(rel))


if __name__ == "__main__":
    main()
