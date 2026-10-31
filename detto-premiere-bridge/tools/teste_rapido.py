# -*- coding: utf-8 -*-
"""TESTE RÁPIDO — roda em segundos e diz se o código está SÃO antes de você usar.

    python tools\\teste_rapido.py

Dois exames:
 1. IMPORTA cada arquivo .py das ferramentas. Pega erro de sintaxe, nome que não existe (o `caminho` do painel),
    `import` errado — o tipo de coisa que derruba TUDO em silêncio. Biblioteca de fora que falta (cv2, mediapipe,
    faster_whisper...) conta como "pulado", não como erro.
 2. CONTRATO: confere que cada função que um arquivo chama DE OUTRO continua existindo lá (é o que quebra quando
    renomeio algo num canto e esqueço o resto — foi o que aconteceu com `voicestudio_ligado`).

Saída: "TUDO SÃO" (código 0) ou a lista de problemas (código 1). O ATUALIZAR.ps1 roda isto depois do git pull e
VOLTA para a última versão boa se falhar; o GitHub Actions roda a cada push.
"""
import ast
import importlib.util
import sys
import traceback
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PONTE = AQUI.parent

# bibliotecas de fora: faltando, o arquivo é PULADO (no PC dele existem; no GitHub Actions, não)
DE_FORA = {"cv2", "numpy", "mediapipe", "faster_whisper", "PIL", "rembg", "google", "curl_cffi", "requests",
           "yt_dlp", "scipy", "soundfile", "librosa", "torch", "torchaudio", "chatterbox", "pydub", "msvcrt",
           "win32com", "winreg", "pytesseract", "easyocr", "onnxruntime", "matplotlib", "playwright"}

# o que cada arquivo PRECISA ter porque outros chamam (nome -> arquivo)
CONTRATO = {
    "tools/canal/voz.py": ["voicestudio_url", "voicestudio_ligado", "voicestudio_pronto", "voicestudio_vozes",
                           "voicestudio_escolhe", "voicestudio_fala", "pronuncia", "sem_pausas",
                           "INSTRUCAO_PADRAO"],
    "tools/canal/vinheta.py": ["abre", "emenda", "duracao", "formato"],
    "tools/postar/postar.py": ["pasta_padrao", "le_estado", "grava_json", "muda_estado", "fila_de", "ig_e_teste",
                               "testes_ativos", "vaga_de_teste", "sem_vaga_de_teste", "vai_para_celular",
                               "cai_para_normal", "manda_para_celular", "posta_da_fila", "pasta_celular",
                               "legenda_de", "TESTE_JANELA_H", "planeja", "enfileira", "rodada", "proximo",
                               "ig_views", "ig_limite", "studio", "prepara", "postados_hoje", "chave",
                               "agendados_por_dia", "marca_agendado", "tt_pendentes", "CONFIG_PADRAO"],
    "tools/reels/reels.py": ["baixa", "gemini_json", "trava_rodada", "pasta_padrao", "cortes_pontas"],
    "tools/roteiro_ia.py": ["gemini", "texto_gratis", "claude_cli"],
    "tools/historias/historias.py": ["encaixa_cenas"],
    "tools/galo/notas.py": ["do_banco", "do_fotmob", "grava"],
    "tools/galo/passagem.py": ["dados_do_jogo", "escudos", "conferir", "foto_jogador"],
    "tools/shop/shop.py": ["faz_video", "produto_de_link", "produto_da_pasta", "fotos_da_internet",
                           "link_de_video", "palavras", "encaixa", "blocos_legenda"],
    "tools/ffcompat.py": ["filtro_complexo", "filtro_v"],
    "tools/busca_imagem.py": ["buscar"],
    "tools/mp_ajuda.py": ["dica", "comando"],
    "tools/painel/painel.py": ["PAINEL_VERSAO", "estado_painel", "reels_rodando", "log_reels"],
    "tools/painel/edicao.py": ["lista", "novo", "recebe", "iniciar", "cancelar", "refazer", "apagar", "roteiro",
                               "saidas", "arquivo", "laco", "de_caminho", "motivo_do_erro", "pasta_padrao"],
    "tools/painel/canais.py": ["estado", "acao", "laco", "ocupado"],
    "tools/painel/historias_painel.py": ["estado", "acao", "arquivo", "laco", "anota"],
    "tools/painel/shop_painel.py": ["estado", "acao", "arquivo"],
}


