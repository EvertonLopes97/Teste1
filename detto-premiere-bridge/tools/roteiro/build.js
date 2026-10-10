// @ts-check
"use strict";

const { makeMapper } = require("./align");
const { roteiroComponents } = require("./componentes");

/**
 * Converte um roteiro já parseado (parse.js) em EDIT_PLAN para o Bridge.
 *
 * Mapeamento:
 *   [TC]        → cut na V1 PRESENTER (mesmo tempo na mídia e na timeline)
 *   TELA        → graphics (headline, date_stamp, counter, cta...)
 *   GRÁFICO     → graphics (scoreboard, timeline_bar, stat_card...)
 *   EFEITO      → vfx (ZOOM_PUNCH_IN, SLOW_MOTION, DESATURATE...)
 *   VISUAL      → marker "B-ROLL: <termo de busca>" (o b-roll não vem junto)
 *   SFX/MÚSICA  → audio[] (fase 2) + marker de troca de trilha
 *   blocos, linha do tempo, OBS, palavrão, cortes 9:16 → markers
 */

/**
 * @typedef {Object} BuildOptions
 * @property {string} mediaPath
 * @property {string} [mediaId]
 * @property {number} fps
 * @property {number} width
 * @property {number} height
 * @property {string} [projectName]
 * @property {string} [sequenceName]
 * @property {number} [mediaDuration]  se conhecido, cortes além da mídia são descartados/encurtados
 * @property {string} [jobId]
 * @property {Array<{start: number, end: number}>} [keep]  trechos de fala (jump cuts) vindos do alinhamento
 */

/** @param {string} s */
function quoted(s) {
  const out = [];
  const re = /"([^"]+)"/g;
  let m;
  while ((m = re.exec(s))) out.push(m[1].trim());
  return out;
}

