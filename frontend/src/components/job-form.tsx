import { useEffect, useRef, useState, type FormEvent } from "react";
import { ALL_FIELDS, FIELD_LABELS, api, type CatalogPreset, type JobConfiguration, type ProductField } from "@/api";
import { Button } from "./ui/button";

const PENDING_KEY = "catalog-pending-submission";

function submissionKey(configuration: JobConfiguration) {
  const body = JSON.stringify(configuration);
  try {
    const saved: unknown = JSON.parse(sessionStorage.getItem(PENDING_KEY) || "null");
    if (saved && typeof saved === "object" && "body" in saved && "key" in saved
      && saved.body === body && typeof saved.key === "string" && saved.key.length <= 128) {
      return saved.key;
    }
  } catch { /* Storage may be unavailable; the current request still works. */ }
  // getRandomValues also works for the container-only browser-test hostname,
  // where HTTP is not a secure context and randomUUID may be unavailable.
  const key = Array.from(crypto.getRandomValues(new Uint8Array(16)),
    (byte) => byte.toString(16).padStart(2, "0")).join("");
  try { sessionStorage.setItem(PENDING_KEY, JSON.stringify({ body, key })); } catch { /* Optional storage. */ }
  return key;
}

export function JobForm({ onCreate }: {
  onCreate: (configuration: JobConfiguration, key: string) => Promise<void>;
}) {
  const [fields, setFields] = useState<ProductField[]>([...ALL_FIELDS]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [presets, setPresets] = useState<CatalogPreset[]>([]);
  const [presetId, setPresetId] = useState("desk-lamp");
  const [presetError, setPresetError] = useState<string | null>(null);
  const [presetRetry, setPresetRetry] = useState(0);
  const [loadingPresets, setLoadingPresets] = useState(true);
  const pendingRequest = useRef<{ body: string; key: string } | null>(null);
  const preset = presets.find((item) => item.id === presetId);

  useEffect(() => {
    const controller = new AbortController();
    setLoadingPresets(true);
    setPresetError(null);
    async function load() {
      try {
        const result = await api.presets(controller.signal);
        if (controller.signal.aborted) return;
        if (!result.items.length) throw new Error("No catalog presets are available.");
        setPresets(result.items);
        setPresetId((current) => result.items.some((item) => item.id === current) ? current : result.items[0].id);
      } catch (failure) {
        if (!controller.signal.aborted) setPresetError(failure instanceof Error ? failure.message : "Could not load catalog presets.");
      } finally {
        if (!controller.signal.aborted) setLoadingPresets(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [presetRetry]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || fields.length === 0 || !preset || loadingPresets || presetError) return;
    const configuration: JobConfiguration = {
      seed_url: preset.source_url, page_limit: 1,
      selected_fields: ALL_FIELDS.filter((field) => fields.includes(field)),
    };
    setPending(true);
    setError(null);
    try {
      const body = JSON.stringify(configuration);
      const key = pendingRequest.current?.body === body ? pendingRequest.current.key : submissionKey(configuration);
      pendingRequest.current = { body, key };
      await onCreate(configuration, key);
      pendingRequest.current = null;
      try { sessionStorage.removeItem(PENDING_KEY); } catch { /* Optional storage. */ }
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not submit the job. Try again.");
    } finally {
      setPending(false);
    }
  }

  return <section className="card self-start" aria-labelledby="create-heading">
    <p className="eyebrow">Controlled source</p>
    <h2 id="create-heading">Create a job</h2>
    <p className="muted mt-2">Start with one owned product page and inspect exactly what was extracted.</p>
    <form onSubmit={submit} className="mt-6 space-y-5">
      <div>
        <label htmlFor="source-preset">Catalog preset</label>
        <select id="source-preset" disabled={pending || loadingPresets || Boolean(presetError)} value={presetId} onChange={(event) => setPresetId(event.target.value)} className="control mt-2">
          {!presets.length && <option value="desk-lamp">{loadingPresets ? "Loading catalog presets…" : "Catalog presets unavailable"}</option>}
          {presets.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
        {preset && <p className="muted mt-2 break-all text-xs">{preset.source_url}</p>}
        {presetError && <div role="alert" className="error-box mt-2">
          <p>{presetError}</p>
          <Button type="button" variant="outline" className="mt-2" onClick={() => setPresetRetry((value) => value + 1)}>Retry catalog presets</Button>
        </div>}
      </div>
      <fieldset disabled={pending}>
        <legend className="mb-3 text-sm font-semibold">Product fields</legend>
        <div className="space-y-1">
          {ALL_FIELDS.map((field) => <label key={field} className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md px-2 hover:bg-slate-50">
            <input type="checkbox" className="size-4 accent-blue-700" checked={fields.includes(field)} onChange={(event) => {
              setFields((current) => event.target.checked ? [...current, field] : current.filter((item) => item !== field));
            }} />
            <span>{FIELD_LABELS[field]}</span>
          </label>)}
        </div>
      </fieldset>
      <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
        <p><strong className="text-slate-900">Page limit: 1</strong> · up to 3 attempts</p>
        <p className="mt-1">Deterministic extraction. No model inference.</p>
      </div>
      {error && <p role="alert" className="error-box">{error}</p>}
      <Button type="submit" className="w-full" disabled={pending || fields.length === 0 || !preset || loadingPresets || Boolean(presetError)}>
        {pending ? "Submitting…" : "Create job"}
      </Button>
      {fields.length === 0 && <p className="muted">Select at least one field.</p>}
    </form>
  </section>;
}
