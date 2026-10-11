// @ts-nocheck — heurísticas de texto do roteiro (testadas em test/componentes.test.js)
"use strict";

/**
 * Lê os pedidos de tela do roteiro no formato com MODOS (MODO / MG / VFX / TELA / LANCE)
 * e transforma em componentes de motion graphics com dados estruturados:
 *
 *   cards      cards de jogador (foto, escudo, nome, nota com a cor da escala SofaScore)
 *   pitch      campinho (seleção da rodada / dos piores) com os mini-cards na formação
 *   scoregrid  placas de placar da rodada (os jogos citados na FALA)
 *   duel       dois escudos frente a frente com barras de pontos
 *   var        tela de VAR ("CHECKING...")
 *   quote      aspas com a frase e o autor
 *   poll       enquete
 *   vinheta    título de bloco ("GOLEIROS", "DEFESA")
 *   stamps     selos/carimbos ("ANULADO", "✅ CORRETO")
 *   bignum     números grandes caindo ("10" três vezes)
 *   redcard    cartão vermelho
 *   headline   texto de tela em batidas ("MELHORES • PIORES • POLÊMICAS")
 *   cta        curtir / seguir / comentar
 *
 * Cada componente traz "âncoras" (o que é falado quando ele entra), para o diretor
 * sincronizar com a fala real.
 */

const TEAMS = require("./times.json").times;

/** @param {string} s */
function norm(s) {
  return String(s || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}
/** @param {string} s */
const words = (s) => norm(s).replace(/[^a-z0-9]+/g, " ").trim().split(" ").filter(Boolean);
/** @param {string} s */
function stripEmoji(s) {
  return String(s || "")
    .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}\u{2B00}-\u{2BFF}\u{E0000}-\u{E007F}\u{2190}-\u{21FF}]/gu, "")
    .replace(/\s+/g, " ")
    .trim();
}
/** @param {string} s */
function titleCase(s) {
  return s.toLowerCase().replace(/(^|[\s.-])(\p{L})/gu, (_, a, b) => a + b.toUpperCase());
}

/**
 * Clube citado no texto (apelido, nome ou sigla). Com `cap`, só vale palavra com inicial
 * maiúscula (na FALA, "a vitória do Palmeiras" não é o Vitória).
 * @param {string} text @param {{cap?: boolean, sigla?: boolean}} [o]
 */
function findTeam(text, o = {}) {
  const t = ` ${words(text).join(" ")} `;
  let best = null;
  for (const team of TEAMS) {
    for (const ap of team.apelidos) {
      if (ap.length <= 3 && !o.sigla && ap !== norm(team.sigla).slice(0, 3)) continue;
      if (ap.length <= 3 && !o.sigla) continue;
      const i = t.indexOf(` ${ap} `);
      if (i < 0) continue;
      if (o.cap) {
        // confere a inicial maiúscula no texto original
        const re = new RegExp(`(^|[^\\p{L}])${ap.split(" ")[0].replace(/[aeiou]/g, ".")}`, "iu");
        const m = String(text).normalize("NFD").replace(/[̀-ͯ]/g, "").match(re);
        if (!m || !/^\p{Lu}/u.test(String(text).normalize("NFD").replace(/[̀-ͯ]/g, "").slice((m.index || 0) + m[1].length))) continue;
      }
      if (!best || i < best.i || (i === best.i && ap.length > best.len)) best = { team, i, len: ap.length };
    }
  }
  return best ? best.team : null;
}
/**
 * Todos os clubes citados, na ordem do texto. cap: só com inicial maiúscula (fala).
 * @param {string} text @param {{cap?: boolean}} [o]
 */
