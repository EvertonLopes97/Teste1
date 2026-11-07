# -*- coding: utf-8 -*-
"""Coloca a música de fundo num vídeo JÁ editado (depois dos seus cortes no Premiere/CapCut).

    python tools\\trilha.py "video.mp4" "musica.mp3"
    python tools\\trilha.py "video.mp4" "0:00=trap.mp3" "3:40=suspense.mp3" "9:00=trap.mp3"
    python tools\\trilha.py "video.mp4" "musica.mp3" --vol -24 --saida "final.mp4"

- A imagem NÃO é refeita (cópia direta, rápido e sem perder qualidade; 60 fps continua 60 fps).
- A música repete até o fim do vídeo, entra e sai com fade e troca de uma faixa para a outra
  com cruzamento de 2 s no tempo que você indicar ("3:40=arquivo.mp3" = começa aos 3:40 do vídeo).
- Volume: a música fica no nível --vol (padrão -27 LUFS, ~11 dB abaixo da sua voz) e ABAIXA sozinha
  enquanto você fala (sidechain, mais ~8 dB); nos respiros e gráficos sem fala ela sobe de volta.
- Saída padrão: "<video> com trilha.mp4" na mesma pasta; volume final -14 LUFS (padrão do YouTube).
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path


def duracao(arq):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arq)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def tempo(txt):
    p = [float(x.replace(",", ".")) for x in txt.split(":")]
    s = 0.0
    for x in p:
        s = s * 60 + x
    return s


def main():
    ap = argparse.ArgumentParser(description="Música de fundo num vídeo já editado")
    ap.add_argument("video")
    ap.add_argument("musicas", nargs="+", help='"musica.mp3" ou "0:00=a.mp3" "3:40=b.mp3"')
    ap.add_argument("--vol", type=float, default=-27.0, help="volume da música em LUFS (padrão -27; -24 = mais alta, -30 = mais baixa)")
    ap.add_argument("--abaixa", type=float, default=8.0, help="quanto a música abaixa quando você fala, em dB (padrão 8)")
    ap.add_argument("--saida", default="")
    a = ap.parse_args()

    video = Path(a.video)
    if not video.exists():
        sys.exit(f"Não achei o vídeo: {video}")
    dur = duracao(video)
    if dur <= 0:
        sys.exit("Não consegui ler a duração do vídeo.")

    faixas = []
    for m in a.musicas:
        mm = re.match(r"^\s*(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?)\s*=\s*(.+)$", m)
        ini, arq = (tempo(mm.group(1)), mm.group(2)) if mm else (0.0, m)
        arq = Path(arq.strip().strip('"'))
        if not arq.exists():
            sys.exit(f"Não achei a música: {arq}")
        faixas.append((ini, arq))
    faixas.sort(key=lambda x: x[0])
    if faixas[0][0] > 0.5:
        print(f"Aviso: a primeira música só começa em {faixas[0][0]:.1f} s.")

    cruz = 2.0  # cruzamento entre faixas
    entradas, partes, rotulos = ["-i", str(video)], [], []
    for i, (ini, arq) in enumerate(faixas):
        fim = faixas[i + 1][0] + cruz if i + 1 < len(faixas) else dur
        fim = min(fim, dur)
        n = max(0.1, fim - ini)
        entradas += ["-stream_loop", "-1", "-i", str(arq)]
        sai = 3.0 if i + 1 == len(faixas) else cruz
        partes.append(
            f"[{i + 1}:a]atrim=0:{n:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
            f"loudnorm=I={a.vol}:TP=-3:LRA=11,"
            f"afade=t=in:st=0:d={1.5 if i == 0 else cruz},afade=t=out:st={max(0, n - sai):.3f}:d={sai},"
            f"adelay={int(ini * 1000)}:all=1[m{i}]")
        rotulos.append(f"[m{i}]")
    # sidechain: a sua voz (áudio do vídeo) abaixa a música
    limiar = 0.02
    razao = max(1.5, 10 ** (a.abaixa / 20) * 1.2)
    filtro = ";".join(partes + [
        f"{''.join(rotulos)}amix=inputs={len(rotulos)}:duration=longest:normalize=0[mus]" if len(rotulos) > 1 else "[m0]anull[mus]",
        "[0:a]aresample=48000,asplit=2[voz][chave]",
        f"[mus][chave]sidechaincompress=threshold={limiar}:ratio={razao:.2f}:attack=40:release=600:makeup=1[musd]",
        "[voz][musd]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.0:LRA=11,aresample=48000[a]",
    ])
    saida = Path(a.saida) if a.saida else video.with_name(f"{video.stem} com trilha.mp4")
    cmd = ["ffmpeg", "-y", "-v", "error", *entradas, "-filter_complex", filtro,
           "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", f"{dur:.3f}", "-movflags", "+faststart", str(saida)]
    print(f"Trilha: {len(faixas)} música(s), volume {a.vol} LUFS, abaixa {a.abaixa} dB quando você fala...")
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit("Falhou ao colocar a trilha (veja a mensagem do ffmpeg acima).")
    print(f"Pronto: {saida}")


if __name__ == "__main__":
    main()
