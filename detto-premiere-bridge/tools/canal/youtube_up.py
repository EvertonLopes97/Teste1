# -*- coding: utf-8 -*-
"""Postagem AUTOMÁTICA no YouTube pela API oficial (YouTube Data API v3).

Uma vez só (veja o LEIA-ME.txt): criar o projeto no Google Cloud, ligar a "YouTube Data API v3", criar a credencial
"App para computador" e salvar como  <pasta do canal>\\client_secret.json. Depois:
    python tools\\canal\\canal.py --login        (abre o navegador: escolha o CANAL NOVO e clique em Permitir)
O token fica em <pasta do canal>\\token.json e renova sozinho — a partir daí posta sem você.
"""
import subprocess
import sys
import time
from pathlib import Path

ESCOPOS = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]


def _libs():
    try:
        import google_auth_oauthlib  # noqa: F401
        import googleapiclient  # noqa: F401
    except ImportError:
        print("youtube: instalando as bibliotecas do Google (uma vez só)...", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "google-api-python-client", "google-auth-oauthlib"], check=False)


def credenciais(pasta, abrir_navegador=False):
    _libs()
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    pasta = Path(pasta)
    token = pasta / "token.json"
    cred = Credentials.from_authorized_user_file(str(token), ESCOPOS) if token.exists() else None
    if cred and cred.expired and cred.refresh_token:
        try:
            cred.refresh(Request())
        except Exception:
            cred = None
    if not cred or not cred.valid:
        if not abrir_navegador:
            raise SystemExit("YouTube sem login: rode  python tools\\canal\\canal.py --login  (uma vez).")
        segredo = pasta / "client_secret.json"
        if not segredo.exists():
            raise SystemExit(f"Falta o {segredo} (credencial 'App para computador' do Google Cloud — veja o LEIA-ME.txt).")
        cred = InstalledAppFlow.from_client_secrets_file(str(segredo), ESCOPOS).run_local_server(port=0, prompt="consent")
    token.write_text(cred.to_json(), encoding="utf-8")
    return cred


def canal_logado(pasta):
    from googleapiclient.discovery import build

    yt = build("youtube", "v3", credentials=credenciais(pasta), cache_discovery=False)
    r = yt.channels().list(part="snippet", mine=True).execute()
    it = (r.get("items") or [{}])[0]
    return it.get("snippet", {}).get("title", "?"), it.get("id", "?")


def posta(pasta, video, titulo, descricao, tags, thumb=None, privacidade="public", publicar_em=None, sintetico=True, log=print):
    """sobe o vídeo; devolve o id. publicar_em = ISO 8601 (ex.: 2026-10-16T18:00:00-03:00) agenda a estreia."""
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    yt = build("youtube", "v3", credentials=credenciais(pasta), cache_discovery=False)
    status = {"privacyStatus": "private" if publicar_em else privacidade, "selfDeclaredMadeForKids": False,
              # narração com voz gerada por IA: o YouTube pede essa marcação ("conteúdo alterado ou sintético")
              "containsSyntheticMedia": bool(sintetico)}
    if publicar_em:
        status["publishAt"] = publicar_em
    corpo = {"snippet": {"title": titulo[:100], "description": descricao[:4900], "tags": tags[:30], "categoryId": "17",
                         "defaultLanguage": "pt-BR", "defaultAudioLanguage": "pt-BR"}, "status": status}
    media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=corpo, media_body=media)
    resp, falhas = None, 0
    while resp is None:
        try:
            st, resp = req.next_chunk()
            if st:
                log(f"   enviando {int(st.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and falhas < 5:
                falhas += 1
                time.sleep(5 * falhas)
                continue
            raise
    vid = resp["id"]
    if thumb and Path(thumb).exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb), mimetype="image/jpeg")).execute()
        except HttpError as e:
            log(f"   thumb não subiu ({e.resp.status}): o canal precisa estar VERIFICADO (telefone) para thumb personalizada")
    return vid
