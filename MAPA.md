# MAPA DO DETTO — onde fica cada coisa

Para a nossa conversa: diga o **nome da área** (ex.: "mexe só nos REELS") que eu mexo apenas ali.
Detalhe técnico de cada área está no `CLAUDE.md`; aqui é o mapa, curto.

Tudo roda da pasta `detto-premiere-bridge`. Mídia e configurações ficam em `E:\DETTO\...` (não entram no git).

---

## Se algo parou de funcionar — nesta ordem

| Passo | Comando | O que faz |
|---|---|---|
| 1 | `python tools\doutor.py` | diz **por que** parou: IA, voz, travas, Instagram, disco e o último erro de cada registro → `tools\diagnostico.txt` (cole aqui) |
| 2 | `.\detto-premiere-bridge\VOLTAR.ps1` | devolve o código para a última versão que passou no teste (sua mídia não é tocada) |
| 3 | `python tools\teste_rapido.py` | diz se o código está são (importa tudo + confere o contrato entre os arquivos) |
| 4 | `.\detto-premiere-bridge\ATUALIZAR.ps1` | baixa o código novo, roda o teste e **volta sozinho** se vier quebrado |

O painel em memória é o programa **velho** até reiniciar: depois de atualizar, use o botão **Reiniciar o painel**.

---

## As áreas

| Área | O que é | Onde mexer | Registro (o que ler quando falha) |
|---|---|---|---|
| **PAINEL** | a tela em `localhost:8730`, as abas e as rodadas automáticas | `tools\painel\painel.py` + `painel.html` (**suba as duas versões juntas**) | `E:\DETTO\postar\painel.log` |
| **POSTAGEM** | fila, horários, Instagram/TikTok/YouTube/Kwai, Reels teste, pasta do Drive | `tools\postar\postar.py` | `E:\DETTO\postar\postar.log` |
| **REELS** | meme = seu começo + viral; links, modo TROCA, importação do Drive | `tools\reels\reels.py` | `E:\DETTO\reels\painel_reels.log`, `links_falhos.txt` |
| **EDIÇÃO COM ROTEIRO** | você grava lendo o roteiro → horizontal + verticais | `tools\editar.py`, `tools\roteiro\*`, `tools\motion\*` | `<job>\painel_log.txt`, `<job>\conferencia.txt` |
| **HISTÓRIAS** | reels em série, o público escolhe A/B | `tools\historias\historias.py` + `palco\` | `E:\DETTO\historias\painel_historias.log` |
| **CANAL NOTÍCIAS** | vídeo do Galo pela imprensa, voz clonada, máscara | `tools\canal\canal.py` | `E:\DETTO\canal_galo\canal.log` |
| **CANAL GTA 6** | notícias e gameplay comentada de GTA 6 (o mesmo canal.py, preset `gta6`) | `tools\canal\canal.py` (`PRESETS`) | `E:\DETTO\canal_gta6\canal.log` |
| **CANAL VLOGS/GAMEPLAY** | vlog montado da pasta do Drive | `tools\canal\canal_vlog.py`, `tools\vlog\vlog.py` | `E:\DETTO\canal_vlogs\canal.log` |
| **TIKTOK SHOP** | produto → reels de venda | `tools\shop\shop.py` + `cartelas.js` | `E:\DETTO\shop\shop.log`, `produtos_falhos.txt` |
| **GALO (estádio)** | elenco passando pela sua mão, notas do jogo | `tools\galo\passagem.py`, `notas.py` | sai na tela + `<saida>_conferir.jpg` |
| **REACT** | DETTO REAGE (câmera + tela + original) | `tools\react\react.py` | sai na tela |
| **VOZ** | VoiceStudio → Fish → Chatterbox, pronúncia, sem pausas | `tools\canal\voz.py` | o registro de quem chamou |
| **IA DE TEXTO** | Gemini → IAs grátis → Claude da assinatura | `tools\roteiro_ia.py` | o registro de quem chamou |
| **IMAGENS** | banco de jogadores/escudos e busca na internet | `tools\jogadores.py`, `tools\busca_imagem.py`, `tools\banco\` | `<job>\imagens_conferir.jpg` |
| **COR** | HDR do iPhone → SDR (master antes de editar) | `tools\sdr.py`, `tools\cor.py`, `tools\cor_lut.py` | sai na tela |
| **MARCA** | vinheta de abertura, banner/perfil dos canais, thumbs | `tools\canal\vinheta.py`, `marca.py`, `tools\thumb\` | sai na tela |

## Quem depende de quem (o que para junto)

- **IA de texto caiu** → param: reels (escolha do começo e o texto), histórias (o episódio), notícias (as falas), shop (o roteiro).
- **Voz caiu** (VoiceStudio fechado/sem voz cadastrada e sem `FISH_API_KEY`) → param: notícias, histórias, shop.
- **Trava presa** (`.reels_rodando`, `.shop_rodando`, `.canal_rodando`, `.postando`) → aquela parte não roda mais; o `doutor.py` mostra.
- **Um trabalho pesado por vez**: edição, canais e histórias esperam uns aos outros de propósito (o PC não aguenta dois).
- **Disco cheio** (menos de ~8 GB) → render e voz falham no meio. Apague `tmp`/`galo_tmp` e os `prontos` antigos.

## Chaves (variáveis do Windows, `setx NOME "chave"`) — nunca cole chave no chat

`GEMINI_API_KEY` (a principal) · `CEREBRAS_API_KEY`, `GROQ_API_KEY`, `MISTRAL_API_KEY`, `OPENROUTER_API_KEY` (IAs grátis)
· `FISH_API_KEY` (voz, reserva) · `PEXELS_API_KEY`, `PIXABAY_API_KEY` (apoio do vlog).

## Antes de eu dizer "pronto"

`npm run check` (testes e teste visual) · `python tools\teste_rapido.py` · sintaxe no Python 3.11 ·
e, quando mexo no painel, as duas versões juntas.
