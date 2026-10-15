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
