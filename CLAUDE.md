# DETTO — editor de vídeos do @detto.galo

**VOZ, GESTO E FOTO DA THUMB (o que só ele pode fazer): `VOZ-E-GESTO.md`** · **SOCORRO: `SOCORRO.md`** · **MAPA DO PROJETO: `MAPA.md`** (áreas, onde mexer em cada uma, qual registro ler, quem depende de quem).
Ele diz "mexe só nos REELS" e eu mexo só ali.

## 10/nov — SHORTS DE FUNCIONALIDADES DO GTA 6 (exemplo "o que vai ser o GTA 6")

- Referência que ele mandou (68 s, tela cheia, trailer/gameplay trocando a cada 2–3 s, legenda de 1–2 palavras BRANCA no meio, setas vermelhas): no tema `gta` a legenda agora é de 2 palavras, branca, a 60% da altura. `auto.reels_gta_meta`: um short sim, um não vira FUNCIONALIDADE (`--viral` + `--tema gta` → `ideias_funcoes_gta`, só o mostrado nos trailers/confirmado; `REGRAS_GTA_FUNCAO`: gancho, 1 detalhe por cena, busca do trecho daquela função). Voz = perfil detto. NÃO feito: setas vermelhas nos detalhes e VÍDEO LONGO horizontal de funcionalidades (próximo passo). Atenção: o exemplo tem marca d'água de outra conta — não copiar.

## 09/nov (noite) — NARRADO MAIS VIRAL, SEM CORTAR A PESSOA, 5 POR DIA NO DRIVE

- Ele mandou 5 exemplos (Haaland/Enzo, árbitro, Caracas, Gavi e a princesa): topo ~70% com planos de 2–3 s, rosto SEMPRE inteiro,
  legenda pequena com palavra amarela, história de bastidor; embaixo a reação dele.
- `pessoa.corta_plano`: antes era corte central (cortava o jogador). Agora `foco_do_plano` acha os rostos grandes (YuNet), a janela
  do corte é CENTRADA no rosto; se o rosto não cabe, entra o plano inteiro com fundo desfocado. Sem rosto = corte central. Testado.
