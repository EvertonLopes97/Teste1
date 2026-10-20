# -*- coding: utf-8 -*-
"""Escreve o roteiro de edição (formato DETTO) a partir da transcrição, usando o Gemini
(quase de graça) em vez do Claude. O Claude fica só para ajustes.

    python tools/roteiro_ia.py words.json roteiro.txt [--titulo "Cinco camisas"]

Precisa da chave: variável de ambiente GEMINI_API_KEY (crie em https://aistudio.google.com/apikey).
No Windows (uma vez):  setx GEMINI_API_KEY "sua-chave"   e abra outro PowerShell.
Modelo: GEMINI_MODEL (padrão gemini-2.5-flash).
"""
import argparse
import json
import os
import re
import subprocess
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

REGRAS = """Você é editor de vídeos de futebol do canal @detto.galo (humor, opinião, curiosidades).
Escreva o ROTEIRO DE EDIÇÃO no formato abaixo, em português, a partir da transcrição com tempos.

FORMATO (siga à risca; os tempos são da GRAVAÇÃO, m:ss):
=====================================================================
 ROTEIRO + MAPA DE EDIÇÃO — "TÍTULO"
=====================================================================

=====================================================================
 0. GANCHO (0:00 – 0:20)
=====================================================================

[0:00 – 0:08]  MODO: [CAM]
FALA: "frase exata da transcrição"
TELA: "MELHORES • PIORES • POLÊMICAS"
EFEITO: punch-in em "palavra"

[0:08 – 0:20]  MODO: [CAM+MG]
FALA: "..."
MG: dois cards entram sincronizados com a fala: RONALDO (Bahia) 9,5 → NEYMAR (Santos) 8,3

=====================================================================
 1. NOME DO BLOCO (0:20 – 1:30)
=====================================================================

[0:20 – 0:24]  MODO: [MG+VO]
MG: vinheta "GOLEIROS"

[0:24 – 0:40]  MODO: [MG+VO]
FALA: "Quarta-feira: Inter 2 a 1 Corinthians. Bragantino 1 a 1 Mirassol."
MG: as PLACAS DE PLACAR caem uma por vez, sincronizadas com cada placar falado.

[0:40 – 0:55]  MODO: [CAM]
FALA: "..."
TELA: enquete "ERA VERMELHO? ✅ SIM / ❌ NÃO — COMENTA!"

=====================================================================
 CORTES VERTICAIS (9:16) PRA TIKTOK / REELS / SHORTS
=====================================================================
1. "TEMA" — [0:08 – 1:10]. Gancho na tela: "FRASE DO GANCHO"

MODOS (um por trecho):
- [CAM] só a câmera (opinião, reação, improviso). TELA só para textos curtos, enquete ou chamada.
- [CAM+MG] câmera pequena no canto + gráfico (quando explica um dado).
- [MG+VO] só o gráfico com a voz por baixo (placares, notas, seleção da rodada).

O QUE O MG PODE PEDIR (escreva assim, o editor automático entende):
- cards de jogador: NOME EM MAIÚSCULAS (Time) nota com vírgula. Ex.: "SAVARINO (Fluminense) 10,0 → ERICK (Vitória) 10,0".
  Cartão vermelho: "... e um cartão vermelho carimba em cima" na frase do jogador.
- placares da rodada: "as PLACAS DE PLACAR caem uma por vez" (os jogos vêm da FALA: "Time 2 a 1 Time").
- campinho: "o campo desce ... título "SELEÇÃO DA RODADA"" e a formação, uma linha por setor, do ataque ao goleiro:
  [ NEYMAR 8,3 ]   [ ARTUR 8,2 ]
  [ RONALDO 9,5 ]
- duelo de pontos: "barras de pontos: FLA 61 x PAL 60" (siglas de 3 letras).
- vinheta de bloco: vinheta "NOME".   - aspas: aspas "FRASE" — Autor.
- selos: selo "ANULADO" / "✅ CORRETO".   - tela de VAR: "vira a TELA DE VAR".
- números grandes: VFX: três "10" azuis caem do topo.
- carta FUT 3D (vira na tela): MG: CARTA FUT: NOME (Time) nota.

EFEITOS PRO (VFX, na palavra falada com no "palavra"; no máximo 1 a cada ~15 s, só nos momentos fortes):
- VFX: texto atrás "POLÊMICA" no "polêmica"   (palavra gigante ATRÁS dele; abertura de assunto)
- VFX: rastreio "EU NO DOMINGO" • "ASSISTINDO DE CASA" no "domingo"   (etiqueta presa na cabeça dele)
- VFX: mira "ALVO DA TORCIDA" no "torcida"   (alvo travando no rosto dele, quando ele vira o assunto)
- VFX: emoji 🤡 na cabeça no "palhaçada"   (emoji grudado na cabeça)
- VFX: congela "GABIGOL" • "O PROVOCADOR" no "cara"   (imagem para, ele recortado com contorno e o nome)
- VFX: texto 3D "VIRADA" no "virada"   (palavra 3D girando; "vermelho" no fim deixa vermelha)
- TRANSIÇÃO: glitch / zoom / whip / nenhuma   (no trecho que abre bloco; sem nada = automática)

REGRAS:
- Um trecho [m:ss – m:ss] por frase/ideia (5 a 15 s), cobrindo a fala inteira, em ordem, sem buracos.
- FALA = texto exato da transcrição daquele trecho.
- Gráfico só quando a fala cita placar, nota, número, nome, ranking ou lista (no máximo 1 a cada ~8 s).
- NUNCA invente nota, placar ou time: use só o que está na fala. Sem a nota na fala, não faça card.
- EFEITO: punch-in nas frases de impacto; zoom lento no suspense.
- Na chamada para seguir/comentar: TELA: "COMENTA AÍ" + botão "SEGUIR".
- CORTES VERTICAIS: um por tema (30 a 75 s), com um gancho forte.
- Responda SÓ com o roteiro, sem comentários.
"""


