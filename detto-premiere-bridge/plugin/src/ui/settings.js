"use strict";

/** Persistência das configurações do painel em localStorage. */

const KEY = "detto.bridge.config.v1";

/** @returns {Partial<import("../core/config").BridgeConfig>} */
function loadSettings() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (_) {
    return {};
  }
}

/** @param {Partial<import("../core/config").BridgeConfig>} settings */
function saveSettings(settings) {
  try {
    localStorage.setItem(KEY, JSON.stringify(settings));
  } catch (_) {
    /* ignora: configuração volta ao padrão na próxima sessão */
  }
}

module.exports = { loadSettings, saveSettings };
