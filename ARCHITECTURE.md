# Architecture

## Accepted decision and progress

The user accepted the baseline on 2026-10-21. Local implementation began on 2026-10-23. User-run output verified backend builds, migration `0001_local_jobs`, 21 backend tests, six healthy backend services, and the live API → outbox → RabbitMQ → worker → PostgreSQL smoke check with source evidence. Frontend image creation, TypeScript checking, the Vite production build, 3 component tests, and 1 Playwright browser test also passed. Screenshots and user observations confirmed UI submission, completed results, evidence inspection, and jobs retained after browser reload. A job queued while the worker was stopped completed with exactly one saved result and accessible evidence after worker restart. A cancelled queued job stayed cancelled with no result after restart. The user confirmed that all seven services became healthy after a full application stop/start and that an existing completed job's result and evidence remained accessible. The user subsequently reported the active-extraction crash-recovery follow-up complete; its output was not independently reinspected in this diagram review. The user saved the generated [frontend lockfile](frontend/package-lock.json), supplied its contents for review, and successfully rebuilt the web image using it through `npm ci`. Tests and production compilation initially passed before this rebuild. The user subsequently confirmed the post-lockfile tests/builds and remaining verification follow-ups complete. Control/reply and event queues use connection-exclusive lifetimes for RabbitMQ 4.3 compatibility; the job queue remains durable. Frontend container stages pin npm 11.6.0 after an npm 10 dependency-resolver failure. Documentation issue #1 was recorded as closed and Done. The user reports implementation issue #2 complete; its closed state and Done board status were subsequently observed on 2026-10-26.

Remote hosting, inference hardware/model, costs, retention, and Vercel connectivity remain open. They do not block the first deterministic local working flow, which needs no model inference. Verify Vercel connectivity before committing to the remote integration design. Resolve hosting, budget, retention, and public-demo controls before public release. No providers, hardware, model, or costs have been selected, and no services have been provisioned.

## Current local architecture

![Current local architecture: React/Vite and FastAPI create jobs in PostgreSQL; the outbox dispatcher publishes to RabbitMQ; the Celery worker fetches the owned fixture and saves records, snapshots, and field evidence.](assets/architecture/local-architecture.svg)

[Editable draw.io source](assets/architecture/local-architecture.drawio) · [Vector SVG](assets/architecture/local-architecture.svg) · [High-resolution PNG (5400 × 3540)](assets/architecture/local-architecture.png)

This diagram represents the implemented local fixture flow. PostgreSQL is authoritative for job state and saved evidence; RabbitMQ carries durable tasks. The UI polls FastAPI through Vite's proxy. API, UI, and fixture host ports bind to localhost; database and broker ports stay inside Compose. The optional browser-test container is omitted from the runtime view. Agents, rendering, evaluation UI/background jobs, review, exports, and remote hosting remain later increments. A separate offline evaluation CLI is implemented in source and described below; it is outside this runtime-service diagram and its user-run baseline is recorded below.

The source and exports were authored together from the same layout, with editable draw.io cells and connectors. The SVG also embeds the draw.io model. Edit the source in diagrams.net and re-export SVG/PNG together to keep all three versions aligned. Diagram verification used source/configuration comparison, XML parsing, PNG metadata, and visual inspection; no application commands or tests were run.

## Components and responsibilities

The local `web` service uses React, Vite, TypeScript, Tailwind, and local shadcn/ui-style buttons/dialogs backed by Radix. Vite proxies `/api` to FastAPI; only localhost port 5173 is published for the UI. An optional `ui-tests` Compose profile uses Chromium/Playwright to test the live workflow. Component checks cover selected fields, retry idempotency, and pending submissions. Browser checks cover create, reload, saved results, escaped snapshot text, and dialog focus. Prior user-run results recorded above report these checks passing. The user subsequently confirmed post-lockfile tests/builds and the mobile/accessibility follow-up complete; no new runtime checks were performed for this diagram.

Accepted architecture baseline: shared FastAPI/Celery backend codebase and separate React frontend.  Uvicorn serves the local API. Pydantic defines contracts and emits JSON Schema; SQLAlchemy persists PostgreSQL data, with Alembic migrations. RabbitMQ carries durable Celery work; PostgreSQL is the authoritative job state.

