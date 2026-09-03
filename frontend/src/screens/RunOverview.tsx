import { asOfDate, ms, percent, rupees } from "../lib/format";
import type { ResultsDocument } from "../lib/types";

// §23.1 — headline strip, four source cards, the one-line pitch. Also carries
// the §17.2 comparison table and the tolerance constants (§23.6), and the
// §24 "LLM layer unavailable" banner when a run hit that.
export function RunOverview({ doc }: { doc: ResultsDocument }) {
  const s = doc.summary;
  const matched = s.matched ?? 0;
  const llm = doc.llm_contribution;
  const llmRan = llm.enabled;
  const llmUnavailable = llmRan && llm.hypotheses_proposed === 0 && s.runtime_ms_llm === 0;

  const sources: [string, number, string][] = [
    ["Merchant orders", doc.source_totals.orders_gross, "gross, before any deduction"],
    ["Razorpay recon", doc.source_totals.recon_net, "net of fees, tax, refunds"],
    ["Bank statement", doc.source_totals.bank_credited, "one lump credit per settlement"],
    ["Accounting ledger", doc.source_totals.ledger_revenue, "revenue booked (gross)"],
  ];

  return (
    <>
      <h1 className="screen-title t-display-lg">{doc.label}</h1>
      <p className="screen-lede">
        Four systems, four different totals for the same month.{" "}
        <strong>
          {matched} of {s.records_processed} reconciled automatically
        </strong>
        , every rupee of the rest explained. Data as of {asOfDate(doc.generated_at)}.
      </p>

      {llmUnavailable && (
        <div className="callout callout--warn">
          <strong>LLM hypothesis layer was unavailable for this run.</strong> The pipeline
          completed on the deterministic cascade alone — <code>HYPOTHESIS_LAYER_UNAVAILABLE</code>,
          not an error (§15.4).
        </div>
      )}

      <div className="metric-strip">
        <Metric label="Match rate" value={s.match_rate == null ? "—" : percent(s.match_rate)}
          sub={`${matched} / ${s.records_processed} correct vs sealed key`} />
        <Metric label="Match precision"
          value={s.match_precision == null ? "—" : percent(s.match_precision)}
          sub={`${s.false_matches ?? 0} false matches`} />
        <Metric label="Unresolved" value={String(s.unresolved)}
          sub="each with a specific reason" />
        <Metric label="Cascade runtime" value={ms(s.runtime_ms_cascade)}
          sub={`${s.throughput_per_sec_cascade.toLocaleString("en-IN")} records/sec`} />
      </div>

      <div className="source-grid">
        {sources.map(([name, total, note]) => (
          <div className="source-card" key={name}>
            <div className="source-card__name t-caption-up">{name}</div>
            <div className="source-card__total t-money-lg">{rupees(total)}</div>
            <div className="muted t-body-sm" style={{ marginTop: 4 }}>
              {note}
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <h2 className="card__title t-title-lg">How it compares (§17.2)</h2>
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Approach</th>
                <th className="col-amount">Records</th>
                <th className="col-amount">Rate</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Naive baseline — exact id + stated fee + exact UTR + net closes</td>
                <td className="col-amount">{doc.baseline.matched}</td>
                <td className="col-amount">{percent(doc.baseline.match_rate)}</td>
              </tr>
              <tr>
                <td>Cascade{llmRan ? " (deterministic only)" : ""}</td>
                <td className="col-amount">{matched}</td>
                <td className="col-amount">{s.match_rate == null ? "—" : percent(s.match_rate)}</td>
              </tr>
              <tr>
                <td>Cascade + LLM hypothesis layer</td>
                <td className="col-amount">
                  {llmRan ? matched + llm.records_resolved : "not run"}
                </td>
                <td className="col-amount">
                  {llmRan
                    ? `${llm.records_resolved} added`
                    : "—"}
                </td>
              </tr>
              <tr>
                <td>Resolvable ceiling — best achievable against the sealed key</td>
                <td className="col-amount">{doc.ceiling.resolvable ?? "—"}</td>
                <td className="col-amount">
                  {doc.ceiling.rate == null ? "—" : percent(doc.ceiling.rate)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        {llmRan && (
          <p className="t-body-sm muted" style={{ marginTop: 12 }}>
            The LLM proposed {llm.hypotheses_proposed} grouping(s); the verifier rejected{" "}
            {llm.hypotheses_rejected_by_verifier}. It resolved {llm.records_resolved} of{" "}
            {s.records_processed} — a small number is evidence <em>for</em> the architecture
            (§15.5).
          </p>
        )}
      </div>

      <div className="card">
        <h2 className="card__title t-title-lg">Tolerance constants</h2>
        <p className="t-body-sm muted">
          Fixed before measurement, never widened after (PROJECT_RULES.md rule 7). Echoed here so
          every allowance is visible.
        </p>
        <div className="tol-list">
          <span className="tol">
            amount delta / derived line = <code>{doc.tolerance_constants.amount_delta_paise_per_derived_line} paise</code>
          </span>
          <span className="tol">
            UTR truncation = <code>{doc.tolerance_constants.utr_truncation_digits} digits</code>
          </span>
          <span className="tol">
            ledger lag = <code>{doc.tolerance_constants.ledger_lag_days} day</code>
          </span>
        </div>
      </div>
    </>
  );
}

function Metric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="metric">
      <div className="metric__label t-caption-up">{label}</div>
      <div className="metric__value t-stat">{value}</div>
      <div className="metric__sub t-body-sm">{sub}</div>
    </div>
  );
}
