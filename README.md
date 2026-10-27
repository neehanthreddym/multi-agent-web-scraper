![Competitor Product Intelligence — catalog pages connected to structured product records and source evidence](assets/banner.png)

# Competitor Product Intelligence

Competitor Product Intelligence turns product pages into structured catalog records. Track extraction jobs, inspect prices and availability, and trace each extracted field to saved source evidence.

**Status:** The local ten-fixture workflow is verified through user-run builds, 100 backend tests, five frontend component tests, four Playwright browser tests, and live API → queue → worker → PostgreSQL checks. Direct browser review on 2026-10-26 confirmed preset selection, saved evidence, null reasons and keyboard behavior at a narrow viewport. The offline deterministic baseline also passed on 2026-10-26: all ten saved development records and twelve null reasons matched the labels, with matching result fingerprints across two runs. Review, exports, agents, evaluation UI and public deployment remain later increments. These development results do not establish accuracy on unseen websites.

## Planned workflow

1. Configure approved seed URLs, product fields, and crawl limits.
2. Start a background job and monitor progress.
3. Inspect product records alongside saved field evidence.
4. Review ambiguous results and preserve original values when correcting them.
5. Export CSV or JSON and inspect evaluation scores and failures.

Initial fields: product name, source product ID, current price, currency, availability, and product URL. Missing values stay null with a reason.

## Current capabilities

The local UI now loads ten server-owned sources from `GET /presets`, creates one-page jobs for the selected fixture, lets you select product fields, polls job progress, filters the latest 100 jobs by status, cancels unfinished jobs, and displays original results with field evidence and saved HTML as escaped text. Preset loading failures offer retry, and submission stays disabled until a source is available. New evidence includes parent objects for missing fields and original containers for unsupported offers. PostgreSQL retains jobs, snapshots, and records. A separate offline CLI evaluates saved fixtures and writes original predictions and scores as JSON; its tests and repeatable ten-page development baseline passed. Arbitrary catalogs, pagination/discovery, human review, exports, agents, rendering, evaluation UI/background jobs, and public deployment are not implemented yet.

## Development fixture dataset

The [catalog fixture guide](fixtures/README.md) documents ten saved development pages, a separate answer key with sixty field labels and evidence references, dataset version `1.0.0`, and SHA-256 fingerprints. Cases cover different JSON-LD layouts, missing values, ambiguous currency, invalid prices, and unsupported offers. The original desk-lamp page is preserved. Direct source review and user-run consistency verification passed on 2026-10-25, including all three verifier PASS messages; that integrity check did not measure extraction accuracy. Issue #4 adds preset selection and URL-scoped extraction. User-run output confirmed all five application images built, 69 backend tests passed with one deprecation warning, and all five frontend component tests passed. TypeScript/Vite compilation, the ten-fixture live acceptance check and all four Playwright browser tests passed on 2026-10-26. Direct browser review also passed: ten presets, source URL changes, graph-monitor results, null reasons and absence evidence, plus keyboard operation, visible focus and Escape/focus restoration at a measured 390-pixel CSS width. This is not a physical-device or full accessibility audit. See the [verified checks in the architecture](ARCHITECTURE.md#issue-4-implementation-and-verified-checks-2026-10-26). The offline evaluation implementation and measured development baseline for Issue #5 are recorded below.

## Stack

- **Frontend:** React, Vite, TypeScript, Tailwind CSS, shadcn/ui.
- **Backend:** Python, FastAPI, Uvicorn, Pydantic, SQLAlchemy, Alembic, PostgreSQL.
- **Background jobs:** Celery and RabbitMQ.
- **Fetching:** HTTPX, Beautiful Soup, and lxml. LangGraph and Playwright for Python rendering are planned.
- **Local development:** Podman Compose. Ollama is planned for later model evaluation and is not a Compose service. No model is selected yet.
- **Testing:** pytest, Vitest component tests, and Playwright UI tests. Offline deterministic scoring functions and metric edge-case tests are implemented; all 100 backend tests passed with networking disabled on 2026-10-26 (one non-failing TestClient deprecation warning).

## Build local first

