"use strict";

/**
 * Diálogos e seletores de arquivo/pasta via UXP (`uxp.storage.localFileSystem`).
 */

function lfs() {
  return require("uxp").storage.localFileSystem;
}

/**
 * Confirmação modal (SIM/NÃO). Usada antes de qualquer alteração potencialmente destrutiva.
 * @param {string} message
 * @returns {Promise<boolean>}
 */
function confirmDialog(message) {
  const dialog = document.getElementById("confirm-dialog");
  document.getElementById("confirm-text").textContent = message;
  return new Promise((resolve) => {
    const yes = document.getElementById("confirm-yes");
    const no = document.getElementById("confirm-no");
    const finish = (value) => {
      yes.removeEventListener("click", onYes);
      no.removeEventListener("click", onNo);
      dialog.close();
      resolve(value);
    };
    const onYes = () => finish(true);
    const onNo = () => finish(false);
    yes.addEventListener("click", onYes);
    no.addEventListener("click", onNo);
    if (typeof dialog.uxpShowModal === "function") dialog.uxpShowModal({ title: "DETTO", resize: "none" });
    else dialog.showModal();
  });
}

/**
 * @param {string[]} types extensões sem ponto, ex.: ["json"]
 * @returns {Promise<{path: string, name: string, read: () => Promise<string>} | null>}
 */
async function pickFile(types) {
  const file = await lfs().getFileForOpening({ types, allowMultiple: false });
  if (!file) return null;
  return {
    path: file.nativePath,
    name: file.name,
    read: () => file.read(),
  };
}

/** @returns {Promise<string|null>} caminho nativo da pasta */
async function pickFolder() {
  const folder = await lfs().getFolder();
  return folder && folder.nativePath ? folder.nativePath : null;
}

module.exports = { confirmDialog, pickFile, pickFolder };
