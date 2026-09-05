// Small shared presentational bits. Grouped in one file — each is a few lines
// and they always travel together.

import { rupeesPlain } from "../lib/format";
import type { ExceptionRow, RecordRow } from "../lib/types";

export function Spinner() {
  return <div className="spinner" role="status" aria-label="Loading" />;
}

/** Emerald / rose / amber / grey per design.md status semantics.
    AMBIGUOUS_DUPLICATE is amber ("requires review"), never rose. */
export function StatusBadge({ record, reasonCode }: { record?: RecordRow; reasonCode?: string }) {
  const code = reasonCode ?? "";
  if (record?.status === "matched") {
    return <span className="badge badge--matched t-caption-up">Matched</span>;
  }
  if (code === "NOT_A_SETTLEMENT") {
    return <span className="badge badge--excluded t-caption-up">Excluded</span>;
  }
  if (code === "AMBIGUOUS_DUPLICATE") {
    return <span className="badge badge--review t-caption-up">Requires review</span>;
  }
  return <span className="badge badge--exception t-caption-up">Exception</span>;
}

/** Grey chip for a cascade pass, pale-yellow-outlined chip for the LLM.
    The one place a tint of the brand colour appears outside a primary action —
    so the "LLM is a sliver" story is countable at a glance. */
export function PassTag({ pass }: { pass: string | null }) {
  if (!pass) return <span className="muted t-body-sm">—</span>;
  const isLlm = pass === "llm_verified";
  return (
    <span className={`pass-tag ${isLlm ? "pass-tag--llm" : "pass-tag--cascade"}`}>
      {isLlm ? "llm" : pass}
    </span>
  );
}

export function Money({ paise, className = "" }: { paise: number; className?: string }) {
  const neg = paise < 0;
  return (
    <span className={`money ${neg ? "money--neg" : ""} ${className}`}>{rupeesPlain(paise)}</span>
  );
}

export function ReasonPill({ ex }: { ex: ExceptionRow }) {
  return (
    <span className="mono t-body-sm" title={ex.reason_text}>
      {ex.reason_code}
    </span>
  );
}
