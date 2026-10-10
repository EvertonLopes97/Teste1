# -*- coding: utf-8 -*-
"""ALA GALO — "o elenco passando" (v4: roteiro de gestos + rastreio da mão e do rosto).

    python tools/galo/passagem.py jogo.json
    python tools/galo/passagem.py "E:/DETTO/galo/IMG_1900.MOV" "Atletico Mineiro Cruzeiro"   (sem json)

1. Rastreia seu corpo (rastrear.py) e escreve <video>.roteiro.json com o que você fez:
     entra   → rosto olha para a direita: o jogador chega pela direita
     passa   → rosto acompanha até a esquerda: ele atravessa NA VELOCIDADE DO ROSTO e sai
     puxa    → a mão vai buscar do outro lado: ele volta preso na mão
     carinho → a mão encosta de leve: ele balança
     bate    → a mão sobe e desce: ele afunda (fraco = meio corpo, forte = só a cabecinha)
               e sobe de volta já no lugar exato da próxima batida
     joga    → agarra e arremessa para o lado: voa para fora (som de chicote)
   O jogador só sai da tela com "passa" (sem puxão logo depois) ou "joga".
2. Notas do SofaScore: quem apanha mais (e mais forte) recebe as piores notas — a pior fica com
   quem apanha no fim; quem só passa ou ganha carinho recebe as melhores.
3. Placar do Google no alto, sons de soco / chicote / whoosh (Mixkit, uso livre).

Para corrigir um gesto: edite <video>.roteiro.json e rode de novo (ele usa o arquivo editado;
"refazer_roteiro": true no jogo.json gera de novo do zero).

jogo.json:
{
  "video": "C:/.../IMG_1853.MOV",
  "jogo": "Athletico Atletico Mineiro",
  "time": "Atlético Mineiro",
  "jogadores": ["Nome", ...],   // opcional: ordem manual em vez das notas
  "com_placar": false,          // placar do Google no alto (padrão: sem)
  "saida": "....mp4"            // o vídeo começa quando o 1º jogador entra e acaba quando o último sai
}
"""
import json
import math
import subprocess
import sys
import urllib.parse
import wave
from pathlib import Path

import cv2
import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent))
import galo  # noqa: E402
from cor import sdr_se_preciso  # noqa: E402
import gestos as G  # noqa: E402

UA = "Mozilla/5.0"
SR = 48000


# ================================================================== internet

def get_json(url):
    # curl_cffi (pip install curl_cffi) se passa pelo Chrome: o SofaScore não bloqueia (403)
    try:
        from curl_cffi import requests as cr
        r = cr.get(url, impersonate="chrome", timeout=25, headers={"Referer": "https://www.sofascore.com/"})
        if r.status_code == 200:
            return r.json()
    except Exception:  # noqa: BLE001 — sem curl_cffi ou falhou: tenta o curl
        pass
    r = subprocess.run(["curl", "-sS", "-m", "25", "-A", UA, "-H", "Referer: https://www.sofascore.com/", url], capture_output=True)
    try:
        return json.loads(r.stdout.decode("utf-8", "replace") or "{}")
    except json.JSONDecodeError:
        return {}


def baixar(url, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["curl", "-sSfL", "-m", "60", "-A", UA, "-o", str(destino), url], check=True)
    return destino


