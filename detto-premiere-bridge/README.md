# DETTO PREMIERE BRIDGE

Plugin UXP para Adobe Premiere Pro que funciona como **executor** do DETTO ORCHESTRATOR.
A IA não edita o vídeo: ela produz um `EDIT_PLAN.json`, e o Bridge transforma esse plano em
projeto, sequência, tracks, clips e markers **reais e editáveis** no Premiere, usando apenas a
API oficial `premierepro` (sem simular mouse ou teclado).

```
DETTO ORCHESTRATOR → EDIT_PLAN.json → DETTO PREMIERE BRIDGE → Premiere Pro → Projeto / Sequência / Timeline
```

## Requisitos

- Premiere Pro **25.6+**, que tem a API UXP de terceiros (os tipos foram conferidos contra `@adobe/premierepro` 26.5)
- UXP Developer Tool (UDT) para carregar o plugin em desenvolvimento
- Node 20+ (somente para os testes e o typecheck)

## Instalação (desenvolvimento)

1. Abra o **UXP Developer Tool** → *Add Plugin* → selecione `plugin/manifest.json`.
2. Com o Premiere aberto, clique em **Load**. O painel aparece em *Window → UXP Plugins → DETTO VIDEO ENGINE*.
3. Em **Configurações**, escolha a pasta `detto-video-engine` (fila de jobs, logs, backups e projetos novos)
   e, de preferência, um preset `.sqpreset` com **5 tracks de vídeo e 4 de áudio** (veja *Limitações*).

O plugin não precisa de build: é JavaScript CommonJS carregado direto pelo UXP. O TypeScript é usado
para checagem estática via JSDoc (`npm run typecheck`).

## Painel

| Campo | Conteúdo |
|---|---|
| Premiere | CONNECTED / DISCONNECTED (+ versão) |
| UXP | versão do runtime |
| Project / Sequence | projeto e sequência ativos (atualizados a cada 3 s) |
| Edit Plan | arquivo carregado |
| Status | IDLE / PROCESSING / PAUSED / COMPLETE / ERROR + passo atual |

Botões: **CARREGAR EDIT PLAN**, **ANALISAR PLANO** (modo preview com contagens, erros e avisos),
**EXECUTAR**, **PAUSAR/RETOMAR** (pausa entre operações), **RENDERIZAR** (fase 2),
**ABRIR PROJETO** e **LOG** (exportável em JSONL).

## Pipeline de execução

| Passo | O que faz |
|---|---|
| `VALIDATE_PLAN` | schema + coerência (FPS, intervalos, referências, duplicados). Com erro, nada é executado |
| `DETECT_ENVIRONMENT` | versões do Premiere e do UXP e estado da conexão |
| `CHECK_MEDIA` | verifica cada arquivo no disco. Mídia ausente gera erro, e só os cortes dela são ignorados |
| `ENSURE_PROJECT` | reutiliza o projeto ativo; com `project.path`, abre o arquivo se existir ou cria se não existir; sem projeto aberto, cria em `projects/` |
| `BACKUP_PROJECT` | copia o `.prproj` salvo para `backups/` antes de alterar. Sem backup possível, pede confirmação |
| `IMPORT_MEDIA` | importa no bin `DETTO_MEDIA` somente o que ainda não está no projeto (sem duplicar) |
| `ENSURE_SEQUENCE` | reutiliza ou cria a sequência e aplica FPS/resolução. Se a sequência já tiver clips, pede confirmação; recusando, cria `NOME_<data>` e preserva a original |
| `ENSURE_TRACKS` | nomeia V1 PRESENTER, V2 B-ROLL, V3 GRAPHICS, V4 OVERLAYS, V5 VFX REFERENCES, A1 VOICE, A2 MUSIC, A3 SFX, A4 AMBIENCE |
| `PLACE_CLIPS` | overwrite de cada corte (in/out da mídia → posição na timeline), alinhado ao frame. Não duplica clips existentes e restaura o in/out do clip de origem |
| `CREATE_MARKERS` | markers com cor. Não duplica (mesmo nome e mesmo tempo) |
| `GRAPHICS_PLACEHOLDERS` | cada graphic vira um marker com duração, `GFX HEADLINE: texto`, e os dados em JSON no comentário |
| `VFX_PLACEHOLDERS` | idem, `VFX: nome` |
| `APPLY_EFFECTS` | fase 2. Hoje registra `{"status": "fallback", "reason": "effect_not_available"}` e segue |
| `SAVE_PROJECT` | salva o projeto (configurável) |

Toda edição passa por `project.lockedAccess` + `project.executeTransaction`, ou seja, cada operação
aparece no **Undo** do Premiere com o prefixo `DETTO:`.

Falhas por item (mídia ausente, corte fora do intervalo, track inexistente) são registradas e o
processo continua (`completed_with_errors`). Só falhas que deixam o estado incerto interrompem o job
(`failed`): plano inválido, Premiere desconectado, projeto inexistente, cancelamento.