function findTeams(text, o = {}) {
  const plain = String(text || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const found = [];
  for (const team of TEAMS) {
    let best = Infinity;
    for (const ap of team.apelidos) {
      if (ap.length <= 3) continue;
      const re = new RegExp(`(^|[^\\p{L}])(${ap.replace(/[-\s]+/g, "[-\\s]+")})(?![\\p{L}])`, "giu");
      for (const m of plain.matchAll(re)) {
        if (o.cap && !/^\p{Lu}/u.test(m[2])) continue;
        best = Math.min(best, (m.index || 0) + m[1].length);
      }
    }
    if (best < Infinity) found.push({ team, i: best });
  }
  return found.sort((a, b) => a.i - b.i).map((f) => f.team);
}

/** @param {string} sigla */
const teamBySigla = (sigla) => TEAMS.find((t) => t.sigla === sigla.toUpperCase() || t.apelidos.includes(norm(sigla))) || null;

/** @param {string} r */
const rating = (r) => Number(String(r).replace(",", "."));

// ------------------------------------------------------------------ elenco citado no roteiro

const NAME = String.raw`(?:[A-ZÀ-Ý]\.\s?)?[A-ZÀ-Ý][A-ZÀ-Ý'’]+(?:[ -][A-ZÀ-Ý][A-ZÀ-Ý'’]+)*`;
const NOTE = String.raw`(10(?:,0)?|\d,\d)(?![\d,])`;
const MENTION_RE = new RegExp(String.raw`(${NAME})\s*(?:\(([^)]*)\))?\s*${NOTE}(\s*\([^)]*\))?`, "gu");
const NOT_NAME = new Set(["CARD", "CARDS", "DO", "DA", "DE", "DOS", "DAS", "BADGE", "NOTA", "VS", "MG", "COM", "E", "O", "A", "CAPITÃO", "CAPITAO"]);

/**
 * @typedef {{name: string, team: any, rating: number|null, key: string[]}} Person
 */
class Roster {
  constructor() {
    /** @type {Person[]} */
    this.list = [];
  }
  /**
   * Acha a pessoa pelo nome (completo, "A. TELLES", só o sobrenome) ou cria.
   * @param {string} raw @param {{team?: any, rating?: number|null, create?: boolean}} [o]
   */
  get(raw, o = {}) {
    const key = words(raw).filter((w) => !NOT_NAME.has(w.toUpperCase()));
    if (!key.length) return null;
    const initial = /^[A-ZÀ-Ý]\.\s?/.test(raw.trim()) ? key[0][0] : null;
    const sur = key[key.length - 1];
    const same = (/** @type {Person} */ p) => p.key.join(" ") === key.join(" ");
    let p = this.list.find(same);
    if (!p && initial) p = this.list.find((x) => x.key.length > 1 && x.key[x.key.length - 1] === sur && x.key[0][0] === initial);
    if (!p && key.length === 1) {
      // "TELLES" → Alex Telles; mas "ERICK" não é "Erick Pulga" quando a nota não bate
      const c = this.list.filter((x) => x.key[x.key.length - 1] === sur || (x.key.length === 1 && x.key[0] === sur));
      p = c.find((x) => o.rating == null || x.rating == null || x.rating === o.rating) || null;
      if (p && p.key.length > 1 && p.key[0] === sur) p = null;
    }
    if (!p && key.length > 1 && !initial) {
      // nome completo novo cujo sobrenome já existe com a mesma nota: é a mesma pessoa
      p = this.list.find((x) => x.key.length === 1 && x.key[0] === sur && (o.rating == null || x.rating === o.rating)) || null;
      if (p) {
        p.key = key;
        p.name = titleCase(raw);
      }
    }
    if (!p) {
      if (o.create === false) return null;
      if (initial) return null; // abreviação de alguém que não conhecemos
      p = { name: /\p{Ll}/u.test(raw) ? raw.trim() : titleCase(raw.trim()), team: null, rating: null, key };
      this.list.push(p);
    }
    if (o.team && !p.team) p.team = o.team;
    if (o.rating != null && p.rating == null) p.rating = o.rating;
    return p;
  }
  /**
   * Pessoas do elenco citadas num texto (sem nota), na ordem em que aparecem.
   * @param {string} text
   */
  inText(text) {
    const t = ` ${words(text).join(" ")} `;
    /** @type {Array<{p: Person, i: number}>} */
    const found = [];
    const used = /** @type {Array<[number, number]>} */ ([]);
    // nomes completos primeiro (mais longos), depois sobrenomes
    const cands = this.list.flatMap((p) => [
      { p, s: p.key.join(" ") },
      ...(p.key.length > 1 && p.key[p.key.length - 1].length >= 4 ? [{ p, s: p.key[p.key.length - 1] }] : []),
      // primeiro nome raro ("Flaco"), se ninguém mais tem
      ...(p.key.length > 1 && p.key[0].length >= 5 && this.list.filter((x) => x.key[0] === p.key[0]).length === 1 ? [{ p, s: p.key[0] }] : []),
    ]);
    cands.sort((a, b) => b.s.length - a.s.length);
    for (const c of cands) {
      let from = 0;
      for (;;) {
        const i = t.indexOf(` ${c.s} `, from);
        if (i < 0) break;
        from = i + 1;
        const j = i + c.s.length + 1;
        if (used.some(([a, b]) => i < b && j > a)) continue;
        used.push([i, j]);
        if (!found.some((f) => f.p === c.p)) found.push({ p: c.p, i });
      }
    }
    return found.sort((a, b) => a.i - b.i).map((f) => f.p);
  }
}

/**
 * O nome aparece sozinho na fala (não é "Anderson Daronco" quando o jogador é "Anderson").
 * @param {string} text @param {Person} p
 */
function alone(text, p) {
  const plain = String(text).normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const low = plain.toLowerCase();
  const test = (/** @type {string} */ name, /** @type {boolean} */ strict) => {
    const re = new RegExp(`\\b${name.replace(/ /g, "\\s+")}\\b`, "g");
    for (const m of low.matchAll(re)) {
      const after = plain.slice((m.index || 0) + m[0].length);
      if (!strict || !/^\s+\p{Lu}/u.test(after)) return true;
    }
    return false;
  };
  return test(p.key.join(" "), true) || (p.key.length > 1 && test(p.key[p.key.length - 1], false));
}

/**
 * Menções com nota num texto de MG: "RONALDO (Bahia) 9,5", "[ NEYMAR 8,3 ]", "CARD ANDERSON 6,0".
 * @param {string} text @param {Roster} roster
 */
function mentions(text, roster) {
  /** @type {Array<{p: Person, rating: number, tags: string, index: number, end: number}>} */
  const out = [];
  for (const m of String(text).matchAll(MENTION_RE)) {
    let name = m[1].trim();
    // tira "CARD", "CARD DO" etc. do começo
    const parts = name.split(/\s+/);
    while (parts.length && NOT_NAME.has(parts[0].replace(/\.$/, "")) && !/^[A-ZÀ-Ý]\.$/.test(parts[0])) parts.shift();
    name = parts.join(" ");
    if (!name || name.replace(/[^A-ZÀ-Ý]/g, "").length < 3) continue;
    const team = m[2] ? findTeam(m[2], { sigla: true }) : null;
    const r = rating(m[3]);
    const p = roster.get(name, { team, rating: r });
    if (!p) continue;
    // só símbolos (⚽ 🎯); descrição ("badge laranja") não vai para a tela
    const tags = (m[4] || "").replace(/[()+]|\p{L}+/gu, " ").replace(/\s+/g, " ").trim();
    out.push({ p, rating: r, tags, index: m.index || 0, end: (m.index || 0) + m[0].length });
  }
  return out;
}

/**
 * Monta o elenco citado no roteiro todo (nomes, times e notas).
 * @param {import("./parse").Roteiro} roteiro
 */
function buildRoster(roteiro) {
  const roster = new Roster();
  // LISTA DE ASSETS: "Ronaldo (BAH), Alex Telles (BOT)"
  for (const m of String(roteiro.assets || "").matchAll(/(\p{Lu}[\p{L}'.]+(?:\s\p{Lu}[\p{L}'.]+)*)\s*\(([A-Z]{3})\)/gu)) {
    const team = teamBySigla(m[2]);
    if (team) roster.get(m[1], { team });
  }
  for (const seg of roteiro.segments) {
    for (const f of ["MG", "TELA", "GRAFICO", "LANCE"]) if (seg.fields[f]) mentions(seg.fields[f], roster);
  }
  // time pela fala: "Ronaldo, do Bahia", "o Anderson, da Chape"
  const fala = roteiro.segments.map((s) => s.fields.FALA || "").join(" ");
  const fw = fala.replace(/["“”]/g, "").split(/\s+/);
  for (const p of roster.list) {
    if (p.team) continue;
    const sur = p.key[p.key.length - 1];
    for (let i = 0; i < fw.length && !p.team; i++) {
      if (norm(fw[i]).replace(/[^a-z]/g, "") !== sur) continue;
      const after = fw.slice(i + 1, i + 5).join(" ");
      const m = after.match(/^(?:,\s*)?d[oa]s?\s+(\S+(?:\s\S+)?)/i);
      if (m) p.team = findTeam(m[1], { cap: true });
    }
  }
  // nota pela fala: "Ronaldo, do Bahia, nota 9,5", "o João Victor, do Mirassol, tirou 5"
  for (const p of roster.list) {
    if (p.rating != null) continue;
    const sur = p.key[p.key.length - 1];
    const m =
      norm(fala).match(new RegExp(`\\b${sur}\\b,?\\s+(10|\\d,\\d)\\b`)) ||
      norm(fala).match(new RegExp(`\\b${sur}\\b[^.?!]{0,45}?\\b(?:nota|tirou|com)\\s+(10|\\d(?:,\\d)?)\\b`));
    if (m) p.rating = rating(m[1]);
  }
  return roster;
}

// ------------------------------------------------------------------ modos

/** @param {string} modo */
function normModo(modo) {
  const m = String(modo || "").toUpperCase();
  const tags = [...m.matchAll(/\[([A-Z+ ]+)\]/g)].map((x) => x[1].replace(/\s+/g, ""));
  const main = tags.filter((t) => t !== "VFX");
  // "[LANCE+VO] → [MG+VO]": vale o último (o lance só existe se houver o vídeo do lance)
  const last = main[main.length - 1] || (tags.includes("VFX") ? "CAM" : "");
  return { modo: last, vfx: tags.includes("VFX"), lance: main.includes("LANCE+VO") };
}

// ------------------------------------------------------------------ componentes

/** @param {any} p @param {number|null} r @param {string} [tags] */
function card(p, r, tags = "") {
  return {
    name: p.name,
    team: p.team ? p.team.nome : "",
    sigla: p.team ? p.team.sigla : "",
    rating: r ?? p.rating,
    tags: tags.trim(),
    anchor: p.name,
  };
}

/** Textos entre aspas, sem os que são descrição de animação ("pop", "thud"). @param {string} s */
function quotedCaps(s) {
  return [...String(s).matchAll(/"([^"]+)"/g)]
    .map((m) => m[1].trim())
    .filter((q) => {
      const t = stripEmoji(q).replace(/\bx\b/g, "X");
      return /\p{Lu}{2,}|\d/u.test(t) && t === t.toUpperCase();
    });
}

/**
 * Jogos citados na fala: "Inter 2 a 1 Corinthians", "Vitória 4 a 0 na Chape".
 * @param {string} fala
 */
function gamesInFala(fala) {
  const txt = String(fala).replace(/["“”]/g, "");
  /** @type {Array<{label: string, games: any[]}>} */
  const groups = [];
  const dayRe = /(segunda|ter[çc]a|quarta|quinta|sexta|s[áa]bado|domingo)(?:-feira)?\s*:/gi;
  const days = [...txt.matchAll(dayRe)].map((m) => ({ i: m.index || 0, label: m[1].toUpperCase().replace("TERCA", "TERÇA") }));
  const re = /(\p{Lu}[\p{L}]+(?:\s\p{Lu}[\p{L}]+)?)\s+(\d+)\s+a\s+(\d+)\s+(?:(?:na|no|em cima d[oa]|contra o|contra a)\s+)?(\p{Lu}[\p{L}]+(?:\s\p{Lu}[\p{L}]+)?)/gu;
  for (const m of txt.matchAll(re)) {
    const a = findTeam(m[1]);
    const b = findTeam(m[4]);
    if (!a || !b || a === b) continue;
    const day = days.filter((d) => d.i <= (m.index || 0)).pop();
    const label = day ? day.label : "";
    let g = groups.find((x) => x.label === label);
    if (!g) groups.push((g = { label, games: [] }));
    g.games.push({ a: a.nome, sa: Number(m[2]), sb: Number(m[3]), b: b.nome, siglaA: a.sigla, siglaB: b.sigla, anchor: `${m[1]} ${m[2]} a ${m[3]} ${m[4]}` });
  }
  return groups;
}

/**
 * Componentes de um trecho.
 * @param {any} seg @param {Roster} roster @param {any[]} [games] jogos citados no roteiro todo
 */
function segmentComponents(seg, roster, games = [], titulo = "") {
  // o que ele FALOU de verdade (transcrição alinhada) vale mais que a FALA escrita no roteiro
  const F = { ...seg.fields, ...(seg.spoken ? { FALA: seg.spoken } : {}) };
  /** @type {string[]} */
  const ajustes = [];
  const mg = [F.MG, F.GRAFICO].filter(Boolean).join("\n");
  const vfx = [F.VFX, F.EFEITO].filter(Boolean).join("\n");
  const tela = F.TELA || "";
  const all = [mg, vfx, tela, F.TELESTRATOR || "", F.LANCE || ""].join("\n");
  const up = all.toUpperCase();
  const { modo, vfx: hasVfx, lance } = normModo(F.MODO);
  /** @type {any[]} */
  const comps = [];
  const add = (/** @type {string} */ type, /** @type {any} */ data, /** @type {string} */ anchor = "", /** @type {string} */ place = "plate") => comps.push({ type, data, anchor, place });

  // tela de VAR
  if (/TELA DE VAR|VIRA A TELA DE VAR/.test(up)) add("var", { label: /CHECKING/.test(up) ? "CHECKING..." : "CHECAGEM" }, "", "plate");

  // números grandes caindo: três "10" azuis
  const big = vfx.match(/(tr[êe]s|dois|duas|\d)\s+"(\d+)"/i);
  if (big) {
    const n = { tres: 3, três: 3, dois: 2, duas: 2 }[norm(big[1])] || Number(big[1]) || 1;
    add("bignum", { text: big[2], count: Math.min(5, n), color: /azu/i.test(vfx) ? "blue" : "" }, big[2], modo === "CAM" ? "overlay" : "plate");
  }

  // vinheta de bloco
  if (/VINHETA/.test(mg.toUpperCase())) {
    const q = quotedCaps(mg).map(stripEmoji).filter(Boolean);
    const title = q[q.length - 1] || stripEmoji(String(seg.block).replace(/^\d+\.\s*/, "").split(/[—:]/)[0]);
    add("vinheta", { title }, "", "plate");
  }

  // placas de placar da rodada
  if (/PLACAS? DE PLACAR|PLACAS|GRID/.test(mg.toUpperCase())) {
    const groups = gamesInFala(F.FALA || "");
    if (groups.reduce((n, g) => n + g.games.length, 0) >= 2) add("scoregrid", { title: "PLACARES DA RODADA", groups }, "", "plate");
  }

  // duelo de pontos: "FLA 61 x PAL 60"
  const duel = mg.match(/\b([A-Z]{3})\s+(\d+)\s*x\s*([A-Z]{3})\s+(\d+)/);
  if (duel && teamBySigla(duel[1]) && teamBySigla(duel[3])) {
    const ta = /** @type {any} */ (teamBySigla(duel[1]));
    const tb = /** @type {any} */ (teamBySigla(duel[3]));
    const lbl = quotedCaps(mg).find((q) => /PONTO/.test(q)) || `${Math.abs(Number(duel[2]) - Number(duel[4]))} PONTO${Math.abs(Number(duel[2]) - Number(duel[4])) === 1 ? "" : "S"}`;
    add("duel", { a: { team: ta.nome, sigla: ta.sigla, pts: Number(duel[2]) }, b: { team: tb.nome, sigla: tb.sigla, pts: Number(duel[4]) }, label: stripEmoji(lbl) }, ta.nome, "plate");
  }

  // placar animado "0x2 → 1x2 → 2x2"
  const seq = mg.match(/placar animado\s+((?:\d\s*x\s*\d\s*(?:→|->)?\s*)+)/i);
  if (seq) {
    const steps = [...seq[1].matchAll(/(\d)\s*x\s*(\d)/g)].map((m) => [Number(m[1]), Number(m[2])]);
    /** @type {any[]} */
    const teams = [];
    for (const w of String(F.FALA || "").split(/[\s,.]+/)) {
      const t = findTeam(w, { cap: true });
      if (t && !teams.includes(t)) teams.push(t);
    }
    // times dos jogadores citados (o "Neymar" é do Santos)
    for (const m of mentions(mg, roster)) if (m.p.team && !teams.includes(m.p.team)) teams.push(m.p.team);
    // ordem mandante x visitante: a do jogo citado no roteiro ("Santos 2 a 2 Flamengo")
    const g = games.find((x) => teams.some((t) => t.sigla === x.siglaA) && teams.some((t) => t.sigla === x.siglaB));
    const A = g ? teamBySigla(g.siglaA) : teams[0];
    const B = g ? teamBySigla(g.siglaB) : teams[1];
    if (steps.length && A && B) add("scoreseq", { a: A.nome, b: B.nome, siglaA: A.sigla, siglaB: B.sigla, steps }, "", "plate");
  }

  // aspas
  if (/ASPAS/.test(mg.toUpperCase())) {
    const q = [...mg.matchAll(/"([^"]{8,})"/g)].map((m) => m[1]).sort((a, b) => b.length - a.length)[0];
    const author = (mg.match(/[—–-]\s*([\p{Lu}][\p{L}.]+(?:\s[\p{Lu}][\p{L}.]+)*)\s*\.?\s*$/mu) || [])[1] || "";
    if (q) add("quote", { text: stripEmoji(q), author }, author || q.split(" ").slice(0, 3).join(" "), "plate");
  }

  // campinho
  const gridLines = mg.split("\n").filter((l) => /\[\s*[^\]]*\d\s*\]/.test(l));
  const isPitch =
    (/CAMPO|CAMPINHO|MINI-?CARD|BANCO DE RESERVAS/.test(mg.toUpperCase()) && /SELE[ÇC][ÃA]O/.test(`${seg.block} ${mg}`.toUpperCase())) ||
    (/CAMPINHO|SELE[ÇC][ÃA]O D/.test(String(seg.block).toUpperCase()) && modo === "MG+VO");
  if (isPitch) {
    const rows = gridLines.map((l) => [...l.matchAll(/\[\s*([^\]]+?)\s*\]/g)].map((m) => {
      const mm = m[1].match(new RegExp(`^(${NAME})\\s+${NOTE}`, "u"));
      if (!mm) return null;
      const p = roster.get(mm[1], { rating: rating(mm[2]) });
      return p ? { ...card(p, rating(mm[2])), red: /CART[ÃA]O VERMELHO/.test(up) && false } : null;
    }).filter(Boolean));
    const title = stripEmoji(quotedCaps(mg).find((q) => /SELE/.test(q)) || "");
    // banco: "No banco: Flaco López" / "card do Flaco"
    const bench = /BANCO/.test(mg.toUpperCase()) ? roster.inText(mg).filter((p) => !rows.flat().some((c) => c && c.name === p.name)).map((p) => card(p, p.rating)) : [];
    // capitão e cartões citados no MG ("O card do Tomás Pérez ... CAPITÃO", "João Victor ... cartão vermelho")
    const flags = mg.split("\n").filter((l) => !/\[\s*[^\]]*\d\s*\]/.test(l)).join(" ").split(/\.\s|;/).map((l) => ({ ps: roster.inText(l), cap: /CAPIT[ÃA]O/i.test(l), red: /cart[ãa]o vermelho/i.test(l) }));
    for (const r of rows.flat()) {
      for (const f of flags) if (f.ps.some((p) => p.name === r.name)) {
        if (f.cap) r.captain = true;
        if (f.red) r.red = true;
      }
    }
    add("pitch", { title, worst: /PIOR/.test(`${seg.block} ${title}`.toUpperCase()), rows: rows.filter((r) => r.length), bench, fire: /fogo/i.test(mg) }, "", "plate");
  }

  // cards de jogador (fora do campinho)
  if (!isPitch) {
    const ms = mentions(mg, roster);
    let list = ms.map((m) => card(m.p, m.rating, m.tags));
    // "CARD DO RONALDO", "CARD ALAN PATRICK" sem nota
    if (!list.length && /CARD/i.test(mg)) list = roster.inText(mg).map((p) => card(p, p.rating));
    // "card do Tite com cartão vermelho": alguém fora do elenco (técnico), sem nota
    if (!list.length) {
      const m = mg.match(/card d[oa]\s+(\p{Lu}[\p{L}]+(?:\s\p{Lu}[\p{L}]+)?)/u);
      if (m) {
        const p = roster.get(m[1]);
        if (p) list = [card(p, p.rating)];
      }
    }
    // "quatro cards com badge vermelho" sem nomes: os jogadores citados na fala
    const nWord = (mg.match(/\b(dois|duas|tr[êe]s|quatro|cinco|seis|\d)\s+cards?\b/i) || [])[1];
    if (!list.length && nWord) {
      const n = { dois: 2, duas: 2, tres: 3, quatro: 4, cinco: 5, seis: 6 }[norm(nWord)] || Number(nWord);
      list = roster.inText(F.FALA || "").filter((p) => p.rating != null).slice(0, n).map((p) => card(p, p.rating));
    }
    // lance sem vídeo: cards de quem é citado na fala
    if (!list.length && lance && !comps.length) list = roster.inText(F.FALA || "").filter((p) => p.rating != null && alone(F.FALA || "", p)).slice(0, 2).map((p) => card(p, p.rating));
    // fala diferente do roteiro: o card acompanha o que foi DITO (sai quem não foi citado,
    // entra quem foi citado e tem nota no roteiro)
    if (seg.spoken && list.length && !lance) {
      const ditos = roster.inText(seg.spoken).filter((p) => alone(seg.spoken, p));
      const nomes = ditos.map((p) => p.name);
      // só mexe em quem estava ESCRITO na FALA do roteiro (o card citado só no MG fica)
      const escritos = roster.inText(seg.fields.FALA || "").map((p) => p.name);
      if (list.some((c) => nomes.includes(c.name))) {
        const fora = list.filter((c) => !nomes.includes(c.name) && escritos.includes(c.name) && c.rating != null);
        if (fora.length && fora.length < list.length) {
          list = list.filter((c) => !fora.includes(c));
          ajustes.push(`cards: tirei ${fora.map((c) => c.name).join(", ")} (você não citou)`);
        }
        const novos = ditos.filter((p) => p.rating != null && !escritos.includes(p.name) && !list.some((c) => c.name === p.name)).slice(0, Math.max(0, 6 - list.length));
        if (novos.length) {
          list.push(...novos.map((p) => card(p, p.rating)));
          ajustes.push(`cards: entrou ${novos.map((p) => p.name).join(", ")} (você citou)`);
        }
      }
    }
    // cartão vermelho: vale para quem é citado na mesma frase ("card do Pérez ... cartão vermelho")
    for (const sent of all.split(/\n|\.\s|;|→/)) {
      if (!/cart[ãa]o vermelho|glitch vermelho/i.test(sent)) continue;
      const ps = roster.inText(sent).map((p) => p.name);
      for (const c of list) if (ps.includes(c.name)) c.red = true;
    }
    if (list.length) {
      // destaques escritos no MG: "ENTROU NO INTERVALO", "4 GOLS = OS DOIS", "RESULTADO: PERDEU 1 x 0"
      const stat = mg.match(/contador\s+"?([^"]*?)"?\s+sobe de (\d+) at[ée] (\d+)/i);
      const statLabel = stat ? stripEmoji(stat[1]).toUpperCase() : "";
      const notes = quotedCaps(mg)
        .map(stripEmoji)
        .filter((q) => q.length > 3 && q !== statLabel && !list.some((c) => norm(q).includes(norm(c.name))) && !/^LANCE \d/.test(q));
      const res = mg.match(/RESULTADO:\s*([^;.\n"]+)/i);
      if (res && !notes.some((n) => n.includes(stripEmoji(res[1]).toUpperCase().replace(/\bX\b/, "x").trim()))) notes.push(stripEmoji(res[1]).toUpperCase().replace(/\bX\b/, "x"));
      add("cards", { cards: list.slice(0, 6), notes: notes.slice(0, 2), stat: stat ? { label: statLabel, from: Number(stat[2]), to: Number(stat[3]) } : null, link: (mg.match(/linha animada[^"]*"([^"]+)"/i) || [])[1] || "" }, list[0].anchor, "plate");
    }
  }

  // cartão vermelho sozinho (sem card do jogador)
  if (/cart[ãa]o vermelho 3D|cart[ãa]o vermelho.*batendo/i.test(all) && !comps.some((c) => c.type === "cards" || c.type === "pitch")) add("redcard", { label: "VERMELHO DIRETO" }, "vermelho", "plate");

  // selos / carimbos
  const stampSrc = [mg, F.TELESTRATOR || "", vfx].join("\n");
  if (/SELO|CARIMB|ANULADO/i.test(stampSrc)) {
    const items = quotedCaps(stampSrc)
      .map((q) => stripEmoji(q.replace(/^LANCE \d\s*/i, "")))
      .filter((q) => q.length >= 4 && !/^(VAR|CHECKING\.\.\.)$/.test(q))
      .slice(0, 3)
      .map((q) => ({ text: q, kind: /✅|CORRETO/.test(q) ? "ok" : /❌|N[ÃA]O ERA|ANULADO|SUSPENSO/.test(q) ? "bad" : "warn" }));
    const used = comps.filter((c) => c.type === "cards").flatMap((c) => c.data.notes);
    for (let k = items.length - 1; k >= 0; k--) if (used.includes(items[k].text)) items.splice(k, 1);
    if (items.length) add("stamps", { items }, items[0].text, comps.length ? "plate" : modo === "CAM" ? "overlay" : "plate");
  }

  // enquete
  if (/ENQUETE/.test(tela.toUpperCase())) {
    const quoted = [...tela.matchAll(/"([^"]+)"/g)].map((m) => m[1])[0];
    // sem pergunta escrita: a pergunta da fala ("quem foi o craque da rodada? Savarino, Matheuzinho ou Erick?")
    const pieces = String(F.FALA || "").replace(/["“”]/g, "").split(/(?<=\?)/);
    let fq = "";
    let fo = /** @type {string[]} */ ([]);
    pieces.forEach((pc, k) => {
      const ps = roster.inText(pc).filter((p) => alone(pc, p));
      if (ps.length >= 2) {
        fo = ps.map((p) => p.name.toUpperCase());
        const own = pc.replace(/^.*[:,]\s*/, "").trim();
        fq = own.split(/\s+/).length >= 4 && !ps.some((p) => norm(own).includes(norm(p.name))) ? own : (pieces[k - 1] || "").split(/[:,.]\s*/).pop() || "";
      }
    });
    const q = quoted || `${fq} ${fo.join(" / ")}`;
    const question = stripEmoji((q.match(/^[^?]+\?/) || [q.split(/[—✅❌]/)[0]])[0]).trim();
    let options = q.replace(/^[^?]+\?/, "").split(/\/|\sx\s|—/).map((o) => stripEmoji(o).trim()).filter((o) => o && !/COMENTA/i.test(o));
    if (options.filter((o) => o.length >= 2).length < 2) {
      // opções só com emoji: times ou jogadores citados na fala
      const teams = [];
      for (const w of String(F.FALA || "").split(/[\s,.?!]+/)) {
        const t = findTeam(w, { cap: true });
        if (t && !teams.includes(t)) teams.push(t);
      }
      options = fo.length >= 2 ? fo.slice(0, 3) : teams.slice(0, 3).map((t) => t.nome.toUpperCase());
    }
    if (options.length >= 2) add("poll", { question: question.toUpperCase(), options: options.slice(0, 3) }, "", "overlay");
  }

  // fotos da internet: camisas/uniformes dos times citados, ou o que o VISUAL pedir
  const visual = F.VISUAL && !/^facecam/i.test(F.VISUAL.trim()) ? F.VISUAL : "";
  const pedeFoto = /camisa|uniforme|manto|foto|imagem/i.test(mg) || visual;
  if (pedeFoto && !comps.some((c) => ["cards", "pitch", "scoregrid", "fotos"].includes(c.type))) {
    const base = `${mg} ${visual}`;
    const ano = (base.match(/\b20\d\d\b/) || (F.FALA || "").match(/\b20\d\d\b/) || [String(new Date().getFullYear())])[0];
    // o tema do vídeo vale para todos os trechos ("CAMISAS 3 DOS TIMES" → terceira camisa)
    const tema = `${base} ${F.FALA || ""} ${titulo}`;
    const qual = /camisas?\s*(3|tr[êe]s)\b|terceir|third/i.test(tema) ? "terceira camisa" : /camisas?\s*(2|dois)\b|segund|reserva|away/i.test(tema) ? "segunda camisa" : "camisa";
    let teams = findTeams(base);
    if (!teams.length) teams = findTeams(F.FALA || "", { cap: true });
    /** @type {any[]} */
    let items = [];
    if (/camisa|uniforme|manto/i.test(base) && teams.length) {
      items = teams.slice(0, 3).map((t) => ({ query: `${qual} ${t.nome} ${ano}`, exige: [t.nome.split(/[-\s]/)[0]], label: `${t.nome.toUpperCase()} • ${qual.toUpperCase()}`, anchor: t.nome, sigla: t.sigla }));
    } else {
      const q = (base.match(/"([^"]{4,})"/) || [])[1] || stripEmoji(visual || mg).replace(/\(.*?\)/g, "").slice(0, 80);
      const pessoa = roster.inText(q)[0];
      items = [{ query: q.trim(), exige: pessoa ? [pessoa.key[pessoa.key.length - 1]] : teams.slice(0, 1).map((t) => t.nome.split(/[-\s]/)[0]), label: stripEmoji(quotedCaps(base)[0] || ""), anchor: pessoa ? pessoa.name : teams[0] ? teams[0].nome : "" }];
    }
    if (items.length && items[0].query) add("fotos", { items }, items[0].anchor, "plate");
  }

  // textos de tela (CAM): batidas de palavra e chamadas
  if (tela && !/ENQUETE/.test(tela.toUpperCase())) {
    const q = quotedCaps(tela).map(stripEmoji).filter(Boolean);
    const cta = /SEGUI|COMENT|CURT|LIKE|COMPARTILH|INSCREV/i.test(tela);
    if (cta) add("cta", { label: q.find((x) => !/^SEGUIR$/.test(x)) || (/COMENT/i.test(tela) ? "COMENTA AÍ" : "DEIXA O LIKE"), button: /SEGUI/i.test(tela) ? "SEGUIR" : /LIKE|CURT/i.test(tela) ? "CURTIR" : "SEGUIR" }, "segue comenta curte like compartilha", "overlay");
    else if (q.length) add("headline", { lines: q[0].split(/\s*[•|]\s*/).filter(Boolean).map((t, i, arr) => ({ text: t, box: arr.length > 1 && i === Math.floor(arr.length / 2) })) }, q[0], modo === "CAM" ? "overlay" : "plate");
  }

  return { modo, vfx: hasVfx, lance, comps, ajustes };
}

/**
 * Componentes do roteiro inteiro. O campinho que começa num trecho e continua nos
 * seguintes do mesmo bloco (título → jogadores → banco) vira um só.
 * @param {import("./parse").Roteiro} roteiro
 */
function roteiroComponents(roteiro) {
  const roster = buildRoster(roteiro);
  const games = roteiro.segments.flatMap((s) => gamesInFala(s.fields.FALA || "").flatMap((g) => g.games));
  const per = roteiro.segments.map((s) => segmentComponents(s, roster, games, roteiro.title || ""));
  // campinho contínuo no bloco
  per.forEach((p, i) => {
    const pitch = p.comps.find((c) => c.type === "pitch");
    if (!pitch) return;
    const seg = roteiro.segments[i];
    for (let k = i + 1; k < per.length && roteiro.segments[k].block === seg.block; k++) {
      const q = per[k].comps.find((c) => c.type === "pitch");
      if (!q) break;
      if (q.data.rows.length) pitch.data.rows = q.data.rows;
      if (q.data.bench.length) pitch.data.bench = q.data.bench;
      if (!pitch.data.title && q.data.title) pitch.data.title = q.data.title;
      pitch.data.fire = pitch.data.fire || q.data.fire;
      q.continues = true; // o diretor estende o campinho por estes trechos
      pitch.span = k;
    }
  });
  // título padrão do campinho
  for (const p of per) for (const c of p.comps) if (c.type === "pitch" && !c.data.title) c.data.title = c.data.worst ? "SELEÇÃO DOS PIORES" : "SELEÇÃO DA RODADA";
  // toda polêmica abre com a tela de VAR
  roteiro.segments.forEach((s, i) => {
    const prevVar = i > 0 && per[i - 1].comps.some((c) => c.type === "var");
    if (/** @type {any} */ (s).opensSub && /POL[ÊE]MICA/i.test(/** @type {any} */ (s).sub || "") && !prevVar && !per[i].comps.some((c) => c.type === "var")) {
      per[i].comps.unshift({ type: "var", data: { label: (/** @type {any} */ (s).sub || "").replace(/:.*/, "").toUpperCase() }, anchor: "", place: "plate", short: true });
    }
  });
  return {
    segments: per,
    people: roster.list.map((p) => ({ name: p.name, team: p.team ? p.team.nome : "", sigla: p.team ? p.team.sigla : "", sofa: p.team ? p.team.sofa : null, rating: p.rating })),
  };
}

module.exports = { roteiroComponents, segmentComponents, buildRoster, normModo, findTeam, findTeams, gamesInFala, mentions, norm, stripEmoji, TEAMS };
