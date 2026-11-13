# SOCORRO — o que fazer quando alguma coisa para

Imprima ou deixe aberto. Tudo aqui se resolve **sem mim**. Comandos no PowerShell, a partir de `C:\Users\guebe\Teste1`.

---

## Os 5 comandos que resolvem quase tudo

| Quando | Comando |
|---|---|
| **Algo parou e não sei por quê** | `cd detto-premiere-bridge ; python tools\doutor.py` → abre `tools\diagnostico.txt` |
| **Quero atualizar** (volta sozinho se vier quebrado) | `.\detto-premiere-bridge\ATUALIZAR.ps1` |
| **Atualizei e piorou** | `.\detto-premiere-bridge\VOLTAR.ps1` |
| **Guardar configurações e logins** (faça 1x por semana) | `.\detto-premiere-bridge\BACKUP.ps1` |
| **Perdi configuração/login** | `.\detto-premiere-bridge\RESTAURAR.ps1` |

O backup guarda o que **não dá para refazer**: config de cada canal, estado das contas, histórico, tokens de
login (Instagram, TikTok, YouTube) e a versão do código. Vídeo não entra — isso se refaz.

---

## Sintoma → causa → o que fazer

**"Canal rodou e não criou vídeo"**
1. O card do canal mostra *Máscara* e *Voz de referência*? Se disser "nenhuma gravação" ou "falta", é isso:
   suba no Drive em `Meu Drive\DETTO\canal_noticias\mascara` (5 vídeos seus de 5–10 s, o nome diz o clima) e
   `...\voz` (20–30 s da sua voz). A rodada seguinte copia sozinha.
2. VoiceStudio aberto? Sem ele e sem a chave do Fish válida, a rodada para e diz isso no registro.
3. Registro do canal: `E:\DETTO\canal_galo\canal.log` (ou `canal_gta6`).

**"Rodada começou e terminou na hora, sem fazer nada"**
Outra rodada está com a trava. O painel mostra o aviso e o botão **Encerrar a rodada**. Se durar horas, quase
sempre é a voz moendo no Chatterbox — abra o VoiceStudio.

**"Colei um link no reels e sumiu, não virou nada"**
O link que falha **sai da lista** com o motivo. Veja **⚠ Links que NÃO viraram reels** na aba Reels automáticos.
Se disser "não achei a pessoa e o lance", troque o seletor para **modo novo** e clique em Fazer.

**"Instagram não posta, só vai para o Drive"**
Vagas de Reels teste da API acabaram (72 h cada). O painel mostra "🧪 Reels teste ativos". Botões:
**↻ Testar a API de novo** e, na lista do Drive, **✔ Postei** quando você postar pelo celular.

**"As views não aparecem"**
Falta a permissão de estatísticas: painel → Configurações → refazer o login do Instagram.

**"O painel está estranho / a tela não bate com o programa"**
Botão **Reiniciar o painel**. Se não aparecer, feche a janela preta do painel e rode o `ATUALIZAR.ps1`.

**"Mediapipe deu erro" (gestos do Galo, recorte, thumb)**
`python -m pip install --upgrade mediapipe` (nunca rebaixe o protobuf).

**"Sem espaço em disco"**
Apague `E:\DETTO\*\tmp`, `galo_tmp` e os `prontos` antigos. O doutor mostra quanto resta.

---

## Onde fica cada coisa

| O quê | Onde |
|---|---|
| Código | `C:\Users\guebe\Teste1\detto-premiere-bridge` |
| Mídia, configs e filas | `E:\DETTO\...` (postar, reels, edicao, canal_galo, canal_gta6, historias, shop) |
| Backups | `E:\DETTO\backups\<data-hora>` |
| Registro de cada parte | veja a tabela do `MAPA.md` |

## O que só você pode fazer (eu não alcanço o seu PC)

**Passo a passo completo disso: `VOZ-E-GESTO.md`** (como gravar a voz, as máscaras e a foto da thumb).

- Gravar e subir **máscara** e **voz** no Drive.
- Deixar o **VoiceStudio** aberto com a sua voz clonada.
- Refazer o **login do Instagram** com a permissão de estatísticas.
- Manter as **chaves** nas variáveis do Windows (`setx NOME "chave"`) — **nunca cole chave no chat**.
