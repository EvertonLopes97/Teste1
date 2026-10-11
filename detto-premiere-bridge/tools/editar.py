# -*- coding: utf-8 -*-
"""Edição completa com UM comando, sem gastar o Claude:

    python tools/editar.py "C:/Users/guebe/Videos/edição ia/gravação.mp4" [--roteiro "roteiro.txt"] [--teste] [--sem-verticais]

SEU ROTEIRO: se você gravou com um roteiro (mesmo mudando as falas), passe com --roteiro ou deixe
o .txt na mesma pasta com o MESMO NOME do vídeo ("rodada 29.txt" ao lado de "rodada 29.MOV").
O sistema bate cada trecho do roteiro com o que você FALOU de verdade (transcrição) e usa os
comandos dele (MODO, MG, VFX, TELA...): cards, campinho, placares, VAR, enquete. Sem roteiro,
o Gemini escreve um.

Passos (cada um é pulado se o arquivo já existir na pasta do job, então dá para refazer só o fim):
  1. transcrição palavra por palavra (faster-whisper, na sua placa de vídeo)      → words.json
  2. rastreio do rosto (YuNet)                                                      → face.json
  3. roteiro: o SEU (--roteiro / mesmo nome do vídeo) ou escrito pelo Gemini (GEMINI_API_KEY) → roteiro.txt
     (se preferir, escreva/edite o roteiro.txt você mesmo ou peça ao Claude e rode de novo)
  4. plano de edição (corte conservador: só pausas > 0,8 s)                         → EDIT_PLAN.json
  5. vídeo horizontal (YouTube) + o mesmo vídeo inteiro em 9:16 (TikTok/Reels) + um vertical por
     corte sugerido, com voz tratada e seus efeitos sonoros
  6. fotos dos jogadores/escudos conferidas pelo elenco do SofaScore              → jogadores.json
  7. conferência antes de entregar (cor × gravação, fotos, volume)                → conferencia.txt/.jpg
--teste: só o primeiro minuto.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PONTE = Path(__file__).resolve().parents[1]
T = PONTE / "tools"


def roda(cmd):
    print("\n>>", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=PONTE)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("--teste", action="store_true")
    p.add_argument("--sem-verticais", action="store_true")
    p.add_argument("--titulo", default="")
    p.add_argument("--sfx", help="volume dos efeitos sonoros (padrão 0.3; 0.15 = mais baixo, 0.5 = mais alto, 0 = sem efeitos)")
    p.add_argument("--roteiro", help="seu roteiro (.txt); senão procura <nome do vídeo>.txt na pasta do vídeo")
    a = p.parse_args()
    video = Path(a.video).resolve()
    if not video.exists():
        perto = sorted(video.parent.glob("*")) if video.parent.exists() else []
        raise SystemExit(f"Não achei o vídeo: {video}\n"
                         + (("Arquivos nessa pasta:\n  " + "\n  ".join(p.name for p in perto[:30])) if perto else
                            "Essa pasta não existe. Confira o caminho (no Explorador: botão direito no vídeo > Copiar como caminho)."))
    job = video.with_name(video.stem + "_job")
    job.mkdir(exist_ok=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(video)], capture_output=True, text=True, check=True).stdout.strip())
    py = sys.executable
    if not (job / "words.json").exists():
        roda([py, T / "transcrever.py", video, job / "words.json"])
    if not (job / "face.json").exists():
        modelo = PONTE / "yunet.onnx"
        if not modelo.exists():
            roda(["curl", "-sSfL", "-o", modelo, "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
                  "face_detection_yunet/face_detection_yunet_2023mar.onnx"])
        roda([py, T / "motion" / "facetrack.py", video, job / "face.json", "--model", modelo])
    # o roteiro do Everton (gravou com ele, mesmo mudando as falas) vale mais que o do Gemini
    seu = Path(a.roteiro).resolve() if a.roteiro else None
    if seu is None:
        for c in (video.with_suffix(".txt"), video.with_name(video.stem + "_roteiro.txt"), job / "roteiro_base.txt"):
            if c.exists():
                seu = c
                break
    if seu is not None:
        if not seu.exists():
            raise SystemExit(f"Não achei o roteiro: {seu}")
        alvo = job / "roteiro.txt"
        # --roteiro: sempre vale o seu; achado na pasta: só se for mais novo que o do job (que você pode ter ajustado)
        if not alvo.exists() or a.roteiro and seu.read_bytes() != alvo.read_bytes() or seu.stat().st_mtime > alvo.stat().st_mtime:
            shutil.copyfile(seu, alvo)
            print(f"\nRoteiro: {seu.name} (o seu) → alinhado com o que você falou")
    if not (job / "roteiro.txt").exists():
        roda([py, T / "roteiro_ia.py", job / "words.json", job / "roteiro.txt", "--titulo", a.titulo])
    roda(["node", T / "roteiro-to-plan.js", job / "roteiro.txt", "--media", video, "--duration", f"{dur:.2f}",
          "--words", job / "words.json", "--gap", "0.8", "--job", video.stem, "--out", job / "EDIT_PLAN.json",
          "--report", job / "alinhamento.json"])
    plano = json.loads((job / "EDIT_PLAN.json").read_text(encoding="utf-8"))
    if (plano.get("meta") or {}).get("people"):
        # fotos dos jogadores e escudos, conferidos pelo elenco atual de cada time
        try:
            roda([py, T / "jogadores.py", job / "EDIT_PLAN.json"])
        except subprocess.CalledProcessError:
            print("Aviso: não consegui buscar as fotos dos jogadores (sem internet?). Os cards saem com as iniciais.")
    base = ["node", T / "render-dynamic.js", job / "EDIT_PLAN.json", "--video", video, "--face", job / "face.json",
            "--fonts", PONTE / "fonts", "--work", job / "tmp"] + (["--sfx", a.sfx] if a.sfx else [])
    trecho = ["--from", "0", "--to", "60"] if a.teste else []
    roda(base + trecho + ["--out", job / "horizontal.mp4"])
    # conferência antes de entregar: cor × gravação (HDR do iPhone), fotos, volume
    try:
        roda([py, T / "conferir.py", job / "horizontal.mp4", video, "--job", job])
    except subprocess.CalledProcessError:
        print("Aviso: a conferência automática falhou; confira o vídeo antes de postar.")
    # o vídeo inteiro também em 9:16 (TikTok / Reels), com gráficos e legendas refeitos para o vertical
    roda(base + trecho + ["--format", "vertical", "--out", job / "vertical_completo.mp4"])
    if not a.sem_verticais and not a.teste:
        cortes = sorted({int(m.group(1)) for x in plano.get("markers", []) for m in [re.match(r"9:16 #(\d+)", x.get("name", ""))] if m})
        for k in cortes:
            roda(base + ["--cut", k, "--out", job / f"vertical_{k}.mp4"])
    conf = job / "conferencia.txt"
    if conf.exists():
        print("\n" + conf.read_text(encoding="utf-8").splitlines()[0])
    print(f"\nPronto: {job}")


if __name__ == "__main__":
    main()
