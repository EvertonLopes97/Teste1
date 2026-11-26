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
# no LOGIN pede também o de comentar (force-ssl); o token antigo continua valendo para postar
ESCOPOS_LOGIN = ESCOPOS + ["https://www.googleapis.com/auth/youtube.force-ssl"]


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
    if cred and abrir_navegador and token.exists() and ESCOPOS_LOGIN[-1] not in token.read_text(encoding="utf-8"):
        cred = None  # login de novo pedido no painel: o token antigo não tem a permissão de comentar → pede de novo
    if not cred or not cred.valid:
        if not abrir_navegador:
            raise SystemExit("YouTube sem login: rode  python tools\\canal\\canal.py --login  (uma vez).")
        segredo = segredo_de(pasta)
        if not segredo:
            raise SystemExit(f"Falta o client_secret.json (credencial 'App para computador' do Google Cloud) em {pasta} "
                             f"ou em {pasta.parent / 'youtube'} — veja o LEIA-ME.txt.")
        cred = InstalledAppFlow.from_client_secrets_file(str(segredo), ESCOPOS_LOGIN).run_local_server(port=0, prompt="consent")
    token.write_text(cred.to_json(), encoding="utf-8")
    return cred


def segredo_de(pasta):
    """a credencial do Google Cloud: na pasta do canal ou a compartilhada (E:\\DETTO\\youtube) — vale para os dois canais"""
    for f in (Path(pasta) / "client_secret.json", Path(pasta).parent / "youtube" / "client_secret.json"):
        if f.exists():
            return f
    return None


def tem_login(pasta):
    return (Path(pasta) / "token.json").exists()


def canal_logado(pasta):
    from googleapiclient.discovery import build

    yt = build("youtube", "v3", credentials=credenciais(pasta), cache_discovery=False)
    r = yt.channels().list(part="snippet", mine=True).execute()
    it = (r.get("items") or [{}])[0]
    return it.get("snippet", {}).get("title", "?"), it.get("id", "?")


def posta(pasta, video, titulo, descricao, tags, thumb=None, privacidade="public", publicar_em=None, sintetico=True, log=print, categoria="17"):
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
    corpo = {"snippet": {"title": titulo[:100], "description": descricao[:4900], "tags": tags[:30], "categoryId": categoria,
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


def comenta(pasta, video_id, texto):
    """comentário do próprio canal no vídeo (os créditos). Fixar o comentário a API não faz — é no YouTube Studio."""
    from googleapiclient.discovery import build

    yt = build("youtube", "v3", credentials=credenciais(pasta), cache_discovery=False)
    r = yt.commentThreads().insert(part="snippet", body={"snippet": {"videoId": video_id, "topLevelComment": {
        "snippet": {"textOriginal": texto[:9500]}}}}).execute()
    return r.get("id")


# o que o YouTube responde em `status.rejectionReason`, em português e com o que fazer
MOTIVOS = {
    "copyright": "RECLAMAÇÃO DE DIREITO AUTORAL — o dono das imagens reclamou do trecho de imprensa",
    "claim": "RECLAMAÇÃO DE DIREITO AUTORAL (Content ID) no trecho de imprensa",
    "duplicate": "VÍDEO DUPLICADO — este mesmo vídeo já estava no canal",
    "trademark": "marca registrada",
    "inappropriate": "conteúdo considerado impróprio",
    "legal": "motivo legal",
    "length": "vídeo longo demais para a conta",
    "uploaderAccountSuspended": "a conta do canal está suspensa",
    "uploaderAccountClosed": "a conta do canal foi encerrada",
    "termsOfUse": "termos de uso",
}


def situacao(pasta, video_id):
    """COMO ESTÁ O VÍDEO DEPOIS DE POSTADO — é a resposta para "foi bloqueado e eu não sabia" (05/nov).

    Devolve {'estado', 'motivo', 'privacidade', 'bloqueado', 'embutivel', 'paises_bloqueados'}.
    `status.rejectionReason` é o campo que diz se foi direito autoral ou vídeo DUPLICADO — os dois casos que
    aconteceram com ele no mesmo dia. `contentDetails.regionRestriction.blocked` diz em que países caiu
    quando é uma reclamação parcial (o vídeo fica no ar, mas não no Brasil, o que dá no mesmo)."""
    from googleapiclient.discovery import build

    yt = build("youtube", "v3", credentials=credenciais(pasta), cache_discovery=False)
    r = yt.videos().list(part="status,contentDetails,processingDetails", id=video_id).execute()
    itens = r.get("items") or []
    if not itens:
        # vídeo que some da listagem foi APAGADO ou derrubado pelo YouTube
        return {"estado": "sumiu", "motivo": "o vídeo não existe mais no canal (apagado ou derrubado)",
                "bloqueado": True, "privacidade": "", "paises_bloqueados": []}
    st = (itens[0].get("status") or {})
    cd = (itens[0].get("contentDetails") or {})
    bloq = ((cd.get("regionRestriction") or {}).get("blocked") or [])
    razao = st.get("rejectionReason") or ""
    estado = st.get("uploadStatus") or ""
    motivo = MOTIVOS.get(razao, razao)
    # o vídeo pode estar "processed" e mesmo assim bloqueado no Brasil por reclamação parcial
    if not motivo and "BR" in bloq:
        motivo = "BLOQUEADO NO BRASIL por reclamação de direito autoral (o vídeo está no ar em outros países)"
    return {"estado": estado, "motivo": motivo, "privacidade": st.get("privacyStatus") or "",
            "embutivel": st.get("embeddable"), "paises_bloqueados": bloq,
            "bloqueado": bool(razao) or estado in ("rejected", "failed") or "BR" in bloq}
