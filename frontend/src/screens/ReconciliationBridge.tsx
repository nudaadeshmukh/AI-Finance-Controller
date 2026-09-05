import type { ExplorerFilter } from "../App";
import { rupees } from "../lib/format";
import type { BridgeBand, ResultsDocument } from "../lib/types";

// §23.2 — the horizontal waterfall from gross orders to bank credit. Each band
// is clickable and filters the Match Explorer to the records behind it. This
// is the screen that proves every rupee of the gap is accounted for.
export function ReconciliationBridge({
  doc,
  onBandClick,
}: {
  doc: ResultsDocument;
  onBandClick: (f: ExplorerFilter) => void;
}) {
  const bands = doc.bridge;
  const max = Math.max(...bands.map((b) => Math.abs(b.amount)), 1);

  return (
    <>
      <h1 className="screen-title t-display-md">Reconciliation bridge</h1>
      <p className="screen-lede">
        Start at what the merchant sold. Subtract every deduction the payment processor and
        the calendar impose. Land — to the paise — on what the bank actually paid in.
      </p>

      <div className="card">
        <div className="waterfall">
          {bands.map((b) => (
            <Band key={b.label} band={b} max={max} onClick={onBandClick} />
          ))}
        </div>
        <p className="t-body-sm muted" style={{ marginTop: 16 }}>
          Click any band to see the records behind it in the Match Explorer.
          "Settled next cycle" / "Prior cycle spillover" are the signed accrual-vs-cash
          timing residual — the difference between when revenue was earned and when it
          cleared.
        </p>
      </div>
    </>
  );
}

function Band({
  band,
  max,
  onClick,
}: {
  band: BridgeBand;
  max: number;
  onClick: (f: ExplorerFilter) => void;
}) {
  const isTotal = band.sign === "=";
  const isNeg = band.sign === "-";
  const cls = isTotal ? "wf-band--total" : isNeg ? "wf-band--neg" : "";
  const width = `${Math.max(4, (Math.abs(band.amount) / max) * 100)}%`;
  const prefix = band.sign === "=" ? "=" : band.sign;

  return (
    <button
      className={`wf-band ${cls}`}
      disabled={isTotal || band.record_keys.length === 0}
      onClick={() =>
        onClick({ label: band.label, recordKeys: new Set(band.record_keys) })
      }
    >
      <span className="t-title-sm">{band.label}</span>
      <span className="wf-band__bar" style={{ width }} />
      <span className="wf-band__amount">
        {prefix} {rupees(Math.abs(band.amount))}
      </span>
    </button>
  );
}