def falas(words, pausa=0.6):
    """Agrupa as palavras em frases com tempo de início (quebra nas pausas e na pontuação)."""
    linhas, atual, ini = [], [], None
    for k, w in enumerate(words):
        if ini is None:
            ini = w["s"]
        atual.append(w["w"])
        prox = words[k + 1] if k + 1 < len(words) else None
        if prox is None or prox["s"] - w["e"] > pausa or re.search(r"[.!?]$", w["w"]) or len(atual) > 28:
            linhas.append(f"[{int(ini // 60):02d}:{ini % 60:05.2f} – {int(w['e'] // 60):02d}:{w['e'] % 60:05.2f}] {' '.join(atual)}")
            atual, ini = [], None
    return "\n".join(linhas)


API = "https://generativelanguage.googleapis.com/v1beta"


def _chamar(url, corpo=None, tempo=300):
    req = urllib.request.Request(url, data=corpo, headers={"Content-Type": "application/json",
                                                           "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=tempo).read())
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "ignore")[:400]
        raise RuntimeError(f"Gemini respondeu {e.code}: {detalhe}") from None


def modelos_disponiveis():
    """Modelos que a sua chave pode usar: 'flash' estáveis primeiro (rápidos, baratos e com cota), depois os preview."""
    r = _chamar(f"{API}/models?pageSize=200")
    nomes = [m["name"].split("/", 1)[1] for m in r.get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    ruins = ("image", "tts", "audio", "live", "embedding", "learnlm", "gemma", "robotics", "computer-use")
    nomes = [n for n in nomes if not any(x in n for x in ruins)]

    def nota(n):
        versao = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)", n)[:1]] or [0.0]
        return ("flash" not in n, "lite" in n, "preview" in n or "exp" in n, -versao[0], n)
    return sorted(nomes, key=nota)


_MODELO_BOM = None
_CACHE_MODELO = Path.home() / ".detto_gemini_modelo"


def gerar(corpo, log=print, tentativas=5):
    """chama o Gemini tentando os modelos que existem para a sua chave: o que funcionou da última vez, o
    GEMINI_MODEL, o gemini-flash-latest e os da lista do Google (pula modelo aposentado/sem cota; repete 1x se
    demorar). Devolve a resposta (dict) ou levanta RuntimeError com o último erro."""
    global _MODELO_BOM
    ordem = []
    try:
        ordem.append(_CACHE_MODELO.read_text().strip())
    except OSError:
        pass
    ordem += [_MODELO_BOM, os.environ.get("GEMINI_MODEL"), "gemini-flash-latest"]
    ordem = [m for m in dict.fromkeys(ordem) if m]
    lista_buscada = False
    ultimo = None
    i = 0
    while i < len(ordem) and i < tentativas + 3:
        modelo = ordem[i]
        for vez in range(2):
            try:
                r = _chamar(f"{API}/models/{modelo}:generateContent", corpo, tempo=150)
                _MODELO_BOM = modelo
                try:
                    _CACHE_MODELO.write_text(modelo)
                except OSError:
                    pass
                return r
            except RuntimeError as e:
                ultimo = e
                log(f"   Gemini ({modelo}): {str(e)[:140]}")
                if " 400" in str(e) and "API key" in str(e) or " 403" in str(e):
                    raise
                break  # 404 (aposentado), 429 (sem cota), 5xx: próximo modelo
            except Exception as e:  # tempo esgotado / rede: tenta de novo uma vez
                ultimo = e
                log(f"   Gemini ({modelo}): {str(e)[:140]}" + (" — tentando de novo" if vez == 0 else ""))
        i += 1
        if i >= len(ordem) and not lista_buscada:
            lista_buscada = True
            try:
                ordem += [m for m in modelos_disponiveis() if m not in ordem][:tentativas]
            except Exception as e:
                log(f"   Gemini: não consegui a lista de modelos ({e})")
    raise RuntimeError(f"nenhum modelo Gemini respondeu ({ultimo})")


def gemini(prompt):
    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("Falta a chave GEMINI_API_KEY (veja o topo deste arquivo).")
    corpo = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.4}}).encode()
    try:
        r = gerar(corpo)
    except RuntimeError as e:
        if " 400" in str(e) or " 403" in str(e):
            raise SystemExit(f"{e}\nA chave foi recusada: gere outra em https://aistudio.google.com/apikey "
                             f"(começa com AIza) e rode setx GEMINI_API_KEY de novo.")
        raise SystemExit(str(e))
    print(f"Roteiro feito pelo modelo {_MODELO_BOM}")
    return r["candidates"][0]["content"]["parts"][0]["text"]



