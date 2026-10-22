# Design System

## Direction and tokens

Use a restrained, professional workspace: neutral surfaces, readable tables, clear hierarchy, and one primary action per panel. Implement with React, Vite, TypeScript, Tailwind CSS, and shadcn/ui. 

| Token | Default |
|---|---|
| Canvas / surface | #F8FAFC / #FFFFFF |
| Text / secondary text | #0F172A / #475569 |
| Border | #CBD5E1 |
| Primary / focus | #1D4ED8 |
| Success / warning / error | #166534 / #92400E / #B91C1C |

Use status colors as text on pale backgrounds, always with labels or icons. Verify contrast in actual component combinations.

Use the system sans-serif stack. Body: 16px/24px; table: 14px/20px; headings: 24px/32px and 20px/28px.  Spacing follows 4, 8, 12, 16, 24, and 32px; cards use 16–24px padding and 8px corners.

## Small screen structure

- **Jobs:** compact dashboard table, status filters, Create job button; create form in a dedicated panel with field-level validation and a budget summary.
- **Job detail:** progress counts, current stage, errors, cancellation, results table, and exports. Count fetched, extracted, and failed pages separately; avoid false precision in progress percentages.
- **Evidence/review panel:** selected field, original value, source excerpt and locator, null reason, proposed correction, and approve/reject controls. Show review history.
- **Evaluation tab:** dataset and method selector, score summary, comparison table, failures with evidence links, and a clear automated/reviewed label.

Reuse buttons, labeled inputs, checkboxes, status badges, tables, tabs, dialogs, alerts, skeletons, and toasts. Tables support sorting, pagination, status filters, sticky headers, and horizontal scrolling on narrow screens. 

## Interaction and accessibility

Show skeletons during initial loading, explicit empty-state actions, actionable errors with retry where safe, and persistent success status. Disable duplicate submissions while pending. Confirm cancellation and rejection; retain edits when saving fails. Render null as “Unavailable” with its reason.

Use semantic headings and tables, associated labels, keyboard operation, visible focus, and approximately 44px action targets. Panels manage and restore focus; dialogs support Escape. Announce job changes politely without reading every poll. Never rely on color alone. Evidence is escaped text by default, with no executable page content.
