import { useEffect, useState } from "react";
import { api, FIELD_LABELS, type Evidence, type ProductField, type ProductRecord } from "@/api";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "./ui/dialog";

export function EvidenceDialog({ record }: { record: ProductRecord }) {
  const [open, setOpen] = useState(false);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [snapshot, setSnapshot] = useState("");
  const [field, setField] = useState<ProductField>((Object.keys(record.fields)[0] || "product_name") as ProductField);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setEvidence(null);
    setError(null);
    async function load() {
      try {
        const data = await api.evidence(record.id, controller.signal);
        const text = await api.snapshot(data.snapshot_id, controller.signal);
        if (!controller.signal.aborted) { setEvidence(data); setSnapshot(text); }
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Could not load evidence.");
      }
    }
    void load();
    return () => controller.abort();
  }, [open, record.id, retry]);

  const observation = evidence?.fields[field];
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button variant="outline">Inspect evidence</Button></DialogTrigger>
    <DialogContent>
      <DialogTitle className="text-2xl font-semibold">Source evidence</DialogTitle>
      <DialogDescription className="muted mt-2">Original extraction and the saved page that supports it. Page content is displayed as text.</DialogDescription>
      {error ? <div role="alert" className="error-box mt-5">
        <p>{error}</p><Button variant="outline" className="mt-3" onClick={() => setRetry((value) => value + 1)}>Retry evidence</Button>
      </div> : !evidence ? <p role="status" className="muted mt-5">Loading saved evidence…</p> : <div className="mt-6 space-y-5">
        <div><label htmlFor="evidence-field">Field</label>
          <select id="evidence-field" className="control mt-2" value={field} onChange={(event) => setField(event.target.value as ProductField)}>
            {(Object.keys(evidence.fields) as ProductField[]).map((key) => <option key={key} value={key}>{FIELD_LABELS[key]}</option>)}
          </select>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="eyebrow">Original value</p>
          <p data-testid="evidence-value" className="mt-2 break-words text-lg font-semibold">{observation?.value ?? "Unavailable"}</p>
          {observation?.null_reason && <p className="muted mt-1">Reason: {observation.null_reason.replaceAll("_", " ")}</p>}
          <p className="muted mt-3">Method: {observation?.extraction_method ?? record.extraction_method}</p>
          {observation?.evidence ? <>
            <p className="muted mt-2">JSON-LD script index: {observation.evidence.script_index}</p>
            <p className="mt-1 break-all font-mono text-sm">{observation.evidence.field_path}</p>
            <pre className="code-box mt-3">{observation.evidence.excerpt}</pre>
          </> : <p className="muted mt-2">No supporting field evidence was found.</p>}
        </div>
        <dl className="space-y-3 text-sm">
          <div><dt className="font-semibold">Source URL</dt><dd className="mt-1 break-all text-slate-600">{evidence.source_url}</dd></div>
          <div><dt className="font-semibold">Observed</dt><dd className="mt-1 text-slate-600">{new Date(evidence.observed_at).toLocaleString()}</dd></div>
          <div><dt className="font-semibold">Snapshot SHA-256</dt><dd className="mt-1 break-all font-mono text-xs text-slate-600">{evidence.sha256}</dd></div>
        </dl>
        <details className="rounded-lg border border-border p-4">
          <summary className="cursor-pointer py-2 text-sm font-semibold">Saved page (text)</summary>
          <pre data-testid="snapshot-text" className="code-box mt-3 max-h-80 overflow-auto">{snapshot}</pre>
        </details>
      </div>}
    </DialogContent>
  </Dialog>;
}
