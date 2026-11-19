// @ts-check
"use strict";

const { TIME_EPSILON } = require("./constants");

/** FPS comuns aceitos (NTSC incluído). */
const COMMON_FPS = Object.freeze([23.976, 24, 25, 29.97, 30, 48, 50, 59.94, 60, 119.88, 120]);

/**
 * Compara duas taxas de quadros com tolerância (29.97 == 29.97002997...).
 * @param {number} a
 * @param {number} b
 */
function fpsEquals(a, b) {
  return Math.abs(Number(a) - Number(b)) < 0.01;
}

/**
 * Converte segundos para número de frames (arredondado ao frame mais próximo).
 * @param {number} seconds
 * @param {number} fps
 */
function secondsToFrames(seconds, fps) {
  return Math.round(seconds * fps);
}

/**
 * Alinha um tempo em segundos ao frame mais próximo.
 * @param {number} seconds
 * @param {number} fps
 */
function snapToFrame(seconds, fps) {
  if (!fps || fps <= 0) return seconds;
  return secondsToFrames(seconds, fps) / fps;
}

/**
 * Indica se o tempo já está alinhado a um frame.
 * @param {number} seconds
 * @param {number} fps
 */
function isFrameAligned(seconds, fps) {
  return Math.abs(snapToFrame(seconds, fps) - seconds) < TIME_EPSILON;
}

/**
 * @param {number} a
 * @param {number} b
 * @param {number} [epsilon]
 */
function timesEqual(a, b, epsilon = TIME_EPSILON) {
  return Math.abs(a - b) < epsilon;
}

/**
 * Formata segundos como timecode HH:MM:SS:FF.
 * @param {number} seconds
 * @param {number} fps
 */
function toTimecode(seconds, fps) {
  const roundFps = Math.round(fps) || 30;
  const totalFrames = Math.round(seconds * fps);
  const frames = totalFrames % roundFps;
  const totalSeconds = Math.floor(totalFrames / roundFps);
  const pad = (/** @type {number} */ n) => String(n).padStart(2, "0");
  return `${pad(Math.floor(totalSeconds / 3600))}:${pad(Math.floor(totalSeconds / 60) % 60)}:${pad(totalSeconds % 60)}:${pad(frames)}`;
}

module.exports = { COMMON_FPS, fpsEquals, secondsToFrames, snapToFrame, isFrameAligned, timesEqual, toTimecode };