HTTPX fetches one selected page from ten exact server-owned fixture URLs; Beautiful Soup and lxml parse its JSON-LD. Planned later increments add Playwright for Python with Chromium for rendering and LangGraph for three bounded roles: Discovery proposes product/pagination links; Extraction maps content to selected fields; Validation investigates conflicts and recommends acceptance, retry, or review. Code will validate recommendations and control tools. These rendering and agent capabilities are not implemented in the current flow.

## Processing and durability

UI → API → PostgreSQL job/outbox → RabbitMQ → Celery worker → snapshots/extractions → PostgreSQL → polled UI.

Commit job creation and an outbox entry together; a worker-side dispatcher publishes pending entries and tolerates duplicate delivery. Persist page checkpoints and attempts. Use unique job/canonical-URL constraints and idempotent result writes; preserve meaningful URL query parameters. Recover expired worker leases after crashes.

Discover static links and pagination within scope. Extract JSON-LD first, deterministic rules second, model assistance only when necessary. Apply deterministic validation before agent investigation.  Store prices as decimal amounts, currencies as explicit codes, and availability as a normalized value with raw evidence.

Proposed defaults: 20 unique pages including seeds/pagination, two retries per page, one concurrent request per domain, one request/second, 30-second request timeout, 2 MB response limit, ten-minute job deadline, 20 model calls, and 40,000 total model tokens. Bound graph steps to 30 per page, within the job budget. Reserve budgets atomically; retries consume request/model budgets but not additional unique-page slots. A budget stop preserves partial results with a reason. Cancellation checks precede work and writes; in-flight work has timeouts and cannot overwrite terminal state.

## Target API

This table describes the accepted target. The current API implements `GET /presets` plus job creation/list/detail/cancellation, original records, evidence, `/snapshots/{id}` as plain text, `/health`, and `/ready`. Job listing supports limit/offset; records do not yet support pagination, filters, or an effective reviewed view. Review, export, and evaluation routes remain planned.

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

Initial local implementation: `jobs`, `job_outbox`, `snapshots`, and `product_records`. A job represents one page; attempt counts, leases, and attempt history are persisted on the job. For this bounded fixture flow, snapshot HTML and hashes are stored in PostgreSQL alongside metadata, using its existing durable volume. This avoids a separate storage service initially. External snapshot storage remains a later deployment decision. Records preserve original extracted fields; review events and extraction versions follow when human review is implemented. `/ready` checks the migrated database; a separate dispatcher scans committed outbox entries, while the Celery worker performs extraction. The recorded user-run smoke check verified the successful backend path and evidence integrity. Separate user checks covered queued-job recovery, queued-job cancellation, and retained result/evidence after a full stop/start. The user subsequently reported the active-extraction crash-recovery follow-up complete; its output was not independently reinspected in this diagram review.

Job owns configuration, budgets, outbox entries, PageTasks, and Attempts. PageTasks reference immutable Snapshots with URL, UTC observation time, content hash, and storage key. ProductRecord belongs to a job/page; immutable ExtractionVersions contain field values, null reasons, methods, and validation status. FieldEvidence links each candidate to a snapshot excerpt and locator. ReviewEvents append decisions and overrides; derive the effective view without mutating extraction. Separate validation status from human review status.

DatasetVersion owns labeled pages, expected product identities, field values, absence reasons, and evidence references. EvaluationRun links dataset, method, model/prompt versions, predictions, metrics, and failures. Snapshot bytes live in persistent storage; PostgreSQL stores metadata.

## Security and demo boundary

Permit approved HTTP(S) hosts/ports only. Validate seeds, every redirect, DNS resolution, and connection destination; reject loopback, private, link-local, reserved, metadata, and IPv6 equivalents. Enforce network egress controls against DNS rebinding. Apply the same policy to Chromium subresources, navigation, and downloads. Local fixtures use a narrow development exception unavailable in production.

