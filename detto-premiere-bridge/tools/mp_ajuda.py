"""Traduz a bagunça que o MediaPipe cospe quando ele está velho demais para o protobuf instalado.

O erro de verdade some no meio de 40 linhas de grafo:

    AttributeError: 'MessageFactory' object has no attribute 'GetPrototype'
    TypeError: create(): incompatible function arguments... Invoked with: node { calculator: ... }

É sempre a mesma coisa: `MessageFactory.GetPrototype` saiu do protobuf novo, e o mediapipe antigo ainda
chamava. Quem resolve é ATUALIZAR O MEDIAPIPE (o 0.10.30+ usa `GetMessageClass` e nem depende mais do
protobuf) — não mexa no protobuf, que o Gemini e outras bibliotecas usam.
"""

import sys

MARCAS = ("getprototype", "incompatible function arguments", "messagefactory",
          "calculatorgraphconfig", "taskrunner")


def versoes():
    try:
        import mediapipe as mp
        v_mp = getattr(mp, "__version__", "?")
    except Exception:
        v_mp = "(não instalado)"
    try:
        import google.protobuf as pb
        v_pb = getattr(pb, "__version__", "?")
    except Exception:
        v_pb = "(não instalado)"
    return v_mp, v_pb


def e_velho(e):
    """este erro é a incompatibilidade mediapipe x protobuf?"""
    t = str(e).lower()
    return any(m in t for m in MARCAS)


def comando():
    exe = sys.executable or "python"
    return f'"{exe}" -m pip install --upgrade mediapipe'


def dica(e=None):
    """o que escrever na tela quando o MediaPipe não abre"""
    v_mp, v_pb = versoes()
    if e is not None and not e_velho(e):
        return ""
    return ("o MediaPipe instalado é VELHO demais para o protobuf desta máquina "
            f"(mediapipe {v_mp}, protobuf {v_pb}).\n"
            f"   RESOLVE ASSIM, uma vez só:  {comando()}\n"
            "   (não mexa no protobuf: o Gemini e outras bibliotecas usam a versão nova.)")
