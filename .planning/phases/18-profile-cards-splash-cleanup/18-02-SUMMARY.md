---
phase: 18-profile-cards-splash-cleanup
plan: 02
subsystem: ui
tags: [splash, login, css-tokens, fluent2, dark-mode, svg]

requires:
  - phase: 15-design-system
    provides: --color-* CSS custom property token system used throughout splash rules
  - phase: 16-chat-experience-redesign
    provides: base.html template structure that splash.html extends

provides:
  - Fluent 2 splash/login page with geometric SVG logo mark (no emoji)
  - Splash card with 12px border-radius and border instead of box-shadow
  - Correct heading weight (600), Segoe UI Variable font stack
  - Description constrained to 320px max-width with centering
  - btn-signin at 14px with 8px radius

affects: [19-remaining, any future splash page or onboarding work]

tech-stack:
  added: []
  patterns:
    - "Inline SVG for geometric logo marks — avoids font/icon dependency for simple shapes"
    - "splash-logo replaces splash-icon — semantic class rename with display:block centering"

key-files:
  created: []
  modified:
    - chat_app/templates/splash.html
    - chat_app/static/style.css

key-decisions:
  - "Rotated rounded-square SVG (rect rx=6 transform=rotate(45)) used as geometric mark — simpler and more recognisable than an 'A' letterform at small sizes"
  - "letter-spacing reduced to -0.01em from -0.02em on h1 — Segoe UI Variable at 600 weight tracks better with lighter spacing"
  - "--color-* namespace unchanged — dark mode [data-theme='dark'] overrides already cover all splash tokens"

patterns-established:
  - "Splash card: border not shadow, 12px radius, 40px padding — locked Fluent 2 geometry for Phase 18"
  - "btn-signin: 8px radius, var(--color-brand) background, 14px/600 — locked sign-in button spec"

duration: 8min
completed: 2026-03-30
---

# Phase 18 Plan 02: Splash Page Fluent 2 Redesign Summary

**Splash login page redesigned to Fluent 2 aesthetic — geometric SVG logo replaces lightning emoji, card uses 12px border-radius with border (no shadow), heading is 28px/600/Segoe UI Variable, sign-in button at 14px/8px-radius.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-30T00:00:00Z
- **Completed:** 2026-03-30T00:08:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Replaced `&#9889;` lightning emoji with a 40px inline SVG geometric logo mark (rotated rounded square in `var(--color-brand)`) using `splash-logo` class
- Updated `.splash-card` to 12px border-radius, removed `box-shadow`, normalized padding to `40px`
- Set h1 to `font-weight: 600`, `font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif`, `letter-spacing: -0.01em`
- Added `max-width: 320px` with auto margins to `.splash-description` for comfortable reading width
- Removed `.splash-icon` CSS rule entirely; added `.splash-logo` rule with `display: block; margin-bottom: 16px`
- Condensed description from multi-line paragraph to single sentence
- Dark mode continues to work — all `--color-*` tokens preserved in same namespace

## Task Commits

1. **Task 1: Update splash.html markup for Fluent 2 aesthetic** - `845760b` (feat)
2. **Task 2: Update splash CSS for Fluent 2 tokens and geometry** - `4b9919c` (feat)

## Files Created/Modified

- `chat_app/templates/splash.html` - Geometric SVG logo, condensed description, splash-logo class
- `chat_app/static/style.css` - splash-card 12px radius/no shadow, splash-logo rule, h1 typography, description max-width, btn-signin 14px

## Decisions Made

- Used a `rect` element with `rx="6"` rotated 45 degrees rather than a circle or diamond path — simpler SVG, renders cleanly at 40px, and the rounded corners prevent it reading as a sharp danger symbol
- Kept `letter-spacing: -0.01em` (relaxed from `-0.02em`) because Segoe UI Variable at semibold weight already has tighter natural tracking

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Splash page is visually production-ready with Fluent 2 geometry
- Phase 18 Plan 01 (profile cards) and Plan 02 (splash) both complete — Phase 18 is done
- Ready for Phase 19

---
*Phase: 18-profile-cards-splash-cleanup*
*Completed: 2026-03-30*
