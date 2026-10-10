"use strict";

/**
 * Busca de fotos de apoio (b-roll) com licença livre para uso comercial, via Openverse
 * (indexa Wikimedia Commons, Flickr etc.). Só aceita CC0, domínio público, CC BY e
 * CC BY-SA, e registra autor/licença/fonte para os créditos.
 *
 * Fluxo: termos do roteiro → consultas (poucas, com cache) → pool de imagens →
 * melhor imagem por trecho (pessoa citada no título, ano, time, estádio) sem repetir.
 * Na dúvida, o trecho fica SEM foto (melhor nada do que a foto de outra pessoa).
 */

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const API = "https://api.openverse.org/v1/images/";
const LICENSES = "cc0,pdm,by,by-sa";
const UA = "DettoEditor/0.2 (video edit preview)";

/** termos em português → termos de busca (títulos costumam estar em inglês) */
const CONTEXT = [
  [/sub-?20|mundial sub/i, "U-20 World Cup"],
  [/ol[íi]mpic|pequim/i, "Olympics Beijing"],
  [/copa am[ée]rica/i, "Copa America"],
  [/finalíssima|finalissima/i, "Finalissima"],
  [/copa (do mundo|20\d\d)|mundial/i, "World Cup"],
  [/maradona/i, "Maradona"],
  [/maracan[ãa]/i, "Maracana"],
  [/mineir[ãa]o/i, "Mineirao"],
  [/metlife/i, "MetLife Stadium"],
  [/monumental/i, "Estadio Monumental"],
  [/wembley/i, "Wembley"],
  [/lusail/i, "Lusail"],
  [/quito/i, "Quito"],
  [/ta[çc]a|trof[ée]u|levanta/i, "trophy"],
  [/medalha/i, "medal"],
];

const TEAMS = ["Argentina", "Hungria", "Hungary", "Alemanha", "Germany", "Brasil", "Brazil", "Uruguai", "Uruguay", "Chile", "Holanda", "Netherlands", "França", "France", "Croácia", "Croatia", "Islândia", "Iceland", "Nigéria", "Nigeria", "Equador", "Ecuador", "Itália", "Italy", "Colômbia", "Colombia", "Espanha", "Spain", "Inglaterra", "England", "Benin", "Egito", "Egypt"];