## Formato do EDIT_PLAN

Veja `examples/EDIT_PLAN.example.json` e o contrato formal em `schema/edit-plan.schema.json`.
Campos além do exemplo original: `cuts[].id`, `cuts[].track` (`"V2"`, `"B-ROLL"` ou `2`),
`cuts[].audioTrack`, `media[].duration` (valida intervalos antes de executar),
`project.path`, `sequence.preset`, `markers[].comment`, `markers[].duration`, `vfx[]` e `effects[]`.

## Integração com o Orchestrator (fila de jobs)

```
detto-video-engine/
  jobs/pending/      ← Orchestrator grava job-001.json aqui
  jobs/processing/   ← Bridge move ao iniciar
  jobs/completed/    ← sucesso: job-001.json + job-001.report.json + job-001.log.jsonl
  jobs/failed/       ← falha fatal ou JSON inválido (com o .report.json explicando)
  logs/              ← cópia de todos os logs
  backups/           ← backups do .prproj
  projects/          ← projetos criados pelo Bridge
```

O Bridge verifica `jobs/pending` a cada 3 s, por polling (o UXP não tem um watcher de arquivos confiável).
Um job pode ser:

- o próprio EDIT_PLAN; nesse caso o `job_id` é o nome do arquivo;
- `{ "job_id": "job-001", "plan": { ... } }`;
- `{ "job_id": "job-001", "edit_plan_path": "C:/.../EDIT_PLAN.json" }`.

Por padrão, o job é **carregado e analisado**, e o editor clica em EXECUTAR. Com *Executar jobs
automaticamente* ligado, ele roda sem intervenção. Mesmo assim, as confirmações de segurança continuam
valendo: sequência com clips e projeto sem backup.

Cada linha de log:

```json
{"job_id":"job-001","step":"IMPORT_MEDIA","status":"success","timestamp":"2026-10-07T18:42:32.120Z","duration_ms":1200,"target":"camera_001"}
```

`status`: `success | error | warning | fallback | skipped | info`, com `reason` (código curto) e `message`.

## Estrutura do código

```
plugin/
  manifest.json, index.html, index.js, styles.css
  src/main.js            bootstrap: liga UI ↔ controller ↔ Premiere
  src/core/              lógica pura, sem UXP (testada em Node)
    schema.js            parse + validação
    analyze.js           modo preview
    executor.js          pipeline
    steps/               project, media, sequence, clips, markers, effects
    controller.js        estado do painel, execução, fila
    jobQueue.js          pending/processing/completed/failed + watcher
    logger.js, report.js, pause.js, config.js, tracks.js, time.js, paths.js, errors.js, types.js
  src/host/premiereHost.js   adaptador da API premierepro
  src/host/uxpFs.js          adaptador do fs do UXP
  src/ui/                    renderização, diálogos, configurações
schema/edit-plan.schema.json
test/                        node:test com Premiere e filesystem simulados
```

## Testes

```bash
npm install
npm test            # 105 testes
npm run typecheck   # tsc --checkJs
```

Os testes cobrem JSON inválido, mídia inexistente, projeto inexistente, sequência inexistente ou
existente, clip fora do intervalo (no plano e pela duração real detectada no Premiere), FPS
incompatível, arquivo duplicado (ids, caminhos, mídia já no projeto, reexecução sem duplicar clips e
markers), fallbacks, backup, pausa, fila de jobs, e o adaptador Premiere contra um `premierepro` falso
com as assinaturas oficiais.

## Ferramentas: roteiro → EDIT_PLAN → prévia

Para roteiros no formato DETTO (blocos com `[mm:ss – mm:ss]`, FALA/VISUAL/TELA/GRÁFICO/SFX/EFEITO/MÚSICA,
cortes verticais e errata), há dois utilitários em Node (fora do plugin):

```bash
# 1. roteiro → EDIT_PLAN (com transcrição por palavra, alinha à fala real e tira pausas)
node tools/roteiro-to-plan.js roteiro.txt --media "C:/videos/gravacao.mov" \
     --duration 523.4 --words words.json --job messi-na-selecao --out EDIT_PLAN.json

# 2. prévia renderizada com ffmpeg (textos, placas, carimbos, zooms, P&B, linha do tempo, bip)
node tools/render-preview.js EDIT_PLAN.json --video gravacao.mov --out previa.mp4 --fonts ./fonts
```

