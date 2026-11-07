// @ts-check
"use strict";

/**
 * Erro com código estável, usado para distinguir falhas fatais
 * (interrompem o job) de falhas por item (registradas e ignoradas).
 */
class BridgeError extends Error {
  /**
   * @param {string} code    ex.: PROJECT_NOT_FOUND, PREMIERE_DISCONNECTED
   * @param {string} message
   * @param {any} [details]
   */
  constructor(code, message, details) {
    super(message);
    this.name = "BridgeError";
    this.code = code;
    this.details = details;
  }
}

/**
 * Lançado pelo adaptador do host quando a API do Premiere não oferece
 * a operação. O executor converte em `{status: "fallback"}`.
 */
class ApiNotAvailableError extends BridgeError {
  /** @param {string} feature @param {string} [reason] */
  constructor(feature, reason) {
    super(reason || `${feature}_not_available`, `API não disponível nesta versão do Premiere: ${feature}`);
    this.name = "ApiNotAvailableError";
    this.feature = feature;
  }
}

module.exports = { BridgeError, ApiNotAvailableError };