def dados_sofascore(busca, time):
    r = get_json("https://api.sofascore.com/api/v1/search/all?q=" + urllib.parse.quote(busca))
    evs = [x["entity"] for x in r.get("results", []) if "startTimestamp" in x.get("entity", {})
           and x["entity"].get("status", {}).get("type") == "finished"]
    if not evs:
        raise SystemExit(f"Jogo não encontrado no SofaScore: {busca}")
    ev = get_json(f"https://api.sofascore.com/api/v1/event/{max(evs, key=lambda e: e['startTimestamp'])['id']}")["event"]
    lin = get_json(f"https://api.sofascore.com/api/v1/event/{ev['id']}/lineups")
    lado = "home" if galo.slug(time)[:6] in galo.slug(ev["homeTeam"]["name"]) else "away"
    notas = sorted((p["statistics"]["rating"], p["player"]["name"], p["player"].get("shortName", ""))
                   for p in lin[lado]["players"] if p.get("statistics", {}).get("rating"))
    placar = {"competicao": ev["tournament"]["name"].replace("Campeonato Brasileiro", "Brasileirão"),
              "quando": "Hoje", "status": "Encerrado",
              "casa": ev["homeTeam"].get("shortName") or ev["homeTeam"]["name"],
              "fora": ev["awayTeam"].get("shortName") or ev["awayTeam"]["name"],
              "gols_casa": ev["homeScore"].get("current", ""), "gols_fora": ev["awayScore"].get("current", "")}
    for k, t in (("casa", ev["homeTeam"]["name"]), ("fora", ev["awayTeam"]["name"])):
        dest = galo.BANCO / "escudos" / f"{galo.slug(t)}.png"
        if not dest.exists():
            tm = get_json("https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t=" + urllib.parse.quote(t)).get("teams") or []
            if tm and tm[0].get("strBadge"):
                baixar(tm[0]["strBadge"], dest)
        if dest.exists():
            placar[f"escudo_{k}"] = str(dest)
    return placar, notas


def foto_jogador(nome, apelido=""):
    """Banco do elenco oficial (tools/galo/banco/elenco, atualizado por elenco_site.py)."""
    alvos = {galo.slug(nome), galo.slug(apelido or nome)}
    if " " in nome:
        alvos.add(galo.slug(nome.split()[-1]))
    for p in sorted((galo.BANCO / "elenco").glob("*.*")):
        if p.stem in alvos:
            return p
    return None


# ================================================================== sons (Mixkit, licença livre)

# nome do efeito → categorias da biblioteca (pasta do PACK DE EDIÇÃO; senão Mixkit), duração
SONS = {
    "forte": (["soco"], 0.9), "fraco": (["tapa", "soco"], 0.5), "carinho": (["tapa", "pop"], 0.35),
    "chicote": (["chicote", "whoosh"], 0.9), "passa": (["whoosh"], 1.2), "puxa": (["whoosh"], 0.8),
}
VOL = {"forte": 1.0, "fraco": 0.85, "carinho": 0.5, "chicote": 1.0, "passa": 0.8, "puxa": 0.7}
_SOM = {}


def som(nome, n=0):
    import biblioteca_sons as B
    cats, dur = SONS[nome]
    chave = (nome, n % 3)
    if chave not in _SOM:
        arq = next((x for x in (B.arquivo(cc, n) for cc in cats) if x), None)
        _SOM[chave] = (B.carregar(arq, dur) if arq else np.zeros(1, np.float32)) * VOL[nome]
    return _SOM[chave]


# ================================================================== leitura dos gestos

class Corpo:
    def __init__(self, mov):
        q = mov["q"]
        self.T = np.array([x[0] for x in q])
        self.fps = mov["fps"]
        oe, od = G.serie(q, "ombro_e"), G.serie(q, "ombro_d")
        self.sw = float(np.nanmedian(np.abs(oe[:, 0] - od[:, 0])))
        self.mid = G.suave((oe[:, 0] + od[:, 0]) / 2)
        self.shy = G.suave((oe[:, 1] + od[:, 1]) / 2)
        self.px, self.py, self.rx, self.ry, self.vy = {}, {}, {}, {}, {}
        for lado in "ed":
            p = G.serie(q, "pulso_" + lado)
            self.px[lado], self.py[lado] = G.suave(p[:, 0]), G.suave(p[:, 1])
            self.rx[lado] = (self.px[lado] - self.mid) / self.sw   # + = direita da tela
            self.ry[lado] = (self.py[lado] - self.shy) / self.sw   # + = abaixo do ombro
            self.vy[lado] = np.gradient(self.py[lado]) * self.fps / self.sw
        self.olhar = self._olhar(q)

    def _olhar(self, q):
        nar = G.serie(q, "nariz")[:, 0]
        re_, rd = G.serie(q, "orelha_e"), G.serie(q, "orelha_d")
        y = (nar - (re_[:, 0] + rd[:, 0]) / 2) / (0.35 * self.sw)
        y = y / (np.nanpercentile(np.abs(y), 92) / 0.7)
        y[np.abs(y) > 1.3] = np.nan  # braço na frente do rosto
        y = G.suave(y, 1)
        y = np.array([np.median(y[max(0, i - 3):i + 4]) for i in range(len(y))])
        return G.suave(y, 5)

    def i(self, t):
        return int(np.clip(np.searchsorted(self.T, t), 0, len(self.T) - 1))

    def mao(self, lado, t):
        k = self.i(t)
        return float(self.px[lado][k]), float(self.py[lado][k])

    def ol(self, t):
        return float(self.olhar[self.i(t)])