/** @param {string} s */
function slug(s) {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** @param {number} t */
function tc(t) {
  const m = Math.floor(t / 60);
  const s = Math.round(t - m * 60);
  return `${String(m).padStart(2, "0")}m${String(s).padStart(2, "0")}s`;
}

/**
 * Classifica um trecho de TELA/GRÁFICO.
 * @param {string} part
 * @param {"TELA"|"GRAFICO"} field
 */
function graphicType(part, field) {
  const p = part.toUpperCase();
  if (/PLACA|PLACAR ANIMADO|CHAVEAMENTO|PLACAS EM SEQU/.test(p) || /\d\s*X\s*\d/.test(p)) return "scoreboard";
  if (/CARIMBO/.test(p)) return "date_stamp";
  if (/FICHA|ESTANTE|BOLAS DE OURO|TAÇAS EM SILHUETA/.test(p)) return "stat_card";
  if (/BARRA DE RODAP|LINHA DO TEMPO/.test(p)) return "timeline_bar";
  if (/CONTADOR|CRONÔMETRO|RELÓGIO|MEDIDOR/.test(p) || (!/["→]/.test(part) && /^[^:]{2,30}:\s*\+?[\d.]+/.test(part.replace(/^\W+/u, "")))) return "counter";
  if (/INSCREV|SEGUIR|COMENTA|COMPARTILH|SALVA E MANDA|CURTE|ENQUETE|CAIXA DE COMENT/.test(p)) return "cta";
  if (/MAPA/.test(p)) return "overlay";
  return field === "GRAFICO" ? "overlay" : "headline";
}

/**
 * Texto a exibir: strings entre aspas; senão o conteúdo depois de "PLACA:" etc.
 * @param {string} part
 */
function graphicText(part) {
  // parênteses de instrução ("(a placa aparece e desbota...)") saem; "(pênaltis: 4 x 2)" e "(PRORROGAÇÃO)" ficam
  const clean = part.replace(/\s*\(([^)]*)\)/g, (all, inner) => (/\d/.test(inner) || inner === inner.toUpperCase() ? all : ""));
  const placa = clean.match(/PLAC(?:A(?: DE PLACAR| FINAL)?|AR ANIMADO)\s*:\s*([^;]+)/i);
  if (placa) return placa[1].replace(/\s+com setas.*$/i, "").trim();
  // "CHAVEAMENTO ...: ARÁBIA SAUDITA 2 x 1 ARGENTINA" → só o placar
  const colon = clean.indexOf(":");
  if (colon >= 0) {
    const left = clean.slice(0, colon);
    const right = clean.slice(colon + 1).trim();
    if (!/\d\s*x\s*\d/.test(left) && /\d\s*x\s*\d/.test(right)) return right;
  }
  // aspas com palavra minúscula costumam ser descrição de animação ("bate", "pop")
  const q = quoted(clean).filter((t) => !/\p{L}/u.test(t) || t !== t.toLowerCase());
  if (q.length) return q.join(" → ");
  if (colon >= 0) {
    // "duelo lado a lado: MESSI x MBAPPÉ" → depois dos dois-pontos
    const left = clean.slice(0, colon);
    const right = clean.slice(colon + 1).trim();
    if (left === left.toLowerCase() && right && right !== right.toLowerCase()) return right;
  }
  if (/\d\s*x\s*\d/.test(clean)) return clean.trim();
  const caps = clean.match(/[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9+][A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9 •:'?!./─+-]{3,}/g);
  const letters = clean.replace(/[^\p{L}]/gu, "").length;
  const capsLetters = (caps || []).join("").replace(/[^\p{L}]/gu, "").length;
  // linha com maiúsculas e minúsculas misturadas ("Mundial Sub-20 2005"): mantém como está
  const strong = (caps || []).filter((c) => /[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{3,}/.test(c));
  if (strong.length || (caps && capsLetters >= letters * 0.5)) return (strong.length ? strong : caps || []).map((c) => c.trim()).join(" ");
  return clean.trim();
}

/**
 * Divide TELA/GRÁFICO em itens: ";" e quebras de linha separam itens; "|" só separa
 * listas de placares (em "2016 (P&B) | 2026 (cor)" ou "MESSI 126 | BATISTUTA 56" é texto).
 * Linhas só com instrução ("título do vídeo animado:", "(subindo 1, 2, 3...)") viram
 * contexto do item vizinho em vez de item próprio.
 * @param {string} s
 */
function splitParts(s) {
  const raw = s
    .split(/;\s*|\n|\s+\|\s+(?=[^|()]*\d\s*x\s*\d)/)
    .map((p) => p.replace(/^depois[,:]?\s*/i, "").trim())
    .filter(Boolean);
  /** @type {string[]} */
  const parts = [];
  let prefix = "";
  for (const p of raw) {
    if (/^\(.*\)$/.test(p) && parts.length) {
      parts[parts.length - 1] += ` ${p}`;
    } else if (/:$/.test(p) && !/[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{3,}/.test(p.replace(/"[^"]*"/g, ""))) {
      prefix += `${p} `;
    } else {
      parts.push(prefix + p);
      prefix = "";
    }
  }
  if (prefix.trim() && parts.length) parts[parts.length - 1] += ` ${prefix.trim()}`;
  return parts;
}

/** Tags de VFX reconhecidas no texto de EFEITO. */
const VFX_TAGS = [
  [/punch-?in|zoom brusco|meme zoom/i, "ZOOM_PUNCH_IN"],
  [/zoom lento|ken burns/i, "SLOW_ZOOM"],
  [/zoom no seu rosto/i, "ZOOM_PUNCH_IN"],
  [/linha do tempo/i, "TIMELINE_BAR"],
  [/fundo azul-celeste/i, "BACKGROUND_PLATE"],
  [/ganhando cor|volta a ter cor/i, "COLOR_RESTORE"],
  [/slow motion|câmera lenta/i, "SLOW_MOTION"],
  [/freeze frame/i, "FREEZE_FRAME"],
  [/camera shake|tremor de câmera|tremendo/i, "CAMERA_SHAKE"],
  [/preto e branco|P&B|dessatura/i, "DESATURATE"],
  [/sépia/i, "SEPIA"],
  [/glow|brilho dourado/i, "GOLD_GLOW"],
  [/split screen/i, "SPLIT_SCREEN"],
  [/letterbox|barras (pretas|de cinema)/i, "LETTERBOX"],
  [/flash branco/i, "FLASH"],
  [/grão de filme|foto antiga/i, "FILM_GRAIN"],
  [/vinheta/i, "VIGNETTE"],
  [/confete/i, "CONFETTI"],
  [/glitch/i, "GLITCH"],
  [/fade to black/i, "FADE_TO_BLACK"],
  [/cortes? (secos|cada vez mais rápidos)/i, "RHYTHM_CUTS"],
  [/c[íi]rculo vermelho/i, "HAND_DRAWN_CIRCLE"],
  [/flashback|blur/i, "FLASHBACK_TRANSITION"],
  [/CTA|borda dourada/i, "CTA_HIGHLIGHT"],
  [/respiro/i, "BREATH"],
];

/**
 * @param {import("./parse").Roteiro} roteiro
 * @param {BuildOptions} opts
 */
function buildPlan(roteiro, opts) {
  const mediaId = opts.mediaId || "facecam_001";
  const limit = typeof opts.mediaDuration === "number" ? opts.mediaDuration : Infinity;
  const round = (/** @type {number} */ t) => Math.round(t * opts.fps) / opts.fps;
  const segments = roteiro.segments.filter((s) => s.start < limit);

  /** @type {any[]} */ const cuts = [];
  /** @type {any[]} */ const markers = [];
  /** @type {any[]} */ const graphics = [];
  /** @type {any[]} */ const vfx = [];
  /** @type {any[]} */ const audio = [];
  /** @type {any[]} */ const segMeta = [];

  // com alinhamento (keep = trechos de fala), as pausas saem e os tempos são remapeados
  const keep = opts.keep || null;
  const tl = keep ? makeMapper(keep) : (/** @type {number} */ t) => t;
  /** tempo do roteiro original ([TC]) → tempo alinhado, para os cortes 9:16 */
  const fromTc = (/** @type {number} */ t) => {
    const a = segments.find((s) => /** @type {any} */ (s).tc === t);
    if (a) return a.start;
    const b = segments.find((s) => /** @type {any} */ (s).tcEnd === t);
    if (b) return b.end;
    // entre trechos: proporcional ao tempo do roteiro
    const S = /** @type {any[]} */ (segments).filter((s) => typeof s.tc === "number");
    const k = S.findIndex((s) => s.tc > t);
    if (k <= 0) return k === 0 ? S[0].start : S.length ? S[S.length - 1].end : t;
    const p = S[k - 1];
    const n = S[k];
    return p.start + ((t - p.tc) / Math.max(1e-6, n.tc - p.tc)) * (n.start - p.start);
  };
  /** primeira deixa citada no texto que foi encontrada na fala */
  const cueIn = (/** @type {any} */ seg, /** @type {string} */ text) => {
    for (const q of quoted(text || "")) if (seg.cues && typeof seg.cues[q] === "number") return seg.cues[q];
    return null;
  };

  if (keep) {
    // um corte por trecho de fala, quebrado também nas fronteiras do roteiro
    const bounds = segments.map((s) => s.start).filter((t) => t > 0);
    // timeline acumulada em frames inteiros: cortes encostados, sem sobreposição por arredondamento
    let tlFrame = 0;
    for (const k of keep) {
      if (k.start >= limit) continue;
      const pieces = [k.start, ...bounds.filter((b) => b > k.start && b < k.end), Math.min(k.end, limit)];
      for (let j = 0; j + 1 < pieces.length; j++) {
        const a = pieces[j];
        const b = pieces[j + 1];
        const aF = Math.round(a * opts.fps);
        const bF = Math.round(b * opts.fps);
        if (bF - aF < 2) continue;
        cuts.push({ id: `cut_${String(cuts.length + 1).padStart(3, "0")}`, source: mediaId, start: aF / opts.fps, end: bF / opts.fps, timeline: tlFrame / opts.fps, track: "V1", audioTrack: "A1" });
        tlFrame += bF - aF;
      }
    }
  }

  // roteiro com MODO (CAM / CAM+MG / MG+VO / LANCE+VO): componentes estruturados (cards, campinho...)
  const modos = segments.some((s) => s.fields.MODO);
  const comp = modos ? roteiroComponents({ ...roteiro, segments }) : null;

  let lastBlock = "";
  segments.forEach((seg, i) => {
    const end = Math.min(seg.end, limit);
    const S = round(tl(seg.start));
    const E = round(tl(end));
    const dur = Math.max(E - S, 1 / opts.fps);
    const id = `seg_${tc(seg.start)}`;
    if (!keep) cuts.push({ id, source: mediaId, start: seg.start, end: round(end), timeline: seg.start, track: "V1", audioTrack: "A1" });
    const allText = [seg.fields.TELA, seg.fields.GRAFICO].filter(Boolean).join(" ");
    segMeta.push({
      id,
      start: S,
      end: E,
      block: seg.block,
      broll: !!seg.fields.VISUAL && !/^facecam/i.test(seg.fields.VISUAL.trim()),
      mood: /derrota|perdid|expuls|vaiad|triste|elimina|desespero|adeus|zebra|no banco/i.test(allText)
        ? "loss"
        : /campe[ãa]o|t[íi]tulo|ouro|vit[óo]ria|virada|bicampe|recorde|confete/i.test(allText)
          ? "win"
          : "",
      ...(comp
        ? { modo: comp.segments[i].modo, lance: comp.segments[i].lance, comps: comp.segments[i].comps, sub: /** @type {any} */ (seg).sub || "", fala: seg.fields.FALA || "" }
        : {}),
    });

    if (seg.block !== lastBlock) {
      markers.push({ id: `block_${i}`, time: S, name: seg.block, color: "blue", comment: `Início: ${seg.block}` });
      lastBlock = seg.block;
    }
    for (const ev of seg.events) {
      const year = ev.match(/LINHA DO TEMPO avança para (\d{4})/i);
      if (year) markers.push({ time: S, name: `LINHA DO TEMPO → ${year[1]}`, color: "cyan", comment: ev });
      else if (/^M[ÚU]SICA/i.test(ev)) markers.push({ time: S, name: ev.slice(0, 60), color: "green", comment: ev });
      else markers.push({ time: S, name: ev.slice(0, 60), color: "white", comment: ev });
    }
    seg.notes.forEach((n, k) =>
      markers.push({ id: `${id}_obs${k}`, time: S, duration: dur, name: `OBS: ${n.replace(/^OBS[^:]*:\s*/i, "").slice(0, 50)}`, color: "red", comment: n })
    );

    const visual = seg.fields.VISUAL;
    if (visual && !/^facecam/i.test(visual.trim())) {
      const terms = quoted(visual);
      markers.push({
        id: `${id}_broll`,
        time: S,
        duration: dur,
        name: `B-ROLL: ${(terms[0] || visual).slice(0, 60)}`,
        color: "orange",
        comment: `V2 B-ROLL • ${visual}`,
      });
    }

    for (const field of /** @type {const} */ (["TELA", "GRAFICO"])) {
      const value = modos ? "" : seg.fields[field]; // com MODO, os componentes substituem os gráficos genéricos
      if (!value) continue;
      const parts = splitParts(value);
      const step = Math.min(1.5, dur / Math.max(parts.length, 1));
      parts.forEach((part, k) => {
        const cue = cueIn(seg, part);
        const start = round(cue !== null ? tl(cue) : S + (field === "GRAFICO" ? 0.5 : 0) + k * step);
        if (start >= E) return;
        const text = graphicText(part);
        if (!text.replace(/[^\p{L}\p{N}]/gu, "")) return;
        const isInstruction = text === text.toLowerCase() && !/\d/.test(text);
        graphics.push({
          id: `${id}_${field === "TELA" ? "tela" : "gfx"}${k}`,
          type: isInstruction ? "generic" : graphicType(part, field),
          start,
          duration: round(Math.max(1 / opts.fps, E - start)),
          text,
          description: part,
        });
      });
    }

    const efeito = seg.fields.EFEITO;
    if (efeito) {
      const tags = VFX_TAGS.filter(([re]) => /** @type {RegExp} */ (re).test(efeito)).map(([, tag]) => /** @type {string} */ (tag));
      const name = tags.length ? tags.join("+") : "VFX";
      const isPunch = tags.length === 1 && tags[0] === "ZOOM_PUNCH_IN";
      const cue = cueIn(seg, efeito);
      // punch-in pontual: na deixa falada, se encontrada; senão posição aproximada
      const start = isPunch ? round(cue !== null ? Math.max(S, tl(cue) - 0.1) : S + dur * 0.4) : S;
      vfx.push({
        id: `${id}_vfx`,
        name,
        start,
        duration: round(isPunch ? Math.max(1 / opts.fps, Math.min(1.6, E - start)) : dur),
        description: efeito,
        approximate: isPunch && cue === null,
      });
    }
    if (seg.fields.SFX) audio.push({ id: `${id}_sfx`, type: "sfx", start: S, duration: round(dur), description: seg.fields.SFX });
    if (seg.fields.MUSICA) {
      audio.push({ id: `${id}_music`, type: "music", start: S, duration: round(dur), description: seg.fields.MUSICA });
      markers.push({ time: S, name: `MÚSICA: ${seg.fields.MUSICA}`.slice(0, 60), color: "green", comment: seg.fields.MUSICA });
    }
  });

  for (const note of roteiro.timedNotes) {
    if (note.time >= limit) continue;
    const t = round(tl(note.time));
    const n = /** @type {any} */ (note);
    markers.push({ time: t, name: note.text.split(":")[0].slice(0, 40), color: "red", comment: note.text });
    if (n.end && /bip/i.test(note.text)) {
      audio.push({ id: "bleep_palavrao", type: "bleep", start: t, duration: round(Math.max(0.2, tl(n.end) - t)), description: `bip sobre "${n.word}" (opcional)` });
    }
  }
  for (const vc of roteiro.verticalCuts) {
    vc.ranges.forEach((r, k) => {
      const a = fromTc(r.start);
      const b = fromTc(r.end);
      if (a >= limit) return;
      markers.push({
        id: `vertical_${vc.index}_${k}`,
        time: round(tl(a)),
        duration: round(tl(Math.min(b, limit)) - tl(a)),
        name: `9:16 #${vc.index}: ${vc.title}`.slice(0, 60),
        color: "purple",
        comment: vc.hook ? `Gancho: ${vc.hook}` : vc.title,
      });
    });
  }

  // markers no mesmo instante e com o mesmo nome seriam deduplicados pelo Bridge
  const seen = new Set();
  const uniqueMarkers = markers
    .filter((m) => {
      const k = `${m.name}|${m.time}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    })
    .sort((a, b) => a.time - b.time);

  const projectName = opts.projectName || slug(roteiro.title || "detto-video");
  return {
    version: "1.0",
    ...(opts.jobId ? { job_id: opts.jobId } : {}),
    project: { name: projectName, fps: opts.fps, width: opts.width, height: opts.height },
    media: [{ id: mediaId, path: opts.mediaPath, ...(Number.isFinite(limit) ? { duration: limit } : {}) }],
    sequence: { name: opts.sequenceName || "DETTO_MASTER", fps: opts.fps, width: opts.width, height: opts.height },
    cuts,
    markers: uniqueMarkers,
    graphics,
    vfx,
    audio,
    meta: {
      source: "roteiro",
      ...(comp ? { mode: "modos", people: comp.people } : {}),
      title: roteiro.title,
      blocks: roteiro.blocks,
      segments: segMeta,
      errata: roteiro.errata,
      vertical_cuts: roteiro.verticalCuts,
      notes: keep
        ? "Tempos alinhados à fala pela transcrição; pausas longas removidas (jump cuts). Graphics/VFX são placeholders (fase 1)."
        : "Tempos do roteiro são aproximados; ajustar na timeline. Graphics/VFX são placeholders (fase 1).",
    },
  };
}

module.exports = { buildPlan, graphicType, graphicText, splitParts, quoted, slug };
