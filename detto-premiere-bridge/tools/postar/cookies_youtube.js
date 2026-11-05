"use strict";

/**
 * PEGA OS COOKIES DO YOUTUBE NUMA JANELA DE VERDADE — versão Node.
 *
 * POR QUE EM NODE (05/nov): a primeira versão disto era em Python e importava `playwright.sync_api`. Só que
 * o PC dele NÃO tem o Playwright do Python — o que o projeto instala (e usa nas cartelas, nas thumbs e na
 * vinheta) é o do **Node**. Resultado: o programa morria na primeira linha, e o painel ainda assim dizia
 * "Abri uma janela do navegador". A janela nunca abria.
 *
 * Aqui eu uso exatamente o mesmo Chromium que o resto do sistema já usa e que está comprovadamente
 * instalado na máquina dele.
 *
 *   node tools/postar/cookies_youtube.js --saida "E:\DETTO\cookies.txt" --perfil "E:\DETTO\postar\perfil_youtube"
 *   node tools/postar/cookies_youtube.js --atualizar      (sem janela, do perfil já salvo)
 */

const fs = require("fs");
const path = require("path");

function loadPlaywright() {
  const tentativas = [
    "playwright",
    path.join(__dirname, "..", "..", "node_modules", "playwright"),
    "/opt/node-tools/node_modules/playwright",
  ];
  for (const c of tentativas) {
    try {
      return require(c);
    } catch (_) {
      /* próximo */
    }
  }
  throw new Error(
    "Playwright não encontrado. Na pasta detto-premiere-bridge rode:  npm install playwright  " +
      "e depois:  npx playwright install chromium"
  );
}

function chromiumPath() {
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH || "/opt/pw-browsers";
  try {
    const dir = fs.readdirSync(base).find((d) => /^chromium-\d+$/.test(d));
    if (dir) {
      for (const sub of ["chrome-linux", "chrome-linux64", "chrome-win", "chrome-win64"]) {
        for (const exe of ["chrome", "chrome.exe"]) {
          const p = path.join(base, dir, sub, exe);
          if (fs.existsSync(p)) return p;
        }
      }
    }
  } catch (_) {
    /* no Windows o Playwright acha sozinho */
  }
  return undefined;
}

const PROVA = ["SAPISID", "__Secure-3PAPISID", "LOGIN_INFO", "SID"];

function temLogin(cookies) {
  const nomes = new Set(cookies.filter((c) => (c.domain || "").includes("youtube.com")).map((c) => c.name));
  return PROVA.some((p) => nomes.has(p));
}

/**
 * O formato cookies.txt que o yt-dlp lê. Dois detalhes decidem se o arquivo é aceito ou ignorado em
 * silêncio: o separador é TAB, e cookie de SESSÃO (expires -1) é DESCARTADO por quem lê — e é justamente
 * o de sessão que prova o login, então eu dou validade de um ano a esses.
 */
function netscape(cookies, dominio) {
  const umAno = Math.floor(Date.now() / 1000) + 365 * 24 * 3600;
  const linhas = [
    "# Netscape HTTP Cookie File",
    "# gerado pelo DETTO (tools/postar/cookies_youtube.js) - nao edite na mao",
    "",
  ];
  let n = 0;
  for (const c of cookies) {
    const dom = c.domain || "";
    if (dominio && !dom.includes(dominio)) continue;
    if (!c.name || c.value === undefined || c.value === null) continue;
    let exp = Math.floor(Number(c.expires));
    if (!Number.isFinite(exp) || exp <= 0) exp = umAno;
    linhas.push(
      [dom, dom.startsWith(".") ? "TRUE" : "FALSE", c.path || "/", c.secure ? "TRUE" : "FALSE", String(exp), c.name, String(c.value)].join("\t")
    );
    n++;
  }
  return { texto: linhas.join("\n") + "\n", n };
}

/** junta com o que já havia de OUTROS domínios (Instagram/TikTok), para não apagar o login deles */
function grava(saida, texto, dominio) {
  const antigas = [];
  try {
    for (const l of fs.readFileSync(saida, "utf8").split(/\r?\n/)) {
      if (!l.trim() || l.startsWith("#")) continue;
      if (!l.split("\t")[0].includes(dominio)) antigas.push(l);
    }
  } catch (_) {
    /* não existia */
  }
  fs.mkdirSync(path.dirname(saida), { recursive: true });
  fs.writeFileSync(saida, texto.trimEnd().split("\n").concat(antigas).join("\n") + "\n", "utf8");
}

