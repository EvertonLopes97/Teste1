# Messi na Seleção: da expulsão à redenção

`EDIT_PLAN.json` gerado a partir do roteiro `roteiro_edicao_messi.txt` e da gravação
`copy_1199F4BB-9C2C-4DEC-9990-6E27CAC89A56.mov` (1920x1080, 30 fps, 8:43):

```bash
node tools/roteiro-to-plan.js roteiro_edicao_messi.txt \
  --media "C:/DETTO/messi-na-selecao/copy_1199F4BB-9C2C-4DEC-9990-6E27CAC89A56.mov" \
  --duration 523.4 --words words.json --gap 0.55 --job messi-na-selecao --out EDIT_PLAN.json
```

- Transcrição por palavra com Whisper `small` (pt). Os 49 trechos do roteiro foram encontrados na fala.
- Pausas maiores que 0,55 s removidas: 75 cortes, duração final 8:29.
- Antes de carregar no Premiere, troque `media[0].path` pelo caminho real do `.mov` na sua máquina.
