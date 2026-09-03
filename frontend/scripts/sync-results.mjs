// Copies each frozen run's committed results.json into public/data/<run>/ so
// the static app can fetch it at /data/<run>/results.json — the same path
// master_specification.md §23 names. Runs automatically before `dev` and
// `build` (package.json pre-hooks). public/data/ is git-ignored: it is a
// build artifact, the source of truth stays in the repo's top-level data/.
//
// No dependencies — Node built-ins only.

import { copyFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..", "..");
const RUNS = ["clean-august", "heavy-refunds", "holiday-skew", "high-ambiguity"];

let copied = 0;
for (const run of RUNS) {
  const src = resolve(repoRoot, "data", run, "results.json");
  if (!existsSync(src)) {
    console.warn(`sync-results: ${src} missing — run \`python -m recon run --dataset ${run}\` first`);
    continue;
  }
  const dest = resolve(here, "..", "public", "data", run, "results.json");
  mkdirSync(dirname(dest), { recursive: true });
  copyFileSync(src, dest);
  copied += 1;
}
console.log(`sync-results: ${copied}/${RUNS.length} run(s) copied into public/data/`);
if (copied === 0) process.exitCode = 1;