- **CORREÇÃO (20:34, pedido dele)**: NADA de história inventada — o `--viral` pede só assunto viral REAL: possibilidade/projeção/opinião ("Estêvão na Copa de 2030") ou notícia quente. O narrado do Drive já sai 70/30 com REAÇÃO PROVISÓRIA: vídeo dele em `Narrados\reacoes\` ou fotos expressivas em `Narrados\fotos\` (trocam a cada 2,5 s; `reacao_generica`). Ele regrava e troca com `--montar` (usa o `(topo p-reagir).mp4`).
- **VOZ DO NARRADO (20:37)**: perfil VoiceStudio "detto" primeiro (`voz_narrado` no config do narrado muda) + `INSTRUCAO_NARRADO` (expressivo, energia alta). **LISTA DELE**: `Meu Drive\DETTO\Narrados\lista.txt`, um assunto por linha (# comenta), feito em sequência pelo `auto.narrados_meta` mesmo acima dos 5/dia; linha sai ao começar e volta ao topo se falhar.
- **PAINEL + CENAS (20:45)**: aba Reagir tem a **Lista de assuntos** (um por linha → `narrado_lista` grava `Narrados\\lista.txt`; o `auto.narrados_meta` faz um vídeo de cada, a qualquer hora, sem teto). O roteiro devolve `cenas` (frase inicial + sujeito + busca) e `pool_por_cenas`/`inicio_das_cenas` põem os clipes do SUJEITO de cada parte no segundo em que ela é falada (sem cenas = jeito antigo). A reação provisória vem de `Narrados\\reacoes` / `fotos`; execução manual do painel também passa `--drive`. NÃO conferido no PC dele.
- **TEXTO DO VÍDEO-FONTE, TÍTULO E NOME (21:03)**: `pessoa.faixas_de_texto`/`limpeza` acham texto queimado (letra branca/amarela com contorno escuro, em 2 de 4 quadros): na borda de cima/baixo CORTA fora, no meio BORRA a caixa — nunca em cima do rosto (painel de patrocínio atrás da pessoa dava falso positivo). Falhou = usa o plano sem limpar. O TÍTULO agora é como nos virais dele: caixa vermelha arredondada no pé do conteúdo, branca, 2 linhas, 6 s (`faixa_titulo`). Arquivos no Drive saem com o NOME DO TÍTULO (`<título>.mp4`, `<título> (topo p-reagir).mp4`, `.txt`), não `completo.mp4` (a pasta local mantém completo.mp4 porque o painel e a contagem usam).
- **EFEITOS DE DRIBLE (21:39, vídeo "Yamal, o novo Neymar" que ele mandou)**: `efeitos_de_lance` — quando a narração diz drible/caneta/chapéu/lance/golaço etc. (`GATILHOS_LANCE`), põe SETA amarela pulando sobre o jogador (plano aberto) ou ARO (plano próximo) + flash laranja de 0,12 s, até 5 por vídeo a ≥6 s um do outro. Posição: rosto (YuNet) → pessoa (HOG) → centro. NÃO feito: câmera lenta, zoom/blur de movimento. Testado só com recorte do vídeo dele.
- Legenda: sombra, contorno 8, número em verde, palavra-chave amarela. `--tema historia` (REGRAS_HISTORIA: gancho em 3 s, laço
  aberto, só fato público ou personagem fictício) e `--viral` (alterna história/curiosidade e notícia quente, `usados_virais.json`).
- `auto.narrados_meta`: `narrados_dia` 5 (7–22 h, `narrados_auto`, `narrados_seg` 55) → copia `<data> <título>.mp4` + `(topo p-reagir).mp4` + `.txt`
  para `Meu Drive\DETTO\Narrados`; conta pelo `no_drive.txt`; 3 falhas = pausa 1 h. NÃO vai para a fila de postagem. NÃO conferido no PC dele.

## 09/nov — GTA "SEM TRECHOS" E 30 SHORTS/DIA POR CANAL

- **GTA: o vídeo baixava, era transcrito e a rodada terminava "0 trecho(s)… sem trechos para montar"** (status.txt 11:53,
  cookies `logado: false`). Quando NENHUMA IA de texto respondia (`gemini_json` devolve None: cota/rede), `acha_trechos`
  devolvia [] e o laço marcava o vídeo como VISTO — queimado para sempre, o mesmo erro da coleta de 06/nov. Agora
  `IA_FALHOU`: log "⚠ NENHUMA IA de texto respondeu", o vídeo conta em `tentativas` e só na 3ª é abandonado. Se o
  registro mostrar esse aviso, o problema é a IA (chaves/cota), não o canal. Galo: "JÁ VISTOS"/short — sem notícia nova mesmo.
- **SHORTS 30/DIA EM CADA CANAL**: `auto.reels_gta_meta` virou gerador para GTA e Galo (6–23 h, alterna pelo mais
  atrasado; `shorts_dia` 30, `shorts_dia_galo`, `shorts_seg` 45, `shorts_auto`; contagem em `narrado\shorts_contagem.json`).
  Assunto = notícia mais nova do `historico.json` do canal (`usados_<canal>.json`); Galo cai nos portais (`--quente`)
  quando acaba. LIMITE: YouTube Shorts = 4/dia por conta (cota da API ~6 envios/dia no total); Instagram teste ~vagas.

- **"30/30 ok" ERA FALSO (09/nov 18:50)**: o auto contava o short ao COMEÇAR o processo; o narrado morria em segundos porque
  NENHUMA IA de texto respondia (Gemini sem cota + Claude "OAuth session expired" + sem chave grátis) → `roteiro()` levanta
  "a IA não devolveu narração". Agora o auto conta só se saiu `completo.mp4` novo, loga o motivo, 3 falhas seguidas =
  pausa de 1 h + alerta; `topo.mp4` de dias anteriores é apagado e abaixo de 4 GB livres os shorts param. A CAUSA RAIZ é a IA:
  no PC dele, `claude` no terminal (refaz o login) e/ou `GROQ_API_KEY`/`CEREBRAS_API_KEY` (grátis).

## 08/nov — RODADA DE NOTÍCIAS "TRAVADA" DEPOIS DE "vídeo montado"

- Causa provável: `vinheta.emenda` recodificava o vídeo INTEIRO (15 min, 1080p) no CPU com `libx264 -preset medium`,
  sem prazo e sem NENHUMA linha no registro (a vinheta já em cache não loga) — 60–108 min de silêncio e o relógio
  de 110 min matava a rodada. Agora NVENC (testado com 1 quadro) ou x264 veryfast, prazo de 25 min e log "vinheta:
  emendando...". canal.py também loga "thumb: começando/pronta (N min)" e "shorts: N para fazer". Se ainda demorar,
  a linha `TEMPOS:` + essas linhas dizem a etapa. **Mesmo assim ficou >23 min (20:24→20:47)**: agora `emenda_rapida` — corta no quadro-chave seguinte, recodifica só a vinheta (3 s) e junta com `-c copy` (segundos; testado 60 s+3 s = 63,06 s). `DETTO_EMENDA_LENTA=1` volta ao caminho antigo; falhou = cai nele. NÃO conferido no PC dele.

## 06/nov — A RODADA LENTA, OS FORMATOS, O SHOP COM VÍDEO E O "REAGIR"

- **VOZ 1,25x, TRADUÇÃO SÓ EM LÍNGUA ESTRANGEIRA E MODO LANÇAMENTO (06/nov, 22:49)** — **1** `velocidade_voz` padrão 1,25
  (config já existente: ajustar no painel, aba CANAIS, campo Velocidade; a velocidade agora entra na chave do cache da fala,
  senão a voz antiga a 1,0 era reaproveitada). **2 BUG DA TRADUÇÃO EM VÍDEO PT**: `legenda_youtube` pegava a 1ª faixa
  em ordem ALFABÉTICA — "en" (tradução automática do YouTube) vinha antes de "pt" e vídeo em português virava "EN", era
  traduzido e dublado. Agora `_prio`: faixa original (`-orig`) → pt → traduzidas; cache renomeado `.leg2.json`. Dublagem
  segue só para `idioma != pt`. **3 VOICESTUDIO COM LISTA VAZIA**: `voicestudio_pronto` não exige mais perfis listados
  (tenta o nome "everton"/`DETTO_VS_VOZ`). **4 MODO LANÇAMENTO** (18/11 por 7 dias, `lancamento_inicio` no painel.json):
  canal GTA roda de hora em hora (`canais.intervalo_min`) e `auto.reels_gta_meta` faz até 24 reels/dia (8–23 h, a cada
  ~2,5 min checa; 45 s; `reels_gta_dia`/`reels_gta_seg`/`reels_gta_auto`) com `narrado.py --tema gta --tela-cheia --fila`:
  assunto = a notícia mais nova já coletada pelo canal GTA (`historico.json`, `gta_usados.json`), voz dele, clipes do
  YouTube, 1080x1920 sem espaço de reação, direto na fila de postagem. NÃO conferido aqui: YouTube real, voz real.
  Cuidado: clipes de trailer/gameplay de terceiros podem levar Content ID — conferir os primeiros posts.

- **CAPAS: TESTE A/B SEM O ROSTO (06/nov, "vídeos do Galo pegam menos views com a minha foto")** — medi 228 vídeos do
  nicho Galo (`tools\yt\analise_capas.py`, razão = views ÷ mediana do PRÓPRIO canal, vídeos < 7 dias fora): capa CLARA 1,05x
  × escura 0,72x · número no título 1,15x · vermelho 1,12x · rosto enorme (≥5% da área) 0,90x · "VAZOU AGORA" repetido é o pior.
  Quem vence usa rosto FAMOSO + escudo + gancho curto ("CONFIRMOU?") + seta. **NÃO medi** o efeito da cara DELE (sem acesso ao
  analytics) nem TikTok/Shop (robô bloqueado; thumb do Shop não é pública). Por isso o canal.py agora RODIZIA 3 variantes
  (`thumb_variante` no config: `auto`|`rosto`|`gancho`|`tema`): **rosto** = controle (MANCHETE com a sua foto),
  **gancho** = quadro claro + manchete gigante + seta + escudo, SEM rosto, **tema** = igual, com a foto da pessoa do assunto
  (`busca_imagem`, `thumb_destaque`; sem foto cai no gancho). A variante vai em `post.json` (`thumb_variante`).
  Depois de 24 h+: `python tools\yt\capas_ab.py --pasta E:\DETTO\canal_galo` → views/hora por variante (mediana; avisa se <5 vídeos).

- **SHOP: PRODUTO PELO NOME, SÓ IMAGEM DO PRODUTO CERTO, CORTES RÁPIDOS, BOTÕES (06/nov, "aleatórios, imagens nada
  a ver, não compassado")** — **1 RELEVÂNCIA**: `clipes_web.titulo_do_produto`: o título do vídeo-fonte tem de citar o
  produto (nome de 1–2 palavras: todas, a marca tem de aparecer; 3+: dois terços) — "Avanuv fone bluetooth" e
  "melhor travesseiro 2026" não servem para "Travesseiro Avanuv". Sem vídeo do produto certo = cai nas fotos, e sem
  foto NÃO entrega (não inventa imagem). **2 PELO MENOS 3 VÍDEOS** de origem (`min_videos`, no máx. ~4 clipes por
  vídeo), clipes de 2,6 s sem rosto, intercalados A,B,C,A… **3 COMPASSO**: `base_visual` quebra cada cena em cortes de
  ~2,4 s de clipes diferentes, punch-in 1,14x nos ímpares e cor mais viva (`eq`), em vez de 1 clipe em loop.
  **4 `--nome "Travesseiro Avanuv"`** (painel: "2. Produto pelo NOME" → ▶ Montar). **5 BOTÕES** na aba Shop:
  *Criação automática* (`"auto"`, desliga o `shop_meta` do auto.py), *Legenda* (`"legenda"`) e *Narração*
  (`"narracao"`; desligadas = vídeo só com imagem/cartelas/música para ele narrar). `--sem-narracao`/`--sem-legenda`
  na linha de comando. **6 AUTOMÁTICO** agora usa NOMES, não links: `viral_shop.py` lista Shorts de achadinho,
  a IA tira o NOME do produto de cada título (só produto físico específico) → `produtos_nomes.txt`, e o painel roda
  `shop.py --nomes-lista` — antes o link do short virava o vídeo (com gente e de outro criador). PAINEL_VERSAO/
  VERSAO_TELA 2026-11-06f. NÃO conferido aqui: YouTube real (montei com clipes sintéticos: 9 s de cena viraram os
  cortes certos, 1080x1920, cartela por cima); o filtro de título foi testado com 4 títulos.

- **AUTOMÁTICO DO PAINEL (06/nov, "quero que faça isso automático")** — `tools\painel\auto.py`, uma thread do
  painel (`painel.json` > `"painel"`: `auto_atualizar` true, `alerta_rodada_min` 60, `shop_auto` true,
  `shop_meta_dia` 30). **1 RELATÓRIO**: a cada 5 min grava `status.json`/`status.txt` em `<Meu Drive>\DETTO\status`
  (commit, canais: rodando há N min/último problema do log/últimas linhas, fila, disco, yt-dlp, cookies, Shop
  prontos hoje) — é o que a tarefa agendada do Claude lê. **2 ALERTAS** (Telegram/Discord via `viral.avisa`,
  1x por janela): rodada > 60 min, "NÃO RODEI"/Traceback/SEM VOZ novo, disco < 8 GB, atualização feita/revertida.
  **3 ATUALIZA SOZINHO** a cada 30 min: `git fetch`; atrasado + NADA rodando (canal, fila, Shop, edição, postagem)
  + sem arquivo alterado à mão → `pull --ff-only` → `teste_rapido.py` → reprovou = `reset --hard` na versão de
  antes + aviso; passou = `.ultima_boa` + `os._exit(7)` (o painel reabre pelo atalho do Windows). **4 TEMPO POR
  ETAPA** no canal.py (`_etapa`): no fim de toda rodada o canal.log tem a linha `TEMPOS: baixando 31 min · …`
  — é por ela que se acha o gargalo da rodada de 78 min do GTA. **5 SHOP 30/DIA**: `shop_meta` (a cada 2 min,
  PC livre): faltando vídeo, completa o `produtos.txt` com `tools\shop\viral_shop.py` (YouTube Shorts de
  achadinho por categoria, acima da mediana de views, 1 categoria de cada vez) e roda `shop.py --so-links`
  em lotes de 3; cada vídeo registra `⏱ vídeo N pronto em X min`. Canal em fila espera o Shop (e vice-versa).
  **6 SERVIDOR**: `tools\viral\servidor.py` (+ `detto-viral.service`) roda viral.py a cada 20 min e viral_shop a
  cada 6 h num Linux, sem painel. NÃO conferido aqui: YouTube real, TikTok (o TikTok não deixa robô listar —
  "viral" do Shop é o do YouTube Shorts); postar no TikTok em modo "studio" continua MANUAL (gargalo dos 30/dia).

- **"0 VÍDEO(S) DE HOJE" COM VÍDEO DE GTA EM TODO CANAL (06/nov, 09:13 e 09:59): A COLETA QUEIMAVA OS VÍDEOS.**
  `coleta()` gravava `hist["vistos"]` ANTES do download. Rodada com download barrado pelo YouTube (o
  cookie/robô da noite) = os vídeos marcados como vistos para sempre; toda rodada seguinte via a lista
  inteira "já vista", descartava calada e terminava "coleta: 0". Agora: a coleta NÃO marca; o laço de
  download marca só depois de baixar e ler (`acha_trechos`), falha de download conta em `hist["tentativas"]`
  e só na 3ª o vídeo é abandonado; migração única (`vistos_v2`) devolve os vistos dos últimos 3 dias que
  nunca viraram trecho. `considera` agora diz POR QUÊ descarta ("descartados: Sanin Play: duração 150 min 1"
  — antes `max_min_fonte` 120 eliminava gameplay longo em silêncio) e vídeo já visto nem gasta a medição de
  duração (3 chamadas por canal por rodada). Preset gta6 `fontes_versao` 8: IGN e GameSpot (gringos,
  `filtro gta`) + 4 buscas em inglês. Conferido com lista falsa (visto pulado, 150 min recusado com motivo,
  coleta sem marcar). NÃO conferido aqui: o YouTube real.

- **REAGIR: O ASSUNTO TEM DE APARECER E O CORTE É O DO VÍDEO (06/nov, ele mandou topo.mp4/completo.mp4 do
  CR7 e disse "o cr7 não aparece sempre... cortes não corretos").** Quadro a quadro: 13 dos 30 primeiros
  pedaços eram UM programa de TV (duas pessoas + tarja e letreiro deles), o resto a final da Euro 2016 com
  o CR7 em 2 planos, e o corte era em blocos fixos de 2,2 s atravessando troca de câmera. Novo
  `tools\narrado\pessoa.py`: **(1)** a IA devolve `sujeito`/`apelidos`/`sujeito_pessoa` e TODA busca leva o
  nome dele (+ "melhores momentos/gols e jogadas/entrevista"); título do vídeo-fonte tem de citar o sujeito
  e não pode ser react/podcast/debate/ao vivo/jogo completo. **(2)** reconhece o ROSTO: baixa até 4 fotos da
  pessoa (`busca_imagem`, 1 rosto), SFace do OpenCV (`sface.onnx`, 37 MB, baixado 1x do Hugging Face para a
  raiz; limiar de cosseno 0,363) e classifica cada plano em `sujeito` / `contexto` (jogo, torcida) / jogado
  fora (tela preta, close de OUTRA pessoa, 2+ rostos grandes = podcast). Sem o modelo/sem fotos: avisa no
  registro e filtra só por título e close. **(3)** o corte é nas TROCAS DE PLANO reais (`select=gt(scene,0.28)`):
  cada clipe é UM plano inteiro (1,4–2,8 s), nunca atravessa duas câmeras; vídeo sem cortes cai em blocos
  de 2,2 s. **(4)** no máximo 5 planos por vídeo-fonte, nunca 2 seguidos do mesmo vídeo, a linha do tempo
  começa no sujeito e mantém ~2 de cada 3 planos com ele. Conferido com vídeo sintético (astronauta = sujeito,
  Grace Hopper = outra pessoa, as duas juntas = podcast, campo, tela preta): cortes nos 8 limites certos e as
  8 classificações certas. NÃO conferido aqui: a busca no YouTube real e a taxa de acerto do SFace com fotos
  de futebol (o sandbox não abre o YouTube) — depende do primeiro vídeo dele; o registro mostra "N planos
  bons (M com o assunto); descartei ..." por vídeo-fonte.

- **O QUE FAZIA A RODADA DO GTA LEVAR UMA ETERNIDADE: `-J` SEM `--flat-playlist`.** O `videos_ytdlp`
  pedia a lista de cada canal com `-J`, e isso **ABRE OS 8 VÍDEOS INTEIROS**, um a um — 7 canais = 56
  extrações completas por rodada, cada uma passando pelo desafio "n" do YouTube. A LISTA é de graça; o
  caro é abrir vídeo. Agora são DUAS ETAPAS: `--flat-playlist --dump-json` traz id/título/duração numa
  requisição leve, e só os vídeos que o canal **ainda não viu** (`pular=hist["vistos"]`, no máximo 3 por
  canal) ganham a extração completa — **todos numa chamada só** do yt-dlp, porque o custo de abrir um
  processo no Windows é alto. Num dia comum são 0 ou 1 vídeos novos por canal em vez de 8. Conferido com
  uma saída falsa do yt-dlp: 2 chamadas por canal, 3 vídeos abertos em vez de 8. E as fontes passaram a
  ser consultadas **4 ao mesmo tempo** (ThreadPoolExecutor): é espera de rede, não trabalho do PC, então
  a rodada passa a levar o tempo do canal mais lento, não a soma de todos. Cada canal registra
  "N na lista, abri M (Xs)" — é por aí que se vê qual está lento.
- **O OUTRO GARGALO, NO GALO: A TRANSCRIÇÃO.** `legenda_antes_de_transcrever` existia e estava ligado só
  no GTA — o Galo transcrevia no whisper os 8 vídeos de 10 a 25 min de toda rodada. Agora o
  CONFIG_PADRAO tem a chave (`legenda_langs` "pt.*,pt") e `fontes_versao` 6 leva isso ao config que já
  está no PC dele. A proteção é a mesma de sempre: legenda com menos de 60 palavras, ou que cubra menos
  de 50% do vídeo, é RECUSADA e o whisper entra — legenda picada não serve para cortar no fim da frase.
- **O GAMEPLAYRJ NÃO ERA ACHADO porque a lista rápida não traz DESCRIÇÃO.** O filtro `gta` exigia a
  palavra "GTA" no título+descrição; num canal que só fala disso, "ROCKSTAR MOSTROU LUCIA E JASON" é o
  vídeo do dia e não tem a palavra em lugar nenhum. Entraram os SINAIS: `rockstar`, `vice city`,
  `leonida`, `lucia caminos`, `jason duval`.
- **TETO DE TEMPO NA BUSCA** (`max_min_busca`, 4 min) e `max_canais_busca` (5): cada canal novo achado
  pela busca por data dispara uma listagem pesada. Passou do teto, segue com o que achou.
- **ASSUNTO REPETIDO** (o South Park voltou dias depois): `dias_ja_postado` 7 no GTA (era 3 fixo no
  código), `titulo_parecido_max` 0,4 → 0,3 e `parecido_max` 0,8 → 0,6.
- **FORMATOS COM BOTÃO** (`FORMATOS` + `escolhe_formato` no canal.py; painel, card GTA 6): `noticias`
  (o de sempre), `documentario` (estilo Dulebio: barra de capítulo, tela cheia sem máscara, até 5
  trechos de 45 s) e `cartoes` (estilo Gigaton: até 6 trechos de 25 s). `"formato": "auto"` faz o
  RODÍZIO — pelo menos um de cada por dia, olhando o `formato` gravado no `post.json` dos prontos de
  hoje. Os cartões com número grande ("212GB") ainda NÃO existem: hoje o formato muda ritmo e tamanho
  de trecho, e isso está dito a ele.
- **SHOP COM VÍDEO DE VERDADE** (`tools\shop\clipes_web.py`, pedido dele): foto parada com zoom tem cara
  de anúncio velho; o que vende é o produto SENDO USADO, e todo produto popular tem review no YouTube.
  O módulo busca, baixa **só um pedaço do meio** (o começo é o apresentador falando), corta em pedaços
  de ~4 s em 1080x1920 e **DESCARTA os que mostram rosto** (YuNet, o mesmo detector do canal) — rosto de
  terceiro no anúncio dele é o que mais estragaria. Conferido: com a foto de teste do OpenCV (rosto
  humano real) todos os pedaços foram descartados; com imagem sem gente, todos passaram. Ligado por
  `"clipes_internet"` (painel: "Buscar vídeos do produto na internet"). A gravação DELE sempre vem na
  frente. Junto: `"narracao": false` monta o vídeo **sem narração** (só imagem, cartelas e música), para
  ele narrar por cima — aí o tempo das cenas vem da `duracao` alvo, repartido pelo texto de cada cena.
- **NOVO `tools\narrado\` — "REAGIR"** (painel: aba **Reagir**): assunto quente (os feeds do viral.py) →
  a IA escreve a narração → a VOZ DELE narra → **clipes de vídeo de verdade** na tela → `topo.mp4`
  (1080x1344, é o que ele abre para gravar a reação olhando) e `completo.mp4` (1080x1920).
  **TUDO MEDIDO NOS 3 VÍDEOS QUE ELE MANDOU**, não chutado: o corte entre conteúdo e reação fica em
  68% / 72% / 68% da altura (**uso 70%**); o clipe de cima troca a cada **2,2 s** (30 cortes de cena em
  67 s e 33 em 73 s, medidos com `select=gt(scene,0.30)` só na faixa de cima); a narração corre a
  **192 palavras/min**; a legenda é de 1 a 3 palavras em caixa alta, contorno preto grosso, com a
  palavra-chave em amarelo. A primeira versão (foto parada por frase) ESTAVA ERRADA e ele disse isso na
  hora — o que prende no formato é o vídeo trocando rápido.
  **COMO TER 25 CLIPES SEM BAIXAR 25 VÍDEOS**: baixa um pedaço de 3 vídeos sobre o assunto e corta cada
  um em pedaços de 2,2 s (um vídeo de 75 s rende 30). Aqui os clipes MOSTRAM gente DE PROPÓSITO — o
  jogador e o técnico são a notícia —, então `clipes_web.corta_sem_rosto` ganhou `sem_rosto=False`; no
  Shop continua `True`, porque lá a cara de outra pessoa no anúncio é o que estragaria.
  A legenda é sincronizada pela transcrição da própria narração e, se ela falhar, o tempo é repartido
  pelo tamanho das palavras — nunca fica sem legenda. Legenda em PIL e não `drawtext` (que não quebra
  linha nem pinta uma palavra de outra cor); passando de uma linha, ela QUEBRA em duas em vez de cortar
  na borda. Todas as legendas entram num `filter_complex` só, num passe de vídeo.
- **VIDEO STUDIO — o que o hardware deixa e o que não deixa.** O "JSON inválido" dos workflows era BOM:
  `Set-Content -Encoding UTF8` do PowerShell põe 3 bytes invisíveis no começo e
  `read_text(encoding="utf-8")` engasga neles. O painel passou a ler em `utf-8-sig`, avisa quando o JSON
  é o da TELA do ComfyUI em vez do "Save (API Format)", e ganhou `/api/resultado?id=`. MEDIDO na 3050 de
  4 GB: LTXV 2B, 49 frames, 8 passos = **6 s de geração e ~90 s por clipe** (o resto é recarregar 4,6 GB
  de T5 a cada execução, porque 4 GB de VRAM não seguram tudo) — por isso o lote, que enfileira de uma
  vez. **TEXTO→VÍDEO NÃO SERVE PARA PRODUTO**: o modelo INVENTA um produto parecido, com rótulo sem marca
  e escrita errada, e isso não é ajuste — é o tamanho do modelo que cabe em 4 GB. O caminho certo é
  **IMAGEM→VÍDEO** (`LTXVImgToVideo`): a foto REAL do produto é o primeiro quadro e o modelo só cria o
  movimento, então a marca fica certa porque é a foto dele. O vídeo "Achado do GitHub #8" que ele mandou
  sugere o "Open Higgsfield" como alternativa grátis ao Higgsfield — **ele não roda local**: é uma
  interface que chama uma API paga, e o próprio narrador diz isso aos 58 s ("o estúdio é de graça, mas
  cada geração você paga na chave da plataforma"). Dos 9 achados do vídeo, dois o sistema JÁ usa:
  VoiceStudio (voz) e Whisper (transcrição).
- `doutor.py` morria com `UnicodeEncodeError` ('charmap' não tem "←") no console do Windows — justamente
  quando ele tentava descobrir por que o resto morreu. Agora reconfigura o stdout para UTF-8 e, se nem
  assim der, troca os caracteres. A espera pelo Claude caiu de 180 s para 60 s. E o `ATUALIZAR.ps1`
  parou de ENGOLIR o erro do pip (`| Out-Null`): sem internet a atualização "passava" e só aparecia
  horas depois, como download falhando no canal.

## QUANDO O SISTEMA PARA (29/out) — rede de proteção

- **O QUE ESTAVA DERRUBANDO OS VÍDEOS DEPOIS DE POSTADOS (05/nov) — IMAGEM DE JOGO.** Os vídeos do canal
  de notícias eram bloqueados DEPOIS da postagem, e o único que escapou foi justamente o que não tinha
  imagem de imprensa nenhuma. O print da reivindicação fechou o diagnóstico: era um lance de **Atlético de
  Madrid x Bayern pela Champions, imagem da TNT Sports**, que entrou pelo bloco "a volta pelo mundo".
  Transmissão de futebol é o conteúdo mais protegido que existe — o Content ID bloqueia NO MUNDO INTEIRO,
  em segundos, e crédito, comentário e trecho curto não protegem nada. Três consertos:
  **1 `tem_campo()`** — fala de estúdio e lance de jogo são fáceis de separar: a transmissão é um plano
  aberto do GRAMADO, uma mancha verde que ocupa metade da tela. Eu meço o verde em 6 quadros (HSV 35-85) e
  o trecho com gramado em metade deles NÃO ENTRA no vídeo. Medido: transmissão 0,76 · estúdio 0,00 ·
  estúdio com telão verde atrás 0,14 — o limite de 0,42 fica no meio, com folga. `"recusa_lance": false`
  desliga. O trecho recusado é marcado como usado: guardar para a próxima rodada não adianta, continua
  sendo lance.
  **2 o título que anuncia lance nem é baixado**: "melhores momentos", "todos os gols", "gols do/da",
  "highlights", "compacto do jogo", "assista aos gols" entraram no `fora`.
  **3 SABER DO BLOQUEIO SEM OLHAR NA MÃO** (`comum.confere_postados` + `youtube_up.situacao`): o painel
  pergunta ao YouTube, de meia em meia hora, como estão os vídeos dos últimos 3 dias.
  `status.rejectionReason` diz se foi `copyright`/`claim` (reclamação) ou `duplicate` (o mesmo vídeo já
  estava no canal) — os DOIS casos aconteceram com ele no mesmo dia — e `regionRestriction.blocked` pega a
  reclamação parcial (no ar lá fora, bloqueado no Brasil, que dá no mesmo). O card mostra "⛔ O YouTube
  DERRUBOU este vídeo" com o motivo e as FONTES daquele vídeo, e o `historico.json` conta quantas vezes
  cada fonte derrubou (`bloqueios`): depois de alguns, dá para ver qual canal-fonte sempre derruba e tirar
  da lista. Medir em vez de adivinhar, como o resto do sistema.

- **POR QUE O GALO BAIXAVA E O GTA NÃO (05/nov) — a mesma máquina, o mesmo yt-dlp.** A diferença estava no
  config: as fontes do Galo têm `"id"` do canal, então a hora vem do FEED (uma requisição HTTP simples, sem
  yt-dlp nenhum). As do GTA 6 não tinham ID — então TODA rodada fazia uma extração PESADA do yt-dlp em 7
  canais, e com ele clicando "Rodar agora" de 10 em 10 min isso vira centenas de chamadas por hora. O
  YouTube então responde "Sign in to confirm you're not a bot" e aí NEM os canais respondem NEM o download
  funciona: **o canal estava envenenando o próprio IP**. Era por isso que os 7 diziam "o canal NÃO
  RESPONDEU" e nenhum dos 3 vídeos baixava. Consertos: os 7 IDs entraram no preset (conferidos um por um
  em 05/11; cada feed devolveu 15 vídeos), `acha_channel_id()` descobre o ID de qualquer canal novo com UMA
  requisição leve e passa a usar o feed, e `ultimos()` só cai no yt-dlp pesado como último recurso.
- **VÍDEO SÓ COM A ABERTURA E O FECHAMENTO (05/nov)**: o canal de notícias entregou um vídeo sem notícia
  nenhuma no meio. `monta()` sempre põe a 1ª e a última fala, e o laço do meio é sobre `sel` — com `sel`
  vazio sobram as duas falas. A única guarda que existia era a de DURAÇÃO, e o `--forcar` (que é o que o
  botão "Rodar agora" manda) passava direto por ela. Agora há um PISO que o `--forcar` não fura:
  `min_trechos_video` (1) e `min_imprensa_s` (45) — sem isso a rodada termina com "NÃO RODEI" dizendo se
  foi porque os vídeos não baixaram ou porque não havia notícia. `--forcar` serve para não esperar mais
  material, não para montar sem material nenhum.
- **BOTÃO DO LOGIN DO YOUTUBE (05/nov, pedido dele: "quero um botão")** — `tools\postar\cookies_youtube.py`
  + painel, aba CANAIS, no topo. O Chrome novo guarda os cookies com a criptografia da conta do Windows
  (App-Bound Encryption) e o yt-dlp não lê (`Failed to decrypt with DPAPI`); a extensão funciona mas é ele
  quem exporta na mão e o arquivo vence. Aqui o navegador é NOSSO (o Chromium que já vem com o Playwright),
  com PERFIL PERMANENTE em `<DETTO>\postar\perfil_youtube`: ele entra na conta UMA VEZ na janela que abre,
  e daí em diante o painel reexporta sozinho (`--atualizar`, 1x por dia, sem janela e sem login). O arquivo
  sai em `<DETTO>\cookies.txt`, que é onde o `cookies_do_pc()` procura. Dois detalhes que decidem se o
  arquivo é aceito ou ignorado em silêncio: o separador é TAB, e cookie de SESSÃO com `expires=0` é
  DESCARTADO por quem lê — e o de sessão é justamente o que prova o login, então ele ganha validade de 1
  ano. Conferido: o `YoutubeDLCookieJar` do próprio yt-dlp leu os 4 cookies do arquivo gerado, e as linhas
  de outro domínio (Instagram) que já estavam lá foram preservadas.

- **O DPAPI QUE ESCONDIA O MOTIVO DE VERDADE (05/nov) — era isso que impedia o vídeo do dia.** Todo
  download terminava em `ERROR: Failed to decrypt with DPAPI` e a rodada acabava em "sem trechos para
  montar". O DPAPI não era o motivo: `baixa()` tenta 4 degraus (sem cookies → firefox → chrome → edge) e
  guardava só o ÚLTIMO erro — o do Edge, que é o DPAPI do Chrome novo (App-Bound Encryption, o yt-dlp não
  abre). O erro da PRIMEIRA tentativa, o que explicava tudo, era jogado fora. Conferido aqui rodando o
  yt-dlp: o motivo real é **"Sign in to confirm you're not a bot"** — e ESSE se resolve com cookies.
  Consertos: `cookie_quebrado()` separa "não consegui LER os cookies" de "o download falhou" e a mensagem
  final diz o motivo REAL, listando os cookies ilegíveis só no fim; `cookies_do_pc()` acha sozinho um
  `cookies.txt` (pasta do canal, `E:\DETTO`, postar, reels); degrau novo **cliente da TV**
  (`player_client=tv,web_safari,mweb`) ANTES dos navegadores, que passa sem cookie e não depende do DPAPI;
  e a rodada em que NENHUM vídeo baixou termina com "NÃO RODEI: o YouTube pediu login em TODOS os N
  vídeos" + como resolver, em vez de "(ok)" no painel.
  **O que resolve de vez no PC dele: Firefox instalado e logado no YouTube** (não usa DPAPI, não vence);
  ou a extensão "Get cookies.txt LOCALLY" → `E:\DETTO\cookies.txt`.
- OS 7 CANAIS-FONTE DIZENDO "nada novo" (05/nov) na MESMA rodada em que a busca por data achava 4 vídeos
  de hoje — inclusive do @SaninPlay, que está na lista. Duas causas: **1** o feed do YouTube RESPONDE, mas
  com lista ATRASADA, e o código só caía no yt-dlp quando o feed vinha VAZIO — então a lista velha era
  aceita e o vídeo de hoje nunca aparecia (`ultimos(..., desde=)` agora confirma no yt-dlp quando o feed
  não traz nada depois da janela: custa uma chamada exatamente no caso em que eu ia desistir de graça).
  **2** `@Voxel` NÃO EXISTE ("This channel does not have a videos tab"); o canal é **@VOXELOFICIAL**.
  E o registro passou a separar "o canal NÃO RESPONDEU (confira o @)" de "nada novo (o último é de ...)",
  que eram a mesma frase e por isso ninguém viu o @ errado.
- RODADA LENTA E RODADA PRESA (02/nov; 4 h parada, nenhum vídeo no dia): **1** `enc()` nunca usava NVENC —
  20 min de 1080p com desfoque e 3 sobreposições na CPU do notebook, com a RTX 3050 parada do lado. Agora
  ele CODIFICA 1 quadro de teste de verdade (listar em `-encoders` não prova nada: o render morria com
  "Cannot load libcuda.so.1" no meio) e usa a placa quando ela responde; `DETTO_SEM_NVENC=1` força a CPU.
  **2** `log()` escreve a HORA em cada linha e cada peça diz quanto levou — o silêncio das 10:15 às 14:03
  era justamente o render das peças, que não registrava NADA, e por isso "parado" e "demorando" eram a
  mesma coisa no registro. **3** `ff()` põe hora marcada em cada peça, na emenda e no nivelamento, e
  `relogio_da_rodada` encerra a rodada passados 110 min (`"max_minutos_rodada"`), soltando a trava — a
  mesma lição do download de live: nada neste sistema roda sem prazo. **4** `onde_estou` media TODAS as
  peças anteriores a cada notícia (~300 ffprobe num vídeo de 20 min); agora mede cada uma uma vez.
- FEED DO YOUTUBE MORREU (29/out) — era por isso que o canal não criava NADA: o `feeds/videos.xml` passou a
  devolver 404/500 até para ID CERTO de canal, e sem a HORA do vídeo a rodada descartava tudo e terminava
  "0 vídeo(s) de hoje". Agora `ultimos(id, @canal)` tenta o feed e, falhando, pega pelo **yt-dlp**
  (`videos_ytdlp`: hora, duração, tipo e descrição em ~2 s por canal) — e nem precisa mais do ID do canal,
  só do @. O registro diz quando a volta foi usada.
- VOZ ROBÓTICA (29/out): sem VoiceStudio e com a chave do Fish recusada só sobrava o Chatterbox (sotaque de
  Portugal, HORAS de render). Entrou um degrau: **voz NEURAL pt-BR da Microsoft** (`edge_fala`, edge-tts, de
  graça e sem chave, pronta em segundos). A ordem agora é **VoiceStudio → Fish → neural pt-BR → Chatterbox**,
  no canal de notícias, no GTA 6, nas histórias e no shop. `--voz-edge`/`"voz_neural"` troca a voz
  (`pt-BR-AntonioNeural` padrão, `pt-BR-FranciscaNeural` feminina); `--sem-edge`/`"sem_voz_neural"` desliga.
  A SUA voz clonada continua sendo a primeira opção — ela só sai com o VoiceStudio aberto.
  POR QUE A NEURAL SOAVA ROBÓTICA (30/out): não era a voz — era o `sem_pausas` esmagando TODA pausa dela para
  0,13 s. Isso foi feito para o Chatterbox/Fish, que deixam ar morto; a neural já respira certo e, atropelada,
  vira robô. Agora a fala que saiu da neural usa pausa mínima de 0,30 s (`DETTO_PAUSA_NEURAL`) e ela fala com
  +4% de ritmo e +2Hz de tom (`DETTO_PITCH_NEURAL`).
- PRESET INCOMPLETO DERRUBAVA O CANAL (29/out): o `gta6` trocava algumas chaves e não tinha as outras
  (`KeyError: 'voz_ref'` na primeira linha da rodada). Agora cada preset é o `CONFIG_PADRAO` COM as trocas
  dele (`{**CONFIG_PADRAO, **GTA6}`): nenhuma chave some.
- A VOZ QUE NÃO SAI PARA A RODADA COM O MOTIVO (29/out): `SemVoz` no canal.py → "NÃO RODEI: ..." no registro
  (o painel mostra essa linha), em vez de um `CalledProcessError` com traceback.

- TRAVA PRESA DERRUBA TUDO EM SILÊNCIO (29/out): um `canal.py` que travou e ficou VIVO (preso desde 20/10 no PC
  dele) fazia toda rodada seguinte morrer na hora, e o painel só dizia "rodada terminou (ok)" — nenhuma notícia era
  criada por 9 dias. Agora `trava_rodada` ESCREVE pid e hora dentro do arquivo da trava, `dono_da_trava` lê, o
  canal.py registra "NÃO RODEI: outro canal.py está com a trava (pid=..., desde ...)" e o painel mostra o aviso
  vermelho com o botão **Destravar** (`canal_destravar` → taskkill no processo preso). O `doutor.py` também mostra.
- VOICESTUDIO "FECHADO" COM O APP ABERTO (29/out): o teste batia só em `127.0.0.1:3900/v1/models`. Agora
  `_vs_responde` tenta vários caminhos (`/v1/audio/voices`, `/v1/models`, `/health`, `/docs`, `/`) e, se nada
  responder no endereço do config, PROCURA nas portas conhecidas (3900, 8000, 7860, 5000, 8080, 3000, 8188) —
  achando, passa a usar aquela porta na rodada (`VOICESTUDIO_ACHADO`) e diz no registro qual era.
- DRIVE MUDO (29/out): `traz_do_drive` saía calado quando não achava `<Meu Drive>\DETTO\canal_noticias` — a
  máscara e a voz nunca chegavam e o painel só dizia "nenhuma gravação". Agora o registro diz onde procurou e o
  que criar.
- CANAL SEM MÁSCARA/VOZ NÃO RODA MAIS À TOA (29/out): sem gravação em `mascara\` ou sem `voz\minha_voz.wav` a
  rodada ia até o fim e terminava "(ok)" sem entregar nada. Agora ela PARA no começo dizendo o que falta e onde
  subir no Drive. (`DETTO_VOZ_FALSA=1` pula a conferência, para testes.)
- `NameError: name 'cheia' is not defined` DERRUBOU O CANAL (01/nov): a tela cheia (30/out) deixou `not cheia`
  em DUAS funções que não têm esse parâmetro (`peca_fala`, a SUA narração, e o short vertical). O arquivo
  importava normalmente, então o `teste_rapido.py` passava — o erro só estourava quando aquela função rodava,
  **depois de 24 min de transcrição**, e o registro terminava em Traceback. Só o pyflakes do GitHub pegava.
  Agora `teste_rapido.py` tem `confere_nomes()` (pyflakes dentro do teste: "undefined name" e chave de
  dicionário repetida), então isso não sai mais do PC. `pyflakes` entrou no requirements.txt.
  Junto: `regra_nota` era montada e NÃO entrava no prompt (a regra medida dos títulos não valia de nada) e o
  preset gta6 tinha `max_videos_rodada` duas vezes (8 e 4).
- FISH 400 NO SHOP E NAS HISTÓRIAS (01/nov): esses dois mandavam `FISH_VOZ` (variável que não existe, string
  vazia) como `reference_id` → `400 reference_id must be 1..=128 chars` em TODA fala, caíam na voz neural e o
  registro só dizia "o Fish falhou". Agora `voz.fish_voz_dele()` procura a sua `voz\minha_voz.wav`
  (canal_galo → canal_gta6 → `<DETTO>\voz`) e clona uma vez, igual ao canal. `FISH_VOZ` posto na mão continua
  valendo.
- PAINEL DEMORANDO PARA ABRIR (01/nov): o `main()` preparava as pastas em `E:\` e o Drive ANTES de abrir a
  porta, então o navegador subia em branco por segundos. Agora a porta abre primeiro e o resto vem depois.
- BOTÃO "RODAR AGORA" QUE NÃO IA E CANAL QUE PAROU DE RODAR SOZINHO (01/nov): o `roda_agora` disparava o
  canal.py, gravava `ultimo=agora` e devolvia "ok" na hora. Se o filho morresse em 1 s (trava presa, sem
  máscara/voz, SemVoz, erro de código), o botão dizia que começou, nada acontecia **e o `ultimo` já estava
  gravado — então o AUTOMÁTICO só tentaria de novo 2 h depois**, repetindo isso o dia inteiro em silêncio.
  Agora ele (1) confere a TRAVA antes e manda usar o Destravar, (2) espera 2,5 s e, se o processo já morreu,
  lê o MOTIVO no registro (`_por_que_parou`: a linha com "NÃO RODEI"/"SEM VOZ"/Traceback), devolve esse motivo
  como erro do botão, guarda em `painel_canal.json` (`erro`/`erro_em`, que o card mostra) e marca o `ultimo`
  para TENTAR DE NOVO EM ~10 min em vez de 2 h.
- FILA DE ESPERA DOS CANAIS (01/nov, pedido dele): cabe UMA montagem por vez (voz + render comem o PC), mas
  clicar "Rodar agora" com outra rodando **não fazia nada** — `roda_agora` só devolvia erro e o clique parecia
  não ter pegado. Agora o canal entra na `ESPERA` (`_enfileira`) e o laço o começa SOZINHO quando o atual
  termina — a fila na mão passa na frente do automático. O card mostra "Nº na fila de espera" + **Sair da fila**
  (`canal_sair_da_fila`), o botão devolve a frase ("GTA 6 está trabalhando agora. Notícias entrou na fila…") e
  `estado()` manda `na_espera`, `montando` e `espera`. Edição rodando também enfileira (`EDICAO_OCUPADA`).
- **O QUE REALMENTE TRAVOU TUDO (01/nov): O DOWNLOAD DE UMA TRANSMISSÃO AO VIVO.** O registro das 18:16 para
  em `baixando: 🔴 Grêmio x Atlético-MG - Copa do Brasil` e nunca mais sai de lá. O `ytdlp()` rodava
  `subprocess.run` **SEM timeout**, e um live NÃO TEM FIM: a rodada ficou presa para sempre, segurando a trava,
  e todas as seguintes morreram com "outro canal.py está com a trava". Três consertos:
  **1** `ytdlp(..., timeout=600)` e `baixa(..., timeout=1200)` — passando disso, o yt-dlp é encerrado e o
  registro diz "passou de Ns e foi encerrado (transmissão ao vivo ou vídeo gigante?)". Nenhuma rodada pode mais
  ficar presa para sempre.
  **2** `--match-filter "!is_live"` no download: ao vivo nem começa a baixar.
  **3** `"fora_sinais"` (🔴, pré-jogo, pós-jogo, "assista agora") conferido SEM limite de palavra — o `fora`
  usa `\b...\b` e um emoji nunca casaria com isso, e era por isso que "🔴 Grêmio x Atlético-MG" passava: o
  título não tem as palavras "ao vivo" nem "live". `_tipo == "live"` também barra.
- **DESTRAVAR AGORA SEMPRE RESOLVE (01/nov, pedido dele: "era só clicar e fazer, quero que seja assim")**: com
  a trava presa e SEM pid anotado, o botão dizia "não tinha trava presa" e o canal ficava morto até ele caçar o
  processo no Gerenciador de Tarefas. Agora `destrava` vai em ordem: pid morto → apaga a trava; pid vivo →
  encerra; **sem pid → `_processos_do_canal` acha o python.exe que está rodando o `canal.py` daquela pasta
  (Win32_Process/CommandLine; a pasta na linha é o casamento certo, mas sem ela um canal.py ainda é candidato) e
  encerra**; ninguém com ela → apaga o arquivo. E o **Rodar agora se destrava SOZINHO** quando a trava está
  quebrada (sem pid) e segue para a rodada — com pid VIVO ele respeita a rodada em andamento e avisa.
- A TRAVA FANTASMA QUE MATOU O CANAL DE NOTÍCIAS (01/nov, 18h16→20h46 sem rodar): o registro repetia
  "NÃO RODEI: outro canal.py está com a trava **()**" — sem pid — a cada 10 min. A culpa era do PAINEL: o
  `travado()` testava a trava **PEGANDO** ela a cada carregamento de tela, e o `trava_rodada` escreve e
  TRUNCA o arquivo ao pegar. Resultado: (1) o pid do painel entrava no arquivo, mentindo sobre o dono, (2) o
  `f.truncate(1)` APAGAVA o pid do dono de verdade — daí o `()` — e (3) o teste disputava a trava com o
  canal.py no segundo exato em que ele começava, matando a rodada na largada. Agora `travado()` NÃO pega: lê
  o pid anotado e pergunta se aquele processo está VIVO (`vivo()`, OpenProcess+GetExitCodeProcess no Windows,
  `os.kill(pid, 0)` no resto) — pid morto = trava velha = livre. Sem pid anotado, aí sim testa, com
  `trava_rodada(..., so_testa=True)`, que **não escreve e não trunca**. `destrava` ficou completo: pid morto
  avisa que já estava livre, e sem ninguém com a trava ele APAGA o arquivo que ficou para trás.
  Junto: o pedido na FILA não se perde mais quando a largada falha (voltava a dizer "Rodar agora" como se
  nada tivesse acontecido) e erro de UM canal não vira "erro no laço" — o laço segue para os outros.
- DOIS ALARMES FALSOS DO DOUTOR (01/nov): ele dizia "TRAVA PRESENTE" em TODO canal que já rodou um dia — o
  `.canal_rodando` é criado uma vez e FICA ali; só olhar se o arquivo existe não diz nada. Agora ele tenta
  PEGAR a trava, igual à seção TRAVAS (que dizia "livre" dois palmos acima, contradizendo a outra). E o VLOGS
  não cobra mais máscara/voz clonada — o vlog usa o áudio das gravações dele.
- Rótulos do card de GTA 6 no painel: dizia "monta os vlogs novos" e "Ajustes do canal de notícias".
- `doutor.py` ganhou a seção **CANAIS AUTOMÁTICOS**: por canal, se está LIGADO, quando foi a última rodada
  (avisando quando passou do dobro do intervalo), o MOTIVO da última falha, se a trava está presente e se a
  máscara/voz chegaram do Drive. É a resposta direta para "por que não rodou sozinho".
- `python tools\doutor.py` → **por que** parou: versão do código · travas presas · **IA de texto** (testa Gemini,
  as grátis e o Claude, uma por uma) · voz (VoiceStudio aberto? com voz cadastrada?) · Instagram (vagas de Reels
  teste, pausa, fila, Drive) · disco · e a última linha de ERRO de cada registro → `tools\diagnostico.txt`.
- `python tools\teste_rapido.py` → importa TODO .py (nome que não existe, import errado) + CONTRATO: confere que
  cada função chamada de outro arquivo ainda existe (foi o que pegou `caminho` no painel.py, que dava erro 500 em
  /historia, /shop_arquivo e /ed_arquivo). O GitHub Actions roda isso + `pyflakes` a cada push.
- BACKUP MANUAL (29/out): `BACKUP.ps1` guarda em `E:\DETTO\backups\<data-hora>` todo config/estado/histórico
  das pastas do DETTO + os tokens de login + a versão do código (vídeo não entra), mantendo os 10 últimos;
  `RESTAURAR.ps1` lista os backups e devolve o escolhido (fazendo antes um backup do estado de agora;
  `-ComCodigo` volta também o commit daquele dia).
- `ATUALIZAR.ps1` guarda a versão de antes em `.ultima_boa`, roda o teste rápido depois do pull e **volta sozinho**
  se o código novo estiver quebrado. `VOLTAR.ps1` volta na mão (`VOLTAR.ps1 -Versao <commit>` para um ponto certo).
  Mídia e configurações (E:\DETTO) nunca são tocadas por isso.

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
  LINK JÁ FEITO NÃO REFAZ (22/out): `chave_link` tira a IDENTIDADE do vídeo no endereço (yt:ID, ig:CÓDIGO, tt:ID),
  então o mesmo vídeo colado de outro jeito (com ?si=, /shorts/, /p/ no lugar de /reel/, com ou sem www) é reconhecido;
  `links_ja_feitos` junta o `historico.json` (`"links"`) com o `links_feitos.txt` antigo. O link repetido sai do
  links.txt e vai para o próximo, sem gastar download nem Gemini. `--refazer-links` força refazer.
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
  `editar.py` (um por vez; `painel.json` = situação, `painel_log.txt` = registro); edição que para mostra O MOTIVO no
  painel (27/out, `motivo_do_erro`: a última linha do painel_log.txt que parece erro — "No space left on device",
  FileNotFoundError, Traceback —, ignorando a barra do ffmpeg; antes era só "veja o registro"); saídas para assistir/baixar/postar,
  "Ajustar roteiro e refazer" (grava o roteiro.txt do job), vertical completo pode ir sozinho para a fila.
  Tipos de edição: roteiro (editar.py) | REELS com roteiro (editar.py --reels, 9:16) | galo (passagem.py, jogo.json
  com "jogo") | react (react.py, 3 vídeos) | vertical (vertical916.py); os não-roteiro saem em `<pasta>\saidas\`.
  Instagram = REELS TESTE por padrão (`trial_params` MANUAL; `"teste"`, `"graduar"` manual|automatico, `"meta_views"`
  na conta; o TESTE só vale com `video_url`: o vídeo sobe para o Catbox (link público; até 3 vezes) ou Litterbox e o IG
  baixa de lá (tmpfiles e FB não publicado SEMPRE falharam — 2207082/2207076 — e saíram); cada falha de envio aparece no
  registro — erro 2207082/2207076 = o IG não baixou/processou; antes de subir o vídeo é padronizado (`normaliza_ig`: H.264 High, mesmo fps até 60, keyframe a cada 2 s, ≤1080x1920, ≤12 Mbit/s,
  AAC 48 kHz, faststart, em `tmp_ig\`); LINK DO REELS TESTE (22/out): cascata `HOSPEDAGENS`/`"hospedagem"` no config —
  1 `tunel` (o vídeo FICA NO PC e o IG baixa por um endereço público da Cloudflare, `cloudflared` baixado 1x para
  `postar\ferramentas\`, nome sorteado, cai no fim) · 2 Catbox · 3 0x0.st · 4 tmpfiles · 5 Litterbox; CADA link é
  CONFERIDO antes (`_confere_link`: baixa os primeiros bytes de fora, recusa HTML/404/tamanho errado) — link ruim é
  descartado na hora em vez de virar 2207082 e queimar as 4 tentativas; nenhuma hospedagem serviu = NÃO conta erro
  (pausa 10 min, o vídeo fica na fila). Painel: "↻ Tentar todos de novo" devolve as falhas da conta para a fila; falha espera 15 min/45 min/2 h e vai para falhas na 4ª; depois de QUALQUER erro a conta pausa 10 min (`pausa_ate`; antes tentava o próximo da fila na hora → "muitas ações"); erro 2207078 (limite de Reels TESTE da API) ou código 9 "muitas ações" = conta pausa 6 h (`"pausa_bloqueio_h"`), o vídeo não conta erro;
  ESTADO NÃO SE PERDE MAIS (26/out): `grava_json` escreve num .tmp e troca de nome (atômico) + cópia `estado.bak`, `le_estado`
  volta pela cópia se estragar e `muda_estado(base, fn)` relê do disco antes de gravar. Antes o `write_text` apagava o
  arquivo e escrevia depois: quem lesse no meio pegava `{}` calado (1.491 de 4.000 leituras no teste) e a PAUSA DE 24 H
  SUMIA — era por isso que a conta levava 2207078 às 23:15 e tentava de novo às 23:18, a noite toda, renovando o bloqueio.
  `posta_da_fila` relê o estado e confere a pausa na hora de postar (o botão "postar já" passa por cima, `forcar=True`);
  VAGAS DE REELS TESTE (26/out): o 2207078 é "máximo de reels teste publicados pela **Content Publishing API**" —
  NÃO é cota por dia e NÃO é bloqueio da conta (pelo celular ele continua postando; ele só tinha postado 3). É limite
  de testes ATIVOS: a API avalia cada um por 72 h (`TESTE_JANELA_H`). Então `testes_ativos` conta os postados nessa
  janela (promovido/ignorado saem na hora) e o número de vagas é APRENDIDO na recusa (`teste_vagas` = quantos estavam
  ativos ali; `"max_teste"` na conta manda) — nunca trava abaixo do que a conta já conseguiu. Sem vaga, a porta do
  TESTE fecha até `teste_ate` (quando o mais antigo faz 72 h) e **o vídeo ESPERA** — `cai_para_normal` é **false por
  padrão desde 26/out**: subir como normal mandava o vídeo para a página principal, para todos os seguidores, que é o
  contrário do teste que ele quer (`"teste_cai_para_normal": true` na conta liga; painel: "Sem vaga, subir como reels
  normal").
  O TETO APRENDIDO NÃO PRENDE MAIS A CONTA (29/out): uma recusa num dia ruim gravava `teste_vagas` baixo (1 ou 2)
  e, como ele nunca subia, TODO vídeo passava a ir só para o Drive. Agora: `teste_pico` guarda quantos testes a
  conta já teve ativos num envio ACEITO e o teto nunca fica abaixo dele; cada envio aceito sobe o teto
  (`teste_vagas = max(teto, ativos)`); e existe a SONDA — passada a espera, a cada `SONDA_CADA_H` (3 h) ele tenta
  UM teste mesmo "sem vaga" (o 2207078 não conta erro nem pausa de verdade), então o teto volta a subir sozinho.
  Painel: botão **"↻ Testar a API de novo"** (`teste_reset`) esquece o teto aprendido na hora.
  NÃO DEU PELA API → VAI SOZINHO PARA O DRIVE (26/out, `manda_para_celular`, padrão LIGADO): sem vaga de teste, ou
  depois de 4 tentativas de envio falhas, o vídeo é COPIADO para `Meu Drive\DETTO\reels_teste\<conta>` junto com um
  `.txt` com a LEGENDA E AS TAGS (sem a parte depois do "---") e o passo a passo; sai da fila (vai para
  `postar\celular\<conta>\`, não se perde) e fica em `estado[k]["celular"]`. O painel AVISA no topo ("📱 N vídeo(s)
  na pasta do Drive esperando você postar") e o card da conta lista cada um com **"✔ Postei"** (`celular_postei`:
  entra em postados com `via: app`, que não gasta vaga da API, e apaga a cópia do Drive) e **"↩ fila"**
  (`celular_devolver`, volta para a API). `"teste_para_celular": false` desliga. Vídeo que o FFmpeg não lê continua
  indo para falhas\ — esse está estragado mesmo.
  OS 10 POR DIA SÃO DO APP, NÃO DA API (26/out): o limite do 2207078 é só do que sobe pela Content Publishing API e é
  pequeno; no app do Instagram ele consegue os 10. O painel também tem **"Preparar pasta do Reels TESTE"**
  (`prepara_teste`): os próximos 10 da fila vão para `Meu Drive\DETTO\reels_teste\<conta>` (sem Drive, em
  `postar\reels_teste\`) com LEGENDAS.txt explicando o caminho no celular (Drive → Enviar cópia → Instagram → Reels →
  ligar "Reel de teste") e o botão **"Postei os da pasta"** (`teste_postei`) tira da fila e grava em postados com
  `"via": "app"` — e `testes_ativos` IGNORA os com `via: app`, porque eles não gastam o limite da API.
  A MESMA mensagem da fila só sai 1x por hora (`log_1x`): "sem vaga de Reels teste" encheu 40 linhas iguais em 3 h.
  LIBERAR VAGA da API é marcar "Já mandei" (promovido) ou o X (ignorado) no reels teste da lista: enquanto ele não
  gradua no app, o teste fica ocupando vaga até os 72 h. `"graduar": "automatico"` (SS_PERFORMANCE) faz o Instagram
  graduar sozinho e a vaga girar mais rápido. A conta só pausa 24 h no
  bloqueio de verdade ("muitas ações", código 9 sem o 2207078). Painel: "🧪 Reels teste ativos (janela de 72 h): n de N
  · próxima vaga dd/mm hh:mm" e o motivo da pausa; Instagram sem máx./dia = teto 10/dia (`teto_dia`); sem internet (getaddrinfo) = não conta erro, espera 10 min; vídeo que o FFmpeg não lê (`VideoQuebrado`, depois de 6 jeitos de `normaliza_ig`, os últimos tolerantes a quadro estragado) = falhas na hora, sem gastar ação no IG; contador de erros zera depois de 12 h e ao ir para falhas; painel mostra a pausa + "Tirar pausa"; `normaliza_ig` tenta 3 jeitos (áudio vazio → silêncio; sem source_fps → 30 fps); o envio direto ignorava o teste); views pelo insights (permissão instagram_manage_insights) a cada 30 min; mandar para os seguidores é no
  app (a API não faz) → painel avisa e tem "Já mandei". Roteiro sem linha de BLOCO vira um bloco só.
  TIKTOK = modo "studio" (padrão; o TikTok não aprova app para as próprias contas): nada vai pela API; o painel
  planeja horários (`P.planeja`: intervalo/janela/máx. por dia, 20 min a 10 dias), "Preparar pasta" →
  `E:\DETTO\postar\tiktok_studio\<conta>\` (vídeos "01 - 16-10 08h00 - nome" + LEGENDAS.txt), ele agenda no TikTok
  Studio e marca "Agendei" (vai para postados com `agendado_para`). "rascunho"/"direto" = API (opcional).
  REELS no painel: vários links de uma vez → `links.txt`; com `"auto_links"` (padrão) o painel roda
  `reels.py --so-links` sozinho (um por vez, cada pronto vai para a fila). yt-dlp atualiza 1x/dia.
  LINK QUE NÃO VIRA REELS (26/out): o laço do painel olhava só o filho DELE — com a trava `.reels_rodando` na mão da
  tarefa do Windows ele disparava um reels.py a cada 45 s, cada um morria na hora ("outro reels.py já está rodando") e
  os links nunca ficavam prontos; e o registro abria em modo "w", apagando o motivo da falha anterior. Agora
  `reels_rodando()` confere a trava antes (avisa 1x a cada 30 min e espera a vez; os botões de gerar/clipe também),
  `log_reels()` ACRESCENTA (gira em 2 MB) e todo link que sai da lista sem virar reels vai com o MOTIVO para
  `links_falhos.txt` → painel: "⚠ Links que NÃO viraram reels".
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
- CENA FEITA NA MÃO SEM AS CHAVES DE SEMPRE (29/out): quando o `acha_virada` partia o vídeo, as cenas que eu
  criava não tinham `fade_in`/`fade_out` e o `troca_partes` quebrava (`KeyError: 'fade_in'`) logo DEPOIS de
  acertar a virada. Agora elas saem com as mesmas chaves das cenas achadas no vídeo.
- LINK QUE NÃO SEPARA PESSOA/LANCE (29/out, `acha_virada`): vídeo sem corte de cena detectável (crossfade, zoom,
  gravação de tela) e sem barra preta deixava `partes_da_pessoa` devolver "tudo pessoa"/"tudo lance" e o link
  morria em "não achei onde está a pessoa e onde está o lance" (um link dele falhou assim de 27 a 29/out). Agora,
  nessa situação, o Gemini recebe 14 quadros do vídeo inteiro e responde EM QUE SEGUNDO o lance começa
  (`{"segundo":..., "tem_pessoa":...}`); com isso o vídeo é partido em pessoa|lance. Se ele responder
  `tem_pessoa: false`, o registro diz que esse link pede o **modo novo** (não tem pessoa para trocar).
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
  4 qualquer canal da busca por data (`busca_qualquer_canal`) · 5 CAMPEONATOS; `fora` = react/ao vivo/jogo); hora pelo FEED RSS (`rss`), hoje e
  ontem (`max_horas` 48), sem Shorts; `max_videos_rodada` 8 por rodada (o resto na próxima); notícia INTEIRA (15 s a
  `trecho_max_s` 180, corte só no fim de frase), máx. 3 por vídeo; vídeo de PELO MENOS 16 min (`duracao_alvo_min` 16 = imprensa + falas ~12 s cada; sem material e sem --forcar espera; `fontes_versao` 5);
  cada fala CITA a origem do trecho seguinte (`origem`/`origem_falada`: "Globo Esporte MG, no canal X") e o fechamento diz que os créditos estão nos
  comentários; créditos num COMENTÁRIO do canal (`youtube_up.comenta`, escopo youtube.force-ssl → refazer o login do canal uma vez;
  fixar é no Studio) + descrição + faixa "Imagens: origem"; notícia repetida em outro canal ou já
  postada nos últimos 3 dias (`parecido` ≥ `parecido_max` 0,35 nas palavras do assunto, `ja_postado`) fica fora; créditos
  com o programa original (`programa`, "via canal");
  FOCO DO DIA (22/out, mesclagem com botão em 23/out): o assunto que JÁ FOI o vídeo de hoje só volta se VOCÊ ligar
  **"Mesclar assunto do dia"** no painel (`mesclar_assunto`, padrão DESLIGADO) **e** a notícia trouxer FATO NOVO:
  nota ≥ `mesclar_nota_min` 7 e `novidade` ≥ `mesclar_novidade_min` 0,35 (palavras do assunto que não estavam no que
  já foi postado). Aí entra como notícia SECUNDÁRIA, `max_repetidas` 1 por vídeo, nunca em primeiro e nunca no
  título/thumb. Recusa e mesclagem aparecem no registro. O de ONTEM continua fora de vez.
  A VOLTA PELO MUNDO (22/out, `coleta_campeonatos`): em dia de Libertadores, Champions, Copa do Brasil, Sul-Americana,
  Mundial ou rodada do Brasileirão, a rodada busca também 1 vídeo da imprensa por campeonato (`"campeonatos"` no
  config: nome, `termos` do título e `busca` por data; hora pelo feed, prioridade 5). Entram no FIM do vídeo
  (`max_trechos_campeonato` 2, `max_videos_campeonato` 3) e a fala antes do primeiro avisa que agora é a volta pelo
  mundo. Não teve jogo = a busca por data não traz nada e o bloco simplesmente não existe. `"campeonatos_ligado": false` desliga.
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
- VINHETA DE ABERTURA (25/out, `tools\canal\vinheta.py` + `vinheta.js` + `vinheta\`): abertura de 2,4–3 s nos vídeos
  HORIZONTAIS, com a identidade do canal. 3 presets em `CANAIS`: `noticias` (DETTO GALO NOTÍCIAS: listras, faixas
  amarelas, selo PLANTÃO piscando), `galo` (DETTO GALO, a mesma cara sem plantão, sub "RESENHA DO GALO") e `vlog`
  (EVERTON LOPES: luz lima de um lado, roxa do outro). Tempo: entrada → BATIDA aos 45% (flash branco + o nome trava,
  o impacto do som bate junto) → luz passando, selo e risco. Áudio feito no FFmpeg (whoosh + impacto, -16 LUFS).
  Fica guardada em `<DETTO>\marca\vinheta_<canal>_<LxA>_<fps>.mp4` e só é refeita quando o nome muda (`--refazer`);
  o vídeo de todo dia só EMENDA (`emenda` padroniza tamanho/fps/áudio, e o vídeo sem áudio ganha silêncio).
  NUNCA NO SEGUNDO 0 (26/out): vinheta na abertura QUEBRA A RETENÇÃO — o espectador decide se fica nos primeiros
  segundos, e ele precisa ouvir a chamada/resumo com o CTA primeiro. Agora `emenda(..., em=<segundo>)` PARTE o vídeo
  e põe a abertura no meio (`-t em` + vinheta + `-ss em`, num passe só; corte exato, sem quadro perdido). Cada
  programa diz onde a chamada acaba: `canal.py` → o `monta` devolve `abertura_s` (a duração da 1ª peça de fala, que
  é o resumo + CTA); `canal_vlog.py` → a duração do 1º trecho do plano.json (o gancho); `editar.py` →
  `fim_da_abertura(EDIT_PLAN.json)`, o fim do último trecho do PRIMEIRO bloco (ABERTURA / GANCHO) por
  `meta.segments[].block`. Roteiro de um bloco só, ou sem plano, devolve 0 e ela volta para a frente.
  `"vinheta_em"` no config do canal força um segundo fixo (0 = na frente, como era).
  Onde entra sozinha: `canal.py` (notícias), `canal_vlog.py` (vlogs) e `editar.py` no horizontal.mp4 e no
  horizontal_lances.mp4 (`--canal galo|noticias|vlog|sem`, padrão galo). No 9:16 ela NÃO entra (reels não tem
  abertura). `"vinheta": false` no config do canal desliga; `"vinheta_s"` muda a duração.
  Testar: `python tools\canal\vinheta.py --canal galo --ver "<video.mp4>" [--em 8]`.
- REELS COM ROTEIRO (25/out, `editar.py --reels`; painel: tipo **Reels com roteiro (9:16)**): o mesmo fluxo do vídeo
  com roteiro, mas o vídeo INTEIRO vira UM reels 9:16 — sem horizontal, sem cortes, sem thumb e sem vinheta. O
  GANCHO entra escrito na tela nos 3 primeiros segundos (`--gancho` no render-dynamic, que antes só existia com
  `--cut`): vem da linha `GANCHO: ...` do roteiro, senão do 1º corte vertical, senão da 1ª TELA, senão do título.
  A IA escreve o roteiro no formato de reels (`roteiro_ia.py --reels`, `REGRAS_REELS`): gancho nos 2 primeiros
  segundos, TELA a cada ~5 s com 2 a 4 palavras, sem seção de cortes verticais, CTA nos últimos 2 s.
  Saídas: `<job>\reels.mp4` (+ `_lances`) e `<job>\post.txt` com a legenda.
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

## O QUE VIRALIZA NOS NICHOS DELE — medido, não chutado (30/out)

Puxei views, título e duração dos ÚLTIMOS 25 VÍDEOS de cada concorrente e comparei cada vídeo com a MEDIANA
do próprio canal (então não é "canal grande rende mais"; é o que aquele vídeo rendeu a mais que o normal dele).

**GALO — 150 vídeos de 6 canais** (@JornaldoGalo 29,2k inscritos/25k views medianos · @diariodogalo940 39,7k/14k ·
@galoticiasoficial 9,4k/14k · @EUSOUGALO · @TrincaGalo · @ETERNOGALONEWS):
- jornalista FAMOSO no título (Renata Fan, Denílson, Neto, Mauro Cezar…): **1,36x** ← a maior alavanca
- reforço/contratação/mercado: **1,22x** · nome do PROGRAMA no título (Globo Esporte MG, Jogo Aberto): **1,18x**
- pergunta no título: 1,14x · título em duas partes com " / ": 1,11x · 🚨: 1,02x (não muda nada)
- **arbitragem/roubo/VAR: 0,89x** — rende MENOS; não é para construir o título em cima disso
- duração: 16-25 min **1,17x** · 10-16 min 1,01x · 6-10 min 0,97x · 25+ min **0,72x**
- o melhor do nicho: "HG REPRESENTOU O ATLÉTICO..." (140 mil, 5,6x a mediana do canal) — 22 min
→ aplicado: `REGRA_NOTA` (a nota de cada trecho soma +2 para jornalista famoso elogiando o Galo, +1,5 para
  reforço, +1 se dá para citar o programa, −1 se é só arbitragem) e a `regra_titulo` com essa ordem.

**GTA 6 — 96 vídeos de 4 canais** (@SaninPlay 1,36 mi/80k · @GameplayRJ 8,59 mi/156k · @WillMacGTA 26k/40k ·
@NobertoGamer 84,9k/20k):
- o TÍTULO quase não muda nada: 🚨 1,00x · número 1,00x · parênteses 1,00x · #gta6 1,04x
- duas coisas PIORAM: "vazou/vazamento" no título **0,90x** e terminar com "..." **0,90x**
- duração: 12-18 min **1,30x** · 8-12 min 0,90x · 18+ min 1,00x
- quem rende mais por tamanho é o @WillMacGTA (26 mil inscritos, 40 mil views medianos = 1,5x o próprio tamanho)
→ aplicado: `duracao_alvo_min` 13 (era 10), `regra_titulo` sem "vazamento" e sem "...", e `regra_nota` própria
  (novidade concreta vale nota; especulação e recap caem). Neste nicho quem decide é a THUMB e sair TODO DIA.

## YOUTUBE: CAPÍTULOS, RETENÇÃO E CONFERÊNCIA DE TÍTULO (01/nov) — `tools\yt\`, guia `tools\yt\LEIA-ME.txt`

Veio do `youtube-agent-skill` (github.com/Jakeschincariol/youtube-agent-skill, MIT) que ele mandou. As 11
habilidades dele são **prompts de conversa**, não código que roda no canal.py — copiar as 11 não muda vídeo
nenhum. E os 6 .py de lá são **só em inglês** (`title.py` procura "amazing/insane", `hookscore.py` procura
"you/lose/waste"): no título em português dariam nota baixa para TODO vídeo e não veriam "ABSURDO"/"INÉDITO".
Então: as habilidades ficam guardadas em `tools\yt\skills\` (como estão, com a LICENSE; `teste_rapido.py` e o
pyflakes IGNORAM essa pasta — é código de terceiros, não pode reprovar o nosso teste), e os TRÊS que valiam
foram reescritos em pt-BR e LIGADOS no sistema:
- CAPÍTULOS (`tools\yt\capitulos.py`, ligado no canal.py): a barrinha por assunto. O `monta` agora junta
  `marcas` — as peças são emendadas em ORDEM com `-c copy`, então somar a duração das anteriores dá o segundo
  EXATO de cada notícia (conferido: erro de 0,02 s em 30 s) — e a MANCHETE já é o título do capítulo. `monta`
  devolve `(video, abertura_s, marcas)`. A vinheta entra NO MEIO e empurra tudo depois dela, então `desloca`
  soma a duração dela nas marcas seguintes (sem isso cada capítulo cairia no fim da notícia anterior).
  Regras do YouTube conferidas em vez de supostas (3 capítulos, o 1º em 0:00, 10 s cada): não dando, sai SEM
  capítulos e o registro diz — bloco inválido o YouTube ignora em SILÊNCIO, o que é pior. Manchete em CAIXA
  ALTA é rebaixada sem estragar sigla ("GLOBO ESPORTE MG" → "Globo Esporte MG", não "Globo esporte mg").
  `"capitulos": false` desliga; `"capitulo_abertura"` muda o nome do primeiro. `de_transcricao` é o caminho
  para vídeo gravado por ele (acha a virada pela pausa + troca de vocabulário).
- RETENÇÃO (`tools\yt\retencao.py`, na mão) — **era o buraco do sistema**: ele media os CONCORRENTES e nunca
  os próprios vídeos. Lê o CSV do Studio (Analytics → Engajamento → Retenção do público) e separa GANCHO
  (primeiros 30 s → conserta a 1ª frase) · PAREDÕES (queda seca → CORTA aquele trecho) · ESCORREGA (sangria do
  meio → é RITMO, encurta). Com `--capitulos post.json` ou `--words words.json` ele diz O QUE ESTAVA SENDO
  DITO em cada queda. Dois detalhes que só aparecem testando: (1) num vídeo de até ~100 s o eixo em SEGUNDOS é
  idêntico ao eixo em %, e confundir isso jogava o paredão do Short dentro da janela do gancho e o fazia
  DESAPARECER — a `--duracao` decide; (2) paredão é queda fora do normal DAQUELE vídeo (2,5x a queda típica),
  não acima de um número fixo, senão o escorrega de um vídeo ruim enche o relatório e esconde o paredão de
  verdade. Com o Studio mandando ~100 pontos do vídeo inteiro, 30 s de um vídeo longo são 3 ou 4 pontos: aí ele
  NÃO dá veredito de gancho e manda olhar "Os primeiros 30 segundos" no Studio.
- TÍTULO + THUMB (`tools\yt\titulo.py`, roda no fim de cada vídeo do canal e escreve a nota no registro; AVISA,
  nunca barra): o par título+thumb é UMA coisa — o erro mais comum é a thumb repetir palavra do título e gastar
  metade da área de clique. Vagas em PORTUGUÊS (absurdo, inacreditável, urgente, polêmica...). As regras de
  nicho são as MEDIDAS de 30/out: Galo +1,36x jornalista famoso, +1,22x reforço, +1,18x programa, −0,89x
  arbitragem; GTA −0,90x "vazou" e −0,90x terminar com "...". Dois acertos que vieram do teste: o título dele é
  em CAIXA ALTA de propósito (reclamar disso em todo vídeo é ruído — só caixa alta MISTURADA é spam) e, em
  título todo em caixa alta, inicial maiúscula não indica nome próprio (saía "cita nome próprio: ESPORTE, MG:,
  DIRETORES"), então os nomes vêm dos que o NICHO conhece. Nota não chega a 100 com reclamação em aberto.
  `post.json` guarda `capitulos` e `lint_titulo`.

## CANAL DE GTA 6 (29/out) — o mesmo canal.py, outro assunto

`python tools\canal\canal.py --pasta E:\DETTO\canal_gta6 --preset gta6` (painel aba CANAIS: card **GTA 6**).
O canal.py virou genérico: `PRESETS` = `galo` (o CONFIG_PADRAO de sempre) e `gta6`. O preset fica gravado no
config da pasta (`"preset"`), e canal que não é `galo` NÃO recebe as migrações de fontes do Galo.
- O que o preset muda: `assunto`/`persona`/`regra_titulo`/`regras_roteiro` (entram no prompt do roteiro),
  `fontes: []` + `busca` por data (gta 6 notícias/gameplay/trailer/vazamento), `fora` SEM "gameplay" (é o que
  queremos), trecho até 120 s, vídeo de 10 min, `comentario_min_s` 40 (a reação dele no meio do trecho = o react),
  `vinheta_canal: gta6`, `estilo_thumb: gameplay`.
- CANAL GRINGO ENTRA LEGENDADO (30/out): o `transcrever.py` fixava `language="pt"` — a fala em INGLÊS virava
  texto sem sentido em português antes mesmo de existir tradução. Agora `transcrever(..., idioma=None,
  com_idioma=True)` deixa o whisper DESCOBRIR a língua e devolve qual é; `transcreve()` guarda isso no cache
  (`{"palavras": [...], "idioma": "en"}`) e cache antigo (lista pura) é REFEITO nos canais que aceitam fonte de
  fora. O preset gta6 tem `"idioma_fontes": None` (o Galo segue em "pt", que é mais rápido e certeiro).
  Trecho em outra língua: `frases_do_trecho` corta em pedaços de ~9 palavras com tempo, `traduz_frases`
  traduz tudo numa chamada só (Gemini → grátis → Claude) e `legenda_pngs` faz um PNG por frase, que o
  `peca_trecho` QUEIMA na parte de baixo da janela do vídeo (`enable=between`, placa preta, letra branca com
  contorno). A manchete e o resumo saem em português mesmo com a transcrição em inglês, e o roteiro recebe
  `[TRECHO EM EN — vai LEGENDADO]` para a fala dele avisar que é de um canal de fora.
- DUBLAGEM, TELA CHEIA E EMOÇÃO (30/out, pedido dele) — o trecho gringo agora é DUBLADO, não só legendado:
  **1 DUBLAGEM** (`dublagem`, `"dublar": true`): as frases traduzidas viram fala na voz DELE (a mesma cadeia
  VoiceStudio → Fish → neural) e entram no SEGUNDO em que são ditas no original (`adelay`); frase que não cabe
  no espaço dela é acelerada até 1,35x (`atempo`) para não atropelar a seguinte. O áudio original fica atrás em
  0,16 (`"volume_original_dublado"`) e a mistura sai a -16 LUFS. A legenda continua junto.
  **2 TELA CHEIA** (`so_imagens` + `peca_trecho(cheia=True)`, `"tela_cheia_sem_rosto": true`): 5 quadros do
  trecho passam pelo YuNet; rosto GRANDE (>1,2% da tela) em no máximo 1/3 deles = é imagem de jogo/gameplay →
  o vídeo ocupa a TELA INTEIRA e a máscara NÃO entra (a cara dele num canto ao lado de uma gameplay só roubava
  espaço). Tendo alguém falando na tela, o layout de sempre.
  **3 EMOÇÃO NA VOZ** (`CLIMA_VOZ`/`jeito_de_falar` no voz.py): o `clima` de cada fala — que o roteiro já
  escrevia e só servia para escolher a máscara — agora manda na VOZ. Na neural vira ritmo/tom/volume
  (comemorando +14%/+12Hz/+6%, atencao -2%/+2Hz/+4%, bravo +4%/-4Hz/+5%, pensativo -6%/-3Hz...); no
  VoiceStudio vira uma frase dizendo COMO falar ("empolgado, comemorando, com energia alta"). O clima entra na
  chave do cache, então mudar o clima refaz a fala.
- O CANAL PEDIA TRECHO "SOBRE O GALO" NUM VÍDEO DE GTA (30/out): o `(o Galo)` estava FIXO no prompt do
  `acha_trechos` — a IA recebia "marque os trechos em que falam do GTA (o Galo)" e, com razão, não achava
  nada: TODO vídeo terminava "0 trecho(s)". Agora, sem pauta, o alvo vem do `cfg["assunto"]` do canal e o
  registro diz o assunto certo.
- `palavras_do_cache` (30/out): o `.words.json` virou dicionário ({"palavras", "idioma"}) e dois lugares ainda
  liam como lista — `TypeError: string indices must be integers` no meio da montagem. Agora os dois formatos
  valem.
- RODADA DEMORANDO DEMAIS (30/out): transcrever 8 vídeos de 10-25 min no whisper levava a rodada inteira.
  `palavras_rapidas` tenta a LEGENDA do YouTube antes (instantânea, serve para achar o trecho e para
  traduzir); só cai no whisper se não houver legenda ou se ela cobrir menos de 50% do vídeo. Ligado por canal:
  `"legenda_antes_de_transcrever"` + `"legenda_langs"` (gta6: pt e en). O gta6 também baixou
  `max_videos_rodada` para 4 — com 13 min de alvo não precisa de 8.
- GESTO COM CARA DE ROBÔ (30/out, `mascara_longa`): uma gravação de 6 s num trecho de 90 s dava 15 voltas do
  mesmo gesto. Agora as gravações DIFERENTES são emendadas até cobrir o trecho (concat `-c copy`, reencoda só
  se os parâmetros não baterem), então o loop fica muito mais longo e variado.
- AS PALAVRAS DO ASSUNTO (29/out, `"termos"`/`"termos_nao"`): o `apelidos()` procurava o `time` no
  `times.json` (lista de times de FUTEBOL) — num canal de GTA não achava nada, o `fala_do_time` reprovava
  TODO vídeo e a rodada terminava "0 vídeo(s) de hoje" mesmo com os canais respondendo. Agora o preset traz
  as suas (`gta 6`, `grand theft auto vi`, `vice city`, `rockstar games`, `lucia caminos`...) e o
  `termos_nao` tira GTA 5/RP/Online. O Galo continua pelo times.json.
- ASSUNTO ÚNICO: `parecido_max` 0,8 (no Galo é 0,35 — num canal que só fala de GTA 6 TUDO pareceria repetido e a
  rodada ficaria sem material), `mesclar_assunto` ligado, `max_repetidas` 3.
- CINCO VÍDEOS COM QUASE O MESMO TÍTULO (01/nov): "210 GB", "mapa" e "south park" voltaram em todos
  ("GTA 6 VAI OCUPAR 210 GB", "NOVA GAMEPLAY... + 210 GB", "MAPA DO GTA 6 = ... / SOUTH PARK",
  "GTA 6 COM 210 GB E MAPA GIGANTE, GAMEPLAY EM SOUTH PARK", "VAZOU! GTA 6 PODE TER 210 GB E MAPA DUAS VEZES
  MAIOR"). Duas causas, as duas consertadas:
  **1** um ÚNICO `parecido_max` decidia DUAS coisas diferentes. No GTA ele é 0,8 DE PROPÓSITO (frouxo, senão o
  canal fica sem material) — então a notícia da véspera voltava, vinha com a nota mais alta, caía em PRIMEIRO
  e virava o título outra vez. Agora existe `titulo_parecido_max` (gta6 0,4; nos outros `min(0,5, parecido_max)`):
  ENTRAR no vídeo segue frouxo, ser a PRIMEIRA notícia (a que vira título) é apertado — a comparação é com o
  TEXTO das notícias que já foram título (`hist["titulos"]`, 7 dias), e quem já foi título é empurrado para
  trás na ordem. Medido nos títulos reais dele: o repetido dá 0,50 (barrado) e as notícias novas dão 0,00.
  **2** a IA NÃO SABIA o que já tinha saído — ela só via os trechos de hoje e, com razão, titulava no fato mais
  forte, que era o mesmo de ontem. Agora o prompt recebe os 8 últimos títulos do canal e a proibição explícita:
  o título de hoje não pode ser sobre o mesmo fato nem repetir o número/nome que era o gancho deles; sendo o
  mesmo fato, titula no ÂNGULO NOVO, e sem ângulo novo vai para a SEGUNDA notícia mais forte (a thumb também).
- CONTAGEM REGRESSIVA de verdade: `"lancamento": "2026-11-19"` no config → o prompt recebe "HOJE FALTAM N DIAS"
  calculado na hora (19/11/2026, pré-download 12/11, PS5 e Xbox Series; PC sem data; R$ 449,90 / R$ 549,90;
  Lucia Caminos e Jason Duval em Leonida/Vice City). **Proibido inventar**: vazamento é chamado de vazamento.
- Canais-fonte: ele põe os que acompanha no config (`fontes`); sem nenhum, a BUSCA POR DATA já traz o que saiu hoje.
  Pauta de um vídeo específico: cole o link no campo **Pautas** do card (funciona igual ao canal de notícias).
- `vinheta.py` ganhou o preset `gta6` (cara de gameplay: lima e roxo, sub "TUDO SOBRE O GTA 6").
- CANAIS-FONTE (29/out, pedido dele): @SaninPlay, @GameplayRJ, @RockstarGames (oficial), @BRKsEDU,
  **@VOXELOFICIAL** (o @Voxel estava errado e nunca respondeu — conferido 05/nov), @TecMundo, @IGNBrasil.
  Canal que não existir/404 é pulado e a busca por data cobre o resto.
- **NOTÍCIA DE OUTROS GAMES (05/nov, pedido dele)**: o canal descartava "ZELDA OCARINA OF TIME REMAKE" do
  BRKsEDU e o remake da IGN porque os `termos` só aceitam palavras de GTA — justamente a notícia de games
  que ele quer dar. Em vez de inventar mecanismo, reusei o da "VOLTA PELO MUNDO" do Galo, que já existe e
  está testado: `campeonatos_ligado: true` + `"campeonatos"` com DOIS blocos de games (lançamentos/trailers/
  remakes e consoles/PC), que entram no FIM do vídeo (`max_trechos_campeonato` 2) e simplesmente NÃO
  EXISTEM no dia em que não há notícia. A redação do bloco saiu do código e virou config
  (`bloco_extra_nome` "o resto dos games", `bloco_extra_aviso`), porque estava presa a "a volta pelo mundo"
  do Galo. A `regra_titulo` do preset proíbe titular nesse bloco: título e thumb saem SEMPRE do GTA 6.
- **IMAGEM DO JOGO ATRÁS DA SUA FALA (05/nov, `apoio_na_fala`)** — era o buraco visual do canal de games:
  durante a NARRAÇÃO a janela grande mostrava só a máscara dele, então o espectador passava minutos sem ver
  jogo nenhum. Agora `peca_fala(..., apoio=(arquivo, segundo))` põe o trecho da PRÓPRIA notícia que a fala
  está apresentando na janela (mudo, em loop se for curto) e a máscara vai para o canto — ele diz "a
  Rockstar liberou novas imagens" e as imagens estão na tela. Não custa download nenhum: o arquivo já está
  baixado. Ligado só no preset de games, para não mexer no visual do Galo. Conferido renderizando a peça e
  olhando o quadro.
- **MIGRAÇÃO POR PRESET (05/nov)**: o config do GTA 6 já existia no PC dele e `prepara()` só migrava o
  preset `galo` — então NADA que eu mudasse no preset gta6 chegava lá (o @Voxel errado ficaria errado para
  sempre). Agora cada preset tem o seu `fontes_versao` (gta6 = 3) e traz as chaves novas quando ele sobe,
  **preservando o que é dele** (nome_canal, auto_postar, voz_ref — conferido rodando a migração sobre uma
  cópia do config antigo).

## OS 3 CANAIS QUE ELE MANDOU DE REFERÊNCIA — medido (05/nov)

Ele mandou 3 links dizendo que o canal de GTA tem de ter vídeo "como estes". O YouTube não me deixa abrir
vídeo sem cookie, mas o **oembed** dá título e canal sem login, e a listagem do canal dá views e duração —
então dá para medir, que é o que vale. São eles:
- **"REVELADO O PRÉ LOAD DO GTA 6 !!!"** — @gigatongames (2,87 mi inscritos, 128 mil views medianos)
- **"O mundo não está preparado para o GTA 6"** — @Dulebio (**1,87 mil** inscritos, 7,5 mil medianos)
- **"FALTAM 20 DIAS! CRIE SEU CANAL DE GTA 6"** — @nerdsdenegocios (4,36 mi, 257 mil medianos)

**A DURAÇÃO É A ÚNICA COISA EM QUE OS TRÊS CONCORDAM, e concordam muito:** 12-18 min ganha em TODOS
(Gigaton 1,29x · Dulebio **2,73x** · Nerds 2,23x) e 8-12 min PERDE em todos (0,87x · —— · 0,59x). Junta com
a medição de 30/out no nicho de GTA (12-18 min = 1,30x): são 5 canais apontando para a mesma faixa.
→ `duracao_alvo_min` 13 → **14** (cai no meio da faixa mesmo depois da vinheta).

**O DULEBIO É O ACHADO**: 1,87 mil inscritos e o melhor vídeo dele fez **21,6x** a mediana do canal — é
exatamente o vídeo que o Everton mandou, 14 min. É o único dos três do TAMANHO dele, então é o único cujos
números valem para o canal dele:
- NÚMERO no título: **2,00x** · terminar com "!!": **0,05x** (no Gigaton, que é gigante, "!!" dá 1,09x — o
  tamanho do canal inverte o sinal, e por isso vale o dado do canal pequeno)
→ a `regra_titulo` do preset gta6 passou a pedir número concreto e proibir terminar em "!!".

O @nerdsdenegocios NÃO é modelo de formato: é um canal de NEGÓCIOS onde título com "GTA 6" rende **0,35x**
(pergunta no título rende 1,84x). O vídeo dele é um conselho sobre como montar o canal, não uma prova de
que o formato funciona — tratar como opinião, não como medição.

**O QUE A MEDIÇÃO NÃO DIZ** (e eu não vou fingir que diz): como esses vídeos são EDITADOS por dentro. Para
isso eu precisaria assistir, e sem cookie eu não abro vídeo nenhum. Depois do botão do login, eu consigo.

## GAMEPLAY NARRADA (01/nov) — `tools\gameplay\`, guia `tools\gameplay\LEIA-ME.txt`

`python tools\gameplay\gameplay.py --pasta "E:\DETTO\gameplay\<nome>" --jogo "Project Zomboid" --titulo "<a premissa>"`
Gravação bruta → vídeo de 15-20 min com a VOZ DELE narrando em 1ª pessoa + reações + Shorts. Ele pediu
"igual The Gus/Blake Games"; medi os dois nomes e nenhum era (o @thegusr é em inglês, o @BlakeGames tem 105
views) — mas Project Zomboid está na lista dele, então o @thegusr ERA a referência.
MEDIDO (últimos 25 vídeos): **@thegusr 15-25 min = 1,30x** (8-15 min 0,83x) · **@Felps 15-25 min = 1,33x**.
O melhor de cada um vende uma PREMISSA, não um resumo ("I played Project Zomboid in third person!!" 5,6x;
"10 ANOS BEBENDO PETRÓLEO" 3,9x) e o PIOR do @thegusr é o único fora do formato (0,1x) — sair do formato mata.
→ `duracao_alvo_min` 17 e o prompt exige premissa COM NÚMERO: no teste, sem o número a nota do título caía
de 67 para 23 (o `yt\titulo.py` pegou sozinho).
- **O QUE NÃO EXISTIA: `momentos.py`.** Numa gravação de 2 h não há roteiro nem marcação. Três sinais, e
  nenhum com número fixo — vale o que sai do normal DAQUELE vídeo (a mesma lição dos paredões do
  `retencao.py`): VOLUME (tiro/grito/morte) · MOVIMENTO (correria/luta) · **A FALA DELE** (se comentou
  jogando, a PALAVRA dita é o momento: "morri", "consegui" — `GRITOS`/`AUGE`, pesa mais que os outros dois).
  Cada momento pega ~4 s ANTES do pico (a subida é o que prende; cortar no pico entrega o resultado sem a
  tensão) e 3,5 s depois. Conferido numa gravação sintética com ação nos segundos 40, 95 e 150: achou os
  três (35,7s / 91,0s / 145,7s), zero falso positivo, e ignorou fala comum ("de novo") marcando só a reação.
- O resto REUSA o que já existe: `vlog.energia` (movimento/volume), faster-whisper, `canal\voz.py`
  (VoiceStudio → Fish → neural, com o clima mandando na emoção), vinheta depois da chamada, `thumb\viral.py`
  estilo gameplay, `yt\capitulos.py`, `yt\titulo.py` e `vertical916.py` nos Shorts.
- O Gemini olha UM quadro de cada momento e diz o que aconteceu (`rotula`), para a narração falar do que
  está na tela. **Proibido inventar** está no prompt e funciona: no teste com barras de cor, a IA narrou que
  a gravação tinha quebrado em vez de inventar zumbi.
- TRÊS ERROS QUE SÓ O TESTE PEGOU: (1) `filtro_complexo` recebe o CAMINHO de um arquivo, não o texto do
  filtro — passar o texto matava TODA peça em "Failed to set value ... filter_complex_script"; (2) `crop`
  **não aceita `enable`** ("Timeline not supported"), então o punch-in é `scale` com `eval=frame` numa
  expressão de t + crop fixo (`zoompan` é proibido: ~57 s por cena); (3) `drawtext` NÃO quebra linha — uma
  narração de 40 palavras saía numa linha só, metade fora da tela; `quebra()` corta em 42 colunas e a altura
  segue o número de linhas (contar `chr(10)`, não `chr(92)+"n"`, senão a última linha some embaixo).
  E o NVENC agora é testado codificando 1 quadro de verdade: listar em `-encoders` não prova nada e o render
  morria com "Cannot load libcuda.so.1" no meio.
- `--so-momentos` lista o que escolheu e PARA (confira antes de gastar voz e render); `--sem-voz` escreve o
  roteiro e para. `job\momentos.json` é editável na mão.
- Rodou de ponta a ponta aqui com gravação SINTÉTICA. Com gameplay de verdade ainda não — está dito no
  LEIA-ME e foi dito a ele.

## CATCHER DE VIRAIS URGENTES (05/nov) — `tools\viral\`, guia `tools\viral\LEIA-ME.txt`

`python tools\viral\viral.py [--termo "X"] [--vigiar 20] [--sem-baixar]`, pasta `E:\DETTO\viral`.
Notícia quente nos portais → vídeo curto EXPLODINDO sobre ela → baixa em `videos_para_react\` → avisa no
celular (Telegram/Discord). O vídeo baixado já serve de `"original"` do `react.py`, e o assunto vai para
`pautas_virais.txt`, que o canal de notícias lê como pauta — o mesmo viral vira react E vídeo de notícia.

- A REGRA DE OURO são TRÊS variáveis cruzadas, não as views: **tempo** (1 h é a janela nobre, 24 h o
  limite) × **velocidade** (views por MINUTO de vida, o `fator`) × **tamanho do perfil** (menos de 20 mil
  seguidores — senão o vídeo viralizou pelo tamanho do canal e não há onda para pegar). Conferido com
  números: 15.000 views em 29 min num perfil de 8 mil = 517 views/min = 🚨 FAÇA AGORA; o MESMO vídeo num
  canal de 2 milhões é recusado; 15.000 views com 3 dias é recusado; 15.200 em 20 h dá 13 views/min e é
  recusado (precisaria de 360).
- QUATRO COISAS QUE SÓ O TESTE CONTRA OS PORTAIS DE VERDADE MOSTROU:
  **1** `ytsearchdate:` do yt-dlp NÃO EXISTE MAIS (2026.10.26 responde "Unsupported url scheme"). A busca
  é pela URL de resultados com o `sp=` do próprio YouTube ("última hora + curto"), que ainda traz duração
  e views na listagem, de graça.
  **2** a HORA exata de cada vídeo é uma consulta por candidato — e é exatamente a consulta que o YouTube
  barra sem cookies, então TODO candidato era recusado por "não descobri a hora do post". Mas a janela da
  busca JÁ diz a idade: uso o PIOR CASO dela (1 h) e, aí, a exigência fica a base — punir duas vezes a
  mesma incerteza não deixava nada passar. O registro marca esses com "no máximo ~".
  **3** o filtro ANTIGIGANTES tratava "não sei os inscritos" como ZERO, ou seja, um canal de 2 milhões
  PASSAVA pelo filtro feito para barrá-lo. Agora os inscritos são consultados só nos FINALISTAS (poucos,
  já aprovados em views e idade) e quem fica sem o número entra MARCADO ("NÃO conferi o tamanho do
  perfil"), nunca como pequeno.
  **4** `_assunto` pegava as 3 primeiras maiúsculas soltas e saía "Saiba Saiba quem" e "Réver Réver
  manifesta" — busca que não acha nada. Nome próprio é uma SEQUÊNCIA de maiúsculas; e há uma lista
  `ABRE_MANCHETE` (saiba, veja, após, confira...) de palavras que só estão em maiúscula por abrir a
  manchete. O selo do começo ("URGENTE:") também sai, senão o termo de busca era literalmente "URGENTE".
- `_relevante` existe porque o programa BAIXA sozinho: buscar "Réver" trouxe "Rêver de laver du linge" em
  francês. Ou o título tem o termo INTEIRO, ou tem o termo e mais uma palavra forte da manchete. A
  comparação é pelo COMEÇO da palavra (5 letras), senão "Paraguay President Resigns" não casava com
  "Presidente do Paraguai renuncia" — e é justamente o vídeo gringo que ele quer reagir.
- FEEDS conferidos um por um contando os `<item>` (endereço de feed morre calado): G1, GE, GE/Atlético-MG,
  **admin**.cnnbrasil.com.br/feed/ (o `www` redireciona e o `/esportes/feed/` dá 404), UOL notícias e UOL
  esporte. Lance e R7 não devolvem item nenhum e por isso ficaram fora.
- TikTok e Instagram ESTRUTURAIS e DESLIGADOS (`"playwright": true` liga): as duas mudam o HTML toda
  semana, então a leitura é pelo JSON que a página embute, não por seletor de CSS. `feedparser` e
  `requests` são OPCIONAIS (sem eles: XML na mão e aviso só no registro).
- Lista `PROIBIDO` (criança, crime sexual, suicídio, feminicídio): assunto que ele nunca traz.

## TIKTOK SHOP — vídeos de produto automáticos (26/out)

`python tools\shop\shop.py` (painel: aba **TikTok Shop**; guia `tools\shop\LEIA-ME.txt`; pasta `E:\DETTO\shop`).
Produto → reels 9:16 pronto, e cada pronto já entra na fila de postagem (`"postar"` no config, igual aos reels).
- TRÊS ORIGENS, as três ligadas: `produtos.txt` (links colados; link de VÍDEO baixa o vídeo do vendedor junto) ·
  `produtos\<nome>\` (o que chegou em casa: as fotos/vídeos + `produto.json` com nome/preco/preco_de/link/sobre/selo;
  arquivo com "eu"/"review"/"unbox" no nome = a gravação dele) · `--achar <categoria>` (os vídeos de Shop mais vistos
  da categoria por yt-dlp → Gemini diz qual é o produto).
- TRÊS MODOS (`--modo`, ou `"modo"` no produto.json/config): `ia` (fotos + voz clonada + texto + legenda) ·
  `eu` (a gravação dele manda, fotos por cima) · `vendedor` (reaproveita o vídeo do vendedor em 9:16).
- ROTEIRO pela IA (Gemini → grátis → Claude, `REGRAS`): gancho de PROBLEMA nos 2 primeiros segundos → o produto
  resolvendo → 3 vantagens com NÚMERO concreto → objeção respondida → preço/cupom → CTA para a vitrine.
  **Proibido inventar** medida, garantia ou preço que não esteja no material (vídeo de afiliado errado derruba a conta).
- VOZ VoiceStudio → Fish (a mesma cadeia do canal), `pronuncia` + `sem_pausas`; legenda em blocos de 3 palavras pelo
  faster-whisper; cada cena termina onde cai a última palavra da fala dela (`encaixa`, o alinhamento das histórias).
- CARTELAS (`tools\shop\cartelas.js` + `palco\shop.html/css`): PNG transparente por cena (texto do topo com tarja,
  etiqueta de preço vermelha, selo, vantagens com ✓, CTA com seta para a vitrine e a cartela final), postos pelo FFmpeg
  com `overlay ... enable=between(t,...)`. Peças ESTÁTICAS de propósito: a sequência quadro a quadro em 1080x1920 com
  alfa enchia o disco dele. `*palavra*` sai amarela, `_palavra_` verde; com selo na tela o texto não sobe (ficava por baixo).
- ZOOM DA FOTO: `scale` com `eval=frame` + `crop`, **nunca `zoompan`** — o zoompan reescalava a foto inteira a cada
  quadro e levava ~57 s por cena (medido); assim leva ~2 s. Fundo desfocado é borrado em miniatura (136x240) e
  ampliado de volta, em vez de `boxblur=42` em cada quadro.
- A cartela final entra DEPOIS da última fala: a base ganha `tpad=stop_mode=clone` e o som leva `apad` (com
  `-shortest` o vídeo acabava junto com a narração e a chamada de compra sumia).
- Um `shop.py` por vez (`trava_rodada`, `.shop_rodando`). Link/pasta que não vira vídeo sai com o MOTIVO em
  `produtos_falhos.txt` → painel: "⚠ Produtos que NÃO viraram vídeo".
- LINK DE VITRINE (29/out): os links que ele cola são os CURTOS do app (`vt.tiktok.com/ZS9y...`) — não têm
  `/video/` nem `/@`, então `e_video` dava falso, o vídeo do vendedor NUNCA era baixado e o produto ficava sem
  nada. Agora `link_de_video` reconhece os curtos, `endereco_inteiro` segue o redirecionamento (e quem decide é o
  endereço de VERDADE) e a linha do produtos.txt aceita o NOME depois do link:
  `<link> | suporte de celular para mesa | 49,90` — com o nome eu busco as fotos na internet (a página do Shop
  barra robô, de lá não vem nem nome nem foto). Sem nome e sem foto: não faz vídeo e diz isso.
  A IMAGEM VEM ANTES DO ROTEIRO: a IA escrevia um roteiro inventado ("minha cozinha vivia uma bagunça") sobre um
  produto que ela não conhecia; agora o material é conferido primeiro.
- VÍDEO SAIU SEM IMAGEM NENHUMA (27/out): três furos juntos, todos consertados.
  1) **LEGENDA** — o `transcrever.py` grava uma LISTA de `{"w","s","e"}` e o shop tratava como dicionário
  (`'list' object has no attribute 'get'`): o vídeo saía com 0 legendas. `palavras` aceita lista e
  `blocos_legenda` lê `w/s/e`.
  2) **TEMPO DAS CENAS** — `encaixa` chamava o alinhamento das histórias, mas lá a fala é `narracao` e o fim é
  `ate`: não marcava NADA e o `setdefault` punha TODA cena de 0 até o fim (imagem parada e todas as cartelas na
  tela ao mesmo tempo). Agora um ESPELHO traduz as chaves nos dois sentidos.
  3) **SEM FOTO** — produto sem foto/vídeo rendia fundo escuro liso em todas as cenas. Agora `fotos_da_internet`
  busca fotos do produto (o mesmo `busca_imagem.py` das camisas, cache em `shop\fotos_web\`,
  `"fotos_internet": false` desliga) e, não achando nada, **NÃO entrega**: vai para `produtos_falhos.txt`
  dizendo para pôr as fotos em `produtos\<nome>\`. E `midia_da_cena` RODA as fotos (`i % len`) — a mesma foto em
  todas as cenas parecia vídeo travado.
- VOZ: `voicestudio_pronto` (aberto **E** com alguma voz cadastrada) no lugar do `voicestudio_ligado` no shop, nas
  histórias e no `voz.py`. Sem voz nenhuma o VoiceStudio SORTEIA uma (saía voz de mulher) — agora cai no Fish.
- **MANDAR SÓ O SHOP PARA O SÓCIO (05/nov, pedido dele):** `python tools\shop\empacotar.py` monta
  `DETTO-SHOP.zip` (0,2 MB) com INSTALAR.bat, RODAR.bat e LEIA-ME — sem canais, sem painel, sem token nem
  conta de ninguém. Ele SEGUE OS IMPORTS a partir do shop.py em vez de uma lista na mão (que envelheceria
  calada no dia em que o shop passar a importar outra coisa) e **se testa**: roda `import shop` DENTRO do
  pacote e se faltar um arquivo o empacotamento falha AQUI, não no PC do sócio. O pacote já vem com
  `"postar": []` de propósito — o shop.py importa o `postar.py` para pôr na fila, e lá isso prenderia o
  vídeo numa fila que ninguém esvazia. Os dois podem rodar ao mesmo tempo, cada um com a sua pasta
  `shop\` e o seu histórico, dividindo os links.

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
- SINCRONIZAÇÃO (22/out, v2): `encaixa_cenas` faz ALINHAMENTO GLOBAL por programação dinâmica (o mesmo jeito do
  `roteiro/align.js` dos vídeos dele): a fala do roteiro × a transcrição da voz, aceitando palavra trocada, a mais ou
  comida — cada cena termina onde caiu a ÚLTIMA palavra dela. Cena sem âncora divide o espaço entre as vizinhas pelo
  tamanho da fala. Custa ~2 ms. LEGENDA: nunca fecha em palavra fraca ("NÃO CORRA PARA A" não acontece mais, `FRACAS`
  no render.js), bloco de 1 palavra junta com o anterior e cada legenda fica na tela ATÉ a próxima entrar.
- UMA CENA POR FRASE (23/out, `uma_cena_por_frase`): a IA punha 2 ou 3 frases numa cena só e a imagem ficava parada
  enquanto a narração andava (o boneco mexendo as perninhas no mesmo lugar). Agora a cena com 2+ frases e 15+ palavras
  é PARTIDA: cada frase ganha plano e movimento diferentes, e a frase que fala do OBJETO (não do personagem) vira o
  close nele — "ele enche a garrafa" mostra ele enchendo, "quatro litros pesam quatro quilos" fecha na garrafa.
- OBJETOS QUE FALTAVAM (23/out): `interruptor` (quadro de luz, `travado` pisca o X vermelho), `elevador` (duas folhas,
  painel com o andar, `aberta`/`apagado`), `gerador` (máquina industrial com grade e luz) e `lampada` (`apagado`
  desliga o facho) — antes o roteiro usava uma `porta` aleatória para tudo isso. O `celular` ganhou TELA LEGÍVEL:
  faixa vermelha "ALERTA" e o `extra` quebrado em até 4 linhas dentro do aparelho (saía uma tela preta).
- CONFERÊNCIA ANTES DE ENTREGAR (23/out, `tools\historias\confere.py`): roda depois do render e antes de entregar.
  1) NARRAÇÃO falável — número em algarismo, R$, %, 12º, hora "20h30", subsolo "-2", sigla, símbolo: tudo reescrito
  pelo `pronuncia` (que aprendeu hora e número negativo) e o roteiro é corrigido. 2) O QUE A VOZ FALOU × o roteiro —
  mede quanto bateu e lista as palavras que não saíram; abaixo de 85% o episódio é refeito. 3) IMAGEM cena a cena —
  quadro quase preto ou chapado vira problema e a cena é clareada. Achou problema → corrige e MONTA DE NOVO uma vez.
  Saídas: `<job>\conferencia.txt` e `conferencia.jpg` (um quadro de cada cena, em folha).
- EFEITO SONORO SEMPRE (22/out, `garante_sfx`): a IA esquecia de marcar `sfx` e o episódio saía MUDO. Agora toda cena
  sem efeito ganha um pela PALAVRA da narração (`GATILHOS`: celular/vibra → mensagem, porta → porta, luz/apagou →
  click, carro/ronco → motor, água/enche → agua, tiro/grito → susto...), tensão nas cenas de escuro/tremor e um
  whoosh na virada quando passa muito tempo sem som. Nunca mais sai mudo.
- PASTA DE EFEITOS (22/out, `tools\historias\sons_web.py`): baixa do myinstants.com e monta
  `<DETTO>\historias\sons\<categoria>\` (ding, tick, relogio, passos, boom, soco, porta, pop, click, whoosh, riser,
  glitch, trovao, agua, sirene, vidro, motor). `python tools\historias\sons_web.py [--quantos 4] [--categoria X]
  [--listar]`; painel: "🔊 Baixar efeitos sonoros" (completa só o que falta; o que já tem não baixa de novo; aceita
  só 0,2 a 8 s). O `sons()` procura nessa ordem: pasta das histórias → pasta de efeitos do PC → sintetizado (`PARECIDO`
  troca a categoria que não existe pela mais próxima).
- MAIS EDIÇÃO NO EPISÓDIO PRONTO (22/out, `melhora_roteiro`, `--melhorar N`, painel "✨ Mais edição"): a IA recebe o
  roteiro já feito e devolve as cenas mais ricas (closes de apoio, objetos com estado, onomatopeia, relógio, tremor,
  movimento variado, sfx na palavra) com a NARRAÇÃO INTACTA — por isso a voz e as legendas já prontas continuam
  valendo e só o desenho é remontado (rápido e sem gastar voz).
- ANDAR SÓ QUANDO PEDIDO (22/out): `andar` vazio caía em 1 e TODO prédio saía com a etiqueta "1º ANDAR"; agora sem
  `andar` no roteiro o prédio não marca nada.
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
- A ARTE ENCHE A TELA (29/out) — era isso que deixava o episódio com cara de vazio:
  **1 ENQUADRAMENTO** `PLANO` subiu (geral 1,18 · medio 1,70 · close 2,45) e `focoAuto` aponta a câmera no assunto
  quando o roteiro não diz; **tendo gente na cena, ela é o assunto** (misturar com a lâmpada do teto puxava a
  câmera para cima e cortava o personagem). **2 TAMANHO**: cena de apoio (até 2 objetos, sem gente) vira close —
  objeto pequeno cresce 1,55x e sobe para o meio; o que o roteiro já pediu grande (s ≥ 1,3) não é mexido (antes o
  celular estourava com o texto cortado). **3 LUZ**: cena `escuro`/`noite` ganha um FACHO no foco (antes era um
  retângulo chapado, sem nada para olhar); o `mercado` escurece junto (ele desenhava o próprio fundo claro e saía
  iluminado no meio do apagão). **4 REGRA NUMERADA**: `"regra": 2` na cena = selo grande **REGRA 2** no alto
  (`#regra` no palco) — é o que faz salvar o vídeo; número solto em `onomatopeia` vira regra sozinho.
