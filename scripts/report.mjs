import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { makeReport } from "../src/report.js";
// This CLI is optional. Browser export uses the vendored dependency.
const [input, output, library] = process.argv.slice(2);
if (!input || !output || !library)
  throw Error(
    "Usage: node scripts/report.mjs result.json report.docx /absolute/path/to/docx/dist/index.mjs",
  );
const docx = await import(pathToFileURL(resolve(library)).href);
const result = JSON.parse(await readFile(input, "utf8"));
await writeFile(output, await docx.Packer.toBuffer(makeReport(result, docx)));
console.log("Report saved: " + output);