def detectar(c):
    T, f = c.T, c.fps
    ev = []
    for lado in "ed":
        rx, ry, vy = c.rx[lado], c.ry[lado], c.vy[lado]
        casa = np.sign(np.nanmedian(rx))       # lado da tela onde essa mão descansa
        base = float(np.nanmedian(ry))          # altura de descanso (quadril)
        # BATE: rajada de socos — a mão sobe acima do ombro e CADA descida rápida é um soco
        # (3 socos seguidos contam 3; o que desce até o quadril costuma ser o mais forte)
        k = 0
        while k < len(T) - 1:
            if ry[k] < 0.05:
                fim = k  # a rajada acaba quando a mão volta ao quadril (ou em 1,5 s)
                while fim + 1 < len(T) and T[fim] - T[k] < 1.5 and not (ry[fim] > base - 0.2 and T[fim] - T[k] > 0.1):
                    fim += 1
                i, socos = k, []
                while i < fim:
                    if vy[i] > 4.5 and vy[i] >= np.nanmax(vy[max(0, i - 2):i + 3]):
                        j = i
                        while j + 1 <= fim and vy[j + 1] > 0.5:
                            j += 1
                        # contato: onde a mão para de descer; se desceu até o quadril, no meio da descida
                        cont = i + 1 if ry[j] > base - 0.2 else j
                        if abs(rx[cont]) < 0.75 and ry[cont] > -0.3:
                            socos.append((cont, float(vy[i])))
                        i = j + 1
                        continue
                    i += 1
                for cont, pico in socos:
                    ev.append(["bate", float(T[cont]), float(T[cont]), lado, "forte" if pico >= 10 else "fraco"])
                k = fim + 1 if socos else k + 1
                continue
            k += 1
        # JOGA: braço esticado para fora e cruza o corpo até o outro lado
        # PUXA: a mão cruza o corpo na altura da cintura (foi buscar) e volta
        k = 0
        while k < len(T) - 1:
            if casa * rx[k] > 0.85 or (casa * rx[k] > 0.75 and ry[k] < 0.7):
                j = k
                while j + 1 < len(T) and casa * rx[j] > -0.2 and T[j] - T[k] < 0.8:
                    j += 1
                if casa * rx[j] <= -0.2:
                    ev.append(["joga", float(T[k]), float(T[j]), lado])  # solta quando cruza o corpo
                    k = j + int(0.5 * f)
                    continue
            if casa * rx[k] < -0.15 and ry[k] > 0.5:
                j = k
                while j + 1 < len(T) and casa * rx[j] < 0.4 and T[j] - T[k] < 1.2:
                    j += 1
                if casa * rx[j] >= 0.4:
                    ini = k
                    while ini > 0 and casa * rx[ini - 1] < casa * rx[ini] and T[k] - T[ini] < 0.4:
                        ini -= 1
                    ev.append(["puxa", float(T[ini]), float(T[j]), lado])
                    k = j + int(0.3 * f)
                    continue
            k += 1
        # CARINHO: só essa mão sai do quadril e encosta de leve
        outra = "d" if lado == "e" else "e"
        base_o = float(np.nanmedian(c.ry[outra]))
        k = 0
        while k < len(T):
            if base - ry[k] > 0.15 and ry[k] > 0.35 and abs(rx[k]) > 0.2:
                j = k
                while j + 1 < len(T) and base - ry[j + 1] > 0.1:
                    j += 1
                m = k + int(np.argmin(ry[k:j + 1]))
                outra_parada = base_o - c.ry[outra][m] < 0.3
                if 0.15 <= T[j] - T[k] <= 1.2 and outra_parada:
                    ev.append(["carinho", float(T[m]), float(T[m]), lado, float(base - ry[m])])
                k = j + 1
            else:
                k += 1
    jogas = [e for e in ev if e[0] == "joga"]
    puxas = [e for e in ev if e[0] == "puxa"]
    ev = [e for e in ev if not (
        (e[0] == "bate" and any(j[1] - 0.1 <= e[1] <= j[2] + 0.7 for j in jogas)) or
        (e[0] in ("carinho", "puxa") and any(j[1] - 0.45 <= e[1] <= j[2] + 0.45 for j in jogas)) or
        (e[0] == "carinho" and any(p[1] - 0.2 <= e[1] <= p[2] + 0.5 for p in puxas)) or
        (e[0] == "carinho" and any(b[0] == "bate" and -0.5 < b[1] - e[1] < 0.65 for b in ev)))]
    car = sorted([e for e in ev if e[0] == "carinho"], key=lambda e: e[1])
    for a, b in zip(car, car[1:]):  # as duas mãos ao mesmo tempo: fica a que mexeu mais
        if b[1] - a[1] < 0.5 and a in ev and b in ev:
            ev.remove(a if a[4] < b[4] else b)
    # olhar: extremos para a direita (alguém chegando) e para a esquerda (passou)
    ol = c.olhar
    for k in range(3, len(ol) - 3):
        if abs(ol[k]) > 0.38 and abs(ol[k]) == np.abs(ol[max(0, k - 12):k + 13]).max():
            if any(e[1] - 0.3 <= T[k] <= e[2] + 0.5 for e in ev if e[0] in ("joga", "bate")):
                continue
            ini = k  # começo do movimento do rosto
            while ini > 0 and abs(ol[ini - 1]) > 0.3 and np.sign(ol[ini - 1]) == np.sign(ol[k]):
                ini -= 1
            ev.append(["olha_dir" if ol[k] > 0 else "olha_esq", float(T[ini]), float(T[k]), None])
    return sorted(ev, key=lambda e: e[1])