Web content cannot grant tool permissions, change instructions, or access credentials. Models receive bounded content and typed tools. Escape evidence; sandbox any preview with scripts and network disabled. Prevent CSV formula execution. Keep broker, database, snapshots, inference credentials, and administrative operations private; restrict CORS, payload sizes, and logs.

Public demo: server-owned source presets, opaque job access tokens, per-client quotas, global concurrency/spend caps, isolated results, and expiry cleanup.

## Evaluation and testing

The [development fixture dataset](fixtures/README.md), `catalog-development` version `1.0.0`, now contains ten saved HTML pages (the unchanged desk lamp plus nine new cases), a manifest with SHA-256 page/label fingerprints, and a separate answer key with sixty field labels, null reasons, rationales, and source evidence references. Four pages have expected `valid` outcomes and six have expected `needs_review` outcomes under the one-product/one-offer policy. These are authored expectations, not measured results. The labels live outside the served catalog and are excluded from the fixture image. A standard-library verifier is provided for user-run integrity checks. No inference, network calls, backend permissions, or application behavior were changed for this dataset work.

Issue #3 file review on 2026-10-25 checked saved-page counts, required scenarios, manifest/label agreement, hashes, evidence locations/raw values, and preservation of the original desk-lamp bytes through direct file inspection. The user then supplied successful output from the documented read-only Compose verification command: all three PASS lines confirmed ten pages, sixty field labels/evidence references, integrity/locator checks, and the preserved desk-lamp baseline. No commands were executed by the agent. That Issue #3 check covered dataset integrity; the Issue #4 runtime checks below are separate. Issue #5 adds offline scoring, whose measured baseline is recorded below; the earlier dataset integrity check did not measure accuracy.

Compare deterministic, single-extraction-agent, and full workflow methods on identical bytes with fixed inputs and recorded versions. Evaluate discovery link precision/recall separately, then complete runs including missed products. Add held-out layouts and controlled layout changes for final portfolio assessment.

For expected non-null fields, correct predictions are TP; wrong non-null values add both FP and FN; null predictions add FN. Extra product predictions add FP and missed products add FN across applicable fields. Report precision, recall, F1, denominators, complete-record accuracy, evidence coverage/correctness, unsupported-value rate, review rate, failures, retries, runtime, and available model usage. Complete-record accuracy requires every selected field correct; missed expected products fail. Evidence coverage is the fraction of non-null predictions with evidence; correctness measures whether cited evidence supports them. Unsupported-value rate is the fraction of non-null predictions lacking support. Score absent-field null/reason correctness and spurious values separately. Preserve raw automated predictions; label corrected scores separately. Offline verified-label accuracy and live operational checks are distinct.

Use pytest for parsing, metric edge cases, URL security, budgets, and state transitions; integration tests for queue redelivery, recovery, migrations, and cancellation. Use frontend component tests for forms/review states and Playwright UI tests for the complete fixture journey. Validate evidence references and exports.

## Offline deterministic evaluation (Issue #5)

Implementation on 2026-10-26 adds `backend/app/evaluate.py` (offline loader, evidence checks, versioned report and CLI), `evaluation_metrics.py` (pure scoring), and `backend/tests/test_evaluation.py`. No extractor behavior, dependencies, migration, API route, service, frontend or model integration changed. The runner calls `extract_fields` with saved HTML, selected fields and the approved source URL; labels are used only by the loader/evaluator, never passed to extraction. All ten inputs are validated before the first extraction.

Inputs are bounded to 2 MiB per manifest/label/page file. The loader verifies metadata, the ten exact preset identities/URLs, label and page SHA-256 hashes, path containment, original desk-lamp hash, expected single-product records, field/null-reason labels and evidence against the saved JSON-LD. Invalid inputs stop the run without publishing scores. Page-level extraction exceptions are retained as failures and scored as missed expected products; extraction continues for the other saved pages. Offline extraction makes one attempt per page with zero retries. It uses no HTTP fetch entry point, database, queue or model. The documented user-run command also enforces `--network none` at the container boundary; network/HTTP entry points are blocked in the authored offline tests.

Matching uses page identity and record slot, which is appropriate for this one-product-per-page dataset. It does not use a predicted name/SKU/URL or choose a best-scoring match. Missing slots are missed products; additional predicted slots are extras. The pure scorer tests these cases even though the current extractor returns one product or fails explicitly. A future multi-product dataset needs a separate preregistered matching policy.

