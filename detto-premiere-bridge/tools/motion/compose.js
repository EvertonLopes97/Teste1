"use strict";

/**
 * Composição final com ffmpeg: facecam (jump cuts + reenquadramentos + punch-ins)
 * → camada de motion graphics → voz + SFX (+ bip opcional).
 */

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const f3 = (n) => Number(n).toFixed(3);
const win = (a, b) => `gte(it,${f3(a)})*lt(it,${f3(b)})`;

/**
 * @param {{plan: any, direction: any, video: string, layerVideo: string, sfxWav: string,
 *          out: string, width?: number, height?: number, crf?: number, preset?: string,
 *          sfxGain?: number, tmpDir: string}} o
 */
function compose(o) {
  const { plan, direction: d } = o;
  const fps = d.fps;
  const W = o.width || 1280;
  const H = o.height || 720;

  // ----- trechos de fala (vídeo por índice de quadro; áudio em blocos finos: sem deriva)
  const ranges = plan.cuts
    .slice()
    .sort((a, b) => a.timeline - b.timeline)
    .map((c) => [Math.round(c.start * fps), Math.round(c.end * fps)]);
  const vSel = ranges.map(([a, b]) => `between(n,${a},${b - 1})`).join("+");
  const aSel = ranges.map(([a, b]) => `between(t,${(a / fps).toFixed(4)},${(b / fps - 0.0001).toFixed(4)})`).join("+");

  // ----- reenquadramento (zoompan): zoom, centro x/y por plano + punch-ins + tremor
  const zTerms = d.shots.map((s) => `${f3(s.z - 1)}*${win(s.start, s.end)}`);
  const pTerms = d.punches.map((p) => `${f3(p.dz)}*min(1,(it-${f3(p.start)})/0.08)*${win(p.start, p.end)}`);
  const z = `1+${[...zTerms, ...pTerms].join("+") || "0"}`;
  const cx = d.shots.map((s) => `${f3(s.x)}*${win(s.start, s.end)}`).join("+") || "0";
  const cy = d.shots.map((s) => `${f3(s.y)}*${win(s.start, s.end)}`).join("+") || "0";
  const shake = d.filters.shake.map(([a, b]) => win(a, b)).join("+");
  const sx = shake ? `+14*sin(it*47)*(${shake})` : "";
  const sy = shake ? `+10*cos(it*53)*(${shake})` : "";
  const x = `max(0,min(iw-iw/zoom,iw*(0.5+(${cx}))-iw/zoom/2${sx}))`;
  const y = `max(0,min(ih-ih/zoom,ih*(0.5+(${cy}))-ih/zoom/2${sy}))`;

  const enable = (rs) => rs.map(([a, b]) => `between(t,${f3(a)},${f3(b)})`).join("+");
  const post = [];
  if (d.filters.desat.length) post.push(`hue=s=0:enable='${enable(d.filters.desat)}'`);
  if (d.filters.sepia.length) post.push(`colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131:enable='${enable(d.filters.sepia)}'`);
  // leve contraste/saturação "de YouTube" na facecam
  post.push("eq=contrast=1.06:saturation=1.12");

  const fade = d.fadeOut ? `,fade=t=out:st=${f3(Math.max(0, d.fadeOut[1] - 1.5))}:d=1.5` : "";

  // ----- áudio: voz + SFX (+ bip)
  const bleeps = (plan.audio || []).filter((a) => a.type === "bleep");
  const on = bleeps.map((b) => `between(t,${f3(b.start)},${f3(b.start + b.duration)})`).join("+");
  const sfxGain = o.sfxGain ?? 0.55;
  const audio = [
    `[0:a]aresample=48000,asetnsamples=n=64:p=0,aselect='${aSel}',asetpts=N/SR/TB,asetnsamples=n=1024:p=0${on ? `,volume=0:enable='${on}'` : ""}[voz]`,
    `[2:a]aresample=48000,volume=${sfxGain}[fx]`,
  ];
  const mixIns = ["[voz]", "[fx]"];
  if (on) {
    audio.push(`sine=f=1000:sample_rate=48000:d=${f3(d.duration)},volume=0.16,volume=0:enable='not(${on})'[bip]`);
    mixIns.push("[bip]");
  }
  audio.push(`${mixIns.join("")}amix=inputs=${mixIns.length}:duration=first:normalize=0,loudnorm=I=-14:TP=-1.0:LRA=9,aresample=48000,asetpts=N/SR/TB[aout]`);

  const graph = [
    `[0:v]fps=${fps},select='${vSel}',setpts=N/FRAME_RATE/TB,` +
      `zoompan=z='${z}':x='${x}':y='${y}':d=1:s=${W}x${H}:fps=${fps},setsar=1,${post.join(",")}[base]`,
    `[1:v]fps=${fps},format=rgba,scale=${W}:${H}[gfx]`,
    `[base][gfx]overlay=0:0:format=auto:eof_action=pass${fade}[vout]`,
    ...audio,
  ].join(";\n");

  fs.mkdirSync(o.tmpDir, { recursive: true });
  const script = path.join(o.tmpDir, "compose.filter");
  fs.writeFileSync(script, graph);
  const args = [
    "-y", "-hide_banner", "-loglevel", "error", "-nostats",
    "-i", o.video,
    "-i", o.layerVideo,
    "-i", o.sfxWav,
    "-filter_complex_script", script,
    "-map", "[vout]", "-map", "[aout]",
    "-t", f3(d.duration),
    "-c:v", "libx264", "-preset", o.preset || "veryfast", "-crf", String(o.crf || 23), "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
    o.out,
  ];
  const r = spawnSync("ffmpeg", args, { stdio: "inherit" });
  if (r.status !== 0) throw new Error(`ffmpeg falhou (filtro em ${script})`);
  return o.out;
}

module.exports = { compose };