Start with one owned, controlled product page: **UI → API → worker → database → saved result and evidence in the UI**. Use deterministic extraction before adding bounded Discovery, Extraction, and Validation agents.

The ten labeled development fixtures and controlled extraction flow are available. Verify the offline evaluation baseline next, then add review and exports. Crawling stays within approved destinations and application-enforced budgets.

Remote target: Vercel frontend and lightweight API, with separately hosted background services and inference. Providers, inference hardware/model, costs, retention, and Vercel connectivity remain open. The public demo must work while the development computer is offline.

## Documentation

- [Product requirements](PRD.md)
- [Design system](DESIGN_SYSTEM.md)
- [Architecture, evaluation, and implementation sequence](ARCHITECTURE.md)
- [Codex working rules](AGENTS.md)

## Local setup

Prerequisite: a running Podman machine and an available Compose provider. Python and Node run inside containers; no host Python/Node installation is required.

Run from the repository root, one command at a time:

```bash
podman compose config --quiet
podman pull docker.io/library/node:22-bookworm-slim
podman compose build api worker dispatcher fixture web
podman compose up --wait --wait-timeout 180 postgres rabbitmq fixture
podman compose run --rm --no-deps api alembic upgrade head
podman compose run --rm --no-deps --volume "$PWD/fixtures:/fixtures:ro" api python -m pytest -q -o cache_dir=/tmp/catalog-pytest-cache
podman compose run --rm --no-deps web npm test
podman compose run --rm --no-deps web npm run build
podman compose up --wait --wait-timeout 180
podman compose exec -T api python -m app.smoke
podman compose run --rm --no-deps --volume "$PWD/fixtures:/fixtures:ro" --env SMOKE_API_URL=http://api:8000 api python -m app.smoke_fixtures
curl --fail --show-error http://127.0.0.1:8000/health
curl --fail --show-error http://127.0.0.1:8001/products/desk-lamp.html
```

Expected: configuration and builds succeed, migrations apply, backend/frontend tests and the TypeScript/Vite build pass, and all seven application services become healthy. The backend smoke check creates and retains one job, then checks the real queue/worker flow, expected product fields, idempotency, rejected destinations, snapshot integrity, and field-evidence locators. It prints PASS messages and saved job/record IDs only after those checks succeed. The ten-fixture helper then checks all saved fixture labels, snapshot hashes, field evidence, selected fields, idempotency, completed-job worker re-entry and rejected requests; it retains eleven jobs and prints ten fixture PASS lines plus a final summary. This is an acceptance check, not an evaluation score or crash-recovery experiment. The API health response is `{"status":"ok","service":"api"}`; the fixture contains Studio Desk Lamp, LAMP-001, 49.90 USD, and In stock. API documentation is at <http://127.0.0.1:8000/docs>.

Open <http://127.0.0.1:5173> for the local workspace. Create a fixture job, wait for completed status, and use Inspect evidence to view field locators, excerpts, and the saved page as text. Reloading restores the selected job. Jobs continue in the worker independently of the browser. The Vite server proxies `/api` to FastAPI over the private Compose network; this is local development serving, not the remote deployment design.

The saved [frontend dependency lockfile](frontend/package-lock.json) is part of the source files and must be included with the changes. Both frontend image stages use `npm ci` when it is present, with npm pinned to 11.6.0. Their bootstrap fallback uses `npm install` if the lockfile is missing; normal setup should retain the saved lockfile and needs no copy from a running container.

Browser verification uses the optional `test` profile and a Playwright image matching the pinned Playwright package. It downloads a larger image with Chromium and runs four UI → API → worker → database → evidence tests for the default fixture, graph layout, ambiguous currency, and missing offers, including reload and dialog focus checks. Run after the application services are healthy:

```bash
podman compose --profile test build ui-tests
podman compose --profile test run --rm --no-deps ui-tests
```

Expected: four browser tests pass. They retain their created jobs in PostgreSQL. This test does not replace a dedicated mobile/accessibility review or verification of a worker crash during active extraction.

