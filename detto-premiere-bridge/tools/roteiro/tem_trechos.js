// sai 0 se o roteiro tem trechos que o roteiro-to-plan entende; 3 se não tem (o editar.py então monta um a partir dele)
const fs = require("fs");
const { parseRoteiro } = require("./parse");
const b = fs.readFileSync(process.argv[2]);
let t = b.toString("utf-8");
if (t.includes("�")) t = b.toString("latin1");
let r = parseRoteiro(t);
if (!r.segments.length) {
  const i = t.search(/^\s*\[\s*\d{1,2}:\d{2}/m);
  if (i >= 0) r = parseRoteiro(t.slice(0, i) + "\n=====\n BLOCO 1\n=====\n" + t.slice(i));
}
process.exit(r.segments.length ? 0 : 3);
