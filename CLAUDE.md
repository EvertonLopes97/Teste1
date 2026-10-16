# DETTO — editor de vídeos do @detto.galo

Você é o editor/programador deste projeto. O dono é o Everton (fala português; responda em português,
curto e direto). Máquina: Dell G15 (Windows 11, Ryzen 5 6600H, 16 GB, RTX 3050 4 GB), Premiere Pro 2022,
After Effects 2020. Disco com pouco espaço livre: apague pastas `tmp`/`galo_tmp` depois de cada render.

Código em `detto-premiere-bridge/`. Rode os comandos a partir dessa pasta.

## Jeito mais barato (sem gastar o Claude)

`python tools\editar.py "<video>"` faz tudo sozinho: transcrição (faster-whisper, local), rosto, roteiro
pelo Gemini (`GEMINI_API_KEY`, quase de graça), plano, horizontal e verticais. `--teste` = só 1 minuto.
Use o Claude só para AJUSTAR o `roteiro.txt` do job e rodar de novo.
- Saídas: `horizontal.mp4` (YouTube), `vertical_completo.mp4` (o vídeo inteiro em 9:16, gráficos refeitos
  para o vertical) e `vertical_N.mp4` (um short por tema, com o gancho).
- Vídeo JÁ editado em 16:9 (sem o plano): `python tools\vertical916.py edicao.mp4 [saida.mp4] [--partes 60]`
  → 9:16 com recorte no rosto (fundo desfocado); gráfico/foto grande com você pequeno no canto (`--grafico pip`, padrão), só o gráfico (`tela`) ou metade/metade (`dividido`).
- Câmera estática por padrão (zoom sempre no mesmo ponto). `--seguir-rosto 1` no render-dynamic volta a seguir.
- "COMENTA AÍ / SEGUIR" nunca fica no rosto (vai abaixo do queixo ou acima da cabeça).
- Voz tratada por padrão (RNNoise, EQ, de-esser, compressor) e nivelada sozinha (-16 LUFS); efeitos sonoros
  bem abaixo e abaixam enquanto ele fala (sidechain); final -14 LUFS. `--voz 0` desliga o tratamento;
  `--sfx 0.3` = volume dos efeitos (padrão 0.3; ele achou alto o antigo 0.55). Cada efeito é nivelado pelo
  volume percebido (todos na MESMA altura, ~12 dB abaixo da voz).
- Cortes 9:16 (`vertical_N`): gancho escrito na tela nos 3 primeiros segundos; componentes refeitos para o vertical.
- Horizontal sai em 60 fps (YouTube; `--fps 30` volta); verticais em 30. 60 fps = render ~2x mais demorado e mais disco.
- Música de fundo DEPOIS dos cortes dele: `python tools\trilha.py "final.mp4" "0:00=trap.mp3" "5:14=suspense.mp3"`
  → imagem copiada (sem re-render), música em loop com fade/cruzamento, -27 LUFS (`--vol`), abaixa ~8 dB quando ele
  fala (`--abaixa`), final -14 LUFS → "<video> com trilha.mp4". Música: Biblioteca de áudio do YouTube, sem atribuição.
- Efeitos sonoros: os da pasta do Everton. Catalogar uma vez:
  `python tools\biblioteca_sons.py "E:\edição\efeitos de video\PACK DE EDIÇÃO 2.0"` → `sons.json`.
  Categoria sem arquivo usa Mixkit (soco, tapa, chicote, whoosh) ou o sintetizado.

## Lances, thumbs, reels automáticos e testes

