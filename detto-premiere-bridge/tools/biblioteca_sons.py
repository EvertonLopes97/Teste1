# -*- coding: utf-8 -*-
"""Biblioteca de efeitos sonoros do Everton (pasta do PACK DE EDIÇÃO) usada por todas as edições.

Catalogar (uma vez, ou quando acrescentar efeitos):
    python tools/biblioteca_sons.py "E:\\edição\\efeitos de video\\PACK DE EDIÇÃO 2.0"

Lê todos os áudios das subpastas (Efeitos Sonoros, Memes, ...), separa por categoria pelo NOME do
arquivo e grava detto-premiere-bridge/sons.json. Para forçar um efeito numa categoria, renomeie o
arquivo com a palavra da categoria (ex.: "soco forte.mp3") ou edite o sons.json à mão.
Categoria sem arquivo usa os efeitos "famosos" da Mixkit (licença livre), baixados na hora.
"""
import json
import subprocess
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ARQ = RAIZ / "sons.json"
CACHE = RAIZ / "tools" / "galo" / "sons"
AUDIO = {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".wma"}
PULAR = ("musica", "music", "trilha", "song")  # pastas de música não são efeito

CATEGORIAS = {
    "soco": ["soco", "punch", "murro", "pancada", "porrada", "impact", "impacto", "hit", "golpe", "kick",
             "chute", "smack", "bater", "batida", "luta", "fight"],
    "tapa": ["tapa", "slap", "tapinha", "clap", "palma"],
    "chicote": ["chicote", "whip", "chua", "swish", "swing", "lash"],
    "whoosh": ["whoosh", "woosh", "swoosh", "swoosh", "transi", "transition", "swipe", "vento", "wind",
               "passagem", "zoom", "fast"],
    "boom": ["boom", "vine", "bass", "explos", "drop"],
    "pop": ["pop", "bubble", "bolha", "plop"],
    "click": ["click", "clique", "mouse", "tecla", "keyboard"],
    "ding": ["ding", "bell", "sino", "notif", "plim", "correct", "certo", "acerto"],
    "riser": ["riser", "rise", "subida", "suspense", "build", "tensao", "tension"],
    "tick": ["tick", "tic tac", "tictac", "relogio", "clock"],
    "glitch": ["glitch", "estatica", "static", "erro", "error"],
    "fail": ["fail", "bruh", "trombone", "sad", "triste", "errou", "wrong", "buzzer"],
    "risada": ["risada", "laugh", "rindo", "haha", "kkk"],
    "dinheiro": ["cash", "dinheiro", "money", "caixa", "coin", "moeda"],
    "scratch": ["scratch", "disco", "record", "arranh"],
    "camera": ["camera", "shutter", "foto", "flash"],
}

# "famosos" de uso livre (Mixkit) quando a pasta não tiver a categoria
MIXKIT = {"soco": 2155, "tapa": 2167, "chicote": 2050, "whoosh": 1492}


def norm(s):
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return s.replace("_", " ").replace("-", " ")


def catalogar(pastas):
    lib = {k: [] for k in CATEGORIAS}
    for pasta in pastas:
        for f in sorted(Path(pasta).rglob("*")):
            if f.suffix.lower() not in AUDIO:
                continue
            caminho = norm(str(f.relative_to(pasta)))
            if any(p in norm(str(f.parent)) for p in PULAR):
                continue
            for cat, chaves in CATEGORIAS.items():
                if any(ch in caminho for ch in chaves):
                    lib[cat].append(str(f))
                    break
            else:
                lib.setdefault("outros", []).append(str(f))
    ARQ.write_text(json.dumps(lib, ensure_ascii=False, indent=1), encoding="utf-8")
    return lib


def biblioteca():
    try:
        return json.loads(ARQ.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def arquivo(categoria, n=0):
    """Arquivo da categoria (alterna entre os disponíveis); senão o 'famoso' da Mixkit; senão None."""
    lista = [p for p in biblioteca().get(categoria, []) if Path(p).exists()]
    if lista:
        return lista[n % len(lista)]
    sid = MIXKIT.get(categoria)
    if sid is None:
        return None
    mp3 = CACHE / f"{sid}.mp3"
    if not mp3.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["curl", "-sSfL", "-m", "60", "-A", "Mozilla/5.0", "-o", str(mp3),
                            f"https://assets.mixkit.co/active_storage/sfx/{sid}/{sid}-preview.mp3"])
        if r.returncode:
            return None
    return str(mp3)


def carregar(caminho, dur=1.2, sr=48000):
    """Áudio mono float32, sem silêncio no começo, cortado em `dur` segundos e no mesmo volume."""
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(caminho), "-af",
                        f"silenceremove=start_periods=1:start_threshold=-45dB,atrim=0:{dur},"
                        f"afade=t=out:st={dur * 0.75:.3f}:d={dur * 0.25:.3f}",
                        "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True)
    a = np.frombuffer(r.stdout, np.float32)
    return a / max(1e-4, float(np.abs(a).max())) * 0.9


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    lib = catalogar(sys.argv[1:])
    for cat, fs in lib.items():
        print(f"  {cat:<9} {len(fs):>4} arquivos" + (f"  ex.: {Path(fs[0]).name}" if fs else "  (usa Mixkit)"))
    print(f"Gravado: {ARQ}")
