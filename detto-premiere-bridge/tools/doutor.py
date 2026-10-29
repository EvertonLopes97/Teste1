# -*- coding: utf-8 -*-
"""DOUTOR — diz POR QUE o sistema parou, num comando só.

    python tools\\doutor.py            (grava tools\\diagnostico.txt para você colar no Claude)
    python tools\\doutor.py --rapido   (pula os testes que gastam internet/IA)

Confere, nesta ordem: versão do código · travas presas · IA DE TEXTO (Gemini → IAs grátis → Claude) ·
voz (VoiceStudio/Fish) · Instagram (vagas de Reels teste, pausa, fila, Drive) · espaço em disco ·
e a ÚLTIMA LINHA DE ERRO de cada registro (reels, histórias, canais, shop, edição).

Nada aqui muda arquivo nenhum: é só leitura.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PONTE = AQUI.parent
for p in (AQUI, AQUI / "canal", AQUI / "postar", AQUI / "reels", AQUI / "painel"):
    sys.path.insert(0, str(p))

LINHAS = []


def diz(s=""):
    print(s, flush=True)
    LINHAS.append(s)


def titulo(s):
    diz()
    diz(f"=== {s}")


def raiz():
    if os.name == "nt" and Path("E:/").exists():
        return Path("E:/DETTO")
    return Path.home() / "DETTO"


def _cmd(args, tempo=20):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=tempo, cwd=str(PONTE))
        return (r.stdout or r.stderr or "").strip()
    except Exception as e:  # noqa: BLE001
        return f"(não rodou: {str(e)[:80]})"


# ----------------------------------------------------------------- versão
def versao():
    titulo("VERSÃO DO CÓDIGO")
    diz(f"Python: {sys.version.split()[0]}   pasta: {PONTE}")
    diz(f"commit: {_cmd(['git', 'log', '-1', '--format=%h %ad %s', '--date=format:%d/%m %H:%M'])}")
    sujo = _cmd(["git", "status", "--porcelain"])
    diz(f"arquivos mexidos à mão: {len([l for l in sujo.splitlines() if l.strip()])}")
    boa = PONTE / ".ultima_boa"
    if boa.exists():
        diz(f"última versão que passou no teste: {boa.read_text(encoding='utf-8').strip()[:60]}")
    try:
        txt = (AQUI / "painel" / "painel.py").read_text(encoding="utf-8")
        d = re.search(r'PAINEL_VERSAO\s*=\s*"([^"]+)"', txt)
        t = re.search(r'VERSAO_TELA\s*=\s*"([^"]+)"', (AQUI / "painel" / "painel.html").read_text(encoding="utf-8"))
        diz(f"painel no disco: {d.group(1) if d else '?'} / tela {t.group(1) if t else '?'}"
            + ("   (diferentes! suba as duas juntas)" if d and t and d.group(1) != t.group(1) else ""))
    except OSError:
        pass
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:8730/api/estado", timeout=4) as r:
            e = json.loads(r.read())
        diz(f"painel RODANDO agora, versão em memória: {e.get('versao') or '?'}"
            + ("   (diferente do disco: clique em Reiniciar o painel)"
               if d and e.get("versao") and e["versao"] != d.group(1) else ""))
    except Exception as err:  # noqa: BLE001
        diz(f"painel não respondeu em localhost:8730 ({str(err)[:60]}) — ele está aberto?")


# ----------------------------------------------------------------- travas
def travas():
    titulo("TRAVAS (se uma estiver presa, NADA roda)")
    base = raiz()
    alvos = [(base / "reels" / ".reels_rodando", "reels.py"),
             (base / "shop" / ".shop_rodando", "shop.py"),
             (base / "canal_galo" / ".canal_rodando", "canal.py (notícias)"),
             (base / "canal_vlogs" / ".canal_rodando", "canal_vlog.py"),
             (base / "postar" / ".postando", "postar.py")]
    for f, quem in alvos:
        if not f.exists():
            diz(f"livre   {quem}")
            continue
        preso = _trava_presa(f)
        quando = dt.datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m %H:%M")
        diz(f"{'PRESA ' if preso else 'livre '}  {quem}"
            + (f" — um processo vivo está com ela desde {quando}" if preso
               else f" (arquivo antigo de {quando}, não atrapalha)"))


def _trava_presa(f):
    """o arquivo existe, mas a trava é do sistema: só está presa se um processo VIVO a tiver"""
    try:
        g = open(f, "a+")
    except OSError:
        return True
    try:
        if os.name == "nt":
            import msvcrt
            g.seek(0)
            msvcrt.locking(g.fileno(), msvcrt.LK_NBLCK, 1)
            msvcrt.locking(g.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(g.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(g.fileno(), fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        g.close()


# ----------------------------------------------------------------- IA de texto
PERGUNTA = 'Responda SOMENTE com este JSON, sem mais nada: {"ok": 1}'


def ia_de_texto(rapido=False):
    titulo("IA DE TEXTO (sem ela não sai reels, história, notícia nem shop)")
    chaves = ["GEMINI_API_KEY", "CEREBRAS_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY", "OPENROUTER_API_KEY",
              "FISH_API_KEY", "PEXELS_API_KEY", "PIXABAY_API_KEY"]
    diz("chaves no PC: " + ", ".join(f"{k}={'sim' if os.environ.get(k) else 'NÃO'}" for k in chaves))
    if rapido:
        diz("(--rapido: não testei as IAs)")
        return
    try:
        import roteiro_ia as RI
    except Exception as e:  # noqa: BLE001
        diz(f"NÃO consegui nem importar o roteiro_ia.py: {str(e)[:200]}")
        return
    for nome, fn in (("Gemini", lambda: RI.gemini(PERGUNTA)),
                     ("IAs grátis", lambda: RI.texto_gratis(PERGUNTA, log=lambda *_: None)),
                     ("Claude da assinatura", lambda: RI.claude_cli(PERGUNTA, tempo=180, log=lambda *_: None))):
        try:
            r = fn()
            r = (r if isinstance(r, str) else json.dumps(r, ensure_ascii=False))[:120].replace("\n", " ")
            diz(f"{'OK  ' if r.strip() else 'VAZIO'} {nome}: {r.strip() or '(não respondeu nada)'}")
        except Exception as e:  # noqa: BLE001
            diz(f"ERRO  {nome}: {str(e)[:220]}")


# ----------------------------------------------------------------- voz
def voz(rapido=False):
    titulo("VOZ")
    try:
        import voz as V
    except Exception as e:  # noqa: BLE001
        diz(f"não importei o voz.py: {str(e)[:150]}")
        return
    url = V.voicestudio_url()
    ligado = V.voicestudio_ligado(url, tempo=4)
    diz(f"VoiceStudio em {url}: {'aberto' if ligado else 'FECHADO'}")
    if ligado:
        vz = V.voicestudio_vozes(url)
        diz(f"vozes cadastradas: {len(vz)}" + (f" ({', '.join(v['nome'] for v in vz[:6])})" if vz else
            "  ← SEM VOZ NENHUMA: ele sortearia uma voz qualquer, então o sistema cai no Fish"))
    diz(f"Fish Audio: {'chave presente' if os.environ.get('FISH_API_KEY') else 'SEM CHAVE'}")
    if not ligado and not os.environ.get("FISH_API_KEY"):
        diz("=> SEM VOZ: notícias, histórias e shop param aqui. Abra o VoiceStudio (com a sua voz clonada).")


# ----------------------------------------------------------------- Instagram
def instagram():
    titulo("INSTAGRAM / POSTAGEM")
    try:
        import postar as P
    except Exception as e:  # noqa: BLE001
        diz(f"não importei o postar.py: {str(e)[:150]}")
        return
    base = P.pasta_padrao()
    cfg = P.le_json(base / "config.json", {}) or {}
    estado = P.le_estado(base)
    import time as _t
    for c in cfg.get("contas") or []:
        k = f"{c.get('plataforma')}_{c.get('conta')}"
        e = estado.get(k, {}) or {}
        fila = P.fila_de(base, k)
        diz(f"\n-- {k}  ({'LIGADA' if c.get('ligada', True) else 'desligada'})")
        diz(f"   fila: {len(fila)} vídeo(s)")
        pausa = e.get("pausa_ate", 0)
        if pausa > _t.time():
            diz(f"   PAUSADA até {dt.datetime.fromtimestamp(pausa):%d/%m %H:%M} — motivo: {e.get('pausa_motivo', '?')}")
        if c.get("plataforma") == "instagram":
            diz(f"   reels TESTE: {'ligado' if P.ig_e_teste(cfg, c) else 'desligado'}")
            ativos = P.testes_ativos(base, k)
            vagas = int(c.get("max_teste") or e.get("teste_vagas") or 0)
            diz(f"   testes ativos (janela de {P.TESTE_JANELA_H} h): {len(ativos)}"
                + (f" · vagas aprendidas: {vagas}" if vagas else " · vagas: ainda não sei"))
            motivo, libera = P.vaga_de_teste(cfg, base, c, estado, k)
            diz(f"   pode mandar agora? {'SIM' if not motivo else 'NÃO — ' + motivo}"
                + (f" (próxima vaga {libera:%d/%m %H:%M})" if libera else ""))
            if e.get("teste_recusa"):
                diz(f"   última recusa do Instagram: {e['teste_recusa']}")
            diz(f"   vai para o Drive quando não dá pela API? {'sim' if P.vai_para_celular(cfg, c) else 'não'}"
                f" · sem vaga sobe como normal? {'sim' if P.cai_para_normal(cfg, c) else 'não'}")
        cel = e.get("celular") or {}
        if cel:
            diz(f"   esperando VOCÊ postar pelo celular (pasta do Drive): {len(cel)}")
        post = len(list((base / "postados" / k).glob("*.json"))) if (base / "postados" / k).is_dir() else 0
        falhas = len(list((base / "falhas" / k).glob("*.mp4"))) if (base / "falhas" / k).is_dir() else 0
        diz(f"   postados (total): {post} · em falhas: {falhas}")


# ----------------------------------------------------------------- disco e registros
def disco():
    titulo("DISCO")
    for d in ({Path(PONTE.anchor or "/"), raiz()} if raiz().exists() else {Path(PONTE.anchor or "/")}):
        try:
            u = shutil.disk_usage(d)
            diz(f"{d}: {u.free / 2**30:.1f} GB livres de {u.total / 2**30:.1f} GB"
                + ("   ← POUCO ESPAÇO: render e voz falham assim" if u.free < 8 * 2**30 else ""))
        except OSError:
            pass


RUIDO = re.compile(r"^(frame=|size=|\[|Press \[q\]|\s*$)", re.I)
ERRO = re.compile(r"erro|error|exception|traceback|not found|no such|falh|não achei|não consegui|"
                  r"espaço|space left|permission|recusad|invalid|inválid|429|quota|timed out", re.I)


def registros(quantas=4):
    titulo("ÚLTIMOS ERROS DE CADA REGISTRO")
    base = raiz()
    alvos = [("reels", base / "reels" / "painel_reels.log"),
             ("reels (links que falharam)", base / "reels" / "links_falhos.txt"),
             ("histórias", base / "historias" / "painel_historias.log"),
             ("notícias", base / "canal_galo" / "canal.log"),
             ("vlogs", base / "canal_vlogs" / "canal.log"),
             ("shop", base / "shop" / "shop.log"),
             ("shop (produtos que falharam)", base / "shop" / "produtos_falhos.txt"),
             ("postagem", base / "postar" / "postar.log"),
             ("painel", base / "postar" / "painel.log")]
    jobs = sorted((base / "edicao").glob("*/painel_log.txt"), key=lambda f: f.stat().st_mtime) \
        if (base / "edicao").is_dir() else []
    if jobs:   # o registro da edição é por trabalho: pega o mais recente
        alvos.append((f"edição ({jobs[-1].parent.name})", jobs[-1]))
    for nome, f in alvos:
        if not f.exists():
            diz(f"\n-- {nome}: (sem registro em {f})")
            continue
        try:
            linhas = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as e:
            diz(f"\n-- {nome}: não li ({e})")
            continue
        quando = dt.datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m %H:%M")
        ruins = [l.strip() for l in linhas if not RUIDO.match(l) and ERRO.search(l)][-quantas:]
        diz(f"\n-- {nome} (mexido {quando}, {len(linhas)} linhas)")
        for l in ruins or ["(nenhuma linha com cara de erro)"]:
            diz(f"   {l[:300]}")
        if linhas:
            diz(f"   última linha: {linhas[-1].strip()[:300]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true", help="não testa as IAs (nem gasta internet)")
    ap.add_argument("--saida", default=str(AQUI / "diagnostico.txt"))
    a = ap.parse_args()
    diz(f"DOUTOR DETTO — {dt.datetime.now():%d/%m/%Y %H:%M}")
    for passo in (versao, travas, lambda: ia_de_texto(a.rapido), lambda: voz(a.rapido), instagram, disco, registros):
        try:
            passo()
        except Exception as e:  # noqa: BLE001 — um pedaço que falha não pode derrubar o diagnóstico
            diz(f"(este pedaço do diagnóstico falhou: {type(e).__name__}: {str(e)[:200]})")
    Path(a.saida).write_text("\n".join(LINHAS) + "\n", encoding="utf-8")
    diz()
    diz(f"-> {a.saida}   (abra e cole aqui no Claude)")


if __name__ == "__main__":
    main()