def ler_roteiro(c):
    """Máquina de estados: um jogador por vez, que só sai com 'passa' (sem puxão) ou 'joga'."""
    jogs, atual, passou = [], None, None

    def fecha():
        nonlocal atual, passou
        if atual:
            jogs.append(atual)
        atual, passou = None, None

    for e in detectar(c):
        tipo, t = e[0], round(e[1], 2)
        if atual and passou is not None and t - passou > 1.7 and tipo != "puxa":
            fecha()  # passou e ninguém puxou: já saiu
        if atual is None:
            if tipo == "olha_dir":
                atual = {"entra_ini": t, "entra": round(e[2], 2), "acoes": []}
            continue
        if tipo == "olha_dir":
            if passou is not None and t - passou > 0.8:
                fecha()
                atual = {"entra_ini": t, "entra": round(e[2], 2), "acoes": []}
            continue
        if tipo == "olha_esq":
            if passou is None and not any(a[0] in ("bate", "carinho") for a in atual["acoes"]):
                atual["acoes"].append(["passa", t, round(e[2], 2)])
                passou = t
            continue
        if tipo == "puxa":
            atual["acoes"].append(["puxa", t, round(e[2], 2), e[3]])
            passou = None
        elif tipo == "bate":
            if passou is None:
                atual["acoes"].append(["bate", t, e[4], e[3]])
        elif tipo == "carinho":
            if passou is None:
                atual["acoes"].append(["carinho", t, e[3]])
        elif tipo == "joga":
            atual["acoes"].append(["joga", t, round(e[2], 2), e[3]])
            fecha()
    fecha()
    return jogs


# ================================================================== movimento do jogador

def ease(u):
    u = min(1.0, max(0.0, u))
    return 1 - (1 - u) ** 3