- OBJETO NOVO `radio` (rádio de pilha, `"ligado": true` manda ondas saindo da antena) — é o objeto de "a notícia
  chegou sem sinal". E `"saqueado": true` na cena do `mercado` (prateleira vazia, carrinho tombado, vidro no chão).
- CONFERIR A ARTE SEM GASTAR VOZ (29/out): `node tools\historias\folha.js <job>\roteiro.json --out folha.jpg`
  → um quadro de CADA cena numa folha (`--cena 7` para uma só). Olhe isso antes de mandar renderizar.
- ROTEIRO PRONTO VIRA EPISÓDIO (29/out): `python tools\historias\historias.py --serie <pasta> --roteiro <arquivo.json>`
  copia o roteiro para o próximo `ep_NN` e segue o caminho normal (voz dele, legendas, desenho, conferência) — é
  assim que um episódio escrito à mão (ou aqui no Claude) vira vídeo. Exemplo pronto:
  `tools\historias\exemplos\apagao_12andar.json` (prédio, 12º andar, gerador no subsolo, rádio da vizinha,
  mercado saqueado — 5 regras numeradas e escolha A/B).
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
  TEXTO QUE MUDA NO MEIO (25/out): tem meme em que a parte da PESSOA diz uma coisa ("eu no primeiro dia de aula…")
  e o LANCE diz outra ("O resto é história") — o texto da barra do lance era colado em cima da sua parte e a
  conferência barrava o reels. Agora `le_tela` lê o texto nos dois momentos: se forem diferentes (<70% de
  semelhança), cada cena fica com o texto DELA (`usar_barra` false) e a conferência compara com o texto da cena
  certa. Iguais = o da barra continua, que sai mais limpo.
  TEXTO DO MEME (25/out): `texto_do_original` não encerra mais o bloco na primeira linha que não passa no teste —
  uma linha CURTA no meio ("1 mês isolados") cortava a legenda pela metade; agora ela é pulada e o bloco só termina
  num buraco de verdade. `legenda_parada` aceita gap de parágrafo (3,6x a altura). Quando a leitura do PNG é o
  COMEÇO do texto da tela, o registro diz "o recorte pegou SÓ O COMEÇO" (é erro de recorte); palavra trocada sem
  faltar o fim é marcado como possível erro só do OCR. O recorte tem mais folga (16 px: o topo das letras saía
  cortado). Os avisos do OpenCV (YuNet) foram calados pelo `OPENCV_LOG_LEVEL=ERROR`, posto ANTES do primeiro
  `import cv2`.
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
- Notas: quem apanha mais e por último = pior nota; quem passa ou ganha carinho = melhores.
  DE ONDE VÊM AS NOTAS (27/out, `tools\galo\notas.py`): **1 banco do repositório** (`tools\galo\banco\notas\*.json`,
  vem no git pull — funciona sem internet) · **2 FotMob** (responde no PC dele; o SofaScore dá 403) · **3 SofaScore**.
  Gravar um jogo no banco: `python tools\galo\notas.py "Flamengo Atletico Mineiro" --time "Atlético Mineiro"`
  (`--listar` mostra o que já tem). Se o FotMob não responder no PC, rode isso AQUI no Claude e faça push.
  O FotMob não tem busca por texto: `acha_no_fotmob` varre o calendário dos últimos 12 dias e casa os DOIS times
  (`_e_o_jogo`: "Atletico Mineiro" bate com "Atlético-MG" por "atletico" — exigir todos os pedaços derrubava o jogo).
  JÁ NO BANCO (29/out): Atlético-MG 0 x 1 Cruzeiro (29/10, clássico) · Flamengo 3 x 2 Atlético-MG (26/10) ·
  Montevideo City Torque 2 x 0 Atlético-MG (21/10, Sul-Americana) · Atlético-MG 1 x 0 Coritiba (17/10).
  O `do_banco` pega o jogo MAIS NOVO que casa com a busca, então `"jogo": "Atletico Mineiro Cruzeiro"` já traz as
  notas de hoje. Jogo novo: rode o `notas.py` aqui no Claude e faça push.
  SEM NOTAS (27/out): o SofaScore dá 403 no PC dele, então `notas` vinha vazio, NINGUÉM era escalado e o erro
  saía como `KeyError: 'jogador'` lá no render. Agora cai no ELENCO DO BANCO (`banco\elenco`, só .png/.webp/.jpg —
  o `.gitkeep` virava "jogador"), sem nota; a escalação RODA a lista (`k % len`) em vez de `zip`, que deixava
  passagem sem nome quando havia mais gestos que jogadores; e um cinto de segurança no fim manda pôr
  `"jogadores": [...]` no jogo.json se ainda sobrar alguém sem nome. Banco vazio = mensagem dizendo para rodar
  `elenco_site.py` ou pôr os nomes no jogo.json.
