import { cp, mkdir, copyFile, rm, readFile, readdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const root = resolve(import.meta.dirname, "..");
const out = resolve(root, "dist");
if (out !== resolve(root, "dist"))
  throw new Error("Unexpected build directory");
// Every Python module under src is part of the browser runtime, including lazy imports.
const manifest = JSON.parse(await readFile(resolve(root, "src/python-files.json"), "utf8"));
const sourceFiles = await readdir(resolve(root, "src"));
for (const file of sourceFiles.filter(name => name.endsWith(".py")))
  if (!manifest.includes(file)) throw Error(`Missing Python module in src/python-files.json: ${file}`);
for (const file of manifest)
  if (!sourceFiles.includes(file)) throw Error(`Missing runtime file in src: ${file}`);
await mkdir(out, { recursive: true });
for (const name of ["src", "vendor"]) {
  const target = resolve(out, name);
  if (!target.startsWith(out + "/") && !target.startsWith(out + "\\"))
    throw new Error("Unexpected build target");
  await rm(target, { recursive: true, force: true });
}
for (const name of ["index.html", "styles.css"])
  await copyFile(resolve(root, name), resolve(out, name));
for (const name of ["src", "vendor"])
  await cp(resolve(root, name), resolve(out, name), {
    recursive: true,
    filter: (path) => !path.includes("__pycache__") && !path.endsWith(".pyc"),
  });
await mkdir(resolve(out, "examples"), {recursive:true});
await copyFile(resolve(root, "examples/gost-annex-11.json"), resolve(out, "examples/gost-annex-11.json"));
const pkg = JSON.parse(await readFile(resolve(root, "package.json"), "utf8"));
await writeFile(resolve(out, "src/version.js"), "export const siteVersion = " + JSON.stringify(pkg.version) + ";\n");
console.log(`DriveLab ${pkg.version}: static build ready in dist/`);
