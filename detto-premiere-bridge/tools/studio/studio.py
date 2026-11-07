#!/usr/bin/env python3
"""CLIPES DE IA — o Video Studio por dentro do painel (06/nov, pedido dele: "quero tudo com painel").

Era tudo em scripts de PowerShell soltos na pasta de Downloads. Agora é um módulo que o painel chama,
e o que valia nos scripts continua valendo aqui — porque foi MEDIDO no PC dele:

  · a geração em si leva 6 s; os outros ~90 s de cada clipe são o ComfyUI recarregando 4,6 GB de T5,
    porque 4 GB de VRAM não seguram o modelo inteiro. Por isso tudo entra NA FILA de uma vez: o
    primeiro clipe paga o carregamento, os seguintes aproveitam.
  · TEXTO→VÍDEO inventa um produto parecido (rótulo sem marca, escrita errada). Não é ajuste: é o
    tamanho do modelo que cabe em 4 GB. Serve de ambiente/b-roll.
  · IMAGEM→VÍDEO é o caminho do produto REAL: a foto dele é o primeiro quadro e o modelo só cria o
    movimento. A marca fica certa porque é a foto dele.
  · movimento CURTO E LENTO preserva o rótulo; movimento largo derrete a escrita.

Os nomes dos modelos nunca são escritos à mão: vêm do próprio ComfyUI (/object_info).
"""
import json
import mimetypes
import random
import re
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

AQUI = Path(__file__).resolve().parent
WORKFLOWS = AQUI / "workflows"
COMFY_PADRAO = "http://127.0.0.1:8188"

# movimentos que funcionam em 2 s sem estragar o rótulo da embalagem
MOVIMENTOS = [
    "slow camera push in on the product, shallow depth of field, soft natural light, steady shot",
    "slow orbit around the product on a table, soft studio light, steady shot",
    "slow camera pull back revealing the product, soft natural window light, steady shot",
    "slow vertical tilt up along the product, soft light, steady shot",
]
NEGATIVO = "blurry, distorted, warped text, melting label, deformed product, low quality, flicker"


def log(m):
    print(m, flush=True)


# ------------------------------------------------------------------ conversa com o ComfyUI
def _pega(url, tempo=10):
    with urllib.request.urlopen(url, timeout=tempo) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def ligado(comfy=COMFY_PADRAO):
    try:
        _pega(f"{comfy}/system_stats", 6)
        return True
    except Exception:
        return False


