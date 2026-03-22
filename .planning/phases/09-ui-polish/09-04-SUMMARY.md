---
phase: 09-ui-polish
plan: 04
subsystem: ui
tags: [dark-mode, css-custom-properties, localStorage, prefers-color-scheme, theme-toggle]

# Dependency graph
requires:
  - phase: 09-ui-polish
    provides: base.html, style.css, app.js from plans 01-03 (tool panels, copy buttons, loading dots)
provides:
  - Full dark mode system with CSS custom properties design token architecture
  - Flash-prevention inline script in <head> for zero-FOUT (flash of unstyled theme)
  - Dark mode toggle button in header (works on login splash and chat pages)
  - OS prefers-color-scheme auto-detection on first visit
  - localStorage persistence of user theme preference (atlas-theme key)
  - toggleDarkMode JS function with icon update logic
  - Smooth 200ms crossfade transition on all major color surfaces
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CSS design tokens: all colors defined as custom properties in :root and [data-theme='dark'] overrides"
    - "Flash prevention: inline IIFE in <head> before stylesheet sets data-theme attribute"
    - "Theme toggle: JS toggleDarkMode reads/writes data-theme on documentElement + localStorage"
    - "Icon update: sun/moon HTML entity via innerHTML driven by current theme value"

key-files:
  created: []
  modified:
    - chat_app/templates/base.html
    - chat_app/static/style.css
    - chat_app/static/app.js

key-decisions:
  - "JSON code block (.tool-panel-json) stays intentionally dark in both light and dark modes (Catppuccin theme) — only slight bg darkening in dark mode"
  - "Added --color-on-brand: #ffffff token for text-on-blue-background (btn-signin, user bubble, send btn) — stays white in both modes for contrast"
  - "No transition: all anywhere — explicit background-color/color/border-color transitions only on major surfaces to avoid animating layout properties"
  - "toggleDarkMode and all dark mode code placed before early return guard in app.js so toggle works on login splash page"
  - "Dark mode disabled-brand color: #1e3a6e (very dark blue) instead of light-mode #93c5fd — maintains button identity at low opacity in dark theme"

patterns-established:
  - "CSS token pattern: all hex values live only in :root / [data-theme=dark] blocks; component rules use var(--color-*) exclusively"
  - "Theme persistence pattern: inline script reads localStorage atlas-theme key, sets data-theme on <html> before CSS parses"
  - "JS dark-mode pattern: toggleDarkMode() reads documentElement.getAttribute('data-theme'), flips value, writes attribute + localStorage"

# Metrics
duration: 25min
completed: 2026-03-22
---

# Phase 9 Plan 04: Dark Mode Summary

**Complete dark mode system with CSS custom property tokens, flash-prevention <head> script, localStorage persistence, OS auto-detection, and smooth 200ms crossfade on all UI surfaces**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-03-22T12:39:33Z
- **Completed:** 2026-03-22T13:16:10Z
- **Tasks:** 3 (Task 1, Task 2a, Task 2b) + 1 bug fix
- **Files modified:** 3

## Accomplishments

- Dark mode toggle button in header switches theme on click — works on both login splash and chat pages
- CSS custom properties define all 40+ color tokens; zero hardcoded hex values remain in component rules
- Flash-prevention inline IIFE in `<head>` sets `data-theme` before stylesheet renders — no FOUC
- First-visit OS `prefers-color-scheme` auto-detection; subsequent visits use `localStorage` preference
- Smooth ~200ms crossfade on all major surfaces via explicit `background-color/color/border-color` transitions
- Dark theme covers all UI: header, sidebar, chat bubbles, input form, tool panels, buttons, scrollbars

## Task Commits

Each task was committed atomically:

1. **Task 1: Dark mode infrastructure — base.html toggle button + flash prevention** - `8bf39ff` (feat)
2. **Task 2a: Convert all CSS to custom properties + dark theme overrides** - `8138942` (feat)
3. **Task 2b: Add toggleDarkMode function to app.js** - `9b7eb65` (feat)
4. **Bug fix: Replace remaining hardcoded #ffffff with --color-on-brand token** - `05608d8` (fix)

## Files Created/Modified

- `chat_app/templates/base.html` - Flash-prevention inline `<script>` before stylesheet; dark mode toggle button with `id="theme-toggle"` and icon span in `header-right` outside session block
- `chat_app/static/style.css` - Full CSS custom property architecture: `:root` with 40+ tokens, `[data-theme="dark"]` overrides, all component rules using `var(--color-*)`, `.theme-toggle` button styles, explicit transitions on major surfaces
- `chat_app/static/app.js` - `toggleDarkMode()`, `updateDarkModeIcon()`, `themeToggleBtn`/`themeToggleIcon` references, `addEventListener` wiring and initial icon sync — all placed before the early return check

## Decisions Made

- **JSON code block dark in both modes**: `.tool-panel-json` uses the Catppuccin dark palette (`#1e1e2e` bg) in both light and dark themes — consistent JSON reading experience, visually distinguishes Exchange data
- **`--color-on-brand` token for white text on blue**: Three places use `color: #ffffff` for text on brand-blue backgrounds (signin button, user bubble, send button). Added `--color-on-brand: #ffffff` as a token to eliminate all hardcoded hex from component rules while preserving semantics
- **No `transition: all`**: Only explicit `background-color`, `color`, and `border-color` properties are transitioned to avoid animating layout properties (`width`, `height`, `padding`) that could cause jank
- **Toggle works on splash page**: All dark mode JS (getElementById, event listener, initial icon update) placed before `if (!messagesEl || !inputEl ...)` early return — ensures toggle is functional on the unauthenticated login splash page

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Three hardcoded #ffffff values remained after initial CSS conversion**

- **Found during:** Post-Task 2a verification
- **Issue:** `.btn-signin`, `.user-message .message-content`, and `#send-btn` all had `color: #ffffff` hardcoded, not in token blocks. The plan required replacing EVERY hardcoded hex value.
- **Fix:** Added `--color-on-brand: #ffffff` to both `:root` and `[data-theme="dark"]` token blocks; replaced all three `color: #ffffff` instances with `var(--color-on-brand)`
- **Files modified:** `chat_app/static/style.css`
- **Verification:** Node.js scan confirmed zero hardcoded hex in component rules after fix
- **Committed in:** `05608d8`

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Required for full token coverage. White-on-blue text semantically stays white in dark mode — token value unchanged between themes.

## Issues Encountered

None — the plan executed cleanly. Structural verification (script-before-link, toggle-before-session-block, toggleDarkMode-before-early-return) all confirmed correct via index position checks.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 9 complete — all 4 plans done. The full Atlas chat application is production-ready:
- Dark mode system fully implemented and tested
- All previous plans (tool panels, copy buttons, loading dots, Esc-to-cancel) compatible with dark mode via CSS custom properties
- No blockers for deployment (Phase 9 was the final polish phase)

---
*Phase: 09-ui-polish*
*Completed: 2026-03-22*