USO_CLAUDE = Path.home() / ".detto_claude_uso.json"


def le_uso_claude():
    """o que o sistema perguntou ao Claude hoje (o painel mostra; dá para PARAR por lá)"""
    import datetime as _dt
    try:
        u = json.loads(USO_CLAUDE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        u = {}
    hoje = _dt.date.today().isoformat()
    if u.get("dia") != hoje:
        u = {"dia": hoje, "n": 0, "falhas": 0, "seguidas": 0, "ultimas": [], "parado": u.get("parado", False),
             "motivo": u.get("motivo", "")}
    return u


def grava_uso_claude(u):
    try:
        USO_CLAUDE.write_text(json.dumps(u, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _cota_claude():
    """pode perguntar? Não quando você PAROU no painel, ou parou sozinho (6 falhas seguidas = algo quebrado).
    Sem limite por padrão; DETTO_CLAUDE_MAX_DIA=N põe um teto."""
    u = le_uso_claude()
    if u.get("parado"):
        return False, u.get("motivo") or "parado no painel"
    teto = int(os.environ.get("DETTO_CLAUDE_MAX_DIA", "0") or 0)
    if teto and u["n"] >= teto:
        return False, f"chegou no máximo do dia ({teto})"
    return True, ""


def _registra_claude(ok, de, chave, seg, erro=""):
    import time as _t
    u = le_uso_claude()
    u["n"] += 1
    if ok:
        u["seguidas"] = 0
    else:
        u["falhas"] += 1
        u["seguidas"] += 1
        if u["seguidas"] >= 6:
            u["parado"], u["motivo"] = True, "parou sozinho: 6 falhas seguidas (veja o erro e ligue de novo no painel)"
    u["ultimas"] = (u.get("ultimas", []) + [{"t": int(_t.time()), "ok": ok, "de": de[:70], "h": chave, "s": round(seg),
                                              "erro": erro[:160]}])[-30:]
    grava_uso_claude(u)


def claude_cli(prompt, tempo=900, imagens=(), log=print, de="roteiro da edição"):
    """2ª opção quando o Gemini não responde: o Claude da SUA assinatura (Pro/Max), pelo Claude Code instalado no PC
    (`claude -p`). Usa o mesmo limite das conversas com o Claude (trava diária em _cota_claude). Sem chave de API:
    tira ANTHROPIC_API_KEY do ambiente para nunca cair na cobrança da API. `imagens` = fotos que ele abre e olha.
    Devolve o texto ou None."""
    exe = shutil.which("claude")
    if not exe or os.environ.get("DETTO_SEM_CLAUDE"):
        return None
    pode, porque = _cota_claude()
    if not pode:
        log(f"   Claude: não pergunto ({porque})")
        return None
    import hashlib
    import time as _t
    chave = hashlib.sha1((prompt[:4000] + "|".join(str(x) for x in imagens)).encode("utf-8", "ignore")).hexdigest()[:10]
    t0 = _t.time()
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    cmd = [exe, "-p", "--output-format", "text"]
    cwd = None
    if imagens:
        cmd += ["--allowedTools", "Read"]
        cwd = str(Path(imagens[0]).parent)
        prompt = ("Abra e OLHE estas imagens com a ferramenta Read antes de responder (são quadros de um vídeo, em ordem):\n"
                  + "\n".join(str(Path(x).resolve()) for x in imagens) + "\n\n" + prompt)
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=tempo, env=env, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired) as e:
        log(f"   Claude: não respondeu ({e})")
        _registra_claude(False, de, chave, _t.time() - t0, str(e))
        return None
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out:
        erro = (r.stderr or out or f"código {r.returncode}").strip()
        log(f"   Claude: não deu ({erro[:200]})")
        _registra_claude(False, de, chave, _t.time() - t0, erro)
        return None
    _registra_claude(True, de, chave, _t.time() - t0)
    return out


_WHISPER = None


def _fala_do_video(f, log=print):
    """o que se ouve no vídeo (narração, grito, fala) — o Claude não ouve, então vai escrito"""
    global _WHISPER
    try:
        from faster_whisper import WhisperModel
        if _WHISPER is None:
            _WHISPER = WhisperModel(os.environ.get("DETTO_WHISPER_RESERVA", "small"), device="cpu", compute_type="int8")
        wav = Path(f).with_suffix(".wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(f), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=False)
        if not wav.exists():
            return ""
        import numpy as np
        import wave
        with wave.open(str(wav)) as w_:
            audio = np.frombuffer(w_.readframes(w_.getnframes()), np.int16).astype(np.float32) / 32768.0
        segs, _ = _WHISPER.transcribe(audio, language="pt", vad_filter=True)
        return " ".join(f"[{s.start:.1f}s] {s.text.strip()}" for s in segs)[:3000]
    except Exception as e:
        log(f"   (sem transcrição do áudio: {str(e)[:80]})")
        return ""


def claude_partes_json(partes, log=print, quadros=8, de=""):
    """o mesmo pedido feito ao Gemini (texto + imagens + vídeo), feito ao Claude: o vídeo vira QUADROS (fotos em ordem,
    com o tempo) + a TRANSCRIÇÃO do áudio. Devolve o JSON (dict) ou None."""
    import base64
    import tempfile
    pasta = Path(tempfile.mkdtemp(prefix="detto_claude_"))
    textos, imgs = [], []
    try:
        for k, p_ in enumerate(partes):
            if "text" in p_:
                textos.append(p_["text"])
                continue
            d = p_.get("inline_data") or {}
            mime, dado = d.get("mime_type", ""), base64.b64decode(d.get("data", "") or b"")
            if mime.startswith("image/"):
                f = pasta / f"foto{k:02d}.jpg"
                f.write_bytes(dado)
                imgs.append(f)
                textos.append(f"[foto: {f.name}]")
            elif mime.startswith("video/"):
                v = pasta / f"video{k:02d}.mp4"
                v.write_bytes(dado)
                r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)],
                                   capture_output=True, text=True)
                try:
                    dur = float(r.stdout.strip())
                except ValueError:
                    dur = 10.0
                nomes = []
                for q in range(quadros):
                    t = dur * (q + 0.5) / quadros
                    f = pasta / f"video{k:02d}_q{q:02d}_{t:05.1f}s.jpg"
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(v), "-frames:v", "1",
                                    "-vf", "scale=-2:480", "-q:v", "4", str(f)], check=False)
                    if f.exists():
                        imgs.append(f)
                        nomes.append(f"{f.name} ({t:.1f}s)")
                fala = _fala_do_video(v, log)
                textos.append(f"[VÍDEO de {dur:.1f}s — você não assiste vídeo: veja os quadros {', '.join(nomes)}; "
                              f"áudio transcrito: {fala or '(sem fala / só música)'}]")
        prompt = "\n".join(textos) + "\n\nResponda SOMENTE com o JSON pedido, sem explicação e sem ```."
        de = de or re.sub(r"\s+", " ", next((p_["text"] for p_ in partes if "text" in p_), "pergunta"))[:70]
        out = claude_cli(prompt, imagens=imgs, log=log, de="reels: " + de)
        if out and not re.search(r"\{.*\}", out, re.S):
            _registra_claude(False, "reels: resposta sem JSON", "", 0, out[:160])
        if not out:
            return None
        m = re.search(r"\{.*\}", out, re.S)
        return json.loads(m.group(0)) if m else None
    except Exception as e:
        log(f"   Claude: {str(e)[:160]}")
        return None
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def _mmss(t):
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


