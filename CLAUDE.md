# DETTO — editor de vídeos do @detto.galo

Você é o editor/programador deste projeto. O dono é o Everton (fala português; responda em português,
curto e direto). Máquina: Dell G15 (Windows 11, Ryzen 5 6600H, 16 GB, RTX 3050 4 GB), Premiere Pro 2022,
After Effects 2020. Disco com pouco espaço livre: apague pastas `tmp`/`galo_tmp` depois de cada render.

Código em `detto-premiere-bridge/`. Rode os comandos a partir dessa pasta.

## Jeito mais barato (sem gastar o Claude)

`python tools\editar.py "<video>"` faz tudo sozinho: transcrição (faster-whisper, local), rosto, roteiro
pelo Gemini (`GEMINI_API_KEY`, quase de graça); sem Gemini (cota 429/sem chave) o `roteiro_ia.py` tenta as IAs GRÁTIS de texto (`texto_gratis`: CEREBRAS_API_KEY, GROQ_API_KEY, MISTRAL_API_KEY, OPENROUTER_API_KEY — modelo some → pega o maior da lista) e depois o Claude da assinatura dele (`claude_cli`: `claude -p` do Claude Code instalado e logado no PC, sem ANTHROPIC_API_KEY; `DETTO_SEM_CLAUDE=1` desliga) e, sem ele, faz um roteiro SIMPLES pela fala (`roteiro_basico`: [CAM] + legenda, cortes de ~60 s) em vez de parar, plano, horizontal e verticais. `--teste` = só 1 minuto.
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
  SHORT DINÂMICO (20/out, `shortDinamico` no render-dynamic): tira as pausas > 0,35 s de dentro do corte (pelas legendas do plano)
  e, se ficar com menos de 60 s, estende frase a frase (`--min-short 0` desliga; `--pausa-short`). Roteiro pede cortes de 75–110 s.
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
- THUMBS VIRAIS (20/out, `tools\thumb\viral.py` + `viral.js`): VOCÊ (melhor reação — MediaPipe blendshapes, olhando para a
  câmera — recortado do PEITO para cima, contorno branco; sem rosto no vídeo → foto padrão `DETTO_FOTO`/`<DETTO>\marca\eu.jpg`/
  `<DETTO>\thumb_rosto\`; recorte falhou → rosto em quadro) + UM QUADRO DO VÍDEO (`melhores_quadros`: nítido/colorido, sem
  preto/vinheta, nas `faixas`) + O ASSUNTO (2–4 palavras + destaque + selo; IA texto Gemini→grátis→Claude; sem IA = palavras do
  assunto, nunca nome de arquivo) + escudo/jogador. 3 versões (TV inclinada + seta | quadro cheio + texto | dividida + faixa);
  Chromium falhou/sem node → desenho simples pelo PIL (nunca fica sem thumb). Estilos noticia|futebol|vlog|gameplay.
  MANCHETE (22/out, estilo `noticia`): o layout da thumb do canal que foi melhor — o QUADRO DA IMPRENSA em tela cheia e
  nítido é o protagonista, escurecido à esquerda, manchete em 2 linhas (a 2ª colorida) com contorno grosso, selo
  vermelho, escudo no canto e faixa com o nome do canal embaixo; você entra recortado e menor à direita. `listaVersoes`
  põe ela em 1º (é a que sobe no YouTube).
  Onde: `thumb.py <job>` no fim do editar.py (rosto = gravação, quadro = horizontal.mp4, jogadores do jogadores.json);
  canal.py `thumb(..., sel)` (rosto = máscaras surpreso/bravo/rindo primeiro, quadro = o vídeo da imprensa no trecho
  principal, escudo, marca do canal) → `pronto\thumb_1.jpg` (sobe no YouTube; canal precisa ser VERIFICADO por telefone);
  canal_vlog (rosto = clipes do vlog, estilo vlog/gameplay pelo nome); painel Edição react/vlog horizontais → `saidas\thumbs\`
  (`thumbs_depois`, roda separado).
- REELS AUTOMÁTICOS (meme: começo dele + viral): `python tools\reels\reels.py [--quantos 10] [--agendar 07:00]`, pasta
  `E:\DETTO\reels` (`inicios\` = começos dele, nome = o que ele faz; `links.txt` = links TikTok/Insta/YouTube dele;
  senão Shorts mais vistos das hashtags do `config.json`, ≤ `max_dias`). Gemini assiste o viral, escolhe o começo e
  escreve o texto "Quando...", legenda e 5 tags (as do original primeiro). Formato dos exemplos dele: começo em tela
  cheia → flash branco → viral (horizontal ampliado 1,33x com faixa preta), texto TikTok Sans branco no topo (16%).
  Gemini sem cota (429)/sem chave → `gemini_json`: pergunta só de TEXTO → IAs grátis e depois Claude; com foto/vídeo → Claude só se
  `essencial` (conferências extras de imagem pulam: `essencial=False`), o Claude da assinatura (`claude_partes_json` em roteiro_ia: vídeo vira
  4 quadros + transcrição faster-whisper; `claude -p --allowedTools Read`; ~1 min por pergunta; SEM limite (ele pediu; `DETTO_CLAUDE_MAX_DIA` põe teto);
  cada pergunta registrada em ~/.detto_claude_uso.json → painel mostra aviso (n, falhas, REPETINDO a mesma pergunta ≥3x/1 h,
  falhas seguidas) + botão "Parar o Claude"/"Ligar"; 6 falhas seguidas = para sozinho).
  Saída `prontos\AAAA-MM-DD\NN - texto.mp4` + `.txt`. Login Insta/TikTok: `cookies.txt` na pasta ou `--cookies firefox`.
  LINK DELE em formato meme (outra pessoa + lance) = modo TROCA (padrão): fica IGUAL ao original — mesmo texto (copiado
  do próprio vídeo: mínimo dos quadros do lance, linhas centralizadas do topo; OCR só para a legenda), MÚSICA/áudio
  inteiro do original, mesmo lance e duração —, só a parte da outra pessoa (até o corte de cena achado) vira o começo
  dele. `--modo novo` = texto novo + áudio dele. Começo de gravação longa: `.txt` ao lado com `trecho: 8.0-12.4`.
  Cenas (`partes_da_pessoa`): o vídeo é dividido em cenas (corte seco ou fade pelo preto) e cada uma é "pessoa" ou
  "lance" (Gemini com uma foto de cada cena; sem Gemini: 1ª cena + as parecidas com ela). TODA cena da pessoa — no
  começo, no MEIO ou no fim — vira um pedaço do começo dele (seguido; acabou, volta do início), com a legenda daquela
  cena (`legenda_parada`: letra clara em QUALQUER cor — canal mais forte —, linha centralizada e letras de altura parecida;
  copiada pixel a pixel) e o mesmo fade; os lances e o áudio ficam iguais (`troca_partes`).
  COMEÇO dos reels: `trecho_do_inicio` SEMPRE tira o toque no botão de gravar (`cortes_botao`, movimento das pontas, cache
  inicios\.cortes.json); `enquadra` põe o ROSTO no meio e ABAIXO do texto do topo (YuNet, zoom até 1,6x; se não dá, estende a borda
  espelhada) — vale no modo normal (`monta`) e no TROCA (`troca_partes`, fim do texto pelo PNG). Um reels.py por vez (`trava_rodada`, `.reels_rodando`: painel + tarefa do Windows juntos faziam o mesmo link 2x); links repetidos no links.txt = um só. Link DELE nunca cai no modo normal: sem pessoa/lance achados = "NÃO FIZ" no registro e o link vai como FALHOU.
  COMEÇOS PELO DRIVE (`importa_inicios`, `reels.py --importar`; o painel roda a cada 10 min): pasta "Começo"/"Começos"/
  "Inícios" na raiz do Meu Drive ou em DETTO (ou `"pastas_inicios_drive"` no config) → Gemini assiste e dá o NOME do que
  ele faz + o melhor trecho (`.txt` com `trecho:` se > 10 s) → copiado para `inicios\` (master SDR já feito) e o arquivo
  é renomeado no Drive também. Já importados: `historico.json` → `importados` (tamanho:data). Sem Gemini: nome original.
- POSTAGEM AUTOMÁTICA: `python tools\postar\postar.py` (APIs oficiais; setup em `tools\postar\LEIA-ME.txt`). Pasta
  `E:\DETTO\postar`: `entrada\<plat>_<conta>\` = fila (mp4 + .txt mesmo nome; texto após "---" não vai), `postados\`,
  `falhas\` (3 erros), `tokens\`, `config.json` (chaves Meta/TikTok, intervalo e horário por conta). Contas: Instagram
  @detto.galo (Reels, posta sozinho), TikTok @detto.galo e @detto.tv pelo TikTok Studio (ver PAINEL; modo API
  "rascunho"/"direto" opcional). Reels entram
  na fila sozinhos (`"postar"` no config dos reels: `["todas"]` = padrão desde 20/out, toda conta LIGADA — Instagram, TikTok, YouTube
  Shorts, Kwai — menos @detto.tv e as com `"reels": false` (`destinos_reels`); painel: "Todas as contas ligadas"; `[]` desliga). `--login instagram|tiktok --conta X [--token]`,
  `--agendar` (a cada 20 min), `--status`, `--agora video --para plat:conta`.
  FACEBOOK: cada post do Instagram vai em seguida para a página ligada (`fb_posta`: /{page}/video_reels start →
  rupload → finish PUBLISHED; > 90 s = /videos normal), com o token da PÁGINA do login pelo Facebook (`pagina_id`
  no token; login do Instagram IGAA não serve). Precisa de `pages_manage_posts`. `"facebook": true` na conta (painel:
  "Facebook também"); falha = `fb_pendentes` no estado.json, nova tentativa nas rodadas (até 3), o Instagram não é
  afetado. `--teste-facebook detto.galo` confere a permissão.
- YOUTUBE SHORTS + KWAI na postagem: plataforma `youtube` (canal que ele já tem: `yt_posta` via `canal/youtube_up.py`,
  token em `tokens\youtube_<conta>\` + marcador `tokens\youtube_<conta>.json`, client_secret próprio na pasta ou o
  compartilhado; título = 1ª linha + #Shorts; máx. 4/dia por padrão — cota 10.000/dia do projeto, 1.600 por envio,
  dividida com os canais) e `kwai` (sem API: `studio()` = verdadeiro, igual ao TikTok Studio; "Preparar pasta" vai para
  `Meu Drive\DETTO\kwai\<conta>` e ele posta pelo app; "✔ Postei"). `--login youtube --conta X`. Destinos dos reels:
  `instagram|tiktok|youtube|kwai:<conta>`. IDENTIDADE dos canais: `tools\canal\marca.py` (banner 2560x1440 com área
  segura 1546x423, perfil 800x800, marca d'água 150x150, molde de thumb; sem escudo oficial). Canais (20/out): DETTO GALO NOTÍCIAS
  (`<saida>\noticias`) e EVERTON LOPES = vlogs + GAMEPLAYS + outros (`<saida>\everton_lopes`, `--foto` = rosto no perfil; moldes
  de thumb vlog e gameplay); cada pasta com CANAL.txt (descrição, palavras-chave, playlists, padrão de envio, links).
  canal_vlog: `nome_canal` EVERTON LOPES + `assinatura` no fim da descrição.
- PAINEL (`tools\painel\painel.py`, só Python, http://localhost:8730; `--instalar` = liga com o Windows + atalho;
  celular no mesmo Wi-Fi com PIN; setup em `tools\painel\LEIA-ME.txt`): enviar vídeos (vão para `entrada\<conta>\`
  ou `reels\inicios\`), fila com ordem (`_ordem.json`), legenda, postar já, falhas, liga/desliga por conta, intervalo,
  horário, máx./dia, pausa geral, chaves e login das contas, legendas de rascunho do TikTok, gerar reels, links.
  Aberto = posta sozinho (rodada a cada 5 min, trava `.postando` contra post duplo com a tarefa do Windows).
  Abas: Postagem | Edição | Reels automáticos | Configurações. EDIÇÃO (`tools\painel\edicao.py`): gravação (upload ou
  caminho no PC, hardlink; pelo caminho pega também o roteiro .txt/.docx e a pasta imagens\ ao LADO do vídeo — `junto_do_video`) + roteiro (.txt/.docx/colado) + imagens → `E:\DETTO\edicao\<data título>\` → roda o
  `editar.py` (um por vez; `painel.json` = situação, `painel_log.txt` = registro); saídas para assistir/baixar/postar,
  "Ajustar roteiro e refazer" (grava o roteiro.txt do job), vertical completo pode ir sozinho para a fila.
  Tipos de edição: roteiro (editar.py) | galo (passagem.py, jogo.json com "jogo") | react (react.py, 3 vídeos) |
  vertical (vertical916.py); os não-roteiro saem em `<pasta>\saidas\`.
  Instagram = REELS TESTE por padrão (`trial_params` MANUAL; `"teste"`, `"graduar"` manual|automatico, `"meta_views"`
  na conta; o TESTE só vale com `video_url`: o vídeo sobe para o Catbox (link público; até 3 vezes) ou Litterbox e o IG
  baixa de lá (tmpfiles e FB não publicado SEMPRE falharam — 2207082/2207076 — e saíram); cada falha de envio aparece no
  registro — erro 2207082/2207076 = o IG não baixou/processou; antes de subir o vídeo é padronizado (`normaliza_ig`: H.264 High, mesmo fps até 60, keyframe a cada 2 s, ≤1080x1920, ≤12 Mbit/s,
  AAC 48 kHz, faststart, em `tmp_ig\`); LINK DO REELS TESTE (22/out): cascata `HOSPEDAGENS`/`"hospedagem"` no config —
  1 `tunel` (o vídeo FICA NO PC e o IG baixa por um endereço público da Cloudflare, `cloudflared` baixado 1x para
  `postar\ferramentas\`, nome sorteado, cai no fim) · 2 Catbox · 3 0x0.st · 4 tmpfiles · 5 Litterbox; CADA link é
  CONFERIDO antes (`_confere_link`: baixa os primeiros bytes de fora, recusa HTML/404/tamanho errado) — link ruim é
  descartado na hora em vez de virar 2207082 e queimar as 4 tentativas; nenhuma hospedagem serviu = NÃO conta erro
  (pausa 10 min, o vídeo fica na fila). Painel: "↻ Tentar todos de novo" devolve as falhas da conta para a fila; falha espera 15 min/45 min/2 h e vai para falhas na 4ª; depois de QUALQUER erro a conta pausa 10 min (`pausa_ate`; antes tentava o próximo da fila na hora → "muitas ações"); erro 2207078 (limite de Reels TESTE da API) ou código 9 "muitas ações" = conta pausa 24 h, o vídeo não conta erro; Instagram sem máx./dia = teto 10/dia (`teto_dia`); sem internet (getaddrinfo) = não conta erro, espera 10 min; vídeo que o FFmpeg não lê (`VideoQuebrado`, depois de 6 jeitos de `normaliza_ig`, os últimos tolerantes a quadro estragado) = falhas na hora, sem gastar ação no IG; contador de erros zera depois de 12 h e ao ir para falhas; painel mostra a pausa + "Tirar pausa"; `normaliza_ig` tenta 3 jeitos (áudio vazio → silêncio; sem source_fps → 30 fps); o envio direto ignorava o teste); views pelo insights (permissão instagram_manage_insights) a cada 30 min; mandar para os seguidores é no
  app (a API não faz) → painel avisa e tem "Já mandei". Roteiro sem linha de BLOCO vira um bloco só.
  TIKTOK = modo "studio" (padrão; o TikTok não aprova app para as próprias contas): nada vai pela API; o painel
  planeja horários (`P.planeja`: intervalo/janela/máx. por dia, 20 min a 10 dias), "Preparar pasta" →
  `E:\DETTO\postar\tiktok_studio\<conta>\` (vídeos "01 - 16-10 08h00 - nome" + LEGENDAS.txt), ele agenda no TikTok
  Studio e marca "Agendei" (vai para postados com `agendado_para`). "rascunho"/"direto" = API (opcional).
  REELS no painel: vários links de uma vez → `links.txt`; com `"auto_links"` (padrão) o painel roda
  `reels.py --so-links` sozinho (um por vez, cada pronto vai para a fila). yt-dlp atualiza 1x/dia.
- COR EXATA: `python tools\cor_lut.py "<gravação iPhone>" "<mesmo vídeo exportado do CapCut, ou o REEL postado feito
  no CapCut com ela>"` (acha sozinho o trecho, fica só com a 1ª cena, ignora texto por cima) → aprende
  a conversão (tabela 33³, polinômio + correção por célula, confere a diferença) em `tools\cor\referencia.cube`; com
  ela, todo HLG usa essa tabela (cor.py/ffopts.js, master `detto_cor v4 lut<data>` refeito). Apagar = volta ao compat.
- COR: SÓ CONVERTE HDR→SDR, não "colore". Padrão "compat" (16/out, o que o CapCut faz no aviso "HDR → SDR"): o HLG do
  iPhone já é compatível com tela comum, então só troca as cores BT.2020 → BT.709, sem tone mapping (parede branca,
  sem lavar nem amarelar). PQ cai no "natural" (npl=350, mobius, desat=1, sat 0,88). `DETTO_TONEMAP=natural|203|antigo`
  volta os de antes; libplacebo só com `DETTO_PLACEBO=1`. `tools\sdr.py` = master SDR antes de editar; lado maior até
  1920 (`--4k` mantém); NVENC cq 16 ou x264 crf 14; áudio sem o APAC; mantém a data; tag `comment=detto_cor v4` (master
  antigo é refeito). `editar.py`, vlog e o COMEÇO dos reels (`<reels>\sdr\`) usam o master (`--sem-sdr` desliga);
  `cor.py`/`ffopts.js` usam a mesma conversão.
- Reels TROCA: o texto do original é copiado PIXEL A PIXEL (mediana dos quadros onde fica parado: mesma fonte, cor e
  contorno). Meme com faixa preta: o texto da BARRA vale para todas as cenas da pessoa (inteiro e limpo; a legenda achada
  em cima da parede saía pela metade/borrada), tirado do preto com borda suave + sombra suave (como o TikTok/CapCut).
- CONFERÊNCIAS do TROCA (reels.py): ANTES de montar — `confere_cenas` (cena "lance" parecida com a pessoa + rosto →
  Gemini compara com a 1ª cena da pessoa → vira "pessoa": a pessoa que volta no meio é coberta) e `le_texto_duplo`
  (PNG do texto × Gemini lendo o quadro original; não bate → testa o outro recorte). DEPOIS — `confere_troca`
  (pixels: cena da pessoa ≠ original, lance = original; Gemini lê o texto em cada cena trocada; Gemini aprova
  um quadro de cada cena). Problema → refaz pelo outro recorte e confere de novo; ainda ruim → `prontos\<dia>\conferir\`
  com o .txt dos problemas, NÃO vai para a fila. Legenda do post: `legenda_viral` (Gemini, nunca "meme";
  `"exemplos_legenda"` no config). Guia de instalação/outro PC/outra conta: `detto-premiere-bridge\INSTALAR.txt`
  (+ `INSTALAR.bat`, `requirements.txt`).
- Importação do Drive: chave = CONTEÚDO (`assinatura`: tamanho + md5 do começo/fim), não nome/data (renomear no Drive
  mudava a data → reimportava a cada 10 min → "nome 2 2 2..." e cópias repetidas). `limpa_inicios_repetidos` apaga as
  cópias do mesmo vídeo em inicios\ (e masters) e tira o " 2 2 2" do nome (no Drive também).
- VLOG (`tools\vlog\vlog.py <pasta> [--titulo --estilo --formato --duracao --legendas --refazer]`, aba Edição tipo
  Vlog; pasta do Google Drive para computador `Meu Drive\DETTO\vlogs\<vlog>`): clipes por data de gravação → SDR →
  faster-whisper + movimento/volume + fotos → diretor (Gemini com fotos e falas; sem Gemini: falas sem silêncio +
  cenas) → `plano.json` (seções com clima; trechos: clip/ini/fim/tipo fala|cena|timelapse/zoom/texto/transicao/sfx)
  → trechos renderizados (fundo desfocado se o formato não bate, punch-in, drawtext) → emenda concat + xfade →
  sfx (sons.json) → trilha.py por clima (`E:\DETTO\musicas\<clima>`) → `vlog.mp4` + `vlog_conferir.jpg`.
  ESTILO AM3NIC (padrão do canal de vlogs desde 19/out; `--estilo` com "am3nic"/"cinemat"): cortes secos, abre com
  cenas de apoio bonitas + frase-gancho, `lugar` (nome do lugar GRANDE no meio, 2,6 s) e `nota` (comentário curto em
  minúsculas embaixo, ~1 a cada 40 s), SEM legenda das falas, pouco sfx. Referência: youtu.be/_qu8VdWmd6s.
  APOIO DA INTERNET (20/out, `tools\vlog\apoio.py`): o diretor põe trecho `"tipo": "externo", "busca": "...", "dur": 2.5` quando ele
  fala de um lugar/momento sem cena própria → Pexels (PEXELS_API_KEY) → Pixabay (PIXABAY_API_KEY) → YouTube (Creative Commons
  primeiro, depois busca normal; pedaço do MEIO, horizontal) com `tem_marca` (logo/marca parada nos cantos ou letreiro embaixo =
  descarta); cache `<DETTO>\vlog_apoio` (`DETTO_APOIO`); créditos `<job>\creditos_apoio.txt` → canal_vlog põe na descrição e num
  comentário. Shorts do canal de vlogs ≥ 60 s.
- CANAIS AUTOMÁTICOS YouTube (`tools\canal\`, painel aba CANAIS, `tools\painel\canais.py`; guia `tools\canal\LEIA-ME.txt`):
  NOTÍCIAS `canal.py` (E:\DETTO\canal_galo: Galo da imprensa + voz clonada Chatterbox + máscara; `pautas.txt` = link,
  arquivo do PC ou assunto → trechos marcados `pauta`, entram primeiro); máscara e voz pelo Drive: `Meu Drive\DETTO\canal_noticias\mascara|voz` → `traz_do_drive` copia a cada rodada (voz = áudio mais novo, qualquer formato → minha_voz.wav); FONTES (20/out, `fontes_versao` 4 migra o config; prioridade 1 imprensa: Jogo Aberto, Alterosa
  (@alterosaesporteAE; programa do dia = live gravada), ESPN, Cortes TNT · 2 TV Galo às vezes (1 vídeo/1 trecho) · 3 canais que JUNTAM
  notícias do Galo (`juntador`: Notícias do Galo/@diariodogalo940, Galotícias, Trinca Galo, Resenha Atleticana, Eterno Galo News,
  Jornal do Galo, Vibra Torcedor, Galo Noticiou, Eu Sou Galo — Gemini marca SÓ a fala da imprensa, ignora o narrador do canal) ·
  4 qualquer canal da busca por data (`busca_qualquer_canal`); `fora` = react/ao vivo/jogo); hora pelo FEED RSS (`rss`), hoje e
  ontem (`max_horas` 48), sem Shorts; `max_videos_rodada` 8 por rodada (o resto na próxima); notícia INTEIRA (15 s a
  `trecho_max_s` 180, corte só no fim de frase), máx. 3 por vídeo; vídeo de PELO MENOS 16 min (`duracao_alvo_min` 16 = imprensa + falas ~12 s cada; sem material e sem --forcar espera; `fontes_versao` 5);
  cada fala CITA a origem do trecho seguinte (`origem`/`origem_falada`: "Globo Esporte MG, no canal X") e o fechamento diz que os créditos estão nos
  comentários; créditos num COMENTÁRIO do canal (`youtube_up.comenta`, escopo youtube.force-ssl → refazer o login do canal uma vez;
  fixar é no Studio) + descrição + faixa "Imagens: origem"; notícia repetida em outro canal ou já
  postada nos últimos 3 dias (`parecido` ≥ `parecido_max` 0,35 nas palavras do assunto, `ja_postado`) fica fora; créditos
  com o programa original (`programa`, "via canal");
  VOZ SEM PAUSAS (20/out): `voz.sem_pausas` corta todo silêncio no MEIO da fala para ≤0,13 s (`--max-pausa`/`DETTO_MAX_PAUSA`,
  `--com-pausas` desliga) — Fish, Chatterbox e as do cache (marca `.sp`); entre frases do Chatterbox 0,08 s; depois da fala 0,2 s.
  ORIGINAL (20/out, `busca_original`): trecho de canal JUNTADOR (Galotícias etc.) → acha o vídeo original (links da descrição, busca
  pelo `programa` e pelas palavras do assunto, por data; nunca outro juntador), acha o MESMO pedaço pela legenda do YouTube
  (`legenda_youtube` json3 + `_janela`, ≥45% igual), baixa SÓ esse pedaço até 1080p (`--download-sections`, `fontes\orig_*.mp4`)
  e o crédito/`fonte` vira o canal original (ex. Band Minas); `juntado_por` guarda o outro. Não achou = fica o do juntador
  (`buscar_original` false desliga). Nome do canal: DETTO GALO NOTÍCIAS (`nome_canal`, migra o antigo) + `assinatura` na descrição.
  VOICESTUDIO (22/out, github.com/debpalash/VoiceStudio — open source, roda NO PC dele, de graça e sem limite): é a PRIMEIRA
  opção de voz. `voz.py` fala pela API local no padrão OpenAI (`POST <url>/v1/audio/speech`, loopback sem senha; padrão
  `http://127.0.0.1:3900`, `DETTO_VOICESTUDIO`/`"voicestudio"` troca) com a fala INTEIRA de uma vez (entonação melhor que
  frase a frase); `voicestudio_ligado` confere antes, `voicestudio_vozes` lista os perfis (`GET /v1/audio/voices`).
  Fechado/erro → Fish Audio → Chatterbox. `--voz-vs`/`"voz_voicestudio"` = perfil da voz clonada, `--velocidade-vs`,
  `--sem-voicestudio`/`"sem_voicestudio"`. Painel aba CANAIS: diz se está ligado, escolhe a voz e a velocidade.
  QUAL VOZ (22/out, `voicestudio_escolhe`): "default" fazia o VoiceStudio SORTEAR (saía ora feminina, ora masculina, e
  nunca a dele). Agora: a voz escolhida no painel → se ela sumiu ou não foi escolhida, procura a SUA voz clonada pelo
  NOME (everton/detto/minha voz) → senão a primeira da lista; o registro diz qual voz entrou. `INSTRUCAO_PADRAO`
  (`--instrucao-vs`/`"instrucao_voz"`) pede pt-BR neutro, bem pronunciado, SEM sotaque europeu.
  VOZ (20/out): `pronuncia` antes de qualquer voz (siglas soletradas CBF→"cê bê éfe", VAR/SAF/FIFA como palavra, números por
  extenso, "2 x 1"→"dois a um", 6º, 8,3, 33', R$); FISH AUDIO primeiro se `FISH_API_KEY` (voz clonada criada 1x → voz\fish_modelo.json,
  `s2.1-pro-free`, `FISH_MODELO=s2.1-pro` pago; sotaque BR — o Chatterbox puxava para Portugal), erro → Chatterbox;
  COMENTÁRIOS NO MEIO: trecho ≥45 s (`comentario_min_s`) ganha 1–2 reações dele ("comentarios" no JSON do roteiro; `ponto_de_pausa`
  = fim de frase, nunca nos 10 s das pontas) → trecho parte 1 → fala → parte 2; durante a REPORTAGEM a máscara é a de nome
  "ouvindo/escutando/assistindo/calmo" ou a de POUCO gesto (`mascara_de(..., durante_reportagem=True)`); botão: `cortes_pontas` (reels.py, o mesmo dos reels) corta também a
  MÃO indo dar pause no fim (movimento que sobe e não desce nos últimos 4 s), mínimos 1,0 s / 1,5 s (avaliação v2 refaz);
  VOZ: frases ≤150 letras, exagero ≤0,6, cfg 0,5, cada frase CONFERIDA pelo tamanho (≈14 letras/s) e refeita até 4x (`frase_boa`),
  voz de teste nunca vira cache; MÁSCARA: `prepara_mascaras` corta o botão (≥0,8 s e o tremor das pontas até 3 s), mede o GESTO
  (movimento) → mascara\avaliacao.txt (muito/médio/pouco); `mascara_de` usa nome do clima ou o gesto (animado → muito), sem repetir e VLOGS `canal_vlog.py` (E:\DETTO\canal_vlogs:
  pasta do Drive `Meu Drive\DETTO\canal_vlogs\<vlog>` parada 20 min → vlog.py → thumb.py → Shorts = janelas com mais
  volume → vertical916). Cada pronto: `prontos\<data - título>\post.json` (status aguardando|na_fila|postando|postado|
  erro|descartado) + video.mp4 + short_N.mp4; `comum.publica` sobe o vídeo e agenda cada Short (+3 h, `publishAt`).
  `auto_postar` false = espera "Aprovar e postar" no painel; "Ligado" (painel_canal.json) = roda sozinho (notícias 2 h,
  8–23 h; vlogs 10 min). Um trabalho pesado por vez (`EDI.OCUPADO`). Login por canal (token.json na pasta do canal);
  client_secret.json compartilhado em E:\DETTO\youtube. `--preparar`, `--postar <pronto>`, `DETTO_VOZ_FALSA=1` (teste: voz de computador pt — Windows SAPI "Maria" / espeak-ng —
  no lugar da clonada; painel: botão "Teste" no card Notícias = `--forcar --nao-postar` com essa voz).
- FFMPEG: `-filter_complex_script` saiu na 8; use SEMPRE `tools\ffcompat.py` (`filtro_complexo`/`filtro_v`, o mesmo que o
  `motion\ffopts.js` faz no Node) — o vlog quebrava com "Unrecognized option 'filter_complex_script'".
- PYTHON 3.11 no PC dele: NADA de `\` dentro das chaves de f-string (no 3.12+ passa, lá quebra — aconteceu no canal.py). Conferir:
  `python3.11 -S -c "import ast,sys;ast.parse(open(sys.argv[1]).read())" arq.py`; o GitHub Actions roda compileall no 3.11.
  canal.py: UMA rodada por vez (`trava_rodada(pasta, ".canal_rodando")`; duas juntas apagavam o tmp\ da outra no meio da voz).
- CÓDIGO NOVO x PAINEL ABERTO (22/out): o painel.html é lido DO DISCO a cada acesso, mas o Python fica em MEMÓRIA —
  depois de um `git pull` o navegador recebe a tela nova e o programa continua o velho. Foi isso que deixou a aba
  Histórias aparecendo VAZIA e o Instagram no caminho antigo por horas (o aviso de "reinicie" também não saía, porque
  quem o gerava era o Python velho). Agora `PAINEL_VERSAO` (painel.py) × `VERSAO_TELA` (painel.html): diferente = a tela
  mostra um aviso VERMELHO e para de desenhar o resto. **Ao mexer no painel.py, suba as duas versões juntas.**
  `codigo_novo()` (data dos arquivos × `SUBIU_EM`) continua avisando quando só os arquivos mudaram; botão
  **Reiniciar o painel** (ação `reiniciar`, `os._exit(7)`; o Python velho não tem a ação → a tela manda fechar na mão).
- ATUALIZAR O PC DELE: `detto-premiere-bridge\ATUALIZAR.ps1` (PowerShell, UTF-8 com BOM) faz tudo na ordem certa —
  fecha o painel (`Get-CimInstance Win32_Process` + CommandLine com "painel"), `git pull` (se falhar pela pasta
  `detto-historias-panel` solta, renomeia para -BACKUP e tenta de novo), confere no disco a `PAINEL_VERSAO`, a marca
  "link conferido" do postar e o historias.py, e abre o painel + o navegador. Mande ele rodar isso em vez de comandos soltos.
- TESTES: `npm run check` (tipos + testes + teste VISUAL `test/visual.test.js`: quadros do palco × `test/visual/ref_*.png`).
  Mudou o visual de propósito → `npm run visual:aprovar`. GitHub Actions roda tudo a cada push (`.github/workflows/testes.yml`).

## HISTÓRIAS EM SÉRIE — reels em que o público escolhe a continuação (22/out)

Formato medido nos virais de out/2026 (Histórias com Kaio 308k, Manual do Benji 372k, Tio do Fim, Insólito, Contos de
Stick): 60–90 s · 9:16 · ilustração CHAPADA desenhada por CÓDIGO (mesmo visual em toda a série) · narração 150–190
palavras/min · legenda GRANDE em caixa alta com a palavra-chave colorida · relógio/contador na tela · cena nova a cada
4–6 s (movimento lento de câmera, NÃO corte rápido).
NARRATIVA: gancho em 2ª pessoa com ordem contra-intuitiva → promessa com risco → personagem de nome simples + hora →
3 a 5 REGRAS NUMERADAS com razão técnica e NÚMERO CONCRETO (180 litros, 1 litro = 1 quilo, 8 km — é o que faz salvar e
compartilhar) → detalhe doméstico brasileiro (a gata, o mercadinho, a laje) → cliffhanger → **ESCOLHA A/B**.
O LAÇO: o episódio termina na escolha → o público comenta A ou B → o episódio seguinte ABRE com o resultado ("84%
mandaram o Lucas pro mercadinho"). É isso que faz a série crescer. Vale para qualquer tema (esporte, trabalho...).

- `python tools\historias\historias.py --novo "<ideia>" --conta instagram:<conta>` → a IA monta o mundo, as regras e os
  personagens em `<DETTO>\historias\series\<nome>\serie.json`.
- `python tools\historias\historias.py [--serie X] [--quantos N] [--apurar]` → apura os votos do episódio anterior
  (`apura`: lê os comentários pela API do Instagram, conta A x B, menos de 3 votos segue pela A) → a IA escreve o
  episódio (`escreve_episodio`, Gemini → IAs grátis → Claude; `limpa_cena` descarta cenário/pose/objeto que o palco não
  sabe desenhar) → voz (VoiceStudio → Fish, com `sem_pausas`) → faster-whisper → `encaixa_cenas` (cada cena termina onde
  a frase dela acaba) → `render.js` → `<serie>\ep_NN\episodio.mp4` → fila de postagem do painel.
- A IA DIRIGE A EDIÇÃO (22/out, Gemini API dele): além do texto, o roteiro traz `plano` (geral|medio|close) com `foco`
  — o CLOSE é o corte de apoio do formato (o celular na hora da mensagem, a torneira, o relógio) —, a ROUPA do
  personagem (`roupa`: moletom|camisa|jaleco|uniforme|terno|pijama|regata|capuz + `mochila`/`bone`/`colete`/`lanterna`,
  a MESMA em todo o episódio e nos seguintes) e `sfx` + **`sfx_palavra`**: o efeito entra na PALAVRA da narração
  (achada nas words do whisper, `marca_sfx`), não no começo da cena. Sem a pasta de sons catalogada, o som é
  SINTETIZADO pelo FFmpeg (`som_sintetico`) — o episódio nunca sai mudo. Plano manda no tamanho (close ≤ 500 px).
  A narração já vem pronta para a voz: números por extenso, sem siglas, símbolos nem abreviações (falas erradas).
- ELENCO (22/out, `elenco`/`aplica_elenco`): cada cena diz `"quem": "<nome>"` e a APARÊNCIA vem do `"elenco"` do
  serie.json — assim o personagem é o MESMO em todos os episódios e um não sai igual ao outro (o zelador saía igual
  ao protagonista). O PRINCIPAL (`"principal"`, o 1º personagem) é exatamente o bonequinho do modelo dele: corte
  `tigela` com a faixa clara, pele clara, moletom `#4a6b6b`, mochila e calça azul. Os secundários pegam um look ainda
  não usado de `LOOKS_SECUNDARIOS` (corte `grisalho|rabo|careca|cacheado|curto|longo|bone`, barba `cheia|cavanhaque|
  bigode`, óculos, pele, roupa e cor diferentes). A IA NÃO escolhe roupa nem cor — só o nome. Para mandar no visual
  de uma pessoa no roteiro à mão, ponha `"livre": true` nela.
- ANDAR CERTO: cenário `predio` com `andar: 12` e `andares: 15` desenha o prédio inteiro, acende a janela daquele
  andar, numera os outros e põe a etiqueta amarela **12º ANDAR** DENTRO do prédio (na borda ela sumia no zoom).
- FIM COM AS DUAS ESCOLHAS (22/out, `fecha_com_escolha`): todo episódio ganha a última cena com a cartela A/B e a
  pergunta entra na NARRAÇÃO, para o narrador ler. A legenda some nessa cena (quem lê são os cards). Sem isso não há
  comentário — e sem comentário não há próximo episódio. A cartela é como a dos virais: pergunta GIGANTE, dois blocos
  de tela cheia (A amarelo, B laranja) com a letra num quadrado preto, e "COMENTA A OU B" pulsando; entra em partes
  (pergunta → A → B → chamada) e fica pelo menos 5 s na tela.
- CENAS DE APOIO — o "B-roll" (22/out, `garante_apoio`): a IA punha o boneco em TODA cena e o vídeo ficava igual do
  começo ao fim. Agora, 3 cenas seguidas com pessoa = a do meio vira CLOSE num objeto, SEM pessoa, escolhido pela
  PALAVRA da narração (`APOIO`: celular/mensagem → celular, água/bomba → torneira, litros → balde, hora → relógio...).
  Alvo de ~30% das cenas sem pessoa; o prompt também exige 1 em cada 3.
- SINCRONIZAÇÃO (22/out): `encaixa_cenas` só ancora a cena quando METADE da frase bate com a transcrição; as que não
  batem (voz falou o número por extenso, trocou palavra) não ficam sem hora — o tempo entre as âncoras é repartido na
  proporção do tamanho da fala de cada uma. LEGENDA: nunca fecha em palavra fraca ("NÃO CORRA PARA A" não acontece
  mais, `FRACAS` no render.js), bloco de 1 palavra junta com o anterior e cada legenda fica na tela ATÉ a próxima
  entrar (sem buraco).
- CONTEXTO, APAGAR E MEXER NO ROTEIRO (22/out): `"contexto"` no serie.json (quem é quem, as regras, o tom, o que não
  pode acontecer) entra em TODOS os prompts — painel: "Contexto da história e ajustes"; linha de comando
  `--contexto "<texto>" --serie X`. APAGAR a série: botão no painel (precisa digitar o nome da pasta) ou
  `--serie X --apagar`. ROTEIRO: painel "Ver e mexer no roteiro" abre o roteiro.json do episódio para editar →
  **Refazer este episódio** (`--refazer N`: apaga voz, legendas e vídeo e monta de novo com o que você escreveu, sem
  criar episódio novo) ou **Usar como base do próximo** (`--base-roteiro <arquivo>`: a IA escreve o seguinte seguindo
  a estrutura e o tom desse).
- CAPAS E ARTE DO PERFIL (22/out, `tools\historias\capa.py` + `arte.js` + `palco\arte.html`): a capa sai junto com
  cada episódio (`ep_NN\capa.jpg`, 1080x1920, com TUDO dentro do quadrado do meio que o Instagram mostra na GRADE;
  `capa_grade.jpg` é esse quadrado). Padrão dos perfis que viralizaram: "EPISÓDIO" pequeno, NÚMERO gigante dourado,
  título em caixa alta (última linha amarela), o desenho da cena mais cheia atrás e o nome da série no rodapé
  (última palavra colorida + selo com o emoji da série, `"emoji"` no serie.json). Arte de perfil em `arte\perfil.png`
  (1080x1080, o personagem com a roupa dele) e `arte\grade.jpg` = as capas lado a lado, para ver o perfil montado.
  `python tools\historias\capa.py [--serie X] [--perfil]` refaz tudo; painel: "Refazer capas + arte".
- ANIMAÇÃO DE VERDADE (22/out): o palco tem DUAS camadas — `#fundo` (cenário, desenhado 1x por cena, só recebe o
  movimento de câmera) e `#atores` (REDESENHADO a cada quadro). `anima(p, t)` recebe o progresso da cena E o tempo:
  bonequinho com cabeça REDONDA (estilo stick), ciclo de caminhada com pés, respiração, piscar sozinho, boca falando
  (`falando`), sobrancelha por `cara` (serio/bravo/assustado/feliz); silhuetas pretas (a multidão), gato com rabo
  balançando, chuva caindo, fumaça subindo, vela tremendo, balde/banheira ENCHENDO (`enchendo`), porta `batendo`,
  celular com `alerta` piscando, `tremor`/`escurece`/`clarao` na cena. Quem anda vai de `x` até `x2` pelo PROGRESSO da
  cena (pelo relógio saía da tela). SFX (`sons`): `sfx` por cena → som da pasta dele nos tempos das cenas, -30 LUFS.
- PALCO `tools\historias\palco\` (cena.html/css/js, Chromium): cenários `cidade predio quarto janela banheiro corredor
  rua laje garagem mercado escuro`, luz `dia tarde noite escuro chuva alerta`, bonequinho em 8 poses, gato, objetos
  (balde, banheira, vela, celular, porta, caixa, moto, carro, mochila, escada, torneira), chuva, relógio/contador/selo,
  onomatopeia, movimento `zoom afasta direita esquerda sobe desce` + PARALLAX (o fundo anda menos que os atores).
  O bonequinho segue o modelo dele: cabeça redonda, cabelo de tigela com faixa clara, olhos ovais grandes,
  sobrancelhas, boca sempre desenhada, mãos redondas e a roupa que a história pedir. Legenda: `*palavra*` sai colorida; sem marcação o
  `destaca()` escolhe (número primeiro). Desenhar por código mantém a série IGUAL em todo episódio e é instantâneo.
- VOCÊ MANDA NA CONTINUAÇÃO (22/out): no painel, antes de "Fazer o episódio N" dá para escolher **A venceu / B venceu**
  (em vez de contar os comentários) e escrever **o que acontece neste episódio** (ex.: "vi um viral e quero usar isso").
  O que você manda vale mais que a apuração e que a votação. Linha de comando: `--continuar a|b` e `--rumo "<texto>"`.
- PAINEL aba **Histórias** (`tools\painel\historias_painel.py`): criar série pela ideia, ligar/desligar, "Fazer o
  episódio N", assistir/baixar, capa, contar os votos, episódios por dia, duração, @ do rodapé, contexto da história,
  emoji da capa, "Ver e mexer no roteiro" (refazer ou usar como base), "Refazer capas + arte" e apagar a série.
  Faz sozinho 1x/dia (8–21 h), um por vez junto com canais e edição.

## Vídeo gravado COM o roteiro dele (padrão)

O Everton grava lendo um roteiro, mas muda as falas. Roteiro DELE sem tempos (roteiro de gravação, sem `[0:00 – 0:08]`/`[CAM] — TÍTULO`):
`editar.py` detecta (`tools/roteiro/tem_trechos.js`), guarda em `<job>\roteiro_seu.txt` e o `roteiro_ia.py --base` (Gemini → Claude)
monta o roteiro de edição SEGUINDO o dele com os tempos da fala; plano ainda falha → `roteiro_basico` (o anterior em roteiro_falhou.txt). `python tools\editar.py "<video>" --roteiro "<roteiro.txt>"`
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
- CAMPINHO (20/out): só é campinho o trecho com a FORMAÇÃO (≥2 linhas `[ NOME 6,1 ]`) ou que pede campo/formação/4-3-3; a vinheta
  do bloco sozinha não (antes saía um campo vazio). Título entre aspas com SELE/CAMPINHO/BAGRE/PIOR; BAGRE/PIOR = `worst`.
  Nota seguida de vírgula de frase ("5,6, e um cartão vermelho") vale (`NOTE` em componentes.js). Nome sem time (só no
  campinho) → `jogadores.py` procura nos elencos dos 20 times do banco (`time_pelo_banco`, único time).
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
