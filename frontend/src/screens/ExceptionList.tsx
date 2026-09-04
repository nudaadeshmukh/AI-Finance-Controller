import { useMemo } from "react";
import { StatusBadge } from "../components/Bits";
import type { ResultsDocument } from "../lib/types";

// §23.4 — every unresolved record with a specific reason and, where the failure
// is ambiguity, both candidates listed. Most submissions hide their failures;
// this one has a screen for them.
export function ExceptionList({
  doc,
  onOpenRecord,
}: {
  doc: ResultsDocument;
  onOpenRecord: (key: string) => void;
}) {
  const byCode = useMemo(() => {
    const m: Record<string, number> = {};
    for (const e of doc.exceptions) m[e.reason_code] = (m[e.reason_code] ?? 0) + 1;
    return m;
  }, [doc]);

  const amountByKey = useMemo(() => {
    const m: Record<string, number> = {};
    for (const r of doc.records) m[r.record_key] = r.display_amount;
    return m;
  }, [doc]);

  return (
    <>
      <h1 className="screen-title t-display-md">Exception list</h1>
      <p className="screen-lede">
        {doc.exceptions.length} records the pipeline could not close. Each carries a
        specific reason. Where two candidates were plausible, both are named — none was
        picked.
      </p>

      <div className="chip-row">
        {Object.entries(byCode).map(([code, n]) => (
          <span className="tol" key={code}>
            <code>{code}</code> · {n}
          </span>
        ))}
      </div>

      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Record</th>
              <th className="col-amount">Amount</th>
              <th>Reason</th>
              <th>Detail / candidates</th>
              <th>Badge</th>
            </tr>
          </thead>
          <tbody>
            {doc.exceptions.map((e) => (
              <tr key={e.record_key} onClick={() => onOpenRecord(e.record_key)}>
                <td className="mono">{e.record_key}</td>
                <td className="col-amount mono">
                  {amountByKey[e.record_key] != null
                    ? (amountByKey[e.record_key] / 100).toLocaleString("en-IN", {
                        minimumFractionDigits: 2,
                      })
                    : "—"}
                </td>
                <td className="mono">{e.reason_code}</td>
                <td className="t-body-sm">
                  {e.reason_text}
                  {e.candidates.length > 0 && (
                    <div className="mono muted" style={{ marginTop: 4 }}>
                      {e.candidates.join("  ·  ")}
                    </div>
                  )}
                </td>
                <td>
                  <StatusBadge reasonCode={e.reason_code} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="t-body-sm muted" style={{ marginTop: 16 }}>
        These {doc.exceptions.length} were not resolved. No guess was recorded — a false
        match is worse than an unresolved record. The{" "}
        {doc.summary.excluded} unrelated bank debits per run are excluded, not counted here.
      </p>
    </>
  );
}