`/health` checks API liveness; `/ready` checks database/schema readiness and is used by the API container health check. Apply migrations before starting the API, dispatcher, and worker. The default fixture URL remains `http://fixture:8080/products/desk-lamp.html`; the other nine exact URLs come from `/presets`. Port 8001 is for viewing the catalog from the host. No arbitrary URLs, redirects, discovery, agents, or rendering are enabled in this increment.

Only the API, fixture, and UI are published, all on localhost. PostgreSQL and RabbitMQ use named volumes and are reachable by service name inside Compose. Example credentials are local-only defaults; optional overrides are listed in `.env.example`. Keep real credentials in an ignored `.env` file. Image tags track patch updates within the named release series. Frontend dependencies have a saved npm lockfile; Python dependencies use pins and bounded ranges without a complete transitive lockfile. The local backend image includes pytest. Frontend buttons and dialogs use local shadcn/ui component patterns with Radix primitives and Tailwind styling.

`GET /presets` lists the ten server-owned fixture IDs, labels, and URLs. `POST /jobs` accepts one listed URL and selected fields with an `Idempotency-Key` header. Reusing a key with the same configuration returns the same job; changing the configuration returns 409. `GET /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/records`, and `GET /records/{id}/evidence` expose progress and original results. `POST /jobs/{id}/cancel` cooperatively cancels unfinished work. `GET /snapshots/{id}` serves saved HTML as plain text.

Jobs and outbox entries are committed together. The dispatcher publishes work; the worker claims a 90-second lease and permits at most three attempts within a ten-minute job budget. Duplicate messages cannot create another record for the same job. Each fetch is capped at 2 MiB; redirects are rejected. Missing/unsupported fields remain null with reasons. Snapshots and original fields persist in PostgreSQL for this small local flow. Queued-job recovery, queued-job cancellation, and persistence across a full stop/start are recorded above as user-verified scenarios. The user reported the active-extraction crash-recovery follow-up complete; its output was not independently inspected during Issue #4 verification. Completed-job worker re-entry in the new smoke helper does not establish crash recovery.

RabbitMQ 4.3 rejects temporary non-exclusive queues. Celery control/reply and event queues are configured as connection-exclusive and auto-deleting for this local worker; the job queue remains durable. Do not re-enable RabbitMQ's deprecated queue feature. Pytest's optional cache is directed to `/tmp`, which is writable by the container's non-root user.

To stop this setup while retaining its volumes:

```bash
podman compose down
```

RabbitMQ's health check uses the image entrypoint so diagnostics run as the `rabbitmq` user. A startup failure reading `.erlang.cookie` with `eacces` requires checking cookie ownership; a root-owned, owner-readable-only cookie is inaccessible to RabbitMQ. Repair only the confirmed ownership mismatch and retain the named volume. The fixture's original inline Python health check received a truncated command and failed with a syntax error. API and fixture checks now use script files instead of inline Python. User-run rebuild and startup output confirmed all four services healthy after these fixes.

If startup fails, stop the sequence and share the error. These diagnostic commands show service state and recent logs:

```bash
podman compose ps
podman compose logs --tail=80 api worker dispatcher postgres rabbitmq fixture web
```

