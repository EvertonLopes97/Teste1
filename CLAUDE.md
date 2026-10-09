# DETTO — editor de vídeos do @detto.galo

Você é o editor/programador deste projeto. O dono é o Everton (fala português; responda em português,
curto e direto). Máquina: Dell G15 (Windows 11, Ryzen 5 6600H, 16 GB, RTX 3050 4 GB), Premiere Pro 2022,
After Effects 2020. Disco com pouco espaço livre: apague pastas `tmp`/`galo_tmp` depois de cada render.

Código em `detto-premiere-bridge/`. Rode os comandos a partir dessa pasta.

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

### Modo gestos (jogadores reagem às mãos do Everton) — padrão para os reels do Galo

`python tools\galo\gestos.py <pasta>\jogo.json` (mesmo jogo.json; `pip install mediapipe==0.10.14` na 1ª vez).
- Rastreia o corpo (`rastrear.py`, salva `<video>.movimento.json`), acha PANCADA / TAPA / CARINHO / EMPURRÃO / PUXÃO,
  divide o vídeo entre os jogadores, põe cada um onde a mão bate, com som em cada gesto. Placar fica acima da cabeça.
- Sem foto no banco → baixa o recorte oficial do TheSportsDB (fotos do Atlético iguais às do reel).
- Imprime a lista de gestos; para corrigir, cole em `"gestos": [[t, "tipo"], ...]` no jogo.json e rode de novo.
