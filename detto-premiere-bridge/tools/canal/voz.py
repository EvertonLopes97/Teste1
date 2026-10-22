# -*- coding: utf-8 -*-
"""Voz CLONADA (a sua) para a narração do canal: Chatterbox Multilingual (grátis, roda no seu PC).

    python tools/canal/voz.py falas.json pasta_saida --ref voz\\minha_voz.wav

falas.json: [{"id": "f01", "texto": "..."}]  →  pasta_saida/f01.wav (mesmo texto + mesma voz = reaproveita).
A referência é um áudio SEU de 10 a 30 s, falando normal, sem música (quanto mais limpo, mais parecido).
Na placa NVIDIA é bem mais rápido; sem ela roda no processador (mais lento, mesmo resultado).
Primeira vez: instala o chatterbox-tts e baixa o modelo (~3 GB).
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def instala():
    try:
        import chatterbox.mtl_tts  # noqa: F401

        return
    except ImportError:
        pass
    print("voz: instalando o Chatterbox (uma vez só, alguns minutos)...", flush=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "chatterbox-tts", "protobuf>=6.31.1"], check=False)
    import chatterbox.mtl_tts  # noqa: F401


def frases(texto, maximo=150):
    """quebra em frases curtas (o modelo perde o fio em texto longo)"""
    partes = re.split(r"(?<=[.!?…])\s+", re.sub(r"\s+", " ", texto.strip()))
    out = []
    for p in partes:
        while len(p) > maximo:
            corte = p.rfind(",", 0, maximo)
            corte = corte if corte > 60 else p.rfind(" ", 0, maximo)
            out.append(p[:corte + 1].strip())
            p = p[corte + 1:].strip()
        if p:
            out.append(p)
    return out


# ------------------------------------------------------------------ pronúncia (as duas vozes leem melhor assim)
LETRAS = {"A": "á", "B": "bê", "C": "cê", "D": "dê", "E": "é", "F": "éfe", "G": "gê", "H": "agá", "I": "i", "J": "jota", "K": "cá",
          "L": "éle", "M": "ême", "N": "êne", "O": "ó", "P": "pê", "Q": "quê", "R": "érre", "S": "ésse", "T": "tê", "U": "u",
          "V": "vê", "W": "dáblio", "X": "xis", "Y": "ípsilon", "Z": "zê"}
# siglas que se LEEM como palavra (o resto é soletrado: CBF → cê bê éfe)
SIGLAS_PALAVRA = {"VAR", "SAF", "FIFA", "UEFA", "CONMEBOL", "GALO", "SUB", "ONU", "COPA", "MRV", "TIM", "BID", "GOL", "PIX"}
SIGLAS_FIXAS = {"CAM": "Galo", "CAP": "Athletico", "SPFC": "São Paulo", "RBB": "Bragantino", "TV": "tevê", "MG": "Minas",
                "SP": "São Paulo", "RJ": "Rio", "PR": "Paraná", "RS": "Rio Grande do Sul", "BH": "bê agá", "ESPN": "ê ésse pê êne",
                "STJD": "ésse tê jota dê", "CEO": "cê é ó", "VS": "contra", "X": "contra"}
UN = "zero um dois três quatro cinco seis sete oito nove dez onze doze treze catorze quinze dezesseis dezessete dezoito dezenove".split()
DEZ = "_ _ vinte trinta quarenta cinquenta sessenta setenta oitenta noventa".split()
CEM = "_ cento duzentos trezentos quatrocentos quinhentos seiscentos setecentos oitocentos novecentos".split()
ORD = {1: "primeiro", 2: "segundo", 3: "terceiro", 4: "quarto", 5: "quinto", 6: "sexto", 7: "sétimo", 8: "oitavo", 9: "nono",
       10: "décimo", 20: "vigésimo", 30: "trigésimo"}


def por_extenso(n):
    n = int(n)
    if n < 20:
        return UN[n]
    if n < 100:
        return DEZ[n // 10] + ("" if n % 10 == 0 else " e " + UN[n % 10])
    if n == 100:
        return "cem"
    if n < 1000:
        return CEM[n // 100] + ("" if n % 100 == 0 else " e " + por_extenso(n % 100))
    if n < 1_000_000:
        mil = "mil" if n // 1000 == 1 else por_extenso(n // 1000) + " mil"
        r = n % 1000
        return mil + ("" if r == 0 else (" e " if r < 100 or r % 100 == 0 else " ") + por_extenso(r))
    milhoes = n // 1_000_000
    r = n % 1_000_000
    return (("um milhão" if milhoes == 1 else por_extenso(milhoes) + " milhões") + ("" if r == 0 else " e " + por_extenso(r)))


def ordinal(n):
    n = int(n)
    if n in ORD:
        return ORD[n]
    if n < 40:
        return ORD[n // 10 * 10] + " " + ORD[n % 10]
    return por_extenso(n)


def pronuncia(texto):
    """o texto do jeito que tem que ser FALADO: siglas soletradas (CBF → cê bê éfe), números por extenso, placar
    "2 x 1" → "dois a um", "6º" → "sexto", "8,3" → "oito vírgula três", "33'" → "trinta e três minutos", "R$ 10 milhões"."""
    t = f" {texto} "
    t = re.sub(r"(\d+)\s*[xX×]\s*(\d+)", lambda m: f"{m.group(1)} a {m.group(2)}", t)
    t = re.sub(r"R\$\s*([\d.,]+)\s*(milhões|milhão|bilhões|bilhão|mil\b)?", lambda m: f"{m.group(1)} {(m.group(2) + ' de') if m.group(2) and m.group(2) != 'mil' else (m.group(2) or '')} reais", t)
    t = re.sub(r"(?<=\w)\s+[xX]\s+(?=\w)", " contra ", t)
    t = re.sub(r"(\d+)\s*[ºª°]", lambda m: ordinal(m.group(1)), t)
    t = re.sub(r"(\d+)\s*'", lambda m: por_extenso(m.group(1)) + " minutos", t)
    t = re.sub(r"(\d+)%", lambda m: por_extenso(m.group(1)) + " por cento", t)
    t = re.sub(r"(\d+),(\d)\b", lambda m: por_extenso(m.group(1)) + " vírgula " + por_extenso(m.group(2)), t)
    t = re.sub(r"\b(\d{1,3}(?:\.\d{3})+)\b", lambda m: m.group(1).replace(".", ""), t)
    t = re.sub(r"\b\d{1,9}\b", lambda m: por_extenso(m.group(0)), t)

    def sigla(m):
        w = m.group(0)
        if w in SIGLAS_FIXAS:
            return SIGLAS_FIXAS[w]
        if w in SIGLAS_PALAVRA:
            return w.capitalize() if w != "VAR" else "var"
        return " ".join(LETRAS.get(c, c) for c in w)
    # siglas: 2 a 5 MAIÚSCULAS seguidas, numa frase que não está toda em maiúsculas
    if sum(c.isupper() for c in texto) < 0.6 * max(1, sum(c.isalpha() for c in texto)):
        t = re.sub(r"\b[A-Z]{2,5}\b", sigla, t)
    else:
        t = t.capitalize()
    return re.sub(r"\s+", " ", t).strip()


# ------------------------------------------------------------------ Fish Audio (API; voz profissional, sotaque BR)
VOICESTUDIO_PADRAO = "http://127.0.0.1:3900"


def voicestudio_url():
    """onde o VoiceStudio está ouvindo (DETTO_VOICESTUDIO troca a porta/endereço)"""
    return (os.environ.get("DETTO_VOICESTUDIO") or VOICESTUDIO_PADRAO).rstrip("/")


def voicestudio_ligado(url=None, tempo=4):
    """o VoiceStudio está aberto no PC? (API local, sem senha em 127.0.0.1)"""
    import urllib.request
    try:
        urllib.request.urlopen(f"{url or voicestudio_url()}/v1/models", timeout=tempo).read(1)
        return True
    except Exception:
        return False


def voicestudio_vozes(url=None):
    """as vozes/perfis instalados (para escolher no painel)"""
    import urllib.request
    try:
        d = json.loads(urllib.request.urlopen(f"{url or voicestudio_url()}/v1/audio/voices", timeout=20).read())
    except Exception:
        return []
    itens = d.get("data") if isinstance(d, dict) else d
    out = []
    for v in itens or []:
        if isinstance(v, dict):
            out.append({"id": str(v.get("id") or v.get("voice_id") or v.get("name") or ""), "nome": str(v.get("name") or v.get("id") or "")})
        elif isinstance(v, str):
            out.append({"id": v, "nome": v})
    return [x for x in out if x["id"]]


def voicestudio_fala(texto, saida, voz="default", url=None, modelo="omnivoice", velocidade=1.0, instrucao=""):
    """uma fala pelo VoiceStudio (open source, roda NO SEU PC — github.com/debpalash/VoiceStudio).
    Fala pela API local no padrão da OpenAI: POST /v1/audio/speech. Devolve wav 24 kHz mono."""
    import tempfile
    import urllib.error
    import urllib.request
    url = url or voicestudio_url()
    corpo = {"model": modelo, "input": texto[:4000], "voice": voz or "default", "response_format": "wav",
             "speed": float(velocidade), "language": "pt"}
    if instrucao:
        corpo["instructions"] = instrucao
    for tentativa in range(2):
        req = urllib.request.Request(f"{url}/v1/audio/speech", data=json.dumps(corpo).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            dados = urllib.request.urlopen(req, timeout=600).read()
            break
        except urllib.error.HTTPError as e:
            detalhe = e.read()[:300].decode("utf-8", "replace")
            if tentativa == 0 and e.code in (400, 404, 422):
                corpo.pop("language", None)  # versão sem o campo extra de idioma
                corpo.pop("instructions", None)
                continue
            raise RuntimeError(f"VoiceStudio {e.code}: {detalhe}") from None
        except Exception as e:
            raise RuntimeError(f"VoiceStudio não respondeu em {url} ({str(e)[:120]})") from None
    if len(dados) < 2000:
        raise RuntimeError(f"VoiceStudio devolveu um áudio vazio ({len(dados)} bytes)")
    tmp = Path(tempfile.gettempdir()) / f"detto_vs_{os.getpid()}.wav"
    tmp.write_bytes(dados)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-ar", "24000", "-ac", "1", str(saida)],
                       capture_output=True, text=True)
    tmp.unlink(missing_ok=True)
    if r.returncode != 0 or not Path(saida).exists():
        raise RuntimeError(f"VoiceStudio: o áudio não abriu ({r.stderr[-150:]})")


def fish_modelo(ref, pasta, chave, log=print):
    """a SUA voz clonada no Fish Audio (uma vez; o id fica guardado em voz\\fish_modelo.json)"""
    import urllib.request
    reg = Path(pasta) / "fish_modelo.json"
    h = hashlib.sha1(Path(ref).read_bytes()).hexdigest()[:12]
    try:
        d = json.loads(reg.read_text(encoding="utf-8"))
        if d.get("ref") == h and d.get("id"):
            return d["id"]
    except (OSError, ValueError):
        pass
    limite = "----detto" + h
    corpo = b""
    for k, v in (("type", "tts"), ("title", "DETTO - minha voz"), ("train_mode", "fast"), ("visibility", "private")):
        corpo += f"--{limite}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    corpo += (f"--{limite}\r\nContent-Disposition: form-data; name=\"voices\"; filename=\"minha_voz.wav\"\r\n"
              f"Content-Type: audio/wav\r\n\r\n").encode() + Path(ref).read_bytes() + f"\r\n--{limite}--\r\n".encode()
    req = urllib.request.Request("https://api.fish.audio/model", data=corpo, method="POST",
                                 headers={"Authorization": f"Bearer {chave}", "Content-Type": f"multipart/form-data; boundary={limite}"})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read())
    mid = r.get("_id") or r.get("id")
    if not mid:
        raise RuntimeError(f"Fish Audio não criou a voz: {str(r)[:200]}")
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(json.dumps({"ref": h, "id": mid}), encoding="utf-8")
    log(f"voz: sua voz criada no Fish Audio ({mid})")
    return mid


def fish_fala(texto, saida, mid, chave, modelo="s2.1-pro-free"):
    """uma fala pelo Fish Audio → wav 24 kHz mono"""
    import tempfile
    import urllib.error
    import urllib.request
    corpo = {"text": texto, "reference_id": mid, "format": "wav", "normalize": True, "temperature": 0.7, "language": "pt-BR"}
    for tentativa in range(2):
        req = urllib.request.Request("https://api.fish.audio/v1/tts", data=json.dumps(corpo).encode(), method="POST",
                                     headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json", "model": modelo})
        try:
            dados = urllib.request.urlopen(req, timeout=300).read()
            break
        except urllib.error.HTTPError as e:
            if tentativa == 0 and e.code in (400, 422):
                corpo.pop("language", None)  # versão da API sem o campo de idioma
                continue
            raise RuntimeError(f"Fish Audio {e.code}: {e.read()[:200]}") from None
    tmp = Path(tempfile.gettempdir()) / f"detto_fish_{os.getpid()}.wav"
    tmp.write_bytes(dados)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-ar", "24000", "-ac", "1", str(saida)], check=True)
    tmp.unlink(missing_ok=True)


def voz_de_teste(texto, saida):
    """voz de computador em português (só para testar a montagem enquanto a sua voz não chega)"""
    import shutil
    import tempfile
    tmp = Path(tempfile.gettempdir()) / f"detto_voz_{os.getpid()}.wav"
    try:
        if os.name == "nt":
            ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'pt*' } | Select-Object -First 1; "
                  "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; $s.Rate = 1; "
                  f"$s.SetOutputToWaveFile('{tmp}'); $s.Speak([Console]::In.ReadToEnd()); $s.Dispose()")
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], input=texto, text=True, encoding="utf-8",
                           capture_output=True, timeout=120)
        elif shutil.which("espeak-ng"):
            subprocess.run(["espeak-ng", "-v", "pt-br", "-s", "165", "-w", str(tmp), texto], capture_output=True, timeout=120)
        if tmp.exists() and tmp.stat().st_size > 2000:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-ar", "24000", "-ac", "1", str(saida)], check=True)
            return True
    except Exception:
        pass
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    return False


def _apara(w, sr, torch):
    """tira o silêncio do começo/fim da frase"""
    a = w.abs().squeeze(0)
    lim = max(float(a.max()) * 0.02, 1e-4)
    idx = (a > lim).nonzero()
    if len(idx) == 0:
        return w
    i0 = max(0, int(idx[0]) - int(sr * 0.03))
    i1 = min(a.shape[0], int(idx[-1]) + int(sr * 0.08))
    return w[:, i0:i1]


def sem_pausas(arquivo, max_pausa=0.13, sr=44100):
    """tira os SILÊNCIOS do meio da fala (a voz de IA às vezes "espaça" entre frases/palavras e entrega que é IA):
    toda pausa interna maior que `max_pausa` fica com `max_pausa`; as pontas ficam com 0,04 s. Junta com fade curto."""
    import wave
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(arquivo), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True)
    a = np.frombuffer(r.stdout, np.float32).copy()
    if a.size < sr * 0.3:
        return 0.0
    q = int(sr * 0.01)  # quadros de 10 ms
    n = a.size // q
    rms = np.sqrt(np.mean(a[: n * q].reshape(n, q) ** 2, axis=1) + 1e-12)
    ref = float(np.percentile(rms, 95))
    mudo = rms < max(ref * 0.018, 1e-4)  # ~35 dB abaixo da fala
    # silêncios curtos demais (entre sílabas) não contam: só trechos >= max_pausa
    pedacos, i, ant = [], 0, 0
    fala = np.nonzero(~mudo)[0]
    if fala.size == 0:
        return 0.0
    ini, fim = max(0, fala[0] - 4) * q, min(n, fala[-1] + 6) * q
    keep_q = int(round(max_pausa / 0.01))
    i = fala[0]
    cortado = 0
    while i < fala[-1]:
        if mudo[i]:
            j = i
            while j < n and mudo[j]:
                j += 1
            if j - i > keep_q:
                meio = keep_q // 2
                pedacos.append(a[ant: (i + meio) * q])
                ant = (j - (keep_q - meio)) * q
                cortado += (j - i - keep_q) * 0.01
            i = j
        else:
            i += 1
    pedacos.append(a[ant: fim])
    if ant == 0:
        pedacos = [a[ini:fim]]
    else:
        pedacos[0] = pedacos[0][ini:]
    f = int(sr * 0.008)
    ramp = np.linspace(0, 1, f, dtype=np.float32)
    saida = []
    for k, p in enumerate(pedacos):
        p = p.copy()
        if p.size > 2 * f:
            if k > 0:
                p[:f] *= ramp
            if k < len(pedacos) - 1:
                p[-f:] *= ramp[::-1]
        saida.append(p)
    y = np.concatenate(saida)
    y = np.clip(y, -1, 1)
    with wave.open(str(arquivo), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((y * 32767).astype(np.int16).tobytes())
    return cortado


def frase_boa(m, fr, ref, exag, torch, tentativas=4):
    """gera a frase e CONFERE: o modelo às vezes embola, gagueja, fica robótico ou corta — o sinal é o tamanho do
    áudio fora do normal para o texto (português falado ≈ 14 letras/s) ou picos/ruído. Refaz com outra semente."""
    esperado = max(0.8, len(fr) / 14.0)
    melhor, nota_m = None, 9e9
    for t in range(tentativas):
        torch.manual_seed(1234 + t * 97)
        kw = {"language_id": "pt", "exaggeration": exag, "cfg_weight": 0.5, "temperature": 0.7 if t == 0 else 0.6}
        if ref:
            kw["audio_prompt_path"] = str(ref)
        try:
            w = m.generate(fr, **kw)
        except TypeError:  # versão do chatterbox sem cfg_weight/temperature
            kw.pop("cfg_weight", None)
            kw.pop("temperature", None)
            w = m.generate(fr, **kw)
        w = _apara(w, m.sr, torch)
        d = w.shape[1] / m.sr
        razao = d / esperado
        # nota: quão longe do tamanho normal (0,7x a 1,6x é normal) + estouro (clipping)
        nota = abs(max(0.0, razao - 1.6)) + abs(max(0.0, 0.7 - razao)) * 2 + float((w.abs() > 0.99).float().mean()) * 50
        if nota < nota_m:
            melhor, nota_m = w, nota
        if nota < 0.05:
            break
        print(f"voz: frase estranha ({d:.1f}s para ~{esperado:.1f}s), refazendo: {fr[:50]}...", flush=True)
    return melhor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("falas")
    ap.add_argument("saida")
    ap.add_argument("--ref", required=False, default="", help="áudio seu (10–30 s) para clonar")
    ap.add_argument("--exagero", type=float, default=0.6, help="emoção (0,3 calmo … 0,9 empolgado)")
    ap.add_argument("--fish-chave", default="", help="chave do Fish Audio (ou FISH_API_KEY)")
    ap.add_argument("--fish-modelo", default=os.environ.get("FISH_MODELO", "s2.1-pro-free"), help="s2.1-pro-free (grátis) ou s2.1-pro")
    ap.add_argument("--voicestudio", default="", help=f"endereço do VoiceStudio (padrão {VOICESTUDIO_PADRAO}; DETTO_VOICESTUDIO)")
    ap.add_argument("--voz-vs", default=os.environ.get("DETTO_VOZ_VS", ""), help="nome/id do perfil de voz no VoiceStudio")
    ap.add_argument("--modelo-vs", default=os.environ.get("DETTO_MODELO_VS", "omnivoice"), help="motor do VoiceStudio")
    ap.add_argument("--velocidade-vs", type=float, default=float(os.environ.get("DETTO_VELOCIDADE_VS", "1.0")))
    ap.add_argument("--sem-voicestudio", action="store_true", help="não usar o VoiceStudio nesta rodada")
    ap.add_argument("--max-pausa", type=float, default=float(os.environ.get("DETTO_MAX_PAUSA", "0.13")),
                    help="maior silêncio no MEIO da fala (s); o resto é cortado")
    ap.add_argument("--com-pausas", action="store_true", help="não tira os silêncios do meio")
    a = ap.parse_args()
    falas = json.loads(Path(a.falas).read_text(encoding="utf-8"))
    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    ref = Path(a.ref) if a.ref else None
    if ref and not ref.exists():
        print(f"voz: não achei a sua voz em {ref} — usando a voz padrão do modelo")
        ref = None
    chave_ref = hashlib.sha1(ref.read_bytes()).hexdigest()[:8] if ref else "padrao"
    if os.environ.get("DETTO_VOZ_FALSA"):
        chave_ref = "falsa"  # a voz de computador do TESTE nunca é reaproveitada num vídeo de verdade
    # QUAL VOZ: 1) VoiceStudio aberto no seu PC (open source, de graça, sem limite) · 2) Fish Audio (chave) · 3) Chatterbox
    url_vs = a.voicestudio or voicestudio_url()
    usa_vs = False
    if not a.sem_voicestudio and not os.environ.get("DETTO_VOZ_FALSA"):
        usa_vs = voicestudio_ligado(url_vs)
        if usa_vs:
            print(f"voz: VoiceStudio ligado em {url_vs} (voz \"{a.voz_vs or 'default'}\")", flush=True)
    falta = []
    for f in falas:
        motor = "vs" if usa_vs else ("fish" if (os.environ.get("FISH_API_KEY") or a.fish_chave) else "cb2")
        marca = f"{motor}:{a.voz_vs}" if motor == "vs" else motor
        h = hashlib.sha1(f"{chave_ref}|{a.exagero}|{marca}|{f['texto']}".encode()).hexdigest()[:10]
        f["arquivo"] = str(out / f"{f['id']}_{h}.wav")
        if not Path(f["arquivo"]).exists():
            falta.append(f)
    # o texto do jeito de FALAR (siglas, números, placares) — vale para todas as vozes
    for f in falta:
        f["falado"] = pronuncia(f["texto"])
    if falta and os.environ.get("DETTO_VOZ_FALSA"):
        # TESTE sem a sua voz (sem baixar o modelo): voz de computador em português — Windows (voz "Maria"),
        # espeak-ng no Linux; sem nenhuma, um tom baixo com o tempo da fala
        for f in falta:
            if not voz_de_teste(f["falado"], f["arquivo"]):
                d = max(1.0, len(f["texto"].split()) * 0.36)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=f=200:d={d:.2f}", "-af", "volume=0.05",
                                "-ar", "24000", f["arquivo"]], check=True)
        falta = []
    if falta and usa_vs:
        # VOICESTUDIO: a fala INTEIRA de uma vez (entonação melhor que frase a frase); o que falhar vai para o resto da fila
        for k, f in enumerate(list(falta)):
            try:
                voicestudio_fala(f["falado"], f["arquivo"], a.voz_vs or "default", url_vs, a.modelo_vs, a.velocidade_vs)
                falta.remove(f)
                print(f"voz (VoiceStudio): {k + 1}/{len(falta) + k + 1}", flush=True)
            except Exception as e:
                print(f"voz: VoiceStudio falhou em uma fala ({str(e)[:160]})", flush=True)
                if k == 0:
                    print("voz: deixo o VoiceStudio de lado nesta rodada; o resto vai pelo Fish/Chatterbox", flush=True)
                    break
    chave_fish = os.environ.get("FISH_API_KEY") or a.fish_chave
    if falta and chave_fish and ref and not os.environ.get("DETTO_VOZ_FALSA"):
        # FISH AUDIO (sotaque brasileiro, mais natural): se der erro, o que faltar vai pelo Chatterbox
        try:
            mid = fish_modelo(ref, out.parent, chave_fish)
            for k, f in enumerate(list(falta)):
                fish_fala(f["falado"], f["arquivo"], mid, chave_fish, a.fish_modelo)
                falta.remove(f)
                print(f"voz (Fish Audio): {k + 1}", flush=True)
        except Exception as e:
            print(f"voz: Fish Audio falhou ({str(e)[:200]}) — o resto vai pelo Chatterbox", flush=True)
    if falta:
        instala()
        import torch
        import torchaudio
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        dev = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"voz: {len(falta)} falas na sua voz ({'placa de vídeo' if dev == 'cuda' else 'processador'})...", flush=True)
        m = ChatterboxMultilingualTTS.from_pretrained(device=dev)
        exag = min(a.exagero, 0.6)  # acima disso o modelo começa a "cantar"/embolar
        for k, f in enumerate(falta):
            pedacos = []
            for fr in frases(f["falado"]):
                w = frase_boa(m, fr, ref, exag, torch)
                pedacos += [w, torch.zeros(1, int(m.sr * 0.08))]
            torchaudio.save(f["arquivo"], torch.cat(pedacos, dim=1), m.sr)
            print(f"voz: {k + 1}/{len(falta)}", flush=True)
    # SEM PAUSAS no meio (vale para Fish, Chatterbox e as já prontas do cache; marca .sp = já tratada)
    if not a.com_pausas:
        for f in falas:
            arq = Path(f["arquivo"])
            marca = arq.with_suffix(".sp")
            if arq.exists() and not marca.exists():
                try:
                    c = sem_pausas(arq, a.max_pausa)
                    marca.write_text(f"{c:.2f}", encoding="utf-8")
                    if c > 0.2:
                        print(f"voz: {f['id']} sem {c:.1f}s de silêncio no meio", flush=True)
                except Exception as e:
                    print(f"voz: não tirei as pausas de {arq.name} ({str(e)[:80]})", flush=True)
    Path(a.falas).write_text(json.dumps(falas, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
