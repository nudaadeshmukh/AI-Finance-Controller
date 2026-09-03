import { assertSchema, type ResultsDocument, type RunId } from "./types";

// public/data/<run>/results.json is produced by scripts/sync-results.mjs
// (the `predev` / `prebuild` hook) from the committed data/<run>/results.json.
export async function loadRun(runId: RunId): Promise<ResultsDocument> {
  const url = `${import.meta.env.BASE_URL}data/${runId}/results.json`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(
      `Could not load ${url} (${res.status}). Run \`npm run sync\` in frontend/ ` +
        "after \`python -m recon run --dataset all\`.",
    );
  }
  return assertSchema((await res.json()) as ResultsDocument);
}