- Fotos: `tools\galo\banco\elenco` (site oficial, sem fundo). Atualizar: `python tools\galo\elenco_site.py`.
- Sem placar (padrão; `"com_placar": true` liga). Corta do 1º jogador entrando até o último sair.
- SEM EFEITOS SONOROS POR PADRÃO (27/out): os sons de soco/chicote entravam por cima da fala dele. Agora o áudio da
  gravação sai INTOCADO (`-map 1:a`, sem baixar o volume) e os efeitos ficam só no `galo_tmp\sfx.wav`, para arrastar
  no app. `"sfx": true` no jogo.json põe no vídeo (`"sfx_vol"`, padrão 0,3 — bem abaixo da voz).
- CONFERIR O RASTREIO (27/out, `conferir`): sai `<saida>_conferir.jpg` — um quadro de CADA gesto lido (até 24), com
  o TEMPO e o que foi lido escritos em cima. Gesto errado se corrige no `<video>.roteiro.json` (o tempo está no
  quadro) e roda de novo, em vez de assistir o vídeo todo procurando.
- Gestos lidos ficam em `<video>.roteiro.json`; corrija ali e rode de novo. Áudio da gravação sem tratamento.
- MEDIAPIPE VELHO x PROTOBUF NOVO (27/out, `tools\mp_ajuda.py`): o erro real era
  `AttributeError: 'MessageFactory' object has no attribute 'GetPrototype'` + `TypeError: create(): incompatible
  function arguments`, enterrado em 40 linhas do grafo. `GetPrototype` saiu do protobuf novo e o mediapipe antigo
  ainda chamava — quebra TUDO que usa mediapipe (gestos do galo, recorte do VFX, rosto da thumb). **Resolve com
  `pip install --upgrade mediapipe`** (o 0.10.30+ usa `GetMessageClass` e nem depende mais do protobuf); NÃO
  rebaixar o protobuf, que o Gemini usa. `mp_ajuda.dica(e)` reconhece o erro e escreve o comando com o python certo;
  `rastrear.py` e `recorte.py` o chamam. `requirements.txt` pede `mediapipe>=0.10.30`.
- QUANDO O RASTREIO FALHA (27/out): o `rastrear.py` morria e só sobrava `CalledProcessError` com o grafo do
  MediaPipe despejado na tela — o motivo sumia. Agora `erro()` escreve "ERRO: <motivo>" e o `carregar_movimento`
  mostra a saída do filho e leva a última linha "ERRO:" para a mensagem (que o painel exibe). Defesas:
  `garante_modelo` confere o tamanho do `pose_landmarker_full.task` (~9,4 MB; <5 MB = baixa de novo para um
  `.baixando` e só então renomeia — download interrompido deixava um arquivo quebrado); `abre_detector` tenta
  VIDEO e, falhando, o modo IMAGE (mais compatível com mediapipe antigo), dizendo o erro de cada um; vídeo que o
  OpenCV não abre, fps de metadado estragado (fora de 1–240 vira 30), relógio do MediaPipe sempre crescente, e
  **nenhuma pessoa achada NÃO grava o movimento.json** (o cache fazia a rodada seguinte "funcionar" com nada dentro).

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
