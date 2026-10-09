# -*- coding: utf-8 -*-
"""ALA GALO v2 — os jogadores reagem aos seus gestos.

    python tools/galo/gestos.py jogo.json

Usa o mesmo jogo.json do galo.py. Passos:
 1. rastreia seu corpo (rastrear.py -> <video>.movimento.json, reaproveitado nas próximas vezes);
 2. acha os gestos: PANCADA (mão desce rápido), TAPA (desce médio), CARINHO (desce devagar),
    EMPURRÃO (mão vai para fora rápido) e PUXÃO (mão vem para o seu corpo);
 3. divide o vídeo entre os jogadores (um por grupo de gestos) e monta:
    o jogador entra pela lateral, fica onde a sua mão bate, amassa e treme na pancada,
    voa no empurrão (e volta se você continuar), vem junto com a mão no puxão e sai no fim;
 4. efeitos sonoros sintetizados em cada gesto (sem trilha).

No final imprime a lista de gestos encontrados. Para corrigir, cole em "gestos" no jogo.json:
  "gestos": [[8.2, "pancada"], [10.6, "tapa"], [12.0, "empurrao"]]
"""
import json
import math
import subprocess
import sys
import urllib.request
import wave
from pathlib import Path

import cv2
import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import galo  # noqa: E402  (placar e recorte com contorno)

SR = 48000
FPS_SAIDA = 30


# ------------------------------------------------------------------ gestos

def carregar_movimento(video):
    arq = Path(str(video) + ".movimento.json")
    if not arq.exists():
        subprocess.run([sys.executable, str(AQUI / "rastrear.py"), str(video), str(arq)], check=True)
    return json.loads(arq.read_text(encoding="utf-8"))


def serie(q, nome):
    a = np.array([x[1].get(nome, [np.nan, np.nan, 0]) for x in q], float)
    a[a[:, 2] < 0.5, :2] = np.nan
    return a


def suave(v, n=3):
    m = np.isnan(v)
    v2 = np.where(m, np.interp(np.arange(len(v)), np.flatnonzero(~m), v[~m]) if (~m).any() else 0, v)
    return np.convolve(v2, np.ones(n) / n, mode="same")


def achar_gestos(mov):
    q, fps = mov["q"], mov["fps"]
    T = np.array([x[0] for x in q])
    oe, od = serie(q, "ombro_e"), serie(q, "ombro_d")
    sw = float(np.nanmedian(np.abs(oe[:, 0] - od[:, 0]))) or 300.0
    cx = suave((oe[:, 0] + od[:, 0]) / 2)
    ev = []
    for lado in "ed":
        p = serie(q, "pulso_" + lado)
        vis = ~np.isnan(p[:, 0])
        x, y = suave(p[:, 0]), suave(p[:, 1])
        vx, vy = np.gradient(x) * fps / sw, np.gradient(y) * fps / sw
        v = np.hypot(vx, vy)
        for i in range(4, len(v) - 4):
            if not vis[i] or v[i] < 5 or v[i] < v[i - 4:i + 5].max():
                continue
            j = i  # fim do golpe: a mão freia
            while j < min(len(v) - 1, i + int(0.3 * fps)) and v[j] > 0.4 * v[i]:
                j += 1
            if vy[i] > 1.2 * abs(vx[i]):
                tipo = "pancada" if v[i] >= 16 else "tapa" if v[i] >= 9 else "carinho"
            elif abs(vx[i]) > 1.2 * abs(vy[i]) and v[i] >= 7:
                fora = np.sign(vx[i]) == np.sign(x[i] - cx[i])
                tipo = "empurrao" if fora else "puxao"
            else:
                continue
            ev.append({"t": float(T[j]), "tipo": tipo, "forca": float(v[i]),
                       "x": float(x[j]), "y": float(y[j]), "xp": float(x[i]), "yp": float(y[i]), "lado": lado})
    ev.sort(key=lambda e: e["t"])
    juntos = []
    for e in ev:  # gestos a menos de 0,25 s = o mesmo gesto (fica o mais forte)
        if juntos and e["t"] - juntos[-1]["t"] < 0.25:
            if e["forca"] > juntos[-1]["forca"]:
                juntos[-1] = e
        else:
            juntos.append(e)
    return juntos, T, mov


def mao_em(mov, t):
    """posição da mão mais afastada do corpo no instante t (para o puxão)."""
    q = mov["q"]
    k = min(range(len(q)), key=lambda i: abs(q[i][0] - t))
    pts = q[k][1]
    cands = [pts.get(n) for n in ("pulso_e", "pulso_d") if pts.get(n) and pts[n][2] > 0.5]
    if not cands:
        return None
    meio = (pts["ombro_e"][0] + pts["ombro_d"][0]) / 2 if "ombro_e" in pts else mov["w"] / 2
    return max(cands, key=lambda c: abs(c[0] - meio))


