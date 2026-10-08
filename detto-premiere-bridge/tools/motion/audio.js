"use strict";

/**
 * Trilha final: voz (com os jump cuts, sem deriva) + SFX + bip opcional, normalizada
 * em -14 LUFS. Opcionalmente recorta trechos (cortes verticais).
 */

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const f3 = (n) => Number(n).toFixed(3);

/**
 * @param {{plan: any, duration: number, video: string, sfxWav: string, out: string, tmpDir: string,
 *          ranges?: Array<[number, number]>, sfxGain?: number}} o
 */
function buildAudio(o) {
  const fps = o.plan.sequence.fps;
  const aSel = o.plan.cuts
    .slice()
    .sort((a, b) => a.timeline - b.timeline)
    .map((c) => {
      const a = Math.round(c.start * fps) / fps;
      const b = Math.round(c.end * fps) / fps;
      return `between(t,${a.toFixed(4)},${(b - 0.0001).toFixed(4)})`;
    })
    .join("+");
  const bleeps = (o.plan.audio || []).filter((x) => x.type === "bleep");
  const on = bleeps.map((b) => `between(t,${f3(b.start)},${f3(b.start + b.duration)})`).join("+");
  const parts = [
    `[0:a]aresample=48000,asetnsamples=n=64:p=0,aselect='${aSel}',asetpts=N/SR/TB,asetnsamples=n=1024:p=0${on ? `,volume=0:enable='${on}'` : ""}[voz]`,
    `[1:a]aresample=48000,volume=${o.sfxGain ?? 0.55}[fx]`,
  ];
  const ins = ["[voz]", "[fx]"];
  if (on) {
    parts.push(`sine=f=1000:sample_rate=48000:d=${f3(o.duration)},volume=0.16,volume=0:enable='not(${on})'[bip]`);
    ins.push("[bip]");
  }
  parts.push(`${ins.join("")}amix=inputs=${ins.length}:duration=first:normalize=0,loudnorm=I=-14:TP=-1.0:LRA=9,aresample=48000,asetpts=N/SR/TB[mix]`);
  const ranges = o.ranges || [[0, o.duration]];
  ranges.forEach(([a, b], i) => parts.push(`${i === 0 && ranges.length === 1 ? "[mix]" : `[m${i}]`}atrim=${f3(a)}:${f3(b)},asetpts=N/SR/TB[r${i}]`));
  if (ranges.length > 1) {
    parts.splice(parts.length - ranges.length, 0, `[mix]asplit=${ranges.length}${ranges.map((_, i) => `[m${i}]`).join("")}`);
    parts.push(`${ranges.map((_, i) => `[r${i}]`).join("")}concat=n=${ranges.length}:v=0:a=1[aout]`);
  } else {
    parts[parts.length - 1] = parts[parts.length - 1].replace("[r0]", "[aout]");
  }
  fs.mkdirSync(o.tmpDir, { recursive: true });
  const script = path.join(o.tmpDir, "audio.filter");
  fs.writeFileSync(script, parts.join(";\n"));
  const r = spawnSync("ffmpeg", ["-y", "-v", "error", "-i", o.video, "-i", o.sfxWav, "-filter_complex_script", script, "-map", "[aout]", "-c:a", "pcm_s16le", o.out], { stdio: "inherit" });
  if (r.status !== 0) throw new Error(`falha no áudio (filtro em ${script})`);
  return o.out;
}

module.exports = { buildAudio };
