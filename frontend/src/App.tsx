import { useEffect, useState } from "react";
import { ALL_FIELDS, FIELD_LABELS, ApiError, api, type Job, type JobConfiguration, type JobStatus, type ProductRecord } from "./api";
import { JobForm } from "./components/job-form";
import { EvidenceDialog } from "./components/evidence-dialog";
import { Button } from "./components/ui/button";

const SELECTION_KEY = "catalog-selected-job";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f-]{27}$/i;

function storedSelection() {
  try { const value = localStorage.getItem(SELECTION_KEY); return value && UUID_PATTERN.test(value) ? value : null; }
  catch { return null; }
}

function Status({ status }: { status: JobStatus }) {
  const colors = {
    queued: "bg-slate-100 text-slate-700", running: "bg-blue-50 text-blue-800",
    completed: "bg-green-50 text-green-800", failed: "bg-red-50 text-red-800",
    cancelled: "bg-amber-50 text-amber-900",
  };
  return <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold capitalize ${colors[status]}`}>{status}</span>;
}

export default function App() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(storedSelection);
  const [job, setJob] = useState<Job | null>(null);
  const [records, setRecords] = useState<ProductRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [filter, setFilter] = useState("all");
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    try { if (selectedId) localStorage.setItem(SELECTION_KEY, selectedId); else localStorage.removeItem(SELECTION_KEY); }
    catch { /* Selection still works in memory when storage is unavailable. */ }
  }, [selectedId]);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setJob(null);
    setRecords([]);
    async function poll() {
      try {
        const list = await api.jobs(controller.signal);
        if (controller.signal.aborted) return;
        setJobs(list.items);
        if (!selectedId && list.items[0]) { setSelectedId(list.items[0].id); return; }
        if (selectedId) {
          const [detail, result] = await Promise.all([
            api.job(selectedId, controller.signal), api.records(selectedId, controller.signal),
          ]);
          if (controller.signal.aborted) return;
          setJob(detail);
          setRecords(result.items);
        }
        setError(null);
      } catch (failure) {
        if (!controller.signal.aborted) {
          if (failure instanceof ApiError && failure.status === 404) {
            setSelectedId(null);
            setNotice("The previous selection is unavailable. Select a saved job or create a new one.");
          } else {
            setError(failure instanceof Error ? failure.message : "Could not reach the local API.");
          }
        }
      } finally {
        if (!controller.signal.aborted) { setLoading(false); timer = setTimeout(() => void poll(), 3000); }
      }
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [selectedId, refresh]);

  async function create(configuration: JobConfiguration, key: string) {
    const created = await api.create(configuration, key);
    setSelectedId(created.id);
    setFilter("all");
    setNotice("Job submitted. Work continues independently of this tab.");
    setRefresh((value) => value + 1);
  }

  async function cancel() {
    if (!job || !window.confirm("Cancel this job? Completed work will be preserved.")) return;
    setCancelling(true);
    try {
      await api.cancel(job.id);
      setNotice("Cancellation recorded. Completed work is preserved.");
      setRefresh((value) => value + 1);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not cancel the job.");
    } finally { setCancelling(false); }
  }

  const visibleJobs = jobs.filter((item) => filter === "all" || item.status === filter);
  const active = job && (job.status === "queued" || job.status === "running");
  return <>
    <a className="skip-link" href="#main">Skip to workspace</a>
    <header className="border-b border-border bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-5 py-5">
        <p className="font-semibold tracking-tight">Competitor Product Intelligence</p>
        <span className="rounded-full border border-border px-3 py-1 text-xs font-medium text-slate-600">Local development</span>
      </div>
    </header>
    <main id="main" className="mx-auto max-w-7xl px-5 py-8">
      <div className="mb-8"><p className="eyebrow">Catalog workspace</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">From product page to source evidence</h1>
        <p className="muted mt-3 max-w-2xl">Run a bounded job, inspect the saved record, and trace each field to its source.</p>
      </div>
      {notice && <p role="status" className="mb-5 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">{notice}</p>}
      {error && <div role="alert" className="error-box mb-5 flex flex-wrap items-center justify-between gap-3">
        <p>{error}</p><Button variant="outline" onClick={() => setRefresh((value) => value + 1)}>Retry connection</Button>
      </div>}
      <div className="grid items-start gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <JobForm onCreate={create} />
        <div className="min-w-0 space-y-6">
          <section className="card" aria-labelledby="jobs-heading">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div><h2 id="jobs-heading">Jobs</h2><p className="muted mt-1">Most recent 100 jobs. Updates every 3 seconds.</p></div>
              <div><label htmlFor="status-filter" className="text-xs">Status filter</label>
                <select id="status-filter" className="control mt-1" value={filter} onChange={(event) => setFilter(event.target.value)}>
                  <option value="all">All statuses</option>
                  {["queued", "running", "completed", "failed", "cancelled"].map((status) => <option key={status} value={status}>{status}</option>)}
                </select>
              </div>
            </div>
            {loading ? <p role="status" className="empty-state">Loading jobs…</p> : visibleJobs.length === 0 ?
              <p className="empty-state">{jobs.length ? "No jobs match this filter." : "No jobs yet. Create your first controlled-page job."}</p> :
              <div className="mt-5 overflow-x-auto"><table>
                <caption className="sr-only">Recent extraction jobs</caption>
                <thead><tr><th>Job</th><th>Status</th><th>Attempts</th><th>Created</th></tr></thead>
                <tbody>{visibleJobs.map((item) => <tr key={item.id} className={selectedId === item.id ? "bg-blue-50/50" : ""}>
                  <td><button type="button" className="min-h-11 text-left font-mono text-sm font-semibold text-blue-700 underline-offset-4 hover:underline" aria-label={`Open job ${item.id}`} aria-pressed={selectedId === item.id} onClick={() => { setSelectedId(item.id); setNotice(null); }}>{item.id.slice(0, 8)}</button></td>
                  <td><Status status={item.status} /></td><td>{item.attempts} / 3</td>
                  <td className="whitespace-nowrap text-slate-600">{new Date(item.created_at).toLocaleString()}</td>
                </tr>)}</tbody>
              </table></div>}
          </section>
          <section className="card" aria-labelledby="results-heading">
            <div className="flex flex-wrap items-center justify-between gap-3"><h2 id="results-heading">Saved results</h2>{job && <Status status={job.status} />}</div>
            {!job ? <p className="empty-state">{selectedId ? "Loading selected job…" : "Select a job to inspect its results."}</p> : <>
              <p data-testid="selected-job-id" className="mt-4 break-all font-mono text-xs text-slate-600">{job.id}</p>
              <p role="status" className="mt-3 text-sm font-medium" data-testid="job-progress">{
                job.status === "completed" ? "Extraction completed. Results saved." :
                job.status === "queued" ? "Queued. Waiting for the worker." :
                job.status === "running" ? "Extracting the approved product page." :
                job.status === "cancelled" ? "Job cancelled." : "Job failed. Inspect the error below."
              }</p>
              <p className="muted mt-1">Page limit: 1 · Attempts: {job.attempts} of 3</p>
              {job.last_error && <p className="error-box mt-4">{job.last_error}</p>}
              {active && <Button variant="destructive" className="mt-4" disabled={cancelling} onClick={() => void cancel()}>{cancelling ? "Cancelling…" : "Cancel job"}</Button>}
              {records.length === 0 ? <p className="empty-state">{active ? "The saved record will appear here when extraction finishes." : "No extracted records were saved for this job."}</p> :
                <div className="mt-5 overflow-x-auto"><table className="results-table">
                  <caption className="sr-only">Original extracted product records</caption>
                  <thead><tr>{ALL_FIELDS.map((field) => <th key={field}>{FIELD_LABELS[field]}</th>)}<th>Validation</th><th>Source evidence</th></tr></thead>
                  <tbody>{records.map((record) => <tr key={record.id}>
                    {ALL_FIELDS.map((field) => <td key={field} className={field === "product_url" ? "max-w-52 break-all" : "min-w-28"}>
                      {record.fields[field] ? <>
                        <span>{record.fields[field]?.value ?? "Unavailable"}</span>
                        {record.fields[field]?.null_reason && <span className="mt-1 block text-xs text-slate-500">{record.fields[field]?.null_reason?.replaceAll("_", " ")}</span>}
                      </> : <span className="text-slate-500">Not selected</span>}
                    </td>)}
                    <td><span className="whitespace-nowrap text-sm">{record.validation_status.replaceAll("_", " ")}</span></td>
                    <td><EvidenceDialog record={record} /></td>
                  </tr>)}</tbody>
                </table></div>}
            </>}
          </section>
        </div>
      </div>
    </main>
  </>;
}