def nomes_do_arquivo(f):
    """os nomes que o arquivo define no topo (def, class, x = ...), sem precisar importar nada"""
    try:
        arvore = ast.parse(Path(f).read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as e:
        return None, str(e)
    out = set()
    for no in arvore.body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(no.name)
        elif isinstance(no, ast.Assign):
            out.update(a.id for a in no.targets if isinstance(a, ast.Name))
        elif isinstance(no, (ast.Import, ast.ImportFrom)):
            out.update((a.asname or a.name).split(".")[0] for a in no.names)
    return out, ""


def confere_contrato():
    problemas = []
    for rel, precisa in CONTRATO.items():
        f = PONTE / rel
        if not f.exists():
            problemas.append(f"{rel}: ARQUIVO SUMIU (outros arquivos dependem dele)")
            continue
        tem, erro = nomes_do_arquivo(f)
        if tem is None:
            problemas.append(f"{rel}: não deu para ler ({erro[:120]})")
            continue
        faltam = [n for n in precisa if n not in tem]
        if faltam:
            problemas.append(f"{rel}: faltam {', '.join(faltam)} — quem chamava isso vai quebrar")
    return problemas


def importa_tudo():
    problemas, ok, pulados = [], 0, 0
    pastas = [PONTE / "tools"]
    arquivos = sorted(f for p in pastas for f in p.rglob("*.py")
                      if "__pycache__" not in f.parts and f.name != "teste_rapido.py")
    # cada pasta de ferramenta entra no caminho, porque os arquivos se importam pelo nome curto
    for d in {f.parent for f in arquivos} | {PONTE / "tools"}:
        sys.path.insert(0, str(d))
    for f in arquivos:
        nome = f"_t_{f.stem}_{abs(hash(str(f))) % 10000}"
        try:
            spec = importlib.util.spec_from_file_location(nome, f)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[nome] = mod
            spec.loader.exec_module(mod)
            ok += 1
        except ModuleNotFoundError as e:
            if (e.name or "").split(".")[0] in DE_FORA:
                pulados += 1
            else:
                problemas.append(f"{f.relative_to(PONTE)}: import que não existe — {e}")
        except SystemExit:
            ok += 1   # arquivo que sai sozinho ao ser lido (argparse) não é erro
        except Exception as e:  # noqa: BLE001
            linha = ""
            for q in traceback.extract_tb(e.__traceback__):
                if str(f) in q.filename:
                    linha = f" (linha {q.lineno}: {q.line})"
            problemas.append(f"{f.relative_to(PONTE)}: {type(e).__name__}: {str(e)[:150]}{linha}")
    return problemas, ok, pulados


def main():
    print("TESTE RÁPIDO DETTO")
    p1, ok, pulados = importa_tudo()
    print(f"  importei {ok} arquivo(s), pulei {pulados} por biblioteca de fora que falta neste computador")
    p2 = confere_contrato()
    print(f"  contrato entre os arquivos: {len(CONTRATO)} arquivo(s) conferido(s)")
    todos = p1 + p2
    if not todos:
        print("\nTUDO SÃO ✔")
        return 0
    print(f"\n{len(todos)} PROBLEMA(S) — o código está quebrado:")
    for x in todos:
        print(f"  - {x}")
    print("\nNÃO use esta versão: rode o VOLTAR.ps1 (volta para a última versão boa) e me mande esta lista.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