- LANCES (versão com e sem; ele escolhe qual posta): `editar.py` roda `tools\lances.py <job>\EDIT_PLAN.json` quando há
  `[LANCE+VO]` ou `LANCE:` → acha o jogo, busca os melhores momentos no YouTube (yt-dlp; título com os 2 times, placar,
  sem live/react), baixa em 720p em `<job>\lances\`, acha cada lance pela NARRAÇÃO (legenda do YouTube ou faster-whisper):
  nome do jogador que ele cita + grito de gol. Entra na hora em que ele fala o nome; sem vídeo → foto do lance.
  Saídas extras `horizontal_lances.mp4`, `vertical_completo_lances.mp4`, `vertical_N_lances.mp4` (render-dynamic
  `--lances lances.json --base <sem lances>` refaz só os trechos de lance e emenda; áudio igual). Conferir:
  `<job>\lances_conferir.jpg`; corrigir `ini`/`fim` no `lances.json`. Roteiro: `LANCE: <link ou arquivo> 1:23-1:31`,
  `LANCE: sem`. YouTube pedindo login: `--cookies firefox` (ou chrome/edge). `--sem-lances` desliga.
- THUMBS: `python tools\thumb\thumb.py "<job ou vídeo>" [--texto "X" --destaque PALAVRA --jogador Nome --fundo-ia]`
  (roda no fim do editar.py) → `<job>\thumbs\thumb_1..4.jpg` + `thumbs.jpg`: melhores reações (MediaPipe Face
  Landmarker, blendshapes), recorte com contorno, texto Anton, jogador do jogadores.json, seta/círculo.
- REELS AUTOMÁTICOS (meme: começo dele + viral): `python tools\reels\reels.py [--quantos 10] [--agendar 07:00]`, pasta
  `E:\DETTO\reels` (`inicios\` = começos dele, nome = o que ele faz; `links.txt` = links TikTok/Insta/YouTube dele;
  senão Shorts mais vistos das hashtags do `config.json`, ≤ `max_dias`). Gemini assiste o viral, escolhe o começo e
  escreve o texto "Quando...", legenda e 5 tags (as do original primeiro). Formato dos exemplos dele: começo em tela
  cheia → flash branco → viral (horizontal ampliado 1,33x com faixa preta), texto TikTok Sans branco no topo (16%).
  Saída `prontos\AAAA-MM-DD\NN - texto.mp4` + `.txt`. Login Insta/TikTok: `cookies.txt` na pasta ou `--cookies firefox`.
  LINK DELE em formato meme (outra pessoa + lance) = modo TROCA (padrão): fica IGUAL ao original — mesmo texto (copiado
  do próprio vídeo: mínimo dos quadros do lance, linhas centralizadas do topo; OCR só para a legenda), MÚSICA/áudio
  inteiro do original, mesmo lance e duração —, só a parte da outra pessoa (até o corte de cena achado) vira o começo
  dele. `--modo novo` = texto novo + áudio dele. Começo de gravação longa: `.txt` ao lado com `trecho: 8.0-12.4`.
  Cenas (`partes_da_pessoa`): o vídeo é dividido em cenas (corte seco ou fade pelo preto) e cada uma é "pessoa" ou
  "lance" (Gemini com uma foto de cada cena; sem Gemini: 1ª cena + as parecidas com ela). TODA cena da pessoa — no
  começo, no MEIO ou no fim — vira um pedaço do começo dele (seguido; acabou, volta do início), com a legenda daquela
  cena (`legenda_parada`, copiada pixel a pixel) e o mesmo fade; os lances e o áudio ficam iguais (`troca_partes`).
  Link DELE nunca cai no modo normal: sem pessoa/lance achados = "NÃO FIZ" no registro e o link vai como FALHOU.
- POSTAGEM AUTOMÁTICA: `python tools\postar\postar.py` (APIs oficiais; setup em `tools\postar\LEIA-ME.txt`). Pasta
  `E:\DETTO\postar`: `entrada\<plat>_<conta>\` = fila (mp4 + .txt mesmo nome; texto após "---" não vai), `postados\`,
  `falhas\` (3 erros), `tokens\`, `config.json` (chaves Meta/TikTok, intervalo e horário por conta). Contas: Instagram
  @detto.galo (Reels, posta sozinho), TikTok @detto.galo e @detto.tv pelo TikTok Studio (ver PAINEL; modo API
  "rascunho"/"direto" opcional). Reels entram
  na fila sozinhos (`"postar"` no config dos reels; `[]` desliga). `--login instagram|tiktok --conta X [--token]`,
  `--agendar` (a cada 20 min), `--status`, `--agora video --para plat:conta`.
  FACEBOOK: cada post do Instagram vai em seguida para a página ligada (`fb_posta`: /{page}/video_reels start →
  rupload → finish PUBLISHED; > 90 s = /videos normal), com o token da PÁGINA do login pelo Facebook (`pagina_id`
  no token; login do Instagram IGAA não serve). Precisa de `pages_manage_posts`. `"facebook": true` na conta (painel:
  "Facebook também"); falha = `fb_pendentes` no estado.json, nova tentativa nas rodadas (até 3), o Instagram não é
  afetado. `--teste-facebook detto.galo` confere a permissão.
- PAINEL (`tools\painel\painel.py`, só Python, http://localhost:8730; `--instalar` = liga com o Windows + atalho;
  celular no mesmo Wi-Fi com PIN; setup em `tools\painel\LEIA-ME.txt`): enviar vídeos (vão para `entrada\<conta>\`
  ou `reels\inicios\`), fila com ordem (`_ordem.json`), legenda, postar já, falhas, liga/desliga por conta, intervalo,
  horário, máx./dia, pausa geral, chaves e login das contas, legendas de rascunho do TikTok, gerar reels, links.
  Aberto = posta sozinho (rodada a cada 5 min, trava `.postando` contra post duplo com a tarefa do Windows).
  Abas: Postagem | Edição | Reels automáticos | Configurações. EDIÇÃO (`tools\painel\edicao.py`): gravação (upload ou
  caminho no PC, hardlink) + roteiro (.txt/.docx/colado) + imagens → `E:\DETTO\edicao\<data título>\` → roda o
  `editar.py` (um por vez; `painel.json` = situação, `painel_log.txt` = registro); saídas para assistir/baixar/postar,
  "Ajustar roteiro e refazer" (grava o roteiro.txt do job), vertical completo pode ir sozinho para a fila.
  Tipos de edição: roteiro (editar.py) | galo (passagem.py, jogo.json com "jogo") | react (react.py, 3 vídeos) |
  vertical (vertical916.py); os não-roteiro saem em `<pasta>\saidas\`.
  Instagram = REELS TESTE por padrão (`trial_params` MANUAL; `"teste"`, `"graduar"` manual|automatico, `"meta_views"`
  na conta; o TESTE só vale com `video_url`: o vídeo sobe para link temporário de 1 h — Litterbox/tmpfiles —, o envio
  direto ignorava o teste); views pelo insights (permissão instagram_manage_insights) a cada 30 min; mandar para os seguidores é no
  app (a API não faz) → painel avisa e tem "Já mandei". Roteiro sem linha de BLOCO vira um bloco só.
  TIKTOK = modo "studio" (padrão; o TikTok não aprova app para as próprias contas): nada vai pela API; o painel
  planeja horários (`P.planeja`: intervalo/janela/máx. por dia, 20 min a 10 dias), "Preparar pasta" →
  `E:\DETTO\postar\tiktok_studio\<conta>\` (vídeos "01 - 16-10 08h00 - nome" + LEGENDAS.txt), ele agenda no TikTok
  Studio e marca "Agendei" (vai para postados com `agendado_para`). "rascunho"/"direto" = API (opcional).
  REELS no painel: vários links de uma vez → `links.txt`; com `"auto_links"` (padrão) o painel roda
  `reels.py --so-links` sozinho (um por vez, cada pronto vai para a fila). yt-dlp atualiza 1x/dia.
- COR: SÓ CONVERTE HDR→SDR, não "colore". `tools\sdr.py` = master SDR antes de editar: libplacebo (placa, Vulkan) com o
  Dolby Vision que o iPhone grava = a conversão do iPhone/CapCut; conferido num quadro (brilho × zscale, sem riscos),
  senão zscale "natural" ajustado para bater com ele (npl=350, mobius, desat=1, saturação 0,88). Lado maior até 1920
  (`--4k` mantém); NVENC cq 16 ou x264 crf 14; áudio sem o APAC; mantém a data; tag `comment=detto_cor v2` (master
  antigo é refeito). `editar.py`, vlog e o COMEÇO dos reels (`<reels>\sdr\`) usam o master (`--sem-sdr` desliga);
  `cor.py`/`ffopts.js` usam o zscale natural (`DETTO_TONEMAP=203|antigo` volta os de antes; `DETTO_PLACEBO=0`).
- Reels TROCA: o texto do original é copiado PIXEL A PIXEL (mediana dos quadros onde fica parado: mesma fonte, cor e
  contorno; meme com faixa preta ganha só um contorno fino).
- VLOG (`tools\vlog\vlog.py <pasta> [--titulo --estilo --formato --duracao --legendas --refazer]`, aba Edição tipo
  Vlog; pasta do Google Drive para computador `Meu Drive\DETTO\vlogs\<vlog>`): clipes por data de gravação → SDR →
  faster-whisper + movimento/volume + fotos → diretor (Gemini com fotos e falas; sem Gemini: falas sem silêncio +
  cenas) → `plano.json` (seções com clima; trechos: clip/ini/fim/tipo fala|cena|timelapse/zoom/texto/transicao/sfx)
  → trechos renderizados (fundo desfocado se o formato não bate, punch-in, drawtext) → emenda concat + xfade →
  sfx (sons.json) → trilha.py por clima (`E:\DETTO\musicas\<clima>`) → `vlog.mp4` + `vlog_conferir.jpg`.
- CANAIS AUTOMÁTICOS YouTube (`tools\canal\`, painel aba CANAIS, `tools\painel\canais.py`; guia `tools\canal\LEIA-ME.txt`):
  NOTÍCIAS `canal.py` (E:\DETTO\canal_galo: Galo da imprensa + voz clonada Chatterbox + máscara; `pautas.txt` = link,
  arquivo do PC ou assunto → trechos marcados `pauta`, entram primeiro) e VLOGS `canal_vlog.py` (E:\DETTO\canal_vlogs:
  pasta do Drive `Meu Drive\DETTO\canal_vlogs\<vlog>` parada 20 min → vlog.py → thumb.py → Shorts = janelas com mais
  volume → vertical916). Cada pronto: `prontos\<data - título>\post.json` (status aguardando|na_fila|postando|postado|
  erro|descartado) + video.mp4 + short_N.mp4; `comum.publica` sobe o vídeo e agenda cada Short (+3 h, `publishAt`).
  `auto_postar` false = espera "Aprovar e postar" no painel; "Ligado" (painel_canal.json) = roda sozinho (notícias 2 h,
  8–23 h; vlogs 10 min). Um trabalho pesado por vez (`EDI.OCUPADO`). Login por canal (token.json na pasta do canal);
  client_secret.json compartilhado em E:\DETTO\youtube. `--preparar`, `--postar <pronto>`, `DETTO_VOZ_FALSA=1` (teste).
- TESTES: `npm run check` (tipos + testes + teste VISUAL `test/visual.test.js`: quadros do palco × `test/visual/ref_*.png`).
  Mudou o visual de propósito → `npm run visual:aprovar`. GitHub Actions roda tudo a cada push (`.github/workflows/testes.yml`).

## Vídeo gravado COM o roteiro dele (padrão)

O Everton grava lendo um roteiro, mas muda as falas. `python tools\editar.py "<video>" --roteiro "<roteiro.txt>"`
(ou o .txt com o MESMO NOME do vídeo na mesma pasta) → o roteiro é copiado para `<job>\roteiro.txt`.
- Alinhamento global roteiro × transcrição (`tools/roteiro/align.js`, programação dinâmica): cada trecho começa
  onde foi FALADO; improviso (`[IMPROVISA: ...]`) e palavras trocadas não atrapalham.
- Legenda = o que ele DISSE (transcrição); o roteiro só corrige a grafia dos nomes; ERRATA vale também.
- Os COMANDOS também seguem a fala: cada trecho guarda o texto falado (`spokenBySegment`); placares, enquete e
  cards saem do que foi dito (quem estava na FALA e ele não citou sai; quem ele citou e tem nota entra).
  Relatório `<job>\ajustes.txt` (roteiro × falado e o que mudou).
- Formato com modos (`tools/roteiro/componentes.js` lê; `tools/motion/director-modos.js` dirige):
  `[CAM]` câmera + legenda | `[CAM+MG]` gráfico + câmera pequena no canto (borda verde-limão) |
  `[MG+VO]` só gráfico | `[LANCE+VO]` sem vídeo do lance → gráfico do trecho ou cards de quem é citado.
- MG vira componente (`tools/motion/stage/modos.js`): cards (`NOME (Time) 9,5`), campinho (linhas `[ NOME 8,3 ]`,
  do ataque ao goleiro; capitão/cartão pela frase), placares da rodada (jogos da FALA "Time 2 a 1 Time"),
  duelo (`FLA 61 x PAL 60`), vinheta, aspas, selos, tela de VAR (toda POLÊMICA abre com ela), números caindo,
  enquete (TELA), CTA. Cada card/placar entra na hora em que o nome/placar é falado.
- Times conhecidos em `tools/roteiro/times.json` (sigla, apelidos, id SofaScore). Time novo → acrescente lá.
- Banco PRONTO (vem no git pull): `tools/banco/jogadores/<id>.webp` (todos os jogadores dos 20 times, sem fundo),
  `tools/banco/elencos/*.json`, `tools/banco/escudos/*.png`. Atualizar (transferências): `python tools\banco_fotos.py`
  (o SofaScore dá 403 no PC do Everton: atualize aqui no Claude e faça push).
- Não achou no banco/SofaScore → `tools/busca_imagem.py` procura na INTERNET até achar (Bing, DuckDuckGo, Wikimedia,
  Openverse; título precisa citar o nome; foto de pessoa precisa de UM rosto e é recortada). Cache `tools/banco/web`.
- Fotos de camisa/objeto: MG com "camisa/uniforme/foto" ou VISUAL → componente `fotos` (1 a 3 lado a lado,
  na hora em que o time é falado); o tema do título ("CAMISAS 3") vale para o vídeo todo.
  Camisa EXATA: a busca usa marca, nome/inspiração (FICHA, frases entre aspas, "TIME • COR • FRASE") e cor do bloco;
  junta os resultados de 4 buscas (nome da camisa, "terceira camisa TIME ANO", "terceiro uniforme", inglês) e fica
  com a que mais bate. Exige time + camisa 3 ("terceir/third/III") e SÓ o ano do vídeo (2026 = 2026 ou 2026/27;
  "25/26", "2025-2026" fora; ano do tema, ex. "Mundial 2006", é aceito); sem ano no título, precisa citar o nome
  da camisa. Descarta: outra marca, outro clube parecido (`"nao"` em times.json: Inter Miami, Atlético Madrid),
  goleiro/treino/polo, concept/vazamento/arte/PES, e foto cuja COR não bate com o roteiro (camisa vinho ≠ foto branca).
  Mesmo time no vídeo = mesma imagem (a da descrição mais completa). Sem foto na rodada rápida = escudo no lugar.
  Busca: 3 imagens por vez, todas as buscas de cada imagem (mostra [n/total]); Ctrl+C pula e segue com o que achou.
  Pasta `imagens\`: camisa = arquivo com o NOME DO TIME (Vasco.jpg); foto de apoio = palavras da busca
  (Santos 1997.jpg, colar Pataxó.jpg, torcida Santos Vila.jpg). Vale antes da internet.
  `<job>\imagens_conferir.jpg`: folha com todas as imagens escolhidas (vermelho = não achou) — confira antes do render.
  Garantido: foto na pasta `imagens\` (do vídeo ou do job) com o nome do time.
- `editar.py` SEMPRE roda `jogadores.py` (antes só com jogador no roteiro → vídeo das camisas saiu sem imagem).
- Comandos de camisa que viram edição: LUPA DE DETALHE na gola/escudo/patch/numeração/etiqueta (círculo ampliado +
  texto; "depois na X" encadeia), comparação lado a lado ("1997" | "2026", "ao lado de uma foto de colar"),
  filtro antigo (sépia+grão), light sweep, luz pulsando, brasas/faíscas, spot, cabide parado/vazio ("?"),
  blackout no "palavra", "?!" congelando, objeto 3D do lado da cabeça (cone, pão de queijo), coração, escurecer,
  etiqueta de preço "R$ ...", mapa SP→RIO + contador "+70.000", varal com as camisas do ranking na abertura,
  PLACA DE NOTA com a nota FALADA ("nota 9", "nove e meio"). Texto de TELA com foto na tela vai por cima dela.
- Seção `CORTES NA GRAVAÇÃO` no roteiro: linhas `- 7:50.7 – 8:25.8 (repetiu)` em tempo da GRAVAÇÃO → somem do vídeo,
  da legenda e do alinhamento (repetições, tentativa refeita). O silêncio antes da 1ª palavra sai sozinho.
- Cabeçalho `[0:00 – 0:08]  [CAM] + [VFX]` (sem "MODO:") e trecho sem tempo `[CAM+MG]  — TÍTULO` também valem.
- PLACAS DE PLACAR com a lista no MG (`VASCO 0 x 0 REMO`, uma por linha) valem mais que a fala; cada placa entra na
  ordem da lista, na hora em que o time é falado. Tabela: `FLAMENGO 64 PTS` (uma por linha) = corrida de barras em pontos.
- Placas do trecho entram na ORDEM da fala; selo com deixa: `VFX: no "virada", selo "VIRADA NO 51'"`. A ERRATA vale
  também para a fala usada nos comandos (card de quem foi falado errado não some).
- "FALA → GRÁFICO:" (frase entre aspas → placa) sem FALA: as frases viram a fala do trecho (alinha e mede a duração).
- "Atlético" sozinho = Galo; "Atlético Nacional/Madrid/Goianiense" não. Corrida de barras: no 9:16, nome e valor
  em cima e barra larga embaixo.
- Fala diferente do roteiro: deixa de EFEITO e nome de card não ditos ficam no lugar "mais ou menos" (onde a palavra
  estaria pela FALA, `alignWords`), em vez de sumir ou ir para o começo do trecho.
- Fotos: `tools\jogadores.py <job>\EDIT_PLAN.json` → `jogadores.json`. Procura no ELENCO atual do time
  (SofaScore); só usa quando o nome bate com UM jogador; senão fica sem foto (iniciais) e aparece no relatório.
  Galo usa as fotos do site (`tools/galo/banco/elenco`). Fotos de apoio (Openverse) só com a pessoa no título.
- Cor: iPhone grava em HDR (HLG). A extração converte para SDR (zscale + tonemap mobius, `DETTO_TONEMAP`).
  Vale também para Galo e React (`tools/cor.py`).
- Disco: o render apaga os quadros de renders antigos, refaz quadro vazio, confere a duração do mp4 (curto = erro claro)
  e o `editar.py` apaga `<job>\tmp` no fim. Aviso de pouco espaço no início do render.
- EFEITOS PRO (VFX, na palavra com `no "palavra"`; 1 a cada ~15 s): `texto atrás "POLÊMICA"` (palavra gigante ATRÁS dele,
  recorte da pessoa pelo MediaPipe em `tools/motion/recorte.py`, só nos quadros do efeito; sem mediapipe vai acima da cabeça),
  `rastreio "EU NO DOMINGO" • "SUB"` (etiqueta presa na cabeça, segue o rosto quadro a quadro), `mira "ALVO" • "SUB"`
  (alvo travando no rosto), `emoji 🤡 na cabeça`, `congela "NOME" • "SUB"` (imagem para, fundo cinza, ele com contorno
  branco + nome; o áudio segue), `texto 3D "VIRADA"` (extrudado girando; "vermelho" na linha = vermelho).
  MG `CARTA FUT: NOME (Time) 4,2` = carta 3D girando (ouro ≥8, prata, "bagre" <6,5); sozinha no [CAM] vai ao lado da cabeça.
  `TRANSIÇÃO: whip|zoom|glitch|flash|nenhuma` no trecho; troca de bloco já tem chicote/zoom automático (vinheta não).
  Um efeito ao lado da cabeça por vez; no 9:16 carta/congela/3D vão embaixo e a legenda sai enquanto estão na tela.
- Conferência antes de entregar: `tools\conferir.py` (roda no editar.py) → `<job>\conferencia.txt` e
  `conferencia.jpg` (gravação × editado): cor, brilho, fotos sem conferência, volume. Leia antes de dizer que terminou.

## Pedido "edita este vídeo" (sem roteiro) — fluxo completo

Quando o Everton passar só a gravação (ex.: `C:\Users\guebe\Videos\edição ia\gravação.mp4`):

1. Pasta do job: `<pasta do vídeo>\<nome>_job\`. Duração: `ffprobe -v error -show_entries format=duration -of csv=p=0 <video>`.
2. Transcrição: `python tools\transcrever.py <video> <job>\words.json`
3. Rosto: `python tools\motion\facetrack.py <video> <job>\face.json --model yunet.onnx`
4. **Você escreve o roteiro** `<job>\roteiro.txt` lendo o `words.json` (formato abaixo). Regras de estilo:
   - um trecho `[mm:ss – mm:ss]` a cada frase/ideia (5–15 s), com a FALA exata da transcrição;
   - TELA/GRÁFICO só onde a fala cita placar, número, data, nome, ranking ou lista (1 a cada ~8 s);
   - EFEITO: punch-in nas frases de impacto; tremida só em placar/cartão/gol;
   - VISUAL com termos de busca concretos (jogador + clube + ano) para as fotos de apoio;
   - CORTES VERTICAIS: um por tema (30–75 s), cada um com o gancho do início do vídeo;
   - ERRATA: nomes que o Whisper errou (jogadores, clubes, camisas).
   Mostre o roteiro ao Everton só se ele pedir; senão siga.
5. Plano: `node tools\roteiro-to-plan.js <job>\roteiro.txt --media "<video>" --duration <dur> --words <job>\words.json --gap 0.8 --job <nome> --out <job>\EDIT_PLAN.json`
   (`--gap 0.8` = corte conservador: só tira pausas longas.)
6. Render horizontal: `node tools\render-dynamic.js <job>\EDIT_PLAN.json --video "<video>" --face <job>\face.json --fonts fonts --work <job>\tmp --out <job>\horizontal.mp4`
   Verticais: o mesmo com `--cut N --out <job>\corteN.mp4`. Teste rápido: `--from 0 --to 60`.
7. Confira 3 quadros (`ffmpeg -ss T -i saida -frames:v 1 q.jpg`) antes de dizer que terminou.

Ajustes pedidos depois ("tira o gráfico do minuto 2", "mais zoom") → edite o `roteiro.txt` e rode de novo os passos 5–6.

### Formato do roteiro (exemplo mínimo)

```
=====================================================================
 ROTEIRO DE EDIÇÃO — "TÍTULO"
=====================================================================

=====================================================================
 ABERTURA / GANCHO
=====================================================================

[00:00 – 00:08]
FALA: "frase exata"
TELA: "CINCO CAMISAS" (palavra por palavra)
EFEITO: punch-in em "camisas"

=====================================================================
 BLOCO 1 — NOME DO BLOCO
=====================================================================

[00:08 – 00:19]
FALA: "..."
VISUAL: Hulk Atlético-MG 2021
GRÁFICO: PLACA DE PLACAR: ATLÉTICO-MG 3 x 3 REMO • BRASILEIRÃO
SFX: impacto

=====================================================================
 CORTES VERTICAIS (9:16) SUGERIDOS
=====================================================================
1. "TEMA": [00:08 – 01:10]. Gancho: "frase do gancho"

=====================================================================
 ERRATA PARA A LEGENDA
=====================================================================
- "Rúlque" → HULK
```

## Ala GALO — reels dos jogos do Atlético

Formato: Everton no estádio, placar estilo Google no topo, jogadores recortados (contorno branco)
entrando e saindo ao lado dele. Sem trilha (ele coloca a música no app).

1. Copie `tools\galo\jogo.exemplo.json` para a pasta do vídeo e preencha placar e jogadores.
2. Fotos: `tools\galo\banco\elenco\<nome>.png` (ou `"foto"` no json). Foto com fundo → `pip install rembg` (o recorte fica salvo em `banco\recortes` e é reaproveitado).
   Escudos: `tools\galo\banco\escudos\<time>.png`.
3. `python tools\galo\galo.py <pasta>\jogo.json`
4. O script imprime os tempos usados; para ajustar, cole em `"tempos"` e rode de novo.

### Elenco passando (reels dos jogos) — padrão para o Galo

`python tools\galo\passagem.py <pasta>\jogo.json` com `{"video": "...", "jogo": "Athletico Atletico Mineiro", "time": "Atlético Mineiro"}`.
- Lê seus gestos e o seu olhar: entra pela direita, passa deslizando no ritmo do rosto, puxão traz de volta
  (quem já saiu vem de FORA da imagem para dentro, no ritmo da mão; nunca aparece direto na mão)
  e ele FICA onde você soltou, batida fraca = meio corpo, forte = só a cabecinha, agarrar e jogar = sai voando.
- Notas do SofaScore: quem apanha mais e por último = pior nota; quem passa ou ganha carinho = melhores.
- Fotos: `tools\galo\banco\elenco` (site oficial, sem fundo). Atualizar: `python tools\galo\elenco_site.py`.
- Sem placar (padrão; `"com_placar": true` liga). Corta do 1º jogador entrando até o último sair.
- Gestos lidos ficam em `<video>.roteiro.json`; corrija ali e rode de novo. Áudio da gravação sem tratamento.

## DETTO REAGE — vídeos de react

`python tools\react\react.py <pasta>\react.json` (exemplo em `tools\react\react.exemplo.json`).
Entradas: `camera` (gravação dele), `tela` (gravação da tela com as pausas), `original` (vídeo reagido bruto).
- Sincroniza câmera↔tela pelo áudio (palma no começo ajuda; senão `offset_camera`).
- Pausa = imagem parada > 0,7 s que volta de onde parou; cada trecho tocado é achado no original (qualidade cheia).
- Tocando: layout DETTO REAGE (vídeo na moldura, câmera no quadro, faixa com `titulo`, painel @detto.galo,
  `mascote`/`patrocinio` opcionais). Pausa: zoom de 0,35 s para a câmera em tela cheia; volta no play.
- Áudio: original abaixa quando ele fala + voz tratada, -14 LUFS. `formato`: horizontal ou vertical.
- O que foi lido fica em `<camera>.react.json`; corrija e rode de novo (`"refazer": true` relê tudo).
- Live no OBS com o mesmo visual: pasta `obs/` (fundo, moldura da câmera, selo da pausa, coleção de cenas
  `DETTO_REAGE_cenas.json`, `LEIA-ME.txt`). Refazer: `python tools\react\obs_template.py`.
