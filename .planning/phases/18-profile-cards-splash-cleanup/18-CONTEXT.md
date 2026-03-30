# Phase 18: Profile Cards, Splash Page, and Cleanup - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Align profile cards and search result cards with Fluent 2 visual standards; redesign the login/splash page to a professional Fluent 2 landing; fix 3 test regressions (DEBT-03), remove get_user_photo_bytes() dead code (DEBT-04), and correct get_colleague_profile user_id schema description (DEBT-05).

</domain>

<decisions>
## Implementation Decisions

### Profile card layout (PROF-01)
- Keep horizontal layout (photo left, info right) — matches current pattern and Fluent 2 Persona component
- Photo stays 48px circle with initials fallback — already correct size for inline chat context
- Info hierarchy: **name** (14px semibold) > job title (12px regular) > department (12px secondary color) > email as link (12px accent color)
- Card uses `--atlas-bg-elevated` background with `--atlas-stroke-1` border and 8px border-radius — same elevated surface tier as user message bubbles (established in 15-02)
- Padding: 12px all sides, 12px gap between photo and info column
- Max-width: 320px — prevents card from stretching full bubble width
- No hover effects or click actions on the card itself — it's informational, not interactive
- Email remains a mailto: link with accent color and underline on hover

### Search result cards (PROF-02)
- Switch from individual bordered cards to a **compact list** inside a single elevated container — Fluent 2 List pattern
- Each row: name (semibold) + separator dot + job title (regular) + department (secondary) on one line; email below if present
- No individual card borders per result — use subtle `--atlas-stroke-2` divider lines between rows
- Outer container uses same `--atlas-bg-elevated` + border-radius as profile card for visual consistency
- Padding: 12px container, 8px vertical per row
- Max 5 visible results before scroll — prevents search results from dominating the conversation
- Visual consistency: same font sizes and token colors as profile card info fields

### Splash/login page (SPLA-01)
- Keep centered card layout — already correct pattern, just needs Fluent 2 polish
- Replace lightning emoji with Atlas wordmark or simple geometric logo mark using `--atlas-accent` color
- Card background: `--atlas-bg-elevated` with 12px border-radius and subtle `--atlas-stroke-1` border — no box-shadow (Fluent 2 prefers borders over shadows for contained surfaces)
- "Atlas" heading in Segoe UI Variable 28px semibold, subtitle in 14px regular secondary color
- "Sign in with Microsoft" button: `--atlas-accent` background, white text, 8px border-radius, Microsoft logo SVG retained — standard Microsoft sign-in button pattern
- Description text kept concise — one sentence about Exchange infrastructure querying
- Dark mode must work correctly (splash.html uses the Flask `style.css` tokens, not React — ensure parity with `--atlas-` equivalents)
- Full viewport height centering with `--atlas-bg-canvas` background

### Claude's Discretion
- Exact transition/animation on splash page (subtle fade-in acceptable)
- Whether to add a subtle background pattern or gradient to splash page
- Internal CSS organization for the splash page (inline in template vs separate file)
- Error state styling if sign-in fails
- Exact approach to the 3 test regression fixes (DEBT-03) — these are mechanical
- How to locate and remove get_user_photo_bytes() dead code (DEBT-04)
- Wording correction for get_colleague_profile schema description (DEBT-05)

</decisions>

<specifics>
## Specific Ideas

- Profile card and search result card should feel like siblings — same elevated surface, same typography scale, same token usage
- Splash page should feel "enterprise but approachable" — clean Fluent 2 card on a quiet background, not flashy
- The existing splash.html is Flask/Jinja2 rendered (not React) — it stays server-rendered since it's pre-auth; style updates happen in `style.css` using equivalent atlas token values
- Search result card currently uses individual bordered cards per result — consolidating into a single list container is a visual improvement that reduces border noise

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 18-profile-cards-splash-cleanup*
*Context gathered: 2026-03-30*