| Measure | Implemented rule |
|---|---|
| Non-null field precision/recall/F1 | Correct non-null value: TP. Wrong non-null value: FP and FN. Missing/null prediction for an expected non-null value: FN. Spurious non-null value for a null label, or on an extra product: FP. Missed products contribute FN for every expected non-null field. Per-field and micro counts/denominators are saved. |
| Value comparison | Finite decimal price strings compare numerically, so 49.9 and 49.90 are equal. Other normalized strings compare exactly; no currency guessing or name/URL-based matching. |
| Complete-record accuracy | Every selected field value and null reason must match. Denominator: all expected products, including missed products; absent products never count as correct, even if all labels are null. Extra products are reported separately and reduce non-null field precision. |
| Exact-page accuracy | Requires the correct product count and all expected records complete; extra products and extraction failures fail the page. |
| Nulls and absence | Expected nulls have separate value and reason accuracy, spurious-value and missing-prediction counts, including a breakdown by expected null reason. Missing fields/products are not treated as correctly predicted nulls. The missing_value/missing_offer groups cover authored absence labels. |
| Evidence coverage | Fraction of all non-null predictions that include evidence, including predictions on extra products. |
| Evidence correctness / unsupported values | Support requires correct normalized value, agreement with an authored script index/pointer/kind/raw value, and an excerpt resolved from the actual saved JSON-LD. Absence checks also require the expected missing key to be absent. Correctness denominator: cited non-null predictions. Unsupported-value denominator: all non-null predictions, including missing citations and extras. Per-page checks also cover null-field citations. |
| Empty denominators | Ratios are undefined (`null` in JSON, `n/a` in the summary), never automatically perfect. F1 uses 2TP/(2TP+FP+FN). |

Reports preserve raw automated observations separately from authored expectations. They identify schema, method and scorer versions; manifest/labels/page hashes; extractor/constants/scorer/runner source hashes; and Python, Beautiful Soup, lxml and HTTPX versions. Findings, failures, all score counts/denominators, review rate, attempts, zero retries/network/model calls and measured elapsed runtime are included. This runtime measures local loading/validation/extraction/scoring, not crawling or model latency. Source version numbers plus content hashes identify the implementation without requiring Git or embedding an absolute developer path. Timing is stored under `execution` and excluded from `result_sha256`; all other report content forms the stable fingerprint. `--check-repeat` runs the evaluator twice and requires identical fingerprints. The summary describes the first run runtime.

Evidence correctness here means agreement with these authored labels and saved bytes. It is not an independent semantic evidence audit, held-out accuracy, a discovery score, a public-site security result or a model comparison. Dependency package versions are recorded; Python transitive dependencies and image digests are not fully locked. Generated reports are ignored under `evaluation-results/`; retain separate filenames for successive runs. The fixture dataset and labels remain unchanged and read-only in the verification container.

Verification completed on 2026-10-26. User-supplied output confirmed `podman compose build api` succeeded (image `35c3df8ac469`) and the complete backend suite passed with `--network none` and read-only fixtures: 100 passed, one non-failing Starlette TestClient deprecation warning, in 0.83 seconds. The user then ran the standalone evaluator with the same network isolation and `--check-repeat`. Both runs produced the same result fingerprint. Direct inspection of the saved `evaluation-results/catalog-v1-baseline.json` confirmed its JSON schema, original predictions, denominators, failures and recorded environment. Its fingerprint was independently recomputed while preserving Python JSON numeric representations; all four source hashes and the manifest/label/page hashes match the current files. No commands, builds, tests or evaluation runs were executed by the agent for Issue #5.

