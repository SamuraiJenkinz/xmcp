# Phase 15: Design System - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the Fluent 2 semantic color token system (`--atlas-` prefix) applied globally, dark mode three-tier surface hierarchy, light mode neutral palette, and Segoe UI Variable typography. This is the visual foundation — all Phases 16-19 build on top of it. No new components or features; only the token/theming layer.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

User explicitly delegated all design system decisions to Claude with the following guidance:

**Guiding principle:** Make the best technology decisions for an enterprise deployment. All choices should reflect enterprise-grade quality — consistency, maintainability, and professional appearance.

**Surface hierarchy**
- Claude decides: number of surface tiers, how sidebar/chat pane/cards/modals layer visually
- Constraint: must match Fluent 2 webDarkTheme conventions and produce a clear visual hierarchy
- Research should investigate: Fluent 2 surface token patterns, Microsoft Copilot's actual surface layering

**Color personality**
- Claude decides: whether to inject an Atlas brand accent or stay strict Fluent 2 neutral, how accent color is used
- Constraint: must feel enterprise-appropriate — not flashy, not bland
- Research should investigate: Fluent 2 accent token system, how Copilot/Teams use brand color within Fluent

**Typography**
- Claude decides: exact type ramp sizes, density, code block font treatment
- Constraint: Segoe UI Variable is locked per success criteria; sizes must follow Fluent 2 type ramp
- Research should investigate: Fluent 2 type ramp specifications, code block font pairing conventions

**Token migration scope**
- Claude decides: how aggressive the `--atlas-` migration is, based on research findings
- Constraint: balance thoroughness with pragmatism — React components are primary target; legacy vanilla JS CSS and login/splash page should be evaluated by research before committing to full migration
- Research should investigate: what CSS currently exists across both React and vanilla JS, migration blast radius, whether a phased approach (React-only now, legacy later in Phase 18) is more appropriate

</decisions>

<specifics>
## Specific Ideas

- Enterprise deployment — professional, polished, not experimental
- Microsoft Copilot aesthetic is the north star (established in milestone goal)
- FluentProvider with webDarkTheme/webLightTheme already wired in App.tsx from Phase 14
- Theme toggle and `data-theme` attribute already functional
- Current CSS is minimal (just Tailwind import) — greenfield opportunity for token system

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-design-system*
*Context gathered: 2026-03-29*
