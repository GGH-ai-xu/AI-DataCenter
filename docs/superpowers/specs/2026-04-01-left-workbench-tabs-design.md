# Left Workbench Tabs Design

## Goal

Unify the six major frontend workbench pages around a console-style navigation model:

- Desktop: left-side sticky workbench tabs
- Mobile: top horizontal tab strip
- Shared interaction and visual language across all workbench pages
- No business-logic rewrites or cross-page tab state coupling

Affected pages:

- `Dashboard.vue`
- `Scheduler.vue`
- `MonitorCenter.vue`
- `TaskManager.vue`
- `EnergyOptimization.vue`
- `AIAssistant.vue`

## Chosen Approach

Use the existing shared `WorkspaceTabs` component as the only tab component and extend it to support:

- vertical desktop layout
- sticky positioning
- horizontal mobile fallback

Use shared layout utility classes, not a new page-shell component. Each page keeps ownership of:

- `activeTab`
- tab content rendering
- page-specific summary blocks
- page-specific side/main content

## Layout Model

All six pages adopt the same structure:

1. `WorkspaceSummary` at the top
2. `workspace-nav-layout` below the summary
3. `workspace-nav-layout__nav` on the left for tabs
4. `workspace-nav-layout__content` on the right for active-tab content

Desktop behavior:

- left nav fixed width
- left nav uses `position: sticky`
- only right content area changes on tab switch
- no layout jump when tab content height changes

Mobile behavior:

- layout collapses to one column
- tabs move above content
- tabs become horizontally scrollable
- labels and descriptions must wrap instead of truncating

## Component Boundaries

`WorkspaceTabs` responsibilities:

- render tab items
- render active state
- support vertical and horizontal presentation
- support sticky-friendly layout
- remain a pure `v-model` tab selector

Shared CSS responsibilities:

- define the left-nav workbench layout
- define desktop/mobile breakpoints
- define tab density, spacing, and sticky offsets

Page responsibilities:

- define tab item data
- own `activeTab`
- render page-specific content

## Page Mapping

- `Dashboard`: `overview / access / live`
- `Scheduler`: `control / results / audit`
- `MonitorCenter`: `system / training / users / timeline`
- `TaskManager`: existing task workbench sections remain, only navigation placement changes
- `EnergyOptimization`: existing analysis and replay sections remain, only navigation placement changes
- `AIAssistant`: `control / chat / model`

## Visual Direction

Adopt option A from the approved mockup:

- narrow console-style left rail
- stacked tab cards
- strong active state
- subdued inactive state
- stable right-side workspace

Avoid:

- drawer navigation on mobile
- separate per-page tab implementations
- top tabs on desktop
- text truncation in tab labels or descriptions

## Error Handling

- If a page has many tabs, the left nav scrolls independently on desktop.
- If a mobile viewport is narrow, tab strip remains scrollable horizontally.
- If descriptions wrap to two lines, tab card height may grow; do not clip text.

## Testing

Add or update tests to verify:

- shared workbench pages still use `WorkspaceTabs`
- left-workbench layout class is present on all six pages
- desktop-oriented tab markup exists only once in shared component
- mobile fallback remains available
- no text truncation rules are reintroduced for tab labels/descriptions

Verification commands:

- `py -3 -m unittest discover -s tests -p test_*.py`
- `cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm run build"`
