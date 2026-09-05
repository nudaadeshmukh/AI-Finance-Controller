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

const TAB_IDS = TABS.map((t) => t.id);
const RUN_IDS = RUNS.map((r) => r.id) as string[];

/** URL hash <-> view state, so a run + screen + open record is a shareable
    link and the browser back button works:
    `#/<run>/<tab>` or `#/<run>/<tab>/<record_key>`. */
function readHash(): { runId: RunId; tab: Tab; recordKey: string | null } {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const parts = raw.split("/").filter(Boolean);
  const runId = (RUN_IDS.includes(parts[0]) ? parts.shift()! : RUNS[0].id) as RunId;
  const tab = (TAB_IDS as string[]).includes(parts[0]) ? (parts.shift() as Tab) : "overview";
  const recordKey = parts.length ? decodeURIComponent(parts.join("/")) : null;
  return { runId, tab, recordKey };
}

export default function App() {
  const initial = readHash();
  const [runId, setRunId] = useState<RunId>(initial.runId);
  const [tab, setTab] = useState<Tab>(initial.tab);
  const [doc, setDoc] = useState<ResultsDocument | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(initial.recordKey);
  const [filter, setFilter] = useState<ExplorerFilter | null>(null);

  // hash -> state (back/forward, external links)
  useEffect(() => {
    const onHash = () => {
      const h = readHash();
      setRunId(h.runId);
      setTab(h.tab);
      setSelectedKey(h.recordKey);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // state -> hash
  useEffect(() => {
    const want = `#/${runId}/${tab}${selectedKey ? `/${encodeURIComponent(selectedKey)}` : ""}`;
    if (window.location.hash !== want) {
      window.history.replaceState(null, "", want);
    }
  }, [runId, tab, selectedKey]);

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
