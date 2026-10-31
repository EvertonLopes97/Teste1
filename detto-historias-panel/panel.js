(function () {
  const $ = (id) => document.getElementById(id);
  const idea = $('idea');
  const duration = $('duration');
  const tone = $('tone');
  const voice = $('voice');
  const ending = $('ending');
  const output = $('output');
  const status = $('status');

  $('build').addEventListener('click', () => {
    const subject = idea.value.trim();
    if (!subject) {
      status.textContent = 'Escreva uma ideia primeiro';
      idea.focus();
      return;
    }
    output.value = `Você é roteirista de vídeos curtos verticais para Reels/TikTok/Shorts. Crie uma história original em português brasileiro com o seguinte briefing.\n\nIDEIA CENTRAL: ${subject}\nDURAÇÃO TOTAL: ${duration.value} segundos\nTOM: ${tone.value}\nNARRAÇÃO: ${voice.value}\nFINAL: ${ending.value}\n\nESTRUTURA OBRIGATÓRIA:\n1. Gancho intrigante nos primeiros 1–2 segundos.\n2. Contexto rápido, sem introdução longa.\n3. Escalada de tensão ou curiosidade, com novas informações a cada poucos segundos.\n4. Reviravolta ou revelação coerente com a história.\n5. Respeite o final escolhido acima e não prometa algo que a história não entrega.\n\nENTREGUE:\n- Roteiro narrado com falas naturais e fáceis de gravar.\n- Divisão em cenas com duração em segundos, totalizando exatamente ${duration.value} segundos.\n- Para cada cena: fala, descrição visual/B-roll, texto curto na tela, sugestão de corte/transição e efeito sonoro opcional.\n- Legendas curtas, de alto contraste, sincronizadas com a fala.\n- Sugestão de trilha discreta, sempre abaixo da voz.\n- Descrição, título e comentário fixado.\n- Não invente que imagens ou sons já foram encontrados; apresente-os como sugestões de produção.\n\nFORMATO: organize o resultado em JSON válido, com title, duration_seconds, scenes (start, duration, fala, visual, texto_tela, transicao, sfx), caption, description, pinned_comment. A soma das durações das cenas deve ser exatamente ${duration.value} segundos.`;
    status.textContent = 'Briefing pronto para copiar';
  });

  $('copy').addEventListener('click', async () => {
    if (!output.value.trim()) {
      status.textContent = 'Gere o briefing primeiro';
      return;
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(output.value);
      } else {
        output.focus(); output.select();
        const copied = document.execCommand('copy');
        if (!copied) throw new Error('copy unavailable');
      }
      status.textContent = 'Copiado';
    } catch (_) {
      output.focus(); output.select();
      status.textContent = 'Selecione o texto e copie manualmente';
    }
  });
})();