# ------------------------------------------------------------------ plano por jogador

def planejar(cfg, gestos, dur, W, H):
    n = len(cfg["jogadores"])
    if len(gestos) < n:  # poucos gestos: o resto dos jogadores só passa
        cortes = [k * dur / n for k in range(1, n)]
    else:  # cortes perto da divisão igual, na maior pausa entre gestos de cada região
        ini, fim = gestos[0]["t"] - 0.6, gestos[-1]["t"] + 0.7
        vaga = (fim - ini) / n
        meios = [((gestos[i - 1]["t"] + gestos[i]["t"]) / 2, gestos[i]["t"] - gestos[i - 1]["t"]) for i in range(1, len(gestos))]
        cortes = []
        for k in range(1, n):
            ideal = ini + k * vaga
            perto = [m for m in meios if abs(m[0] - ideal) < 0.3 * vaga and all(m[0] > c for c in cortes)]
            cortes.append(max(perto, key=lambda m: m[1])[0] if perto else
                          min((m for m in meios if all(m[0] > c for c in cortes)), key=lambda m: abs(m[0] - ideal),
                              default=(ideal, 0))[0])
    limites = [0.0] + cortes + [dur]
    planos = []
    for k, j in enumerate(cfg["jogadores"]):
        a, b = limites[k], limites[k + 1]
        meus = [g for g in gestos if a <= g["t"] < b]
        alvo = [g for g in meus if g["tipo"] in ("pancada", "tapa", "carinho")] or meus
        if alvo:
            px = float(np.median([g.get("xp", g["x"]) for g in alvo]))
            topo = float(np.median([g.get("yp", g["y"]) for g in alvo])) - H * 0.03  # a mão bate no alto da cabeça
        else:
            px, topo = W * 0.68, H * 0.55
        altura = float(np.clip(H - topo + H * 0.04, H * float(j.get("min", 0.38)), H * float(j.get("max", 0.58))))
        entra = max(0.0, (meus[0]["t"] - 0.6) if meus else a + 0.2)
        sai = min(dur, (meus[-1]["t"] + 0.7) if meus else b - 0.2)
        if meus and meus[-1]["tipo"] == "empurrao":
            sai = meus[-1]["t"] + 0.45  # sai voando
        planos.append({"nome": j["nome"], "jog": j, "x": px, "altura": altura, "entra": entra,
                       "sai": max(sai, entra + 1.0), "gestos": meus, "passa": not meus,
                       "borda": W + 50 if px > W / 2 else -50})
    return planos


def ease(u):
    u = min(1.0, max(0.0, u))
    return 1 - (1 - u) ** 3


def estado(p, t, W, mov):
    """x, sx, sy, rot, dy do jogador no instante t (ou None se fora da tela)."""
    if t < p["entra"] or t > p["sai"]:
        return None
    lado_fora = p["borda"]
    if p["passa"]:  # sem gestos: atravessa a tela
        u = (t - p["entra"]) / (p["sai"] - p["entra"])
        return dict(x=-0.3 * W + u * 1.6 * W if lado_fora > 0 else 1.3 * W - u * 1.6 * W, sx=1, sy=1, rot=0, dy=0)
    x = p["x"]
    sx = sy = 1.0
    rot = dy = 0.0
    u = (t - p["entra"]) / 0.32
    if u < 1:
        x = lado_fora + (x - lado_fora) * ease(u) * (1 + 0.06 * math.sin(math.pi * u))
    for g in p["gestos"]:
        d = t - g["t"]
        if g["tipo"] == "puxao" and 0 <= d:
            mao = mao_em(mov, min(t, g["t"] + 0.6))
            if mao:
                x = x + (mao[0] - x) * ease(d / 0.25)
        if d < -0.02 or d > 0.6:
            continue
        if g["tipo"] in ("pancada", "tapa", "carinho"):
            k = {"pancada": 0.14, "tapa": 0.07, "carinho": 0.035}[g["tipo"]]
            amort = math.exp(-d * 9) * math.cos(d * 38)
            sy *= 1 - k * amort
            sx *= 1 + k * 0.5 * amort
            x += {"pancada": 14, "tapa": 7, "carinho": 2}[g["tipo"]] * math.sin(d * 60) * math.exp(-d * 10)
        elif g["tipo"] == "empurrao":
            sentido = 1 if g["x"] > W / 2 else -1
            voo = ease(d / 0.35)
            volta = g is not p["gestos"][-1]
            if volta and d > 0.35:
                voo = 1 - ease((d - 0.35) / 0.25)
            x += sentido * W * 0.75 * voo
            rot = sentido * 25 * voo
    if t > p["sai"] - 0.3 and not (p["gestos"] and p["gestos"][-1]["tipo"] == "empurrao"):
        x = x + (lado_fora - x) * ease((t - (p["sai"] - 0.3)) / 0.3)
    return dict(x=x, sx=sx, sy=sy, rot=rot, dy=dy)


