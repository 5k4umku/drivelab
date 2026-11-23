import { readFile } from "node:fs/promises";
import vm from "node:vm";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { fmt } from "../src/format.js";
import assert from "node:assert/strict";
import { makeReport, makeAssemblyReport } from "../src/report.js";

// Та же версия библиотеки, что используется при выгрузке в браузере.
const D = vm.runInNewContext(
  (await readFile(
    new URL("../vendor/docx-9.6.1.js", import.meta.url),
    "utf8",
  )) + ";docx",
  {
    TextEncoder,
    TextDecoder,
    setTimeout,
    clearTimeout,
    setImmediate,
    Buffer,
    Uint8Array,
    ArrayBuffer,
  },
);
for (const [name, make] of [
  ["helical-seminar", makeReport],
  ["automatic-coefficients", makeReport],
  ["reducer-three-stage", makeAssemblyReport],
  ["internal-pair", makeReport],
  ["reducer-editor", makeAssemblyReport],
]) {
  const result = JSON.parse(
    await readFile(
      new URL(`../examples/${name}.result.json`, import.meta.url),
      "utf8",
    ),
  );
  const archive = await D.Packer.toBuffer(make(result, D));
  assert.ok(archive.length > 10000, `${name}: пустой отчёт`);
  assert.equal(
    archive.subarray(0, 2).toString(),
    "PK",
    `${name}: отсутствует ZIP-контейнер DOCX`,
  );
  console.log(`${name}: DOCX сформирован (${archive.length} байт)`);
}

// Check the values inside a freshly calculated report, including the engineering status.
const root = fileURLToPath(new URL("..", import.meta.url));
const stage = JSON.parse(execFileSync("python", ["-B", "src/engine.py", "examples/gost-annex-11.json"], {
  cwd: root, encoding: "utf8",
}));
const archive = await D.Packer.toBuffer(makeReport(stage, D));
const readDocument = `
import io, json, sys, zipfile
from xml.etree import ElementTree as ET
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
      'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}
with zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read())) as doc:
    xml = ET.fromstring(doc.read('word/document.xml'))
    footer = ET.fromstring(doc.read('word/footer1.xml'))
    print(json.dumps({
        'runs': [n.text for n in xml.findall('.//w:t', ns)],
        'formulas': [n.text for n in xml.findall('.//m:oMath/m:r/m:t', ns)],
        'footer': ''.join(footer.itertext()),
        'breaks': len(xml.findall('.//w:pageBreakBefore', ns)),
        'headers': sum(row.get('{%s}val' % ns['w']) not in ('0', 'false') for row in xml.findall('.//w:tblHeader', ns)),
    }))
`;
const inspect = bytes => JSON.parse(execFileSync("python", ["-B", "-c", readDocument], {input: bytes}));
const { version } = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
function checkLayout(doc) {
  assert.ok(doc.runs.includes("DriveLab   /   " + version));
  assert.ok(doc.footer.includes("DriveLab " + version));
  assert.match(doc.footer, /\bPAGE\b/);
  assert.match(doc.footer, /\bNUMPAGES\b/);
  assert.ok(doc.headers > 0);
}
const stageDocument = inspect(archive);
checkLayout(stageDocument);
assert.deepEqual(stageDocument.formulas, stage.trace.map(step => step.formula));
const runs = stageDocument.runs;
for (const stress of [stage.rating.h, ...stage.rating.fs, stage.rating.hmax, ...stage.rating.fsmax])
  assert.ok(runs.includes(fmt(stress, 3)), "В отчёте отсутствует результат " + stress);
const pending = stage.checks.find(item => item.status === "pending");
assert.ok(runs.includes(pending.detail));
console.log("Приложение 11: в DOCX сверены шесть напряжений и условие применимости.");

const rootPair = JSON.parse(execFileSync("python", ["-B", "src/engine.py", "examples/gost-root-fatigue.json"], {
  cwd: root, encoding: "utf8",
}));
const rootDoc = await D.Packer.toBuffer(makeReport(rootPair, D));
const rootRuns = inspect(rootDoc).runs;
for (const [i, yd] of [.938966447, .912194723].entries()) {
  assert.ok(rootRuns.includes("Yδ" + (i + 1)));
  assert.ok(rootRuns.some(line => line?.includes(fmt(yd, 6))));
  assert.ok(rootRuns.some(line => line?.includes(rootPair.input.gost.roots[i].evidence)));
}
console.log("В DOCX проверены коэффициенты Yδ и обоснования обоих венцов.");

const assembly = JSON.parse(await readFile(new URL("../examples/reducer-three-stage.result.json", import.meta.url), "utf8"));
const assemblyDocument = inspect(await D.Packer.toBuffer(makeAssemblyReport(assembly, D)));
checkLayout(assemblyDocument);
assert.equal(assemblyDocument.breaks, assembly.stages.length);
assert.ok(assemblyDocument.runs.includes(fmt(assembly.outputTorque, 6)));
assert.deepEqual(assemblyDocument.formulas, [
  ...assembly.trace.map(step => step.formula),
  "ΣF = 0; ΣMx = 0; ΣMy = 0; M = r × F",
  ...assembly.stages.flatMap(stage => stage.result.trace.map(step => step.formula)),
]);
for (const stage of assembly.stages) {
  assert.ok(assemblyDocument.runs.includes("Ступень " + (stage.index + 1) + ". Полный расчёт"));
  for (const check of stage.result.checks) assert.ok(assemblyDocument.runs.includes(check.detail));
}
console.log("Версия, поля страниц, формулы сборки и полные приложения ступеней проверены.");
