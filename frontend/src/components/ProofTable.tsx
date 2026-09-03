import { rupeesPlain } from "../lib/format";
import type { Proof } from "../lib/types";

// The ArithmeticProof display (design.md `proof-table`). Renders the closing
// equation as a labelled list, with the expected/observed line set apart and a
// delta pill that is emerald at 0, rose otherwise — this is the frame that
// carries the llm-hallucination rejection moment (§24).
export function ProofTable({ proof }: { proof: Proof }) {
  const rows: [string, number][] = [
    ["Gross orders", proof.gross],
    ["Processing fees", -proof.fees],
    ["GST on fees", -proof.tax],
    ["Refunds", -proof.refunds],
  ];
  return (
    <div className="proof">
      {rows.map(([label, value]) => (
        <div className="proof__row" key={label}>
          <span>{label}</span>
          <span className={value < 0 ? "money--neg" : undefined}>{rupeesPlain(value)}</span>
        </div>
      ))}
      <div className="proof__row proof__row--total">
        <span>Expected net</span>
        <span>{rupeesPlain(proof.expected_net)}</span>
      </div>
      <div className="proof__row proof__row--total">
        <span>Observed (bank credit)</span>
        <span>{rupeesPlain(proof.observed_net)}</span>
      </div>
      <div className="proof__row" style={{ borderBottom: 0, paddingTop: 12 }}>
        <span>Delta</span>
        <span className={`delta ${proof.delta === 0 ? "delta--zero" : "delta--nonzero"}`}>
          {rupeesPlain(proof.delta)} {proof.delta === 0 ? "· closes" : "· rejected"}
        </span>
      </div>
      {proof.tolerance_applied > 0 && (
        <div className="proof__row muted" style={{ borderBottom: 0 }}>
          <span>Tolerance applied</span>
          <span>{rupeesPlain(proof.tolerance_applied)}</span>
        </div>
      )}
    </div>
  );
}