| Measured baseline | Result |
|---|---|
| Dataset / method / scorer | catalog-development 1.0.0, development split; json_ld_deterministic 1.0.0; scorer 1.0.0 |
| Pages / selected fields | 10 pages, one product per page, all six fields: 48 expected non-null values and 12 expected nulls |
| Field micro precision / recall / F1 | 100% / 100% / 100%; TP=48, FP=0, FN=0; precision and recall denominators 48; F1 denominator 96 |
| Complete records / exact pages | 10/10 (100%) for both; no missed or extra products |
| Null values / reasons | 12/12 (100%) for both; zero spurious values or missing predictions. Expected reasons: missing_value 2/2, missing_offer 4/4, unsupported_value 2/2, unsupported_offer_structure 4/4. |
| Non-null evidence coverage / label-source agreement | 48/48 (100%) for both; unsupported values 0/48 (0%). All 60 per-field citation checks in the report are true. |
| Review burden | 6/10 predicted records marked needs_review (60%); this is validation status, not human review. |
| Failures / attempts / retries | 0 failures, 10 extraction attempts, 0 retries |
| HTTP requests / model calls | 0 / 0; evaluation container networking disabled |
| Local runtime | 0.075396 seconds for the first run, excluding the repeat run; timing is outside the stable fingerprint |
| Recorded environment | Python 3.12.15; beautifulsoup4 4.15.0; lxml 6.1.3; httpx 0.28.1 |

Result SHA-256: `036d21ae7134b5e3e259427eb7b1a137ee5ef438273ae153f8ff0aa92fe5d142`. The report stays local in the ignored output directory; source and documentation retain the procedure and measured summary. These are measured results on the same ten authored development fixtures used while implementing extraction. They do not estimate held-out/public-site accuracy, independent semantic evidence correctness, discovery quality or model performance. Background evaluation jobs and an evaluation dashboard remain deferred. The existing TestClient deprecation warning remains. Runtime acceptance for Issue #5 is complete. GitHub Issue #5 was closed as completed on 2026-10-26 with all six checklist items checked. Its project card was moved to Done and verified there (five Done cards). No Git commit or push was performed for Issue #5; delivery remains separate.


## Issue #4 implementation and verified checks (2026-10-26)

`FIXTURE_PRESETS` and `FIXTURE_URLS` in backend constants own the ten exact approved destinations. `GET /presets` exposes only IDs, labels and URLs; the UI loads this list and submits the selected `seed_url` with the existing fields and one-page limit. The API and worker both validate exact membership, including rejection of altered queries/fragments/credentials/ports/schemes and unknown paths. Product URL extraction must match the chosen source, even when another URL is also an approved fixture. The default desk-lamp request and persisted configuration shape remain compatible; no migration is added.

Snapshots and original records retain their existing persistence flow. Evidence now adds optional `kind` and `missing_key` metadata: absent fields reference their existing parent object; unsupported offer structures reference the original offers container. Previously stored evidence without these optional keys remains readable. Limits, leases, outbox dispatch, cancellation guards and terminal-state checks retain their existing implementation. No inference, unrestricted destinations, rendering, review, exports or scoring is added.

Authored checks cover the ten labeled pages and evidence, exact destination rejection, redirects, selected-page URL matching, absence evidence, UI preset retry/selection/idempotency, and four browser journeys. A new live acceptance helper exercises the API → outbox → RabbitMQ → worker → PostgreSQL path for ten fixtures plus one subset-field job, retaining eleven jobs. It checks completed-job worker re-entry; it does not replace crash/restart testing. Labels are mounted read-only into verification containers and remain outside runtime images.

Static review traced the API/form contract, worker source argument, exact URL guards and evidence paths against the dataset. React review checked effect cleanup, functional state updates, derived selection, labels, loading/error states and pending controls. The agent executed no terminal commands. The following command results were verified from user-supplied output; historical counts earlier in this document apply to previous revisions.

| Check | Verified result |
|---|---|
| Application images (2026-10-25) | All five built: fixture, API, dispatcher, worker and web. |
| Backend tests | 69 passed; one non-failing Starlette TestClient deprecation warning. |
| Frontend component tests | All five passed. |
| TypeScript and Vite production build (2026-10-26) | Passed; 93 modules transformed. |
| Migration and service startup (2026-10-26) | Alembic initialized normally without an error or upgrade step; all seven application services became healthy. No new migration was required. |
| Legacy live smoke check (2026-10-26) | API → outbox → RabbitMQ → worker → PostgreSQL, idempotency, rejected destination, snapshot integrity and safe content type passed. |
| Ten-fixture live acceptance check (2026-10-26) | All ten fixture jobs, selected fields, idempotency, completed-job worker re-entry, rejected requests and saved evidence passed; eleven jobs retained. |
| Browser image and tests (2026-10-26) | Pinned Playwright image built with `npm ci`; all four browser tests passed in 15.9 seconds, including reload and saved evidence. |

