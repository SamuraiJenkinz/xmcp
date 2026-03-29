---
phase: 15-design-system
plan: "01"
subsystem: ui
tags: [css-custom-properties, tailwind-v4, design-tokens, fluent-2, atlas, dark-mode]

# Dependency graph
requires:
  - phase: 14-functional-port
    provides: React SPA with Tailwind v4 @import prefix(tw) already in index.css
provides:
  - Complete --atlas- semantic token system in frontend/src/index.css
  - Light mode defaults on :root, dark mode overrides on [data-theme="dark"]
  - @layer base document typography and background from tokens
  - @theme inline Tailwind bridge exposing atlas tokens as tw: utility classes
affects: [15-02, 16-shell-layout, 17-sidebar, 18-chat-surface, 19-input-toolbar]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Atlas token naming: --atlas-{category}-{variant} (bg-canvas, text-primary, stroke-1)"
    - "Tailwind bridge: @theme inline maps --color-atlas-* and --font-atlas to tw: utilities"
    - "Dark mode: data-theme attribute on html element, no JS class toggling needed"

key-files:
  created: []
  modified:
    - frontend/src/index.css

key-decisions:
  - "Token order in index.css: @import → :root → [data-theme=dark] → @layer base → @theme inline — ensures variable resolution before Tailwind theme consumption"
  - "62 --atlas- custom properties covering surface, text, stroke, accent, status, font-family, font-sizes, line-heights"
  - "Fluent 2 type ramp used exactly: 10/12/14/16/20/24/28/32px sizes with matching line heights"
  - "Segoe UI Variable first in font stack for optical sizing support on Windows"

patterns-established:
  - "Token reference pattern: all component styles consume var(--atlas-*) directly, never hardcoded hex values"
  - "Theme switching: [data-theme='dark'] attribute selector overrides only color tokens; typography tokens are shared"

# Metrics
duration: 5min
completed: 2026-03-29
---

# Phase 15 Plan 01: Design Token System Summary

**62 Fluent 2-based --atlas- CSS custom properties (light/dark), @layer base typography, and Tailwind @theme inline bridge — single source of truth for all subsequent visual phases**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-29
- **Completed:** 2026-03-29
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Defined 62 `--atlas-` custom properties across surface hierarchy, text hierarchy, strokes, brand accent, status colors, font families, Fluent 2 font sizes, and Fluent 2 line heights
- Implemented light defaults on `:root` and dark overrides on `[data-theme="dark"]` — enabling zero-JS theme switching via HTML attribute
- Set `@layer base` styles: html/body font, size, line-height, color, background from tokens; `font-optical-sizing: auto` for Segoe UI Variable; code/pre/kbd use mono token
- Bridged 9 Atlas tokens to Tailwind utilities via `@theme inline` (canvas, surface, elevated, primary, secondary, accent, stroke, base font, mono font)
- Vite production build and TypeScript compilation both clean

## Task Commits

1. **Task 1+2: Define Atlas token system and verify build** - `505d48a` (feat)

**Plan metadata:** _(committed after this SUMMARY)_

## Files Created/Modified

- `frontend/src/index.css` - Complete Atlas design token system: 109 lines replacing the original 1-line file

## Decisions Made

- Token file ordering is `@import → :root → [data-theme="dark"] → @layer base → @theme inline`. The `:root` block must precede `@theme inline` so CSS custom property values are defined before Tailwind consumes them.
- Typography tokens (font families, sizes, line heights) are intentionally excluded from `[data-theme="dark"]` — they are theme-invariant. Only color-related tokens override in dark mode.
- `@theme inline` maps only the 9 most commonly needed tokens to Tailwind utilities. Full token set is still accessible via `var(--atlas-*)` directly.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All `--atlas-` tokens defined and verified in production build
- `[data-theme="dark"]` override block ready for App.tsx `data-theme` attribute set at module load (already implemented in Phase 14)
- Phase 15-02 (shell layout visual pass) and all subsequent phases (16-19) can consume tokens immediately
- No blockers

---
*Phase: 15-design-system*
*Completed: 2026-03-29*
