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
  8. versão COM LANCES de cada vídeo (trechos [LANCE+VO]: vídeo do lance baixado dos melhores momentos)
     → horizontal_lances.mp4, vertical_completo_lances.mp4, vertical_N_lances.mp4 (você escolhe qual postar)
--teste: só o primeiro minuto.   --sem-lances: não busca os lances.   --cookies chrome: YouTube pedindo login.
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


def tem_trechos(f):
    """o roteiro tem trechos que o plano entende? ([0:00 – 0:08] / [CAM] — TÍTULO com FALA:) — mesmo teste do roteiro-to-plan"""
    try:
        r = subprocess.run(["node", str(T / "roteiro" / "tem_trechos.js"), str(f)], cwd=PONTE, capture_output=True, text=True)
        return r.returncode != 3
    except OSError:
        return True


def roda(cmd):
    print("\n>>", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=PONTE)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fps", type=int, default=60, help="fps do horizontal (padrão 60, o do YouTube; verticais saem em 30)")
    p.add_argument("video")
    p.add_argument("--teste", action="store_true")
    p.add_argument("--sem-verticais", action="store_true")
    p.add_argument("--titulo", default="")
    p.add_argument("--sfx", help="volume dos efeitos sonoros (padrão 0.3; 0.15 = mais baixo, 0.5 = mais alto, 0 = sem efeitos)")
    p.add_argument("--roteiro", help="seu roteiro (.txt); senão procura <nome do vídeo>.txt na pasta do vídeo")
    p.add_argument("--sem-lances", action="store_true", help="não faz a versão com o vídeo dos lances")
    p.add_argument("--sem-thumbs", action="store_true", help="não faz as 4 thumbs")
    p.add_argument("--cookies", default=None, help="navegador logado no YouTube (chrome, edge, firefox) se pedir login")
    p.add_argument("--sem-sdr", action="store_true", help="não faz o master SDR antes (gravação HDR do iPhone)")
    p.add_argument("--reels", action="store_true",
                   help="REELS COM ROTEIRO: o vídeo inteiro vira um reels 9:16 (sem horizontal, sem cortes, sem thumb)")
    p.add_argument("--canal", default="galo", choices=["galo", "noticias", "vlog", "sem"],
                   help="vinheta de abertura do horizontal (padrão galo; 'sem' = nenhuma)")
    a = p.parse_args()
    video = Path(a.video).resolve()
    if not video.exists() and video.parent.exists():
        # nome digitado com espaço/ponto/maiúscula diferente ("times. mp4" × "times .mp4"): acha o parecido
        chave = lambda p: re.sub(r"[^a-z0-9]", "", p.name.lower())  # noqa: E731
        iguais = [p for p in video.parent.iterdir() if p.is_file() and chave(p) == chave(video)]
        if len(iguais) == 1:
            print(f"Usando o vídeo: {iguais[0].name}")
            video = iguais[0]
    if not video.exists():
        perto = sorted(video.parent.glob("*")) if video.parent.exists() else []
        raise SystemExit(f"Não achei o vídeo: {video}\n"
                         + (("Arquivos nessa pasta:\n  " + "\n  ".join(p.name for p in perto[:30])) if perto else
                            "Essa pasta não existe. Confira o caminho (no Explorador: botão direito no vídeo > Copiar como caminho)."))
    job = video.with_name(video.stem + "_job")
    job.mkdir(exist_ok=True)
    orig = video
    # HDR do iPhone: converte para SDR UMA vez antes de tudo (o que você fazia no CapCut) e edita a partir dele
    if not a.sem_sdr:
        sys.path.insert(0, str(T))
        from sdr import master_sdr
        try:
            video = master_sdr(orig)
        except Exception as e:
            print(f"Aviso: o master SDR falhou ({e}); sigo com a gravação original (cor convertida no render).")
            video = orig
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
        for c in (orig.with_suffix(".txt"), orig.with_name(orig.stem + "_roteiro.txt"), job / "roteiro_base.txt"):
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
        roda([py, T / "roteiro_ia.py", job / "words.json", job / "roteiro.txt", "--titulo", a.titulo]
             + (["--reels"] if a.reels else []))
    elif not tem_trechos(job / "roteiro.txt"):
        # o SEU roteiro não está no formato com tempos ([0:00 – 0:08] + FALA:) — ex.: o roteiro de gravação, escrito antes:
        # a IA monta o roteiro de edição SEGUINDO o seu (ordem, gráficos, nomes) com os tempos da fala. Antes parava com erro.
        seu_txt = job / "roteiro_seu.txt"
        shutil.copyfile(job / "roteiro.txt", seu_txt)
        print("\nO seu roteiro não tem os tempos ([0:00 – 0:08] + FALA:). Monto o roteiro de edição a partir dele + do que você falou...")
        roda([py, T / "roteiro_ia.py", job / "words.json", job / "roteiro.txt", "--titulo", a.titulo, "--base", seu_txt]
             + (["--reels"] if a.reels else []))
    plano = [T / "roteiro-to-plan.js", job / "roteiro.txt", "--media", video, "--duration", f"{dur:.2f}",
             "--words", job / "words.json", "--gap", "0.8", "--job", orig.stem, "--out", job / "EDIT_PLAN.json",
             "--report", job / "alinhamento.json", "--ajustes", job / "ajustes.txt"]
    try:
        roda(["node"] + plano)
    except subprocess.CalledProcessError:
        # roteiro que a IA escreveu fora do formato: última saída, o roteiro simples pela fala (o vídeo sai mesmo assim)
        print("\nO roteiro não virou plano; faço o roteiro SIMPLES pela fala para o vídeo sair (o anterior fica em roteiro_falhou.txt).")
        shutil.copyfile(job / "roteiro.txt", job / "roteiro_falhou.txt")
        sys.path.insert(0, str(T))
        from roteiro_ia import roteiro_basico
        (job / "roteiro.txt").write_text(roteiro_basico(json.loads((job / "words.json").read_text(encoding="utf-8")), a.titulo),
                                         encoding="utf-8")
        roda(["node"] + plano)
    plano = json.loads((job / "EDIT_PLAN.json").read_text(encoding="utf-8"))
    # SEMPRE: fotos dos jogadores, escudos e as imagens pedidas no roteiro (camisas, fotos de apoio)
    # (antes só rodava quando o roteiro tinha jogador; no vídeo das camisas ficava sem nenhuma imagem)
    try:
        roda([py, T / "jogadores.py", job / "EDIT_PLAN.json"])
    except subprocess.CalledProcessError:
        print("Aviso: não consegui buscar as fotos/imagens (sem internet?). Camisa sem foto sai com o escudo.")
    except KeyboardInterrupt:
        # Ctrl+C na busca: segue a edição com o que já achou
        print("\nBusca de imagens pulada (Ctrl+C). Seguindo a edição com o que já foi achado.")
    if (job / "imagens_conferir.jpg").exists():
        print(f"Imagens escolhidas: {job / 'imagens_conferir.jpg'}")
    # vídeo dos lances (versão com lances): melhores momentos do YouTube, lance achado pela narração
    lances = None
    pede = any(c.get("type") == "lance" for s_ in (plano.get("meta") or {}).get("segments", []) for c in s_.get("comps", []))
    if pede and not a.sem_lances:
        try:
            roda([py, T / "lances.py", job / "EDIT_PLAN.json"] + (["--cookies", a.cookies] if a.cookies else []))
        except (subprocess.CalledProcessError, KeyboardInterrupt):
            print("Aviso: busca dos lances falhou/pulada. Sai só a versão sem lances.")
        lj = job / "lances.json"
        if lj.exists() and any(L.get("video") and L.get("dur") for L in json.loads(lj.read_text(encoding="utf-8")).get("lances", [])):
            lances = lj
            print(f"Lances achados: confira {job / 'lances_conferir.jpg'}")
    base = ["node", T / "render-dynamic.js", job / "EDIT_PLAN.json", "--video", video, "--face", job / "face.json",
            "--fonts", PONTE / "fonts", "--work", job / "tmp"] + (["--sfx", a.sfx] if a.sfx else [])
    trecho = ["--from", "0", "--to", "60"] if a.teste else []
    # YouTube: horizontal em 60 fps (gráficos e movimentos a 60 reais; a gravação a 30 é repetida)
    def com_lances(args, saida):
        """a mesma saída com o vídeo dos lances: só os trechos de lance são refeitos e emendados"""
        if lances and saida.exists():
            try:
                roda(base + args + ["--lances", lances, "--base", saida, "--out", saida.with_name(saida.stem + "_lances.mp4")])
            except subprocess.CalledProcessError:
                print(f"Aviso: a versão com lances de {saida.name} falhou; a sem lances está pronta.")

    # ---------------------------------------------------------------- REELS COM ROTEIRO
    # o vídeo inteiro em 9:16, com o gancho escrito na tela nos 3 primeiros segundos. Sem horizontal, sem cortes,
    # sem thumb: o que sai é UM reels pronto para a fila de postagem.
    if a.reels:
        vc = (plano.get("meta") or {}).get("vertical_cuts") or []
        gancho = (vc[0].get("hook") or vc[0].get("title") or "") if vc else ""
        if not gancho:   # a linha "GANCHO: ..." que a IA escreve no roteiro de reels
            m = re.search(r"^\s*GANCHO:\s*(.+)$", (job / "roteiro.txt").read_text(encoding="utf-8"), re.M)
            gancho = (m.group(1).strip().strip('"') if m else "")
        if not gancho:   # sem gancho no roteiro: a primeira TELA, senão o título
            tela = next((c.get("data", {}).get("text", "") for it in (plano.get("meta") or {}).get("segments", [])
                         for c in it.get("comps", []) if c.get("type") in ("tela", "texto")), "")
            gancho = tela or a.titulo or ""
        saida = job / "reels.mp4"
        roda(base + trecho + ["--format", "vertical"] + (["--gancho", gancho] if gancho else []) + ["--out", saida])
        com_lances(trecho + ["--format", "vertical"] + (["--gancho", gancho] if gancho else []), saida)
        try:
            roda([py, T / "conferir.py", saida, video, "--job", job])
        except subprocess.CalledProcessError:
            print("Aviso: a conferência automática falhou; confira o vídeo antes de postar.")
        shutil.rmtree(job / "tmp", ignore_errors=True)
        print(f"\nREELS pronto: {saida}" + (f"\nGancho na tela: {gancho}" if gancho else ""))
        legenda = job / "post.txt"
        if not legenda.exists():
            titulo = a.titulo or orig.stem
            legenda.write_text(f"{titulo}\n\n#futebol #galo #atleticomineiro\n", encoding="utf-8")
        print(f"Legenda do post: {legenda}")
        return
    roda(base + trecho + ["--fps", str(a.fps), "--out", job / "horizontal.mp4"])
    com_lances(trecho + ["--fps", str(a.fps)], job / "horizontal.mp4")
    # VINHETA DE ABERTURA do canal, na frente do horizontal (o vertical não leva: reels não tem abertura)
    if a.canal != "sem":
        try:
            sys.path.insert(0, str(T / "canal"))
            import vinheta as VIN

            for h_ in (job / "horizontal.mp4", job / "horizontal_lances.mp4"):
                if h_.exists():
                    VIN.abre(h_, a.canal)
        except Exception as e:
            print(f"Aviso: a vinheta não entrou ({str(e)[:140]})")
    # conferência antes de entregar: cor × gravação (HDR do iPhone), fotos, volume
    try:
        roda([py, T / "conferir.py", job / "horizontal.mp4", video, "--job", job])
    except subprocess.CalledProcessError:
        print("Aviso: a conferência automática falhou; confira o vídeo antes de postar.")
    # o vídeo inteiro também em 9:16 (TikTok / Reels), com gráficos e legendas refeitos para o vertical
    roda(base + trecho + ["--format", "vertical", "--out", job / "vertical_completo.mp4"])
    com_lances(trecho + ["--format", "vertical"], job / "vertical_completo.mp4")
    if not a.sem_verticais and not a.teste:
        cortes = sorted({int(m.group(1)) for x in plano.get("markers", []) for m in [re.match(r"9:16 #(\d+)", x.get("name", ""))] if m})
        for k in cortes:
            roda(base + ["--cut", k, "--out", job / f"vertical_{k}.mp4"])
            com_lances(["--cut", k], job / f"vertical_{k}.mp4")
    # 4 thumbs (suas melhores reações + texto + jogador) para escolher
    if not a.sem_thumbs and not a.teste:
        try:
            roda([py, T / "thumb" / "thumb.py", job])
        except (subprocess.CalledProcessError, KeyboardInterrupt):
            print("Aviso: as thumbs falharam; rode depois: python tools\\thumb\\thumb.py \"" + str(job) + "\"")
    # tudo pronto: os quadros extraídos/compostos ocupam vários GB (disco cheio corta o vídeo)
    shutil.rmtree(job / "tmp", ignore_errors=True)
    conf = job / "conferencia.txt"
    if conf.exists():
        print("\n" + conf.read_text(encoding="utf-8").splitlines()[0])
    print(f"\nPronto: {job}")


if __name__ == "__main__":
    main()