def suave_io(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def fim_passa(a):
    return (a[2] if len(a) > 2 else a[1] + 0.4) + 0.05


def progresso_olhar(c, ta, tb, ts):
    """0→1 entre ta e tb no ritmo em que o rosto vira (só anda para a frente, sem tremer)."""
    k0, k1 = c.i(ta), c.i(tb)
    g = c.olhar[k0:k1 + 1]
    lin = np.clip((ts - ta) / max(1e-3, tb - ta), 0, 1)
    if len(g) < 3 or abs(g[-1] - g[0]) < 0.25:
        return lin * lin * (3 - 2 * lin)
    u = np.clip((g - g[0]) / (g[-1] - g[0]), 0, 1)
    u = np.maximum.accumulate(u)
    u = np.convolve(np.pad(u, 3, mode="edge"), np.ones(7) / 7, mode="valid")
    tt = c.T[k0:k1 + 1]
    u = np.interp(ts, tt, u, left=0.0, right=1.0)
    return 0.85 * u + 0.15 * lin


def trajetoria(jog, c, W, H, hjog, dur, fps=30):
    """Desliza na entrada e na passagem (ritmo do rosto); parado no lugar onde você o deixa;
    nas batidas mexe só um pouco para os lados; preso na mão no puxão e no arremesso."""
    wj = hjog * 0.62
    fora_dir, fora_esq = W + wj * 0.55, -wj * 0.55
    ac = jog["acoes"]
    e1 = jog["entra"]
    e0 = min(jog.get("entra_ini", e1 - 0.6), e1 - 0.35)
    t_ini = max(0.0, e0 - 0.1)
    ult = ac[-1] if ac else None
    if ult is None:
        t_fim = min(dur, e1 + 3.0)
    elif ult[0] == "joga":
        t_fim = min(dur, ult[2] + 0.45)
    elif ult[0] == "passa":
        t_fim = min(dur, fim_passa(ult) + 0.15)
    else:
        t_fim = dur
    ts = np.arange(t_ini, t_fim, 1 / fps)
    lim = (wj * 0.42, W - wj * 0.42)

    def mao_x(a, t=None):
        return c.mao(a[-1], a[1] if t is None else t)[0]

    # trechos de movimento base: (ta, tb, xa, xb, modo) com modo "olhar" | "suave" | "mao"
    trechos = [(t_ini, e1, fora_dir, W * 0.78, "olhar")]
    t_cur, x_cur, contatos = e1, W * 0.78, 0
    for a in ac:
        if a[0] == "passa":
            trechos.append((t_cur, fim_passa(a), x_cur, fora_esq, "olhar"))
            t_cur, x_cur, contatos = fim_passa(a), fora_esq, 0
        elif a[0] == "puxa":
            # puxão: se ele já tinha saído, vem de FORA da imagem para dentro, no ritmo da sua mão
            trechos.append((a[1], a[2], x_cur, None, ("puxa_fora" if x_cur <= fora_esq + 1 else "mao", a[3])))
            t_cur, x_cur, contatos = a[2], float(np.clip(c.mao(a[3], a[2])[0], *lim)), 1  # fica onde soltou
        elif a[0] in ("bate", "carinho"):
            alvo = float(np.clip(mao_x(a), *lim))
            if contatos:  # já está no lugar: só um ajuste pequeno, perto de onde a mão bate
                rapido = a[0] == "bate" and t_cur > a[1] - 0.65
                alvo = x_cur if rapido else x_cur + float(np.clip(alvo - x_cur, -0.06 * W, 0.06 * W))
            tb = max(t_cur + 0.05, a[1] - 0.12)
            if contatos:  # parado até perto da batida, então um ajuste curto
                trechos.append((max(t_cur, tb - 0.4), tb, x_cur, alvo, "suave"))
            else:         # chegando: anda até onde você vai bater, no ritmo do rosto
                trechos.append((t_cur, tb, x_cur, alvo, "olhar"))
            t_cur, x_cur, contatos = a[1] + 0.05, alvo, contatos + 1
        elif a[0] == "joga":
            trechos.append((t_cur, a[1], x_cur, x_cur, "suave"))
            trechos.append((a[1], a[2], x_cur, None, ("agarra", a[3])))
            t_cur = a[2]

    base = np.full(len(ts), np.nan)
    for ta, tb, xa, xb, modo in trechos:
        m = (ts >= ta) & (ts <= tb)
        if not m.any():
            continue
        if modo == "olhar":
            u = progresso_olhar(c, ta, tb, ts[m])
            base[m] = xa + (xb - xa) * u
        elif modo == "suave":
            u = np.clip((ts[m] - ta) / max(1e-3, tb - ta), 0, 1)
            base[m] = xa + (xb - xa) * u * u * (3 - 2 * u)
        elif modo[0] == "puxa_fora":
            tt = ts[m]
            hx = np.array([c.mao(modo[1], t)[0] for t in tt])
            g = int(np.argmin(hx))                  # momento em que a mão alcança lá fora (agarra)
            solta = hx[-1]
            u = np.clip((hx - hx[g]) / max(1.0, solta - hx[g]), 0, 1)
            u[:g] = 0
            u = np.maximum.accumulate(u)            # só vem para dentro
            base[m] = xa + (solta - xa) * u
        elif modo[0] == "mao":  # já estava na tela: vai até a mão sem pular
            k = np.clip((ts[m] - ta) / 0.25, 0, 1)
            k = k * k * (3 - 2 * k)
            base[m] = [xa + (c.mao(modo[1], t)[0] - xa) * q for t, q in zip(ts[m], k)]
        elif modo[0] == "agarra":
            u = np.clip((ts[m] - ta) / 0.2, 0, 1)
            u = 1 - (1 - u) ** 3
            base[m] = [xa + (c.mao(modo[1], t)[0] - xa) * k for t, k in zip(ts[m], u)]
    # fora dos trechos: fica parado onde estava
    ultimo = fora_dir
    for k in range(len(base)):
        if np.isnan(base[k]):
            base[k] = ultimo
        ultimo = base[k]

    xs, dys, rots, vis = [], [], [], []
    for k, t in enumerate(ts):
        x = float(base[k])
        dy = rot = 0.0
        dy_mao = None
        bate_dy = 0.0
        visivel = True
        for n, a in enumerate(ac):
            if a[0] == "passa" and t > fim_passa(a):
                prox = ac[n + 1] if n + 1 < len(ac) else None
                if not (prox and prox[0] == "puxa" and t >= prox[1]):
                    visivel = False
            if a[0] in ("puxa", "joga") and a[1] <= t <= a[2]:  # preso na mão: sobe junto
                hy = c.mao(a[3], t)[1]
                alvo_dy = float(np.clip(hy - 0.02 * H - (H - hjog), -0.18 * H, 0.3 * hjog))
                dy_mao = alvo_dy * ease((t - a[1]) / 0.15)
            if a[0] == "puxa" and 0 < t - a[2] < 0.3:  # soltou: desce de volta ao chão
                hy = c.mao(a[3], a[2])[1]
                d0 = float(np.clip(hy - 0.02 * H - (H - hjog), -0.18 * H, 0.3 * hjog))
                dy += d0 * (1 - ease((t - a[2]) / 0.3))
            if a[0] == "joga" and t > a[2]:  # arremessado para o lado
                d = t - a[2]
                xa, xb = c.mao(a[3], a[2] - 0.12)[0], c.mao(a[3], a[2])[0]
                lado = -1 if xb < xa else 1
                x = xb + lado * W * 1.1 * ease(d / 0.35)
                rot = -lado * 35 * ease(d / 0.35)
                hy = c.mao(a[3], a[2])[1]
                d0 = float(np.clip(hy - 0.02 * H - (H - hjog), -0.18 * H, 0.3 * hjog))
                dy_mao = d0 * (1 - ease(d / 0.35)) - 0.08 * hjog * math.sin(min(1.0, d / 0.35) * math.pi)
            if a[0] == "bate":
                d = t - a[1]
                prof = 0.86 if a[2] == "forte" else 0.45
                prox_b = next((b2[1] for b2 in ac[n + 1:] if b2[0] == "bate"), None)
                segura = 0.22 if prox_b is None else min(0.22, max(0.0, prox_b - a[1]))
                env = 0.0
                if 0 <= d < 0.08:
                    env = prof * ease(d / 0.08)
                elif 0.08 <= d < 0.08 + segura:
                    env = prof
                elif d >= 0.08 + segura and d < 0.48 + segura:
                    u = (d - 0.08 - segura) / 0.4
                    env = prof * (1 - ease(u)) - 0.04 * math.sin(math.pi * u)
                bate_dy = max(bate_dy, env * hjog)
                if 0 <= d < 0.18:  # tranco de cada soco, mesmo já estando lá embaixo
                    bate_dy += 0.06 * hjog * math.sin(d / 0.18 * math.pi)
                    x += 4 * math.sin(d * 70) * math.exp(-d * 12)
            if a[0] == "carinho":
                d = t - a[1]
                if 0 <= d < 0.5:
                    dy += 0.06 * hjog * math.sin(d * 22) * math.exp(-d * 6)
        dy += bate_dy
        if dy_mao is not None:
            dy = dy_mao
        xs.append(x)
        dys.append(dy)
        rots.append(rot)
        vis.append(visivel)
    return {"t": ts, "x": np.array(xs), "dy": np.array(dys), "rot": np.array(rots), "vis": np.array(vis)}


def altura_jogador(jog, c, H):
    """Escala para a cabeça ficar onde a sua mão bate."""
    ys = [c.mao(a[-1], a[1])[1] for a in jog["acoes"] if a[0] in ("bate", "carinho")]
    if not ys:
        return H * 0.45
    alvo = float(np.median(ys)) + 0.03 * H
    return float(np.clip(H - alvo, H * 0.38, H * 0.60))


# ================================================================== principal

def main():
    if sys.argv[1].lower().endswith(".json"):
        cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    else:  # direto: passagem.py "video.MOV" "Atletico Mineiro Cruzeiro"
        cfg = {"video": sys.argv[1], "time": "Atlético Mineiro"}
        if len(sys.argv) > 2:
            cfg["jogo"] = sys.argv[2]
    video = Path(cfg["video"])
    mov = G.carregar_movimento(video)
    W, H = mov["w"], mov["h"]
    _, _, dur = galo.sonda(video)
    c = Corpo(mov)

    arq_rot = Path(str(video) + ".roteiro.json")
    if arq_rot.exists() and not cfg.get("refazer_roteiro"):
        roteiro = json.loads(arq_rot.read_text(encoding="utf-8"))
        print(f"Usando o roteiro de gestos: {arq_rot}")
    else:
        roteiro = ler_roteiro(c)
    if not roteiro:
        raise SystemExit("Não achei nenhum jogador passando (rosto olhando para a direita e acompanhando).")

    placar, notas = cfg.get("placar"), []
    if cfg.get("jogo"):
        p, notas = dados_sofascore(cfg["jogo"], cfg.get("time", "Atlético Mineiro"))
        placar = placar or p
    if not cfg.get("com_placar"):  # padrão: sem placar (você coloca depois)
        placar = None

    # quem passa em cada vez (se o roteiro ainda não tiver nome)
    def dor(j):
        b = [a for a in j["acoes"] if a[0] == "bate"]
        return len(b) + sum(a[2] == "forte" for a in b) * 2 + (1 if any(a[0] == "joga" for a in j["acoes"]) else 0)

    faltam = [j for j in roteiro if not j.get("jogador")]
    if faltam and cfg.get("jogadores"):
        for k, j in enumerate(faltam):
            j["jogador"] = cfg["jogadores"][k % len(cfg["jogadores"])]
    elif faltam:
        disp = [n for n in notas if foto_jogador(n[1], n[2])]
        sem = [f"{n[1]} {n[0]}" for n in notas if n not in disp]
        if sem:
            print("Sem foto no banco (pulados):", ", ".join(sem))
        apanham = [j for j in faltam if any(a[0] == "bate" for a in j["acoes"])]
        poupados = [j for j in faltam if j not in apanham]
        # o último a apanhar (e quem apanha mais) leva as piores notas
        ordem = sorted(apanham, key=lambda j: (dor(j), j["entra"]), reverse=True)
        for j, n in zip(ordem, disp):
            j["jogador"], j["nota"] = n[1], n[0]
        for j, n in zip(poupados, disp[::-1]):
            j["jogador"], j["nota"] = n[1], n[0]
    arq_rot.write_text(json.dumps(roteiro, ensure_ascii=False, indent=1), encoding="utf-8")

    imgs = []
    for j in roteiro:
        f = foto_jogador(j["jogador"])
        if not f:
            raise SystemExit(f"Sem foto de {j['jogador']} no banco (rode tools/galo/elenco_site.py)")
        rec = galo.recorte({"nome": j["jogador"], "foto": str(f)}, altura_jogador(j, c, H))
        imgs.append(cv2.cvtColor(np.array(rec), cv2.COLOR_RGBA2BGRA))
    trajs = [trajetoria(j, c, W, H, im.shape[0], dur) for j, im in zip(roteiro, imgs)]

    # sons
    trab = Path(cfg.get("trabalho") or video.with_name("galo_tmp"))
    trab.mkdir(parents=True, exist_ok=True)
    pista = np.zeros(int(SR * (dur + 2)), np.float32)

    cont = {}

    def por(t, nome):
        cont[nome] = cont.get(nome, -1) + 1
        s = som(nome, cont[nome])
        i0 = int(max(0, t) * SR)
        f1 = min(len(pista), i0 + len(s))
        pista[i0:f1] += s[:f1 - i0]

    for j in roteiro:
        por(j.get("entra_ini", j["entra"] - 0.6) - 0.4, "passa")
        for a in j["acoes"]:
            if a[0] == "passa":
                por(a[1] - 0.5, "passa")
            elif a[0] == "bate":
                por(a[1] - 0.03, a[2])
            elif a[0] == "carinho":
                por(a[1] - 0.02, "carinho")
            elif a[0] == "puxa":
                por(a[1], "puxa")
            elif a[0] == "joga":
                por(a[2] - 0.15, "chicote")
    pista = np.tanh(pista * 1.2) * 0.9
    with wave.open(str(trab / "sfx.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((pista * 32000).astype(np.int16).tobytes())

    pl_img, py = None, 0.0
    if placar:
        pl_img = cv2.cvtColor(np.array(galo.placar_png(placar, W)), cv2.COLOR_RGBA2BGRA)
        nar = G.serie(mov["q"], "nariz")[:, 1]
        cab = float(np.nanpercentile(nar, 5)) - 0.75 * c.sw
        py = cfg.get("placar_y", float(np.clip((cab - pl_img.shape[0] - 20) / H, 0.02, 0.15)))

    saida = cfg.get("saida") or str(video.with_name(video.stem + "_galo.mp4"))
    # corta: começa quando o 1º jogador aparece na tela e termina quando o último sai
    t0 = 0.0 if cfg.get("sem_corte") else max(0.0, min(tr["t"][0] for tr in trajs if len(tr["t"])) + 0.15)
    t1 = dur if cfg.get("sem_corte") else min(dur, max(tr["t"][-1] for tr in trajs if len(tr["t"])) + 0.1)
    # iPhone em HDR: lê os quadros de uma cópia com a cor convertida certo
    cap = cv2.VideoCapture(str(sdr_se_preciso(video, trab)))
    fps_in = cap.get(cv2.CAP_PROP_FPS) or 30
    passo = max(1, round(fps_in / 30))
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
         "-r", f"{fps_in / passo:.5f}", "-i", "-", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(video),
         "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(trab / "sfx.wav"),
         "-filter_complex", "[1:a]volume=0.8[o];[o][2:a]amix=inputs=2:duration=first:normalize=0[a]",
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
        if t < t0 - 1e-3:
            continue
        if t > t1:
            break
        if pl_img is not None:
            G.colar(f, pl_img, W / 2, H * py + pl_img.shape[0])
        for tr, im in zip(trajs, imgs):
            if not len(tr["t"]) or t < tr["t"][0] or t > tr["t"][-1]:
                continue
            k = min(len(tr["t"]) - 1, int(round((t - tr["t"][0]) * 30)))
            if tr["vis"][k]:
                G.colar(f, G.transformar(im, 1, 1, tr["rot"][k]), tr["x"][k], H + tr["dy"][k])
        ff.stdin.write(f.tobytes())
    cap.release()
    ff.stdin.close()
    ff.wait()

    print(f"Roteiro de gestos: {arq_rot}")
    for j in roteiro:
        acoes = ", ".join(f"{a[0]} {a[1]}" + (f" ({a[2]})" if a[0] == "bate" else "") for a in j["acoes"])
        print(f"  {j['entra']:5.1f}s  {j['jogador']:<16} nota {j.get('nota', '-')}: {acoes or 'passa'}")
    print(f"Pronto: {saida}")


if __name__ == "__main__":
    main()
