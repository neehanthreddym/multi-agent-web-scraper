![Competitor Product Intelligence — catalog pages connected to structured product records and source evidence](assets/banner.png)

# Competitor Product Intelligence

A portfolio project for collecting product information from approved catalog websites, inspecting source evidence, and measuring extraction quality.

**Status:** Documentation baseline accepted. The first local end-to-end flow is Ready; application implementation has not started. There is no runnable demo or measured extraction performance yet.

## Planned workflow

1. Configure approved seed URLs, product fields, and crawl limits.
2. Start a background job and monitor progress.
3. Inspect product records alongside saved field evidence.
4. Review ambiguous results and preserve original values when correcting them.
5. Export CSV or JSON and inspect evaluation scores and failures.

Initial fields: product name, source product ID, current price, currency, availability, and product URL. Missing values stay null with a reason.

## Stack

- **Frontend:** React, Vite, TypeScript, Tailwind CSS, shadcn/ui.
- **Backend:** Python, FastAPI, Uvicorn, Pydantic, SQLAlchemy, Alembic, PostgreSQL.
- **Background jobs:** Celery and RabbitMQ.
- **Fetching and agents:** HTTPX, Beautiful Soup, lxml, LangGraph, and Playwright for Python with Chromium when needed.
- **Local development:** Podman Compose; Ollama for later model evaluation. No model is selected yet.
- **Testing:** pytest, custom evaluation functions, frontend tests, and Playwright UI tests.

## Build local first

Start with one owned, controlled product page: **UI → API → worker → database → saved result and evidence in the UI**. Use deterministic extraction before adding bounded Discovery, Extraction, and Validation agents.

Next, add ten labeled development fixtures, evaluation, review, and exports. Crawling stays within approved destinations and application-enforced budgets.

Remote target: Vercel frontend and lightweight API, with separately hosted background services and inference. Providers, inference hardware/model, costs, retention, and Vercel connectivity remain open. The public demo must work while the development computer is offline.

## Documentation

- [Product requirements](PRD.md)
- [Design system](DESIGN_SYSTEM.md)
- [Architecture, evaluation, and implementation sequence](ARCHITECTURE.md)
- [Codex working rules](AGENTS.md)

Setup instructions will be added with the first working implementation.