| Roteiro | EDIT_PLAN |
|---|---|
| `[TC]` | cortes na V1 (com `--words`: começo real da FALA + jump cuts nas pausas > 0,8 s) |
| TELA / GRÁFICO | `graphics` tipados: `headline`, `date_stamp`, `scoreboard`, `counter`, `cta`, `stat_card`, `timeline_bar`, `overlay` |
| EFEITO | `vfx` (`ZOOM_PUNCH_IN` na palavra citada, `SLOW_MOTION`, `DESATURATE`, `SEPIA`, `LETTERBOX`...) |
| VISUAL | marker laranja `B-ROLL: termo de busca` (V2) |
| SFX / MÚSICA | `audio[]` (fase 2) + markers de troca de trilha; bip opcional no palavrão |
| blocos, linha do tempo, OBS, 9:16 | markers (azul, ciano, vermelho, roxo) |
| errata | `meta.errata` (para a legenda) |

### Edição dinâmica (estilo Reels/YouTube de futebol)

```bash
# 1. rastreia o rosto (para zooms e janelas centrados no rosto)
python tools/motion/facetrack.py gravacao.mov face.json --model face_detection_yunet_2023mar.onnx

# 2. edição horizontal Full HD
node tools/render-dynamic.js EDIT_PLAN.json --video gravacao.mov --face face.json \
     --fonts ./fonts --work ./tmp-render --out edicao.mp4

# 3. corte vertical 9:16 sugerido no roteiro (1080x1920)
node tools/render-dynamic.js EDIT_PLAN.json --video gravacao.mov --face face.json \
     --fonts ./fonts --work ./tmp-render --cut 1 --out corte1_vertical.mp4
```

| Etapa | O que faz |
|---|---|
| `motion/facetrack.py` | Rastreia o rosto (OpenCV YuNet, 5 amostras/s, trajetória suavizada). |
| `motion/media-search.js` | Fotos de apoio com licença livre para uso comercial (CC0, domínio público, CC BY, CC BY-SA) via Openverse. A escolha leva em conta época, adversário, estádio e competição, evita repetir foto e gera `creditos.txt`. |
| `motion/director.js` | Cada gráfico entra na palavra exata em que é falado (âncora na transcrição: placar "2x1", número, também por extenso, mês da data, nomes). Os gráficos alternam entre estilos: `full` (só o gráfico ou a foto em tela cheia, com a voz ao fundo), `camWindow` (você numa janela com moldura e o gráfico ao lado), `gfxCard` (gráfico num card sobre a câmera) e `photoCard` (foto num quadro com zoom lento). A base é o enquadramento original da gravação; o rosto só é centralizado na dinâmica: zoom seco a cada 3 jump cuts, aproximação lenta nos trechos de suspense (`SLOW_ZOOM`, `BREATH`, `SLOW_MOTION`, `FREEZE_FRAME`) e punch-ins nas deixas, com tremor amortecido de ~2 Hz nos impactos. |
| `motion/stage/*` | Compositor HTML/CSS determinístico: câmera e gráficos no mesmo quadro. |
| `motion/render-frames.js` | Extrai os quadros da gravação (com jump cuts) e compõe cada quadro no Chromium, em paralelo, a 1920x1080 (ou 1080x1920). |
| `motion/sfx.js`, `motion/audio.js` | SFX sintetizados + voz sem deriva + bip opcional, em -14 LUFS. |

Opções: `--format vertical`, `--cut N` (corte 9:16 do roteiro), `--from/--to` (trecho), `--no-images 1`,
`--crf 18`, `--workers 4`.

Para gerar o plano com legendas, use `--words` no `roteiro-to-plan.js` (`--srt` grava as legendas
também em `.srt` para o Premiere). Bandeiras: flagcdn.com (domínio público). Fonte dos títulos: Anton (OFL).

`words.json` é uma lista `[{"w": "palavra", "s": 1.23, "e": 1.48}]`, por exemplo a saída do
Whisper com `word_timestamps=True`. A prévia usa as fontes do roteiro (Anton para títulos) se a pasta
`--fonts` tiver `Anton-Regular.ttf`.

## Limitações conhecidas (fase 1)

- **Criar tracks:** a API UXP atual não oferece isso de forma confiável. Use um `.sqpreset` com 5V/4A
  (Configurações ou `sequence.preset`). Itens destinados a tracks inexistentes viram erro por item, e um
  fallback `track_creation_not_available` é registrado.
- **Graphics e VFX** são placeholders em forma de marker. A troca por MOGRT
  (`SequenceEditor.insertMogrtFromPath`) fica para a fase 2.
- **Effects, áudio, export e render:** fase 2. Hoje geram fallback registrado e não quebram o job.
- O backup copia o último estado **salvo** do `.prproj`. Alterações não salvas no momento da execução
  não entram na cópia.
- O adaptador foi validado contra os tipos oficiais e um Premiere simulado. Ainda falta rodar em
  Premiere real via UDT.

## Roadmap

1. ✅ manifest, painel, conexão, leitura e validação do plano, projeto/sequência, importação, timeline, markers, logging, fila de jobs
2. ⏳ graphics (MOGRT), effects (`VideoFilterFactory` / `ComponentChain`), áudio, export (`EncoderManager`) e render