function sleep(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function curlJson(url) {
  const r = spawnSync("curl", ["-sS", "-A", UA, url], { maxBuffer: 20 * 1024 * 1024 });
  if (r.status !== 0) throw new Error(String(r.stderr));
  return JSON.parse(String(r.stdout));
}

/** Consulta com cache em disco (evita repetir e respeita o limite da API). */
function search(query, cacheDir) {
  const key = query.toLowerCase().replace(/[^a-z0-9]+/g, "_");
  const file = path.join(cacheDir, `q_${key}.json`);
  if (fs.existsSync(file)) return JSON.parse(fs.readFileSync(file, "utf-8"));
  const url = `${API}?q=${encodeURIComponent(query)}&license=${LICENSES}&page_size=20&mature=false`;
  let data = null;
  for (let attempt = 0; attempt < 3 && !data; attempt++) {
    try {
      const d = curlJson(url);
      if (Array.isArray(d.results)) data = d.results;
      else sleep(4000 * (attempt + 1));
    } catch (_) {
      sleep(4000 * (attempt + 1));
    }
  }
  data = data || [];
  fs.writeFileSync(file, JSON.stringify(data));
  sleep(1200);
  return data;
}

const CLUBS = require("../roteiro/times.json").times;
const NOT_PERSON = new Set(["Copa", "Mundial", "Final", "Estádio", "Estadio", "Seleção", "Selecao", "World", "Cup", "Brasileirão", "Libertadores", "Champions", "League", "Foto", "Vídeo", "Video", "Jogo"]);
const strip = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/**
 * Palavras-chave de um trecho (texto do VISUAL + bloco): ano, contexto, seleções/clubes e
 * a PESSOA principal (primeiro nome próprio que não é time nem lugar).
 */
function segmentKeys(text) {
  const year = (text.match(/\b(19|20)\d{2}\b/) || [])[0] || "";
  const ctx = CONTEXT.filter(([re]) => re.test(text)).map(([, k]) => k);
  const teams = TEAMS.filter((t) => new RegExp(`\\b${t}\\b`, "i").test(text));
  const clubs = CLUBS.filter((c) => c.apelidos.some((a) => a.length > 3 && new RegExp(`\\b${a}\\b`).test(strip(text)))).map((c) => c.nome);
  // termos entre aspas são a busca pedida no roteiro; senão o texto todo
  const q = (text.match(/"([^"]+)"/) || [])[1] || text;
  const isTeamWord = (w) =>
    w.length < 3 || TEAMS.some((t) => strip(t) === strip(w)) || CLUBS.some((c) => strip(c.nome) === strip(w) || c.apelidos.some((ap) => ap.split(/[\s-]/).includes(strip(w))));
  const person = [];
  for (const w of q.split(/[\s,.;:()\-–—]+/)) {
    if (/^\p{Lu}[\p{L}']+$/u.test(w) && !NOT_PERSON.has(w) && !isTeamWord(w) && !CONTEXT.some(([re]) => re.test(w))) person.push(w);
    else if (person.length) break;
  }
  return { year, ctx, teams, clubs, person: person.slice(0, 3) };
}

/** Consultas para um trecho, da mais específica para a mais geral. */
function queriesFor(keys) {
  const q = [];
  const who = keys.person.join(" ");
  const where = keys.clubs[0] || keys.teams[0] || "";
  if (who && where) q.push(`${who} ${where} ${keys.year}`.trim());
  if (who && keys.ctx.length) q.push(`${who} ${keys.ctx[0]} ${keys.year}`.trim());
  if (who) q.push(`${who} football`);
  for (const c of keys.ctx.filter((c) => /Stadium|Maracana|Mineirao|Monumental|Wembley|Lusail|Quito/.test(c))) q.push(c);
  return [...new Set(q)];
}

const STADIUMS = /stadium|estadio|maracan|mineir|monumental|wembley|lusail|metlife/i;

function score(img, keys) {
  const hay = strip(`${img.title} ${(img.tags || []).map((t) => t.name).join(" ")}`);
  const title = strip(img.title);
  // o TÍTULO precisa citar a pessoa pedida (tags sozinhas trazem ruído: cachorro "Murfy", outdoor etc.)
  const hasPerson = keys.person.length > 0 && keys.person.every((p) => new RegExp(`\\b${strip(p)}\\b`).test(title));
  if (/version|toy|figur|doll|cartoon|caricat|graffiti|mural|wax|lego|billboard|statue|estatua|sticker|panini/.test(title)) return -99;
  const wantsStadium = keys.ctx.some((c) => STADIUMS.test(c));
  const stadiumHit = keys.ctx.some((c) => STADIUMS.test(c) && hay.includes(c.toLowerCase().split(" ").pop()));
  // precisa ser da pessoa ou do estádio pedido; sem pessoa nem estádio, não arrisca
  if (!hasPerson && !(wantsStadium && stadiumHit)) return -99;
  let s = hasPerson ? 3 : 0;
  if (stadiumHit) s += 5;
  for (const c of keys.ctx) if (!STADIUMS.test(c) && hay.includes(c.toLowerCase().split(" ")[0])) s += 2;
  for (const t of keys.teams) if (hay.includes(strip(t))) s += 2;
  for (const c of keys.clubs) if (hay.includes(strip(c).split(/[-\s]/)[0])) s += 3;
  // outro clube no título (foto de outra época/time)
  if (keys.clubs.length && CLUBS.some((c) => !keys.clubs.includes(c.nome) && c.apelidos.some((a) => a.length > 4 && title.includes(a)))) s -= 4;
  // época: ano igual vale muito; ano distante pesa contra (2026 numa cena de 2005)
  const years = (hay.match(/\b(19|20)\d{2}\b/g) || []).map(Number);
  if (keys.year) {
    const want = Number(keys.year);
    if (years.length) {
      const diff = Math.min(...years.map((y) => Math.abs(y - want)));
      s += diff === 0 ? 5 : diff <= 2 ? 2 : diff <= 5 ? 0 : -4;
    }
  }
  const w = img.width || 0;
  const h = img.height || 0;
  if (Math.min(w, h) >= 700) s += 1;
  if (Math.min(w, h) && Math.min(w, h) < 380) s -= 3;
  return s;
}

/** URL em tamanho adequado (miniatura do Commons em 1280 px quando possível). */
function sizedUrl(img) {
  const u = img.url || "";
  const m = u.match(/^https:\/\/upload\.wikimedia\.org\/wikipedia\/commons\/([0-9a-f])\/([0-9a-f]{2})\/(.+)$/);
  if (m && (img.width || 0) > 1400 && !/\.svg$/i.test(m[3])) {
    return `https://upload.wikimedia.org/wikipedia/commons/thumb/${m[1]}/${m[2]}/${m[3]}/1280px-${m[3]}`;
  }
  return u;
}

function download(img, dir) {
  const dest = path.join(dir, `img_${img.id}.jpg`);
  if (fs.existsSync(dest) && fs.statSync(dest).size > 1000) return dest;
  const raw = path.join(dir, `raw_${img.id}`);
  const r = spawnSync("curl", ["-sSfL", "-A", UA, "-o", raw, sizedUrl(img)]);
  if (r.status !== 0) return null;
  // normaliza: JPEG, no máximo 1600 px no lado maior
  const f = spawnSync("ffmpeg", ["-y", "-v", "error", "-i", raw, "-vf", "scale='min(1600,iw)':'-2':flags=lanczos", "-q:v", "3", dest]);
  fs.rmSync(raw, { force: true });
  return f.status === 0 && fs.existsSync(dest) ? dest : null;
}

/**
 * @param {Array<{id: string, time: number, text: string}>} needs  trechos que pedem imagem
 * @param {{cacheDir: string, log?: (m: string) => void}} opts
 * @returns {Record<string, {file: string, title: string, creator: string, license: string, source: string, score: number}>}
 */
function findImages(needs, opts) {
  opts = { ...opts, cacheDir: path.resolve(opts.cacheDir) }; // o Chromium precisa de caminho absoluto
  fs.mkdirSync(opts.cacheDir, { recursive: true });
  const log = opts.log || (() => {});
  /** @type {Map<string, any>} */
  const pool = new Map();
  const add = (results) => {
    for (const r of results) if (!pool.has(r.id) && r.url && !/\.(svg|gif)$/i.test(r.url)) pool.set(r.id, r);
  };
  // só consultas do próprio roteiro (deduplicadas); nada fixo
  const asked = new Set();
  const keysById = new Map();
  for (const n of needs) {
    const keys = segmentKeys(n.text);
    keysById.set(n.id, keys);
    for (const q of queriesFor(keys)) {
      if (asked.has(q)) continue;
      asked.add(q);
      add(search(q, opts.cacheDir));
    }
  }
  log(`imagens: ${asked.size} consultas, ${pool.size} candidatas com licença livre`);

  /** @type {Record<string, any>} */
  const out = {};
  const usage = new Map();
  let lastId = "";
  for (const n of needs) {
    const keys = keysById.get(n.id);
    const ranked = [...pool.values()]
      .map((img) => ({ img, s: score(img, keys) - 7 * (usage.get(img.id) || 0) - (img.id === lastId ? 10 : 0) }))
      .sort((a, b) => b.s - a.s);
    for (const { img, s } of ranked.slice(0, 6)) {
      if (s < 2) break;
      const file = download(img, opts.cacheDir);
      if (!file) continue;
      out[n.id] = {
        file,
        title: img.title,
        creator: img.creator || "desconhecido",
        license: `CC ${String(img.license).toUpperCase()}${img.license_version ? ` ${img.license_version}` : ""}`.replace("CC CC0", "CC0").replace("CC PDM", "Domínio público"),
        source: img.foreign_landing_url || img.url,
        score: s,
      };
      usage.set(img.id, (usage.get(img.id) || 0) + 1);
      lastId = img.id;
      break;
    }
  }
  return out;
}

/** Texto de créditos (obrigatório para CC BY / BY-SA). */
function creditsText(images) {
  const seen = new Set();
  const lines = ["Créditos das imagens (licenças livres, via Openverse):", ""];
  for (const im of Object.values(images)) {
    if (seen.has(im.file)) continue;
    seen.add(im.file);
    lines.push(`- "${im.title}" — ${im.creator} — ${im.license} — ${im.source}`);
  }
  return lines.join("\n") + "\n";
}

module.exports = { findImages, creditsText, segmentKeys, queriesFor, score, sizedUrl };
