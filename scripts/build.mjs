import { cp, mkdir, copyFile, rm, readFile } from "node:fs/promises";
import { resolve } from "node:path";
const root = resolve(import.meta.dirname, "..");
const out = resolve(root, "dist");
if (out !== resolve(root, "dist"))
  throw new Error("Unexpected build directory");
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
const pkg = JSON.parse(await readFile(resolve(root, "package.json"), "utf8"));
console.log(`DriveLab ${pkg.version}: static build ready in dist/`);
