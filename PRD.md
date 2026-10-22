# Competitor Product Intelligence

## Purpose and user

Help a solo analyst collect product information from approved catalogs, inspect evidence, resolve ambiguity, export results, and measure extraction quality. The portfolio demo includes a UI, Python API, background jobs, bounded agents, and evaluation.

This baseline describes planned capabilities. Start locally as a single-user application; the public demo uses controlled sources and strict resource limits.

## Primary journey

1. Configure seed URLs, allowed domains, selected fields, and a page limit.
2. Start a job; monitor progress or cancel it independently of the browser tab.
3. Filter records and inspect field evidence from saved pages.
4. Correct, approve, or reject ambiguous records while retaining original values.
5. Export CSV or JSON with an explicit automated or reviewed view.
6. Run an evaluation; inspect scores, failures, and examples.

## MVP scope

Extract product name, source product ID when available, current price, currency, availability, and product URL. Support one offer per product detail page. Retain source URL, observation time, extraction method, validation status, and field evidence. Missing or unsupported values remain null with a reason; never infer currency solely from an ambiguous symbol.

Begin with owned static catalog fixtures and pagination. Add approved public catalogs, bounded Discovery/Extraction/Validation roles, and JavaScript rendering after the deterministic flow works. Roles may share a model. 

## Acceptance criteria

- A configured fixture job reaches persisted results with inspectable evidence; refresh or tab closure does not interrupt it.
- Invalid destinations are rejected. Limits apply to discovered links, redirects, rendered requests, retries, and model calls.
- Cancellation stops new work promptly and preserves completed results; worker redelivery does not duplicate records.
- Filters expose validation and review status. Corrections preserve original extraction, author type, time, and reason.
- Exports identify their view and include provenance; rejected records are excluded by default. Null reasons remain available in both formats.
- An evaluation runs against ten labeled saved development pages and displays reproducible automated scores separately from corrections.
- The deployed demo completes the journey while the developer computer is offline.

## Exclusions and success measures

Defer variants, cross-site matching, complex pricing, login-protected scraping, CAPTCHA bypass, unrestricted discovery, billing, and enterprise administration.

Success means the complete journey passes repeatable acceptance checks, evidence supports every accepted non-null field, and retry/recovery checks produce no duplicate records. Publish measured accuracy, review burden, runtime, and usage only after experiments. Set model and performance targets after establishing the baseline; no model is prequalified.

See [architecture](ARCHITECTURE.md) and [design system](DESIGN_SYSTEM.md).