Verification details are recorded in [ARCHITECTURE.md](ARCHITECTURE.md#issue-4-implementation-and-verified-checks-2026-10-26). User-supplied output confirms all seven application services healthy, the saved lockfile used through `npm ci`, passing tests and production compilation, the legacy smoke check and the ten-fixture live acceptance check. The latter retained eleven jobs and checked selected fields, idempotency, completed-job worker re-entry, rejected requests and saved evidence. Direct browser review additionally retained a completed keyboard-submitted graph-monitor job.

Earlier user-run checks established queued-job recovery, queued-job cancellation and persistence after a full stop/start. The user reported the active-extraction recovery follow-up complete; its original output was not independently inspected during Issue #4 verification. The current manual review covered an in-app browser viewport and keyboard interaction; physical devices, screen readers, contrast and other browsers were not audited. One backend TestClient deprecation warning remains. Those live workflow checks did not run models or measure offline extraction accuracy; the separate offline baseline is recorded below. No deployment success is claimed.

## Offline evaluation

`python -m app.evaluate` reads the ten versioned HTML pages directly, runs the existing deterministic extractor without fetching URLs, and scores original predictions against the separate authored labels. It imports no database or worker entry point. No service startup, migrations, model, new package or frontend rebuild is needed for this increment. The commands below disable the evaluation container network and mount fixtures read-only. The image build may need registry/package access.

Run one command at a time from `/Users/neehanth/Documents/PortfolioProjects/multi-agent-web-scraper`, inspecting each result before continuing:

1. Build the API image containing the evaluator and tests. Expected: the image builds successfully. This does not start or recreate the running application.

   ```bash
   podman compose build api
   ```

2. Run the complete backend suite with no container network. Expected: all tests pass, including metric edge cases, corrupted-input rejection, extraction-failure accounting, source-evidence checks, JSON output and repeatability. Verified from user-supplied output on 2026-10-26: 100 passed, one non-failing Starlette TestClient deprecation warning, in 0.83 seconds. The earlier 69-test result belongs to Issue #4.

   ```bash
   podman run --rm --pull=never --network none --volume "$PWD/fixtures:/fixtures:ro" competitor-product-intelligence-api python -m pytest -q -o cache_dir=/tmp/catalog-pytest-cache
   ```

3. Create a local output directory. Expected: the directory exists; it is ignored by Git.

   ```bash
   mkdir -p evaluation-results
   ```

4. Save the baseline JSON. Expected: the terminal shows a concise summary and a matching result SHA-256 across two runs; JSON alone is saved to the named file. Inspect the summary and exit/failure output before relying on the saved scores. Use a new output filename for subsequent retained runs.

   ```bash
   podman run --rm --pull=never --network none --volume "$PWD/fixtures:/fixtures:ro" competitor-product-intelligence-api python -m app.evaluate --fixtures-root /fixtures --check-repeat > evaluation-results/catalog-v1-baseline.json
   ```

The report includes dataset/method/scorer versions, manifest/label/page/code hashes, Python/parser package versions, original predictions, authored expectations, findings, per-field and micro precision/recall/F1 with counts and denominators, complete-record and exact-page accuracy, null-value/reason accuracy by expected reason, evidence coverage/label-source agreement, review burden, extraction failures and runtime. Decimal price strings compare numerically; other field values compare exactly. Undefined ratios are JSON `null` and display as `n/a`. Read the [scoring details and limitations](ARCHITECTURE.md#offline-deterministic-evaluation-issue-5).

`--check-repeat` compares result fingerprints, not entire report bytes: elapsed time is intentionally excluded from the fingerprint. No timestamp or absolute local path is embedded in successful reports. Exit status 0 means the evaluator completed without extraction failures, not that every prediction was correct; 1 saves a scored report containing extraction failures, and 2 indicates invalid inputs or a repeatability failure with no scored JSON. The host redirection can leave an empty file on an input error, so inspect the exit/output before treating it as a report. Generated reports stay local by default. The saved labels, page bytes, original application records and review history are not modified.

Verified on 2026-10-26 from user-run output and direct inspection of the saved report: 100 backend tests passed (one existing deprecation warning), and the offline baseline completed with matching fingerprints across two runs.

| Measured development baseline | Result |
|---|---|
| Field precision / recall / F1 | 100% / 100% / 100%; TP=48, FP=0, FN=0 |
| Complete records / exact pages | 10/10 (100%) for both |
| Null values / reasons | 12/12 (100%) for both; zero spurious values |
| Non-null evidence coverage / label-source agreement | 48/48 (100%) for both; unsupported values 0/48 |
| Extraction failures / HTTP requests / model calls | 0 / 0 / 0 |
| Local runtime | 0.075396 seconds for the first run; repeat-run time is not included |

Result SHA-256: `036d21ae7134b5e3e259427eb7b1a137ee5ef438273ae153f8ff0aa92fe5d142`. See [the architecture baseline record](ARCHITECTURE.md#offline-deterministic-evaluation-issue-5) for denominators, environment, review burden and verification details. These scores describe ten authored development fixtures used during implementation; they are not held-out or public-site accuracy, an independent semantic evidence audit, or model performance.