def modelos(comfy=COMFY_PADRAO):
    """o que ESTE ComfyUI tem instalado — nunca chuto o nome do arquivo"""
    try:
        ck = _pega(f"{comfy}/object_info/CheckpointLoaderSimple", 20)
        cl = _pega(f"{comfy}/object_info/CLIPLoader", 20)
        cks = ck["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        cls = cl["CLIPLoader"]["input"]["required"]["clip_name"][0]
    except Exception as e:
        return {"erro": str(e)[:160]}
    ltx = next((c for c in cks if "ltx" in c.lower()), cks[0] if cks else "")
    t5 = next((c for c in cls if "t5" in c.lower()), cls[0] if cls else "")
    return {"ckpt": ltx, "t5": t5, "todos_ckpt": cks, "todos_clip": cls}


def tem_no(nome, comfy=COMFY_PADRAO):
    try:
        _pega(f"{comfy}/object_info/{nome}", 15)
        return True
    except Exception:
        return False


def manda_imagem(arquivo, comfy=COMFY_PADRAO):
    """sobe a foto para o ComfyUI pelo /upload/image — assim não preciso saber onde fica a pasta dele"""
    arquivo = Path(arquivo)
    limite = "----detto" + uuid.uuid4().hex
    tipo = mimetypes.guess_type(arquivo.name)[0] or "image/png"
    corpo = b"".join([
        f"--{limite}\r\n".encode(),
        f'Content-Disposition: form-data; name="image"; filename="{arquivo.name}"\r\n'.encode(),
        f"Content-Type: {tipo}\r\n\r\n".encode(),
        arquivo.read_bytes(),
        f"\r\n--{limite}\r\n".encode(),
        b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n',
        f"--{limite}--\r\n".encode(),
    ])
    req = urllib.request.Request(f"{comfy}/upload/image", data=corpo, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={limite}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    nome = d.get("name") or arquivo.name
    sub = d.get("subfolder") or ""
    return f"{sub}/{nome}" if sub else nome


def enfileira(wf, comfy=COMFY_PADRAO):
    corpo = json.dumps({"prompt": wf, "client_id": "detto-painel"}).encode()
    req = urllib.request.Request(f"{comfy}/prompt", data=corpo, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8", "replace")).get("prompt_id", ""), ""
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")[:900]
        return "", _explica(detalhe)


def _explica(bruto):
    """o erro do ComfyUI vem como uma parede de JSON; aqui vira uma frase que dá para agir"""
    try:
        d = json.loads(bruto)
    except ValueError:
        return bruto[:300]
    partes = []
    for no, err in (d.get("node_errors") or {}).items():
        for e in err.get("errors", []):
            partes.append(f"nó {no}: {e.get('details') or e.get('message')}")
    if not partes:
        partes.append((d.get("error") or {}).get("message", "") or bruto[:200])
    return " | ".join(partes)[:400]


def resultado(pid, comfy=COMFY_PADRAO):
    """(terminou?, arquivos, erro)"""
    try:
        h = _pega(f"{comfy}/history/{pid}", 20)
    except Exception:
        return False, [], ""
    item = h.get(pid)
    if not item:
        return False, [], ""
    st = item.get("status") or {}
    arqs = []
    for saida in (item.get("outputs") or {}).values():
        for lista in saida.values():
            if isinstance(lista, list):
                for a in lista:
                    if isinstance(a, dict) and a.get("filename"):
                        arqs.append(f"{comfy}/view?filename={a['filename']}"
                                    f"&subfolder={a.get('subfolder', '')}&type={a.get('type', 'output')}")
    if st.get("status_str") == "success" or arqs:
        return True, arqs, ""
    if st.get("completed") or st.get("status_str") == "error":
        msgs = st.get("messages") or []
        return True, [], json.dumps(msgs[-2:], ensure_ascii=False)[:400]
    return False, [], ""


def baixa(url, destino):
    with urllib.request.urlopen(url, timeout=300) as r:
        Path(destino).write_bytes(r.read())
    return destino


# ------------------------------------------------------------------ montar o pedido
def _wf(nome, trocas):
    t = (WORKFLOWS / nome).read_text(encoding="utf-8-sig")   # utf-8-sig: arquivo salvo no Windows pode ter BOM
    for k, v in trocas.items():
        t = t.replace(k, str(v))
    return json.loads(t)


def pedido_texto(prompt, frames, mods):
    return _wf("texto_para_video.json", {
        '"__SEED__"': random.randint(1, 2_000_000_000),
        "__PROMPT__": prompt.replace('"', "").replace("\\", "/"),
        "__NEGATIVE_PROMPT__": NEGATIVO,
        "__LTXV_CKPT__": mods["ckpt"], "__LTXV_T5__": mods["t5"],
        '"length": 49': f'"length": {int(frames)}',
    })


def pedido_imagem(nome_no_comfy, movimento, frames, mods):
    return _wf("imagem_para_video.json", {
        '"__SEED__"': random.randint(1, 2_000_000_000),
        "__PROMPT__": movimento.replace('"', "").replace("\\", "/"),
        "__NEGATIVE_PROMPT__": NEGATIVO,
        "__IMAGEM__": nome_no_comfy,
        "__LTXV_CKPT__": mods["ckpt"], "__LTXV_T5__": mods["t5"],
        '"length": 49': f'"length": {int(frames)}',
    })


def prepara_foto(origem, destino, larg=480, alt=832):
    """a foto em 9:16 com o fundo dela mesma desfocado — esticar o produto deformaria a embalagem.

    `split=2` é obrigatório: a mesma entrada vai para o fundo e para o produto por cima.
    """
    fc = (f"[0:v]split=2[a][b];"
          f"[a]scale={larg}:{alt}:force_original_aspect_ratio=increase,crop={larg}:{alt},boxblur=24[bg];"
          f"[b]scale={larg}:{alt}:force_original_aspect_ratio=decrease[fg];"
          f"[bg][fg]overlay=(W-w)/2:(H-h)/2")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(origem), "-filter_complex", fc,
                        "-frames:v", "1", str(destino)], capture_output=True, text=True, timeout=300)
    if not Path(destino).exists():
        raise RuntimeError(f"não consegui preparar {Path(origem).name}: {(r.stderr or '')[-200:]}")
    return destino


# ------------------------------------------------------------------ a rodada
def roda(pedidos, saida, comfy=COMFY_PADRAO, log=log, prefixo="clipe"):
    """manda TODOS de uma vez e vai baixando conforme ficam prontos"""
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    fila = []
    for nome, wf in pedidos:
        pid, erro = enfileira(wf, comfy)
        if not pid:
            log(f"   RECUSADO ({nome}): {erro}")
            continue
        fila.append((pid, nome))
        log(f"   na fila: {nome}")
    if not fila:
        return []
    log(f"\nRenderizando {len(fila)}. O primeiro carrega os modelos (~3 min); os outros ~1,5 min.")
    feitos, t0 = [], time.time()
    for i, (pid, nome) in enumerate(fila, 1):
        while True:
            time.sleep(5)
            pronto, arqs, erro = resultado(pid, comfy)
            if not pronto:
                if time.time() - t0 > 3 * 3600:
                    log("passei de 3 h esperando; parei.")
                    return feitos
                continue
            if erro and not arqs:
                log(f"   FALHOU ({nome}): {erro}")
                break
            for a in arqs:
                limpo = re.sub(r"[^\w\-]", "_", Path(nome).stem)[:40]
                destino = saida / f"{prefixo}_{i:02d}_{limpo}.mp4"
                try:
                    baixa(a, destino)
                    feitos.append(destino)
                    log(f"   PRONTO -> {destino.name}")
                except Exception as e:
                    log(f"   gerou mas não copiei ({str(e)[:90]})")
            break
    log(f"\n{len(feitos)} clipe(s) em {(time.time() - t0) / 60:.1f} min. Pasta: {saida}")
    return feitos