# ------------------------------------------------------------------ desenho

def colar(frame, rgba, cx, base_y):
    h, w = rgba.shape[:2]
    x0, y0 = int(round(cx - w / 2)), int(round(base_y - h))
    H, W = frame.shape[:2]
    a0, b0 = max(0, x0), max(0, y0)
    a1, b1 = min(W, x0 + w), min(H, y0 + h)
    if a1 <= a0 or b1 <= b0:
        return
    sub = rgba[b0 - y0:b1 - y0, a0 - x0:a1 - x0]
    al = sub[..., 3:4].astype(np.float32) / 255
    roi = frame[b0:b1, a0:a1]
    roi[:] = (sub[..., :3] * al + roi * (1 - al)).astype(np.uint8)


def transformar(img, sx, sy, rot):
    h, w = img.shape[:2]
    img = cv2.resize(img, (max(1, int(w * sx)), max(1, int(h * sy))), interpolation=cv2.INTER_LINEAR)
    if abs(rot) > 0.5:
        h, w = img.shape[:2]
        pad = int(max(h, w) * 0.3)
        img = cv2.copyMakeBorder(img, pad, 0, pad, pad, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0))
        M = cv2.getRotationMatrix2D((img.shape[1] / 2, img.shape[0]), rot, 1)
        img = cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), borderValue=(0, 0, 0, 0))
    return img


# ------------------------------------------------------------------ sons

def som(tipo, forca=10):
    n = lambda s: int(SR * s)  # noqa: E731
    rng = np.random.default_rng(len(tipo))
    if tipo == "pancada":  # soco grave + estalo
        t = np.arange(n(0.35)) / SR
        corpo = np.sin(2 * np.pi * (140 * np.exp(-t * 9) + 45) * t) * np.exp(-t * 11)
        estalo = rng.normal(0, 1, len(t)) * np.exp(-t * 60)
        return 0.9 * corpo + 0.45 * estalo
    if tipo == "tapa":
        t = np.arange(n(0.18)) / SR
        r = rng.normal(0, 1, len(t))
        r = r - np.convolve(r, np.ones(6) / 6, "same")  # mais agudo
        return 0.8 * r * np.exp(-t * 45)
    if tipo == "carinho":  # "boing" suave
        t = np.arange(n(0.3)) / SR
        return 0.35 * np.sin(2 * np.pi * (520 + 180 * np.sin(t * 30)) * t) * np.exp(-t * 9)
    if tipo in ("empurrao", "whoosh"):
        t = np.arange(n(0.4)) / SR
        r = rng.normal(0, 1, len(t))
        r = np.convolve(r, np.ones(18) / 18, "same")
        env = np.sin(np.pi * t / t[-1]) ** 2
        return (1.6 if tipo == "empurrao" else 0.8) * r * env * 3
    if tipo == "puxao":  # zíper rápido
        t = np.arange(n(0.25)) / SR
        return 0.4 * np.sign(np.sin(2 * np.pi * (300 + 1500 * t / t[-1]) * t)) * np.exp(-t * 6) * 0.6
    return np.zeros(1)


def trilha_sfx(planos, dur, destino):
    pista = np.zeros(int(SR * (dur + 1)), np.float32)

    def por(t, s):
        i = int(max(0, t) * SR)
        f = min(len(pista), i + len(s))
        pista[i:f] += s[:f - i]

    for p in planos:
        por(p["entra"], som("whoosh"))
        for g in p["gestos"]:
            por(g["t"] - 0.02, som(g["tipo"], g["forca"]))
        if not (p["gestos"] and p["gestos"][-1]["tipo"] == "empurrao"):
            por(p["sai"] - 0.3, som("whoosh"))
    pista = np.clip(pista, -1, 1)
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((pista * 32000).astype(np.int16).tobytes())


# ------------------------------------------------------------------ principal

