import { useEffect, useMemo, useState } from "react";
import { Spinner } from "./components/Bits";
import { RecordDrawer } from "./components/RecordDrawer";
import { loadRun } from "./lib/data";
import { RUNS, type ResultsDocument, type RunId } from "./lib/types";
import { ExceptionList } from "./screens/ExceptionList";
import { MatchExplorer } from "./screens/MatchExplorer";
import { ReconciliationBridge } from "./screens/ReconciliationBridge";
import { RunOverview } from "./screens/RunOverview";

type Tab = "overview" | "bridge" | "explorer" | "exceptions";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Run overview" },
  { id: "bridge", label: "Reconciliation bridge" },
  { id: "explorer", label: "Match explorer" },
  { id: "exceptions", label: "Exception list" },
];

export interface ExplorerFilter {
  /** label shown to the user, e.g. "Processing fees" or "fee_reversal" */
  label: string;
  /** if set, restrict to these record_keys (from a bridge band) */
  recordKeys?: Set<string>;
  /** if set, restrict to this resolving pass */
  pass?: string;
}

export default function App() {
  const [runId, setRunId] = useState<RunId>(RUNS[0].id);
  const [tab, setTab] = useState<Tab>("overview");
  const [doc, setDoc] = useState<ResultsDocument | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [filter, setFilter] = useState<ExplorerFilter | null>(null);

  useEffect(() => {
    let live = true;
    setDoc(null);
    setErr(null);
    loadRun(runId)
      .then((d) => live && setDoc(d))
      .catch((e) => live && setErr(String(e.message ?? e)));
    return () => {
      live = false;
    };
  }, [runId]);

  const selected = useMemo(() => {
    if (!doc || !selectedKey) return null;
    const record = doc.records.find((r) => r.record_key === selectedKey) ?? null;
    const exception = doc.exceptions.find((e) => e.record_key === selectedKey);
    return record ? { record, exception } : null;
  }, [doc, selectedKey]);

  function openExplorerWith(f: ExplorerFilter) {
    setFilter(f);
    setTab("explorer");
  }

  return (
    <>
      <nav className="topnav">
        <span className="topnav__brand">Reconciliation</span>
        <span className="topnav__spacer" />
        <label className="t-caption-up muted" htmlFor="run" style={{ marginRight: 8 }}>
          Dataset
        </label>
        <select
          id="run"
          className="run-select"
          value={runId}
          onChange={(e) => {
            setRunId(e.target.value as RunId);
            setSelectedKey(null);
            setFilter(null);
          }}
        >
          {RUNS.map((r) => (
            <option key={r.id} value={r.id}>
              {r.label}
            </option>
          ))}
        </select>
      </nav>

      <div className="shell">
        <div className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`tab ${tab === t.id ? "tab--active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {err && (
          <div className="callout callout--warn">
            <strong>Could not load this run.</strong>
            <div className="t-body-sm mono" style={{ marginTop: 6 }}>
              {err}
            </div>
          </div>
        )}

        {!doc && !err && <Spinner />}

        {doc && tab === "overview" && <RunOverview doc={doc} />}
        {doc && tab === "bridge" && (
          <ReconciliationBridge doc={doc} onBandClick={openExplorerWith} />
        )}
        {doc && tab === "explorer" && (
          <MatchExplorer
            doc={doc}
            filter={filter}
            onClearFilter={() => setFilter(null)}
            onOpenRecord={setSelectedKey}
          />
        )}
        {doc && tab === "exceptions" && (
          <ExceptionList doc={doc} onOpenRecord={setSelectedKey} />
        )}
      </div>

      {selected && (
        <RecordDrawer
          record={selected.record}
          exception={selected.exception}
          onClose={() => setSelectedKey(null)}
        />
      )}
    </>
  );
}
