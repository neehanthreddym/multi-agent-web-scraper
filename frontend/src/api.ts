export const SOURCE_URL = "http://fixture:8080/products/desk-lamp.html";
export interface CatalogPreset { id: string; label: string; source_url: string }
export const FIELD_LABELS = {
  product_name: "Product name", source_product_id: "Source product ID",
  current_price: "Current price", currency: "Currency",
  availability: "Availability", product_url: "Product URL",
} as const;
export type ProductField = keyof typeof FIELD_LABELS;
export const ALL_FIELDS = Object.keys(FIELD_LABELS) as ProductField[];
export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export interface JobConfiguration { seed_url: string; page_limit: 1; selected_fields: ProductField[] }
export interface Job {
  id: string; status: JobStatus; configuration: JobConfiguration;
  attempts: number; created_at: string; started_at: string | null;
  finished_at: string | null; deadline_at: string; last_error: string | null;
}
export interface FieldObservation {
  value: string | null; null_reason: string | null; extraction_method: string;
  evidence: {
    script_index: number; field_path: string; excerpt: string;
    kind?: "json_ld_value" | "json_ld_absence"; missing_key?: string;
  } | null;
}
export interface ProductRecord {
  id: string; job_id: string; snapshot_id: string;
  fields: Partial<Record<ProductField, FieldObservation>>;
  extraction_method: string; validation_status: string;
}
export interface Evidence {
  snapshot_id: string; source_url: string; observed_at: string; sha256: string;
  fields: Partial<Record<ProductField, FieldObservation>>;
}

export class ApiError extends Error {
  constructor(readonly status: number, message: string) { super(message); }
}

async function jsonRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, options);
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : null;
    throw new ApiError(response.status, typeof detail === "string" ? detail : `Request failed (${response.status}). Check the local services and retry.`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  presets: (signal?: AbortSignal) => jsonRequest<{ items: CatalogPreset[] }>("/presets", { signal }),
  jobs: (signal?: AbortSignal) => jsonRequest<{ items: Job[] }>("/jobs?limit=100", { signal }),
  job: (id: string, signal?: AbortSignal) => jsonRequest<Job>(`/jobs/${encodeURIComponent(id)}`, { signal }),
  records: (id: string, signal?: AbortSignal) => jsonRequest<{ items: ProductRecord[] }>(`/jobs/${encodeURIComponent(id)}/records`, { signal }),
  create: (body: JobConfiguration, key: string) => jsonRequest<Job>("/jobs", {
    method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key },
    body: JSON.stringify(body),
  }),
  cancel: (id: string) => jsonRequest<Job>(`/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
  evidence: (id: string, signal?: AbortSignal) => jsonRequest<Evidence>(`/records/${encodeURIComponent(id)}/evidence`, { signal }),
  snapshot: async (id: string, signal?: AbortSignal) => {
    const response = await fetch(`/api/snapshots/${encodeURIComponent(id)}`, { signal });
    if (!response.ok) throw new Error(`Could not load the saved page (${response.status}).`);
    return response.text();
  },
};