Direct browser review on 2026-10-26 confirmed all ten preset options and a changed source URL after keyboard selection. Saved graph-monitor results showed Focus Monitor, MON-002, 249.00 EUR and out_of_stock, with currency evidence at `/@graph/1/offers/priceCurrency`. The ambiguous-currency mug displayed Unavailable, reason unsupported value, and the original `$` excerpt. Missing-offer shelf fields displayed Unavailable, reason missing offer, and the parent Product object identifying the absent `offers` key. Saved HTML opened as text.

At a measured 390 × 844 CSS-pixel browser viewport, the form fitted without page-wide horizontal overflow. Tab reached the preset, field checkboxes and submit button with visible focus. A keyboard-submitted graph-monitor job completed in one attempt with saved results and evidence: `9e24a3e6-460b-4b9b-a70b-900a8dc2ff87`. In the evidence dialog, Tab moved from Close evidence to Field to Saved page and back to Close evidence; Enter expanded the saved HTML. Escape dismissed the dialog and restored visible focus to Inspect evidence. The dialog fitted horizontally and used internal vertical scrolling. The temporary viewport override was reset after review. Repeatable commands, including the ten-fixture live acceptance helper, are in the [local setup instructions](README.md#local-setup).

No application code changed during this manual review. This was browser viewport and keyboard verification, not a physical-device, screen-reader, contrast or cross-browser audit. Completed-job worker re-entry does not establish recovery from a crash during active extraction. The deprecation warning remains; no dependency update was attempted. No model calls, evaluation metrics, public-network security verification or deployment were performed. Git delivery is separate from runtime acceptance.

GitHub completion on 2026-10-26: all six acceptance checklist items were checked and Issue #4 was closed as completed through the GitHub connector. The signed-in project board was then inspected directly; the Issue #4 card was moved to Done and verified there (Done count: four). At issue closure, the implementation and documentation were awaiting Git commit and push; the user subsequently authorized the agent to deliver them.

## File review and verification limits (2026-10-23)

Direct file inspection confirmed that the saved npm v3 lockfile matches the dependency declarations in `frontend/package.json`; its resolved package URLs use the public npm registry. Both frontend Docker stages permit this lockfile and use `npm ci` when present. Python transitive dependencies and container image digests are not fully locked.

The project file inventory contained no dependency/build folders, private key files, personal documents, or apparent private credentials in project text. The literal passwords in Compose, backend defaults, and `.env.example` are explicitly disposable local demo values. `.DS_Store` exists locally but is ignored and absent from the Git index. `.env` files, Python caches/virtual environments, `node_modules`, `dist`, and Playwright output are ignored. At that file review, the saved lockfile was not ignored, but it and the implementation files were not yet indexed. The user subsequently confirmed committing and pushing the implementation, documentation, and saved lockfile; remote delivery was not independently reinspected for this diagram. Git ignore rules do not remove already tracked files.

This review used filesystem reads and source/configuration comparison only. The runtime results above are retained from the existing project record; their original output was not available for independent reinspection in this review. No commands, tests, builds, services, or deployments were run. The user subsequently confirmed the post-lockfile tests/builds, active-extraction crash-recovery check, and mobile/accessibility review complete. At that review, evaluation and public-deployment acceptance checks were outstanding and no model scores or extraction performance measurements were available. The later offline deterministic baseline is recorded above; model evaluation and public-deployment acceptance remain outstanding.


## Deployment and delivery

Local Podman Compose runs seven application services: web, API, worker, dispatcher, RabbitMQ, PostgreSQL, and fixture, with persistent database/broker volumes. The optional test profile adds the browser-test container. Ollama/inference is not configured; select and integrate a local model through later evaluation.

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
