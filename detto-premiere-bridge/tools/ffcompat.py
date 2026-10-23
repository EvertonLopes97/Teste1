# -*- coding: utf-8 -*-
"""Opções do FFmpeg que mudaram de nome entre as versões (o mesmo que o tools/motion/ffopts.js faz no Node).

    até a 6.x:      -filter_script:v arq   /  -filter_complex_script arq
    7.0 em diante:  -/filter:v arq         /  -/filter_complex arq      (as antigas FORAM REMOVIDAS na 8)

O PC do Everton tem FFmpeg novo: usar o nome antigo dá "Unrecognized option 'filter_complex_script'".
Use sempre `filtro_complexo(arq)` em vez de escrever a opção na mão.
"""
import re
import subprocess

_MAIOR = None


def versao():
    """o número grande da versão do FFmpeg (build de git sem número = assume nova)"""
    global _MAIOR
    if _MAIOR is None:
        try:
            r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            m = re.search(r"ffmpeg version n?(\d+)", r.stdout or "")
            _MAIOR = int(m.group(1)) if m else 7
        except (OSError, ValueError):
            _MAIOR = 7
    return _MAIOR


def nova():
    return versao() >= 7


def filtro_complexo(arq):
    """["-/filter_complex", arq] (FFmpeg 7+) ou ["-filter_complex_script", arq] (até a 6)"""
    return ["-/filter_complex", str(arq)] if nova() else ["-filter_complex_script", str(arq)]


def filtro_v(arq):
    """["-/filter:v", arq] (FFmpeg 7+) ou ["-filter_script:v", arq] (até a 6)"""
    return ["-/filter:v", str(arq)] if nova() else ["-filter_script:v", str(arq)]
