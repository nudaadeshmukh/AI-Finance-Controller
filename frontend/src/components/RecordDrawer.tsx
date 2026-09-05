import { useEffect } from "react";
import { rupees } from "../lib/format";
import type { ExceptionRow, RecordRow } from "../lib/types";
import { PassTag, StatusBadge } from "./Bits";
import { ProofTable } from "./ProofTable";

// §23.5 — click a row, see the group's source records (grouped by prefix from
// member_keys — results.json §18 carries the keys and the proof, not per-row
// source field values) plus the full audit trail. For an exception, the
// specific reason and every candidate, never a pick.
export function RecordDrawer({
  record,
  exception,
  onClose,
}: {
  record: RecordRow;
  exception?: ExceptionRow;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const bySource = groupBySource(record.member_keys);

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer__head">
          <div>
            <div className="t-title-lg mono">{record.record_key}</div>
            <div style={{ marginTop: 6 }}>
              <StatusBadge record={record} reasonCode={exception?.reason_code} />{" "}
              <PassTag pass={record.pass_name} />
            </div>
          </div>
          <button className="drawer__close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="t-body-sm muted" style={{ marginBottom: 8 }}>
          Amount {rupees(record.display_amount)}
          {record.group_id && <> · group {record.group_id}</>}
        </div>

        {record.status === "matched" ? (
          <>
            <div className="t-caption-up muted" style={{ margin: "16px 0 8px" }}>
              Group members
            </div>
            <div className="drawer__grid">
              {(["order", "recon", "bank", "ledger"] as const).map((src) => (
                <div className="src" key={src}>
                  <div className="src__label t-caption-up">{src}</div>
                  {bySource[src]?.length ? (
                    bySource[src].map((k) => (
                      <div className="src__val" key={k}>
                        {k.replace(`${src}:`, "")}
                      </div>
                    ))
                  ) : (
                    <div className="muted">—</div>
                  )}
                </div>
              ))}
            </div>

            <div className="t-caption-up muted" style={{ margin: "16px 0 8px" }}>
              Arithmetic proof
            </div>
            {record.proof && <ProofTable proof={record.proof} />}
          </>
        ) : (
          exception && (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="t-title-sm">{exception.reason_code}</div>
              <p className="t-body-sm" style={{ color: "var(--body)" }}>
                {exception.reason_text}
              </p>
              {exception.candidates.length > 0 && (
                <>
                  <div className="t-caption-up muted">Candidates — both listed, neither chosen</div>
                  {exception.candidates.map((c) => (
                    <div className="mono t-body-sm" key={c}>
                      {c}
                    </div>
                  ))}
                </>
              )}
              <div className="t-caption-up muted" style={{ marginTop: 8 }}>
                Passes tried
              </div>
              <div className="mono t-body-sm">{exception.passes_tried.join(" · ")}</div>
            </div>
          )
        )}

        <div className="t-caption-up muted" style={{ margin: "20px 0 8px" }}>
          Audit trail
        </div>
        {record.audit.length === 0 && <div className="muted t-body-sm">No entries.</div>}
        {record.audit.map((a, i) => (
          <div className="audit-item" key={i}>
            <span className="audit-stage">{a.stage}</span>
            <span>
              <strong>{a.action}</strong>
              {a.detail && <> — {a.detail}</>}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function groupBySource(keys: string[]): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const k of keys) {
    const src = k.split(":")[0];
    (out[src] ??= []).push(k);
  }
  return out;
}
