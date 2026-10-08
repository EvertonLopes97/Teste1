"use strict";

/**
 * Efeitos sonoros sintetizados (sem banco externo): whoosh, hit, pop, tick, click,
 * ding e riser. Gera um WAV mono 48 kHz com todos os eventos já posicionados.
 */

const fs = require("fs");

const SR = 48000;

function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296) * 2 - 1;
}

/** Filtro passa-banda (state variable) com frequência variável. */
function svfBand(input, freqAt, q = 0.7) {
  const out = new Float32Array(input.length);
  let low = 0;
  let band = 0;
  for (let i = 0; i < input.length; i++) {
    const f = 2 * Math.sin((Math.PI * Math.min(freqAt(i / SR), SR / 6)) / SR);
    const high = input[i] - low - q * band;
    band += f * high;
    low += f * band;
    out[i] = band;
  }
  return out;
}

const env = (t, a, d) => (t < a ? t / a : Math.exp(-(t - a) / d));

/** @type {Record<string, (seed: number) => Float32Array>} */
const SYNTH = {
  whoosh(seed) {
    const len = Math.round(0.42 * SR);
    const r = rng(seed);
    const noise = Float32Array.from({ length: len }, () => r());
    const band = svfBand(noise, (t) => 350 + 3200 * Math.sin(Math.PI * Math.min(1, t / 0.42)), 0.5);
    return band.map((v, i) => {
      const t = i / len;
      return v * Math.pow(Math.sin(Math.PI * t), 2) * 1.6;
    });
  },
  whoosh_short(seed) {
    const len = Math.round(0.2 * SR);
    const r = rng(seed);
    const noise = Float32Array.from({ length: len }, () => r());
    const band = svfBand(noise, (t) => 800 + 4000 * (t / 0.2), 0.6);
    return band.map((v, i) => v * Math.pow(Math.sin((Math.PI * i) / len), 2) * 1.3);
  },
  hit(seed) {
    const len = Math.round(0.6 * SR);
    const r = rng(seed);
    const out = new Float32Array(len);
    let ph = 0;
    for (let i = 0; i < len; i++) {
      const t = i / SR;
      const f = 45 + 70 * Math.exp(-t / 0.05);
      ph += (2 * Math.PI * f) / SR;
      out[i] = Math.sin(ph) * env(t, 0.004, 0.18) * 0.95 + r() * env(t, 0.001, 0.012) * 0.5;
    }
    return out;
  },
  pop() {
    const len = Math.round(0.09 * SR);
    const out = new Float32Array(len);
    let ph = 0;
    for (let i = 0; i < len; i++) {
      const t = i / SR;
      const f = 1300 - 800 * (t / 0.09);
      ph += (2 * Math.PI * f) / SR;
      out[i] = Math.sin(ph) * env(t, 0.002, 0.025) * 0.55;
    }
    return out;
  },
  tick() {
    const len = Math.round(0.03 * SR);
    const out = new Float32Array(len);
    for (let i = 0; i < len; i++) {
      const t = i / SR;
      out[i] = Math.sign(Math.sin(2 * Math.PI * 2200 * t)) * env(t, 0.0005, 0.005) * 0.3;
    }
    return out;
  },
  click(seed) {
    const len = Math.round(0.02 * SR);
    const r = rng(seed);
    const out = new Float32Array(len);
    let prev = 0;
    for (let i = 0; i < len; i++) {
      const n = r();
      out[i] = (n - prev) * env(i / SR, 0.0003, 0.004) * 0.5;
      prev = n;
    }
    return out;
  },
  ding() {
    const len = Math.round(1.2 * SR);
    const out = new Float32Array(len);
    const partials = [
      [1568, 1, 0.5],
      [2349, 0.5, 0.35],
      [3136, 0.3, 0.2],
    ];
    for (let i = 0; i < len; i++) {
      const t = i / SR;
      let v = 0;
      for (const [f, a, d] of partials) v += Math.sin(2 * Math.PI * f * t) * a * env(t, 0.002, d);
      out[i] = v * 0.22;
    }
    return out;
  },
  riser(seed) {
    const len = Math.round(1.0 * SR);
    const r = rng(seed);
    const noise = Float32Array.from({ length: len }, () => r());
    const band = svfBand(noise, (t) => 300 + 2500 * t, 0.4);
    let ph = 0;
    return band.map((v, i) => {
      const t = i / SR;
      ph += (2 * Math.PI * (200 + 900 * t)) / SR;
      return (v * 0.8 + Math.sin(ph) * 0.15) * Math.pow(t, 1.6) * (t > 0.95 ? (1 - t) * 20 : 1);
    });
  },
};

/** Volume relativo de cada efeito na mixagem. */
const GAIN = { whoosh: 0.55, whoosh_short: 0.4, hit: 0.8, pop: 0.6, tick: 0.45, click: 0.6, ding: 0.5, riser: 0.45 };

/**
 * @param {Array<{t: number, kind: string}>} events
 * @param {number} duration
 * @param {string} file
 */
function writeSfxTrack(events, duration, file) {
  const total = Math.ceil(duration * SR);
  const mix = new Float32Array(total);
  const cache = new Map();
  events.forEach((e, n) => {
    const synth = SYNTH[e.kind];
    if (!synth) return;
    const key = `${e.kind}:${n % 4}`; // pequenas variações de ruído
    if (!cache.has(key)) cache.set(key, synth(17 + (n % 4) * 31));
    const buf = cache.get(key);
    const g = GAIN[e.kind] ?? 0.5;
    const start = Math.round(e.t * SR);
    for (let i = 0; i < buf.length && start + i < total; i++) if (start + i >= 0) mix[start + i] += buf[i] * g;
  });
  // limitador suave
  const pcm = Buffer.alloc(total * 2);
  for (let i = 0; i < total; i++) pcm.writeInt16LE(Math.round(Math.tanh(mix[i] * 1.1) * 32000), i * 2);
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + pcm.length, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(SR, 24);
  header.writeUInt32LE(SR * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write("data", 36);
  header.writeUInt32LE(pcm.length, 40);
  fs.writeFileSync(file, Buffer.concat([header, pcm]));
  return file;
}

module.exports = { writeSfxTrack, SYNTH };
