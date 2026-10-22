# Architecture

## Accepted decision and progress

The user accepted the four-document baseline on 2026-10-21 and authorized local implementation using the documented Python stack. Local implementation may proceed in the next task; implementation has not started. The next task, **Build the first local end-to-end flow**, is **Ready**. Documentation is accepted; the issue and board updates will be applied manually by the user.

Remote hosting, inference hardware/model, costs, retention, and Vercel connectivity remain open. They do not block the first deterministic local working flow, which needs no model inference. Verify Vercel connectivity before committing to the remote integration design. Resolve hosting, budget, retention, and public-demo controls before public release. No providers, hardware, model, or costs have been selected, and no services have been provisioned.

## Components and responsibilities

Accepted architecture baseline: shared FastAPI/Celery backend codebase and separate React frontend.  Uvicorn serves the local API. Pydantic defines contracts and emits JSON Schema; SQLAlchemy persists PostgreSQL data, with Alembic migrations. RabbitMQ carries durable Celery work; PostgreSQL is the authoritative job state.

HTTPX fetches static pages; Beautiful Soup and lxml parse them. Playwright for Python with Chromium handles pages requiring rendering. LangGraph coordinates three bounded roles: Discovery proposes product/pagination links; Extraction maps content to selected fields; Validation investigates conflicts and recommends acceptance, retry, or review. Code validates recommendations and controls tools.

## Processing and durability

UI → API → PostgreSQL job/outbox → RabbitMQ → Celery worker → snapshots/extractions → PostgreSQL → polled UI.

Commit job creation and an outbox entry together; a worker-side dispatcher publishes pending entries and tolerates duplicate delivery. Persist page checkpoints and attempts. Use unique job/canonical-URL constraints and idempotent result writes; preserve meaningful URL query parameters. Recover expired worker leases after crashes.

Discover static links and pagination within scope. Extract JSON-LD first, deterministic rules second, model assistance only when necessary. Apply deterministic validation before agent investigation.  Store prices as decimal amounts, currencies as explicit codes, and availability as a normalized value with raw evidence.

Proposed defaults: 20 unique pages including seeds/pagination, two retries per page, one concurrent request per domain, one request/second, 30-second request timeout, 2 MB response limit, ten-minute job deadline, 20 model calls, and 40,000 total model tokens. Bound graph steps to 30 per page, within the job budget. Reserve budgets atomically; retries consume request/model budgets but not additional unique-page slots. A budget stop preserves partial results with a reason. Cancellation checks precede work and writes; in-flight work has timeouts and cannot overwrite terminal state.

## Essential API

| Route | Responsibility |
|---|---|
| POST /jobs | Validate configuration; idempotently enqueue; return 202 and job ID |
| GET /jobs; GET /jobs/{id} | List jobs; return stage, counters, terminal reason |
| POST /jobs/{id}/cancel | Request idempotent cooperative cancellation |
| GET /jobs/{id}/records | Paginated, filtered original/effective records |
| GET /records/{id}/evidence | Safe excerpts and snapshot references |
| POST /records/{id}/reviews | Append correction, approval, or rejection; check revision |
| GET /jobs/{id}/export | CSV/JSON; automated/reviewed view; provenance |
| POST /evaluations; GET /evaluations/{id} | Enqueue run; return metrics and failures |
| GET /health | Minimal service health without secrets |

## Data and evidence

Job owns configuration, budgets, outbox entries, PageTasks, and Attempts. PageTasks reference immutable Snapshots with URL, UTC observation time, content hash, and storage key. ProductRecord belongs to a job/page; immutable ExtractionVersions contain field values, null reasons, methods, and validation status. FieldEvidence links each candidate to a snapshot excerpt and locator. ReviewEvents append decisions and overrides; derive the effective view without mutating extraction. Separate validation status from human review status.

DatasetVersion owns labeled pages, expected product identities, field values, absence reasons, and evidence references. EvaluationRun links dataset, method, model/prompt versions, predictions, metrics, and failures. Snapshot bytes live in persistent storage; PostgreSQL stores metadata.

## Security and demo boundary

Permit approved HTTP(S) hosts/ports only. Validate seeds, every redirect, DNS resolution, and connection destination; reject loopback, private, link-local, reserved, metadata, and IPv6 equivalents. Enforce network egress controls against DNS rebinding. Apply the same policy to Chromium subresources, navigation, and downloads. Local fixtures use a narrow development exception unavailable in production.

Web content cannot grant tool permissions, change instructions, or access credentials. Models receive bounded content and typed tools. Escape evidence; sandbox any preview with scripts and network disabled. Prevent CSV formula execution. Keep broker, database, snapshots, inference credentials, and administrative operations private; restrict CORS, payload sizes, and logs.

Public demo: server-owned source presets, opaque job access tokens, per-client quotas, global concurrency/spend caps, isolated results, and expiry cleanup.

## Evaluation and testing

Start with ten labeled development snapshots. Compare deterministic, single-extraction-agent, and full workflow methods on identical bytes with fixed inputs and recorded versions. Evaluate discovery link precision/recall separately, then complete runs including missed products. Add held-out layouts and controlled layout changes for final portfolio assessment.

For expected non-null fields, correct predictions are TP; wrong non-null values add both FP and FN; null predictions add FN. Extra product predictions add FP and missed products add FN across applicable fields. Report precision, recall, F1, denominators, complete-record accuracy, evidence coverage/correctness, unsupported-value rate, review rate, failures, retries, runtime, and available model usage. Complete-record accuracy requires every selected field correct; missed expected products fail. Evidence coverage is the fraction of non-null predictions with evidence; correctness measures whether cited evidence supports them. Unsupported-value rate is the fraction of non-null predictions lacking support. Score absent-field null/reason correctness and spurious values separately. Preserve raw automated predictions; label corrected scores separately. Offline verified-label accuracy and live operational checks are distinct.

Use pytest for parsing, metric edge cases, URL security, budgets, and state transitions; integration tests for queue redelivery, recovery, migrations, and cancellation. Use frontend component tests for forms/review states and Playwright UI tests for the complete fixture journey. Validate evidence references and exports.

## Deployment and delivery

Local Podman Compose runs UI, API, workers, RabbitMQ, PostgreSQL, fixture service, persistent volumes, and reachable Ollama. Select the local model through evaluation.

Remote target: Vercel frontend and lightweight FastAPI API; independently hosted workers, broker, database, snapshot storage, and reachable inference. Jobs never depend on a browser or laptop. Verify offline-laptop operation, persistence, recovery, and the public journey before claiming deployment success. Provision nothing during documentation.

| Open decision | Working assumption / resolution trigger |
|---|---|
| Hosting and hardware | Select worker, RabbitMQ, PostgreSQL, snapshot providers and CPU/GPU capacity after baseline resource measurements. |
| Inference | Evaluate Ollama models locally; select hosted Ollama or compatible reachable inference before deployment. |
| Costs and retention | Set costs, monthly cap, quotas, and retention before public release. |
| Vercel API integration | Verify runtime limits, broker/database connectivity, TLS, and connection management before committing to the remote integration design. |
| Public-demo controls | Finalize and verify quotas, isolation, access controls, and cleanup before public release. |
| Public catalogs | Begin with owned fixtures; approve external sources and request policies after the basic workflow. |

Implementation sequence: (1) one deterministic controlled-page UI → API → worker → database → evidence flow; (2) ten labeled fixtures and baseline evaluation; (3) bounded agents and needed rendering; (4) review, exports, evaluation UI; (5) deployment and public verification.
