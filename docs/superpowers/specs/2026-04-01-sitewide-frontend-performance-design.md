# Sitewide Frontend Performance Design

## Goal

Improve perceived responsiveness across the whole frontend by removing duplicated realtime data flows, reducing redundant polling, and cutting repeated list/chart recomputation without changing current API contracts or the left-workbench UI structure.

## Scope

- Unify the frontend realtime data entry path.
- Introduce a shared page-domain refresh model with request deduplication and cache staleness rules.
- Reduce repeated derived-state work in `Dashboard.vue`, `TaskManager.vue`, `MonitorCenter.vue`, and `EnergyOptimization.vue`.
- Limit chart work to visible tabs and changed datasets.

## Non-Goals

- No backend protocol redesign.
- No new state/query framework.
- No silent fallback from WebSocket to fake realtime polling.
- No broad UI restyling or page-layout rewrite.
- No workerization or virtualized lists in this round.

## Shared Data Flow

`App.vue` should remain the application shell and stop owning business refresh logic. Frontend data should be split into two explicit entry paths:

- realtime path: one WebSocket connection for `gpus`, `system`, `processes`, and `alerts`
- domain refresh path: page-scoped fetchers for dashboard, monitor, energy, scheduler, and task-governance data

`useWebSocket.js` should become a thin connection manager only. It may connect, reconnect, and parse messages, but store writes must happen through a single shared state layer.

`frontend/src/stores/app.js` should expand from raw arrays into domain-shaped state with:

- realtime payloads and connection metadata
- per-domain `loading`, `error`, `lastUpdatedAt`, and `inFlight`
- shared pre-aggregated summaries consumed by pages

## Shared Refresh Model

A small frontend refresh coordinator should own polling registration and visibility rules:

- refresh only for the active page or active tab
- pause non-critical polling while the document is hidden
- deduplicate concurrent requests for the same domain key
- reuse fresh cached results until a domain-specific `staleTime` expires

This keeps refresh policy in one place instead of spreading `setInterval()` and retry rules across multiple views.

## Page-Level Reductions

### Dashboard

Move repeated `store.processes` and `store.gpus` scans into a shared `dashboardSummary`. Connection status, fairness, self-check, and desktop-service data should refresh independently so one slow call does not force a full dashboard refresh burst.

### Task Manager

Normalize processes once in shared state, then derive summary counters from that normalized list only once per update. The page should keep only lightweight UI filtering. Keyword filtering should use a short debounce to avoid recomputing the whole task list on every keystroke.

### Monitor Center

Each tab should keep its own cached payload and staleness timestamp. Entering a tab should reuse fresh data first, then refresh if needed. Heavy charts and timeline renderers should mount only while their tab is active.

### Energy Optimization

Split fetching by tab instead of loading all datasets every 30 seconds:

- overview: metrics, breakdown, efficiency, scheduler status
- prediction: prediction, schedule history, history comparison
- ai: AI insight and AI anomalies

Chart instances should update only when their source dataset changes. Number animations should run only on initial load or material metric deltas, not on every polling cycle.

## Error Handling

Performance changes must not hide failures. Each domain state should explicitly surface:

- loading state
- request error
- last successful refresh time
- whether the view is showing cached data

WebSocket disconnects remain visible to the UI. The frontend should not silently switch to an alternate fake realtime mode.

## Validation

Validation for this round should cover:

- `App.vue` no longer owning a second realtime data path
- removal or consolidation of duplicated page-level polling timers
- page/domain refreshes pausing when tabs are inactive or the document is hidden
- shared summaries replacing repeated per-page scans where practical
- visible-only chart refresh behavior on `MonitorCenter.vue` and `EnergyOptimization.vue`
- frontend build and smoke verification in the Windows environment already used by the repository scripts
