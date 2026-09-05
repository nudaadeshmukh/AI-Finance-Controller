// The shape of data/<run>/results.json — mirrors master_specification.md §18.
// `schema_version` is asserted at load time (§23.6): a mismatch is a hard
// error, not a best-effort render.

export const SCHEMA_VERSION = 1;

export interface Summary {
  records_processed: number;
  matched: number | null;
  match_rate: number | null;
  match_precision: number | null;
  false_matches: number | null;
  unresolved: number;
  excluded: number;
  runtime_ms_cascade: number;
  runtime_ms_llm: number;
  throughput_per_sec_cascade: number;
}

export interface Baseline {
  name: string;
  matched: number;
  match_rate: number;
}

export interface Ceiling {
  resolvable: number | null;
  rate: number | null;
  achievable: number | null;
  achievable_rate: number | null;
}

export interface LlmContribution {
  enabled: boolean;
  records_resolved: number;
  hypotheses_proposed: number;
  hypotheses_rejected_by_verifier: number;
}

export interface SourceTotals {
  orders_gross: number;
  recon_net: number;
  bank_credited: number;
  ledger_revenue: number;
}

export interface BridgeBand {
  label: string;
  amount: number;
  sign: "+" | "-" | "=";
  record_keys: string[];
}

export interface PassRow {
  name: string;
  matched: number;
  runtime_ms: number;
}

export interface Proof {
  gross: number;
  fees: number;
  tax: number;
  refunds: number;
  expected_net: number;
  observed_net: number;
  delta: number;
  closes: boolean;
  tolerance_applied: number;
}

export interface AuditEntry {
  stage: string;
  action: string;
  detail: string;
}

export type RecordStatus = "matched" | "exception" | "unresolved";

export interface RecordRow {
  record_key: string;
  source: string;
  display_amount: number;
  status: RecordStatus;
  pass_name: string | null;
  group_id: string | null;
  member_keys: string[];
  proof: Proof | null;
  audit: AuditEntry[];
}

export interface ExceptionRow {
  record_key: string;
  reason_code: string;
  reason_text: string;
  passes_tried: string[];
  candidates: string[];
}

export interface FeeSlab {
  method: string;
  period_start: string;
  period_end: string;
  inferred_bps: number;
  gst_bps: number;
  sample_size: number;
  reproduces_all_stated: boolean;
}

export interface ToleranceConstants {
  amount_delta_paise_per_derived_line: number;
  utr_truncation_digits: number;
  ledger_lag_days: number;
}

export interface ResultsDocument {
  schema_version: number;
  run_id: string;
  label: string;
  generated_at: number;
  seed: number;
  summary: Summary;
  baseline: Baseline;
  ceiling: Ceiling;
  llm_contribution: LlmContribution;
  source_totals: SourceTotals;
  bridge: BridgeBand[];
  passes: PassRow[];
  records: RecordRow[];
  exceptions: ExceptionRow[];
  derived_fee_slabs: FeeSlab[];
  tolerance_constants: ToleranceConstants;
}

export function assertSchema(doc: ResultsDocument): ResultsDocument {
  if (doc.schema_version !== SCHEMA_VERSION) {
    throw new Error(
      `results.json schema_version ${doc.schema_version} — this build expects ${SCHEMA_VERSION}`,
    );
  }
  return doc;
}

export const RUNS = [
  { id: "clean-august", label: "Clean month" },
  { id: "heavy-refunds", label: "Heavy refund cycle" },
  { id: "holiday-skew", label: "Holiday-affected settlements" },
  { id: "high-ambiguity", label: "High-ambiguity batch" },
] as const;

export type RunId = (typeof RUNS)[number]["id"];
