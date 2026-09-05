import { useMemo, useState } from "react";
import type { ExplorerFilter } from "../App";
import { Money, PassTag, StatusBadge } from "../components/Bits";
import type { RecordRow, ResultsDocument } from "../lib/types";

const CASCADE_PASSES = ["exact", "aggregate", "fee_reversal", "timing", "tolerance"];

// §23.3 — all 400 records, filterable by resolving pass. The visual point
// lands without narration: the deterministic passes carry almost everything,
// the LLM (pale-yellow tag) is a sliver.
export function MatchExplorer({
  doc,
  filter,
  onClearFilter,
  onOpenRecord,
}: {
  doc: ResultsDocument;
  filter: ExplorerFilter | null;
  onClearFilter: () => void;
  onOpenRecord: (key: string) => void;
}) {
  const [passFilter, setPassFilter] = useState<Set<string>>(new Set());

  const counts = useMemo(() => tallyPasses(doc.records), [doc]);

  const rows = useMemo(() => {
    let rs = doc.records;
    if (filter?.recordKeys) rs = rs.filter((r) => filter.recordKeys!.has(r.record_key));
    if (passFilter.size > 0) rs = rs.filter((r) => passFilter.has(passKeyOf(r)));
    return rs;
  }, [doc, filter, passFilter]);

  function togglePass(key: string) {
    setPassFilter((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  return (
    <>
      <h1 className="screen-title t-display-md">Match explorer</h1>
      <p className="screen-lede">
        Every record and the pass that resolved it. The cascade does the work; the LLM tag
        appears {counts.llm_verified ?? 0} time{counts.llm_verified === 1 ? "" : "s"}.
      </p>

      {filter?.recordKeys && (
        <div className="callout">
          Showing <strong>{rows.length}</strong> records behind{" "}
          <strong>{filter.label}</strong>.{" "}
          <button className="chip" onClick={onClearFilter}>
            Clear
          </button>
        </div>
      )}

      <div className="chip-row">
        {[...CASCADE_PASSES, "llm_verified", "exception"].map((key) => {
          const n = counts[key] ?? 0;
          if (n === 0 && key !== "llm_verified") return null;
          return (
            <button
              key={key}
              className={`chip ${passFilter.has(key) ? "chip--active" : ""}`}
              onClick={() => togglePass(key)}
            >
              {key === "exception" ? "unresolved" : key === "llm_verified" ? "llm" : key} · {n}
            </button>
          );
        })}
        {passFilter.size > 0 && (
          <button className="chip" onClick={() => setPassFilter(new Set())}>
            reset
          </button>
        )}
      </div>

      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Record</th>
              <th className="col-amount">Amount</th>
              <th>Status</th>
              <th>Resolved by</th>
              <th>Group</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.record_key} onClick={() => onOpenRecord(r.record_key)}>
                <td className="mono">{r.record_key}</td>
                <td className="col-amount">
                  <Money paise={r.display_amount} />
                </td>
                <td>
                  <StatusBadge record={r} reasonCode={reasonOf(doc, r.record_key)} />
                </td>
                <td>
                  <PassTag pass={r.pass_name} />
                </td>
                <td className="mono muted">{r.group_id ?? "—"}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  No records match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

function passKeyOf(r: RecordRow): string {
  if (r.status === "matched") return r.pass_name ?? "unknown";
  return "exception";
}

function tallyPasses(records: RecordRow[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const r of records) out[passKeyOf(r)] = (out[passKeyOf(r)] ?? 0) + 1;
  return out;
}

function reasonOf(doc: ResultsDocument, key: string): string | undefined {
  return doc.exceptions.find((e) => e.record_key === key)?.reason_code;
}