/**
 * A raiz da midia. FORA DO WINDOWS o "E:/DETTO" vira uma pasta LITERAL "E:" onde o programa rodar — foi
 * assim que um teste criou `detto-premiere-bridge/E:/DETTO/...` dentro do repositorio, que entrou no
 * commit e quebrou o `git pull` no Windows ("invalid path": ":" nao vale em nome de arquivo).
 */
function raizMidia() {
  if (process.env.DETTO_MIDIA) return process.env.DETTO_MIDIA;
  if (process.platform === "win32") return "E:/DETTO";
  return path.join(require("os").tmpdir(), "DETTO");
}

function arg(nome, padrao) {
  const i = process.argv.indexOf("--" + nome);
  return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : padrao;
}

function hora() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
const log = (m) => console.log(`${hora()} ${m}`);

async function main() {
  const atualizar = process.argv.includes("--atualizar");
  const minutos = Number(arg("minutos", "8")) || 8;
  const dominio = arg("dominio", "youtube.com");
  const url = arg("url", "https://www.youtube.com/");
  const saida = arg("saida", path.join(raizMidia(), "cookies.txt"));
  const perfil = arg("perfil", path.join(raizMidia(), "postar", "perfil_youtube"));

  const { chromium } = loadPlaywright();
  fs.mkdirSync(perfil, { recursive: true });
  const primeira = fs.readdirSync(perfil).length === 0;
  if (atualizar && primeira) {
    log("ERRO: ainda nao existe perfil salvo. Rode SEM --atualizar uma vez, para entrar na conta.");
    process.exit(1);
  }

  const ctx = await chromium.launchPersistentContext(perfil, {
    headless: !!atualizar,
    executablePath: chromiumPath(),
    locale: "pt-BR",
    viewport: { width: 1180, height: 860 },
    args: ["--no-first-run", "--no-default-browser-check"],
  });
  log("JANELA ABERTA" + (atualizar ? " (sem mostrar, so reexportando)" : ""));
  try {
    const pg = ctx.pages()[0] || (await ctx.newPage());
    try {
      await pg.goto(url, { timeout: 60000, waitUntil: "domcontentloaded" });
    } catch (e) {
      log(`nao consegui abrir ${url} (${String(e).slice(0, 90)})`);
    }

    if (atualizar) {
      await pg.waitForTimeout(3500);
      const cks = await ctx.cookies();
      if (!temLogin(cks)) {
        log("o perfil salvo NAO esta mais logado. Rode sem --atualizar e entre de novo.");
        process.exit(1);
      }
      const { texto, n } = netscape(cks, dominio);
      grava(saida, texto, dominio);
      log(`${n} cookie(s) atualizados em ${saida}`);
      return;
    }

    log("==================================================================");
    log("  ENTRE NA SUA CONTA DO GOOGLE na janela que abriu.");
    log("  Voce faz isso UMA VEZ. Depois o painel atualiza sozinho.");
    log(`  Eu fecho a janela sozinho quando detectar o login (ate ${minutos} min).`);
    log("==================================================================");

    const fim = Date.now() + minutos * 60000;
    while (Date.now() < fim) {
      const cks = await ctx.cookies();
      if (temLogin(cks)) {
        log("login detectado - esperando 4 s para pegar todos os cookies...");
        await pg.waitForTimeout(4000);
        const { texto, n } = netscape(await ctx.cookies(), dominio);
        grava(saida, texto, dominio);
        log(`PRONTO: ${n} cookie(s) salvos em ${saida}`);
        return;
      }
      await pg.waitForTimeout(3000);
    }
    log(`passou de ${minutos} min e eu nao vi o login. Nada foi salvo - rode de novo.`);
    process.exit(1);
  } finally {
    try {
      await ctx.close();
    } catch (_) {
      /* já fechou */
    }
  }
}

main().catch((e) => {
  log("ERRO: " + String((e && e.message) || e).slice(0, 300));
  process.exit(1);
});