def roteiro_basico(words, titulo=""):
    """SEM Gemini (cota acabou / sem internet): roteiro simples direto da fala — um trecho [CAM] a cada frase/ideia
    (5–12 s, quebra nas pausas), punch-in nas exclamações e um corte vertical a cada ~60 s. Dá para ajustar depois."""
    frases, atual = [], []
    for k, w in enumerate(words):
        atual.append(w)
        prox = words[k + 1] if k + 1 < len(words) else None
        if prox is None or prox["s"] - w["e"] > 0.6 or re.search(r"[.!?]$", w["w"]) or len(atual) > 28:
            frases.append(atual)
            atual = []
    trechos, cur = [], []
    for f in frases:
        cur += f
        d = cur[-1]["e"] - cur[0]["s"]
        if d >= 5 or f is frases[-1]:
            if d > 12 and len(cur) > len(f):
                trechos.append(cur[: len(cur) - len(f)])
                cur = list(f)
                if f is not frases[-1]:
                    continue
            trechos.append(cur)
            cur = []
    if cur:
        trechos.append(cur)
    L = ["=" * 69, f' ROTEIRO DE EDIÇÃO — "{(titulo or "VÍDEO").upper()}"  (automático, sem IA)', "=" * 69, ""]
    for i, t in enumerate(trechos):
        if i == 0:
            L += ["=" * 69, " ABERTURA / GANCHO", "=" * 69, ""]
        elif i == 1:
            L += ["=" * 69, " BLOCO 1 — O VÍDEO", "=" * 69, ""]
        fala = " ".join(w["w"] for w in t).replace('"', "'")
        L += [f"[{_mmss(t[0]['s'])} – {_mmss(t[-1]['e'] + 0.5)}]", f'FALA: "{fala}"']
        ex = re.findall(r"(\w+)!", fala)
        if ex:
            L.append(f'EFEITO: punch-in em "{ex[0]}"')
        L.append("")
    L += ["=" * 69, " CORTES VERTICAIS (9:16) SUGERIDOS", "=" * 69]
    ini, n, gancho = None, 0, " ".join(w["w"] for w in trechos[0])[:90].replace('"', "'") if trechos else ""
    for t in trechos:
        if ini is None:
            ini = t[0]["s"]
        if t[-1]["e"] - ini >= 55 or t is trechos[-1]:
            if t[-1]["e"] - ini >= 25:
                n += 1
                L.append(f'{n}. "PARTE {n}": [{_mmss(ini)} – {_mmss(t[-1]["e"] + 0.5)}]. Gancho: "{gancho}"')
            ini = None
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("words")
    p.add_argument("saida")
    p.add_argument("--titulo", default="")
    a = p.parse_args()
    words = json.loads(Path(a.words).read_text(encoding="utf-8"))
    prompt = REGRAS + (f"\nTítulo sugerido: {a.titulo}\n" if a.titulo else "") + "\nTRANSCRIÇÃO:\n" + falas(words)
    try:
        texto = gemini(prompt).strip()
        texto = re.sub(r"^```\w*\n|\n```$", "", texto)
    except SystemExit as e:
        # cota do Gemini acabou (429) / sem chave / sem internet: tenta o Claude da assinatura; senão roteiro simples
        print(f"Gemini indisponível ({str(e)[:160]}).")
        texto = claude_cli(prompt)
        if texto and len(texto) > 200:
            print("Roteiro feito pelo Claude (sua assinatura)")
            texto = re.sub(r"^```\w*\n|\n```$", "", texto.strip())
        else:
            print("Fiz um roteiro SIMPLES pela fala (câmera + legenda, cortes de ~60 s). "
                  "Para os gráficos, mande o seu roteiro ou refaça amanhã com o Gemini.")
            texto = roteiro_basico(words, a.titulo).strip()
    Path(a.saida).write_text(texto + "\n", encoding="utf-8")
    print(f"Roteiro: {a.saida} ({texto.count('FALA:')} trechos)")


if __name__ == "__main__":
    sys.exit(main())