def foto_online(nome, destino):
    """Recorte oficial do jogador (TheSportsDB) quando não há foto no banco."""
    url = "https://www.thesportsdb.com/api/v1/json/3/searchplayers.php?p=" + urllib.request.quote(nome)
    try:
        d = json.loads(urllib.request.urlopen(url, timeout=20).read()).get("player") or []
    except Exception:
        return None
    d.sort(key=lambda x: "Mineiro" not in (x.get("strTeam") or ""))
    for x in d:
        if x.get("strCutout"):
            destino.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(x["strCutout"], destino)
            return destino
    return None


def main():
    cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    video = Path(cfg["video"])
    mov = carregar_movimento(video)
    W, H = mov["w"], mov["h"]
    _, _, dur = galo.sonda(video)

    if cfg.get("gestos"):
        gestos = []
        for t, tipo in cfg["gestos"]:
            m = mao_em(mov, t) or [W * 0.6, H * 0.6]
            gestos.append({"t": float(t), "tipo": tipo, "forca": 12.0, "x": m[0], "y": m[1], "lado": "?"})
    else:
        gestos, _, _ = achar_gestos(mov)
    planos = planejar(cfg, gestos, dur, W, H)

    imgs = []
    for p in planos:
        j = dict(p["jog"])
        if not j.get("foto"):
            try:
                galo.achar_foto(j)
            except SystemExit:
                f = foto_online(j["nome"], galo.BANCO / "elenco" / f"{galo.slug(j['nome'])}.png")
                if not f:
                    raise SystemExit(f"Sem foto para {j['nome']} (nem no banco, nem online)")
        rec = galo.recorte(j, p["altura"])
        imgs.append(cv2.cvtColor(np.array(rec), cv2.COLOR_RGBA2BGRA))

    placar = None
    if cfg.get("placar"):
        placar = cv2.cvtColor(np.array(galo.placar_png(cfg["placar"], W)), cv2.COLOR_RGBA2BGRA)
        if "placar_y" not in cfg:  # acima da sua cabeça
            nar = serie(mov["q"], "nariz")[:, 1]
            oe, od = serie(mov["q"], "ombro_e"), serie(mov["q"], "ombro_d")
            sw = float(np.nanmedian(np.abs(oe[:, 0] - od[:, 0]))) or 300.0
            cabeca = float(np.nanpercentile(nar, 5)) - 0.75 * sw
            cfg["placar_y"] = float(np.clip((cabeca - placar.shape[0] - 20) / H, 0.02, 0.15))

    trab = Path(cfg.get("trabalho") or video.with_name("galo_tmp"))
    trab.mkdir(parents=True, exist_ok=True)
    trilha_sfx(planos, dur, trab / "sfx.wav")

    saida = cfg.get("saida") or str(video.with_name("galo_gestos.mp4"))
    cap = cv2.VideoCapture(str(video))
    fps_in = cap.get(cv2.CAP_PROP_FPS) or 30
    passo = max(1, round(fps_in / FPS_SAIDA))
    fps_out = fps_in / passo
    filtro_audio = ("[1:a][2:a]amix=inputs=2:duration=first:normalize=0[a]" if cfg.get("audio_original", True)
                    else "[2:a]anull[a]")
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", f"{fps_out:.5f}",
         "-i", "-", "-i", str(video), "-i", str(trab / "sfx.wav"),
         "-filter_complex", filtro_audio,
         "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", saida], stdin=subprocess.PIPE)
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % passo:
            i += 1
            continue
        t = i / fps_in
        i += 1
        if f.shape[1] != W or f.shape[0] != H:
            f = cv2.resize(f, (W, H))
        if placar is not None:
            colar(f, placar, W / 2, H * float(cfg.get("placar_y", 0.15)) + placar.shape[0])
        for p, img in zip(planos, imgs):
            e = estado(p, t, W, mov)
            if e:
                colar(f, transformar(img, e["sx"], e["sy"], e["rot"]), e["x"], H + e["dy"])
        ff.stdin.write(f.tobytes())
        if i % 150 == 0:
            print(f"\r{t:6.1f} / {dur:.1f} s", end="", flush=True)
    cap.release()
    ff.stdin.close()
    ff.wait()
    print("\nGestos usados (corrija e cole em \"gestos\" no jogo.json se precisar):")
    print(json.dumps([[round(g["t"], 2), g["tipo"]] for g in gestos], ensure_ascii=False))
    for p in planos:
        print(f"  {p['nome']}: {p['entra']:.1f}s → {p['sai']:.1f}s, {len(p['gestos'])} gestos")
    print(f"Pronto: {saida}")


if __name__ == "__main__":
    main()
