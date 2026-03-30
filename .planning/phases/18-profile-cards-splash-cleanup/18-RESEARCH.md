# Phase 18: Profile Cards, Splash Page, and Cleanup - Research

**Researched:** 2026-03-30
**Domain:** React CSS (Fluent 2 tokens), Flask/Jinja2 HTML/CSS, Python test regressions, dead code removal
**Confidence:** HIGH

## Summary

Phase 18 splits into three distinct sub-domains that require no new library installations. All work is applied directly to existing files.

**PROF-01/PROF-02** (profile + search result cards): Both components and their CSS already exist. The React components (`ProfileCard.tsx`, `SearchResultCard.tsx`) use correct atlas token CSS classes. The gap is in the CSS itself — the profile card uses `--atlas-stroke-2` border instead of `--atlas-stroke-1`, has `max-width: none` (no max-width cap), and padding is `12px 16px` instead of `12px`. The search results container has no elevated surface wrapper or max-height scroll — each `.search-result-card` has its own border instead of being rows inside one container.

**SPLA-01** (splash page): The splash page is `chat_app/templates/splash.html` (Jinja2 extending `base.html`) with styles in `chat_app/static/style.css`. It uses its own `--color-*` token namespace, not the React `--atlas-*` tokens. The CONTEXT decision requires the splash page to use `--atlas-*` equivalents in `style.css`. The current splash card uses `box-shadow` and `border-radius: 16px` — Fluent 2 prefers borders over shadows for contained surfaces.

**DEBT-03/04/05** (tech cleanup): Three kinds of mechanical fixes — test assertion updates for 3 failing tests, removal of the dead `get_user_photo_bytes()` function from `chat_app/graph_client.py`, and a schema description correction in `exchange_mcp/tools.py` for `get_colleague_profile`.

**Primary recommendation:** All three plan files should be self-contained with no cross-dependencies. The CSS/visual work is purely in existing files. No package installs needed.

## Standard Stack

### Core (already in project — no new installs)
| File | Purpose | Why This Phase Touches It |
|------|---------|--------------------------|
| `frontend/src/components/ChatPane/ProfileCard.tsx` | React profile card component | PROF-01 CSS class alignment |
| `frontend/src/components/ChatPane/SearchResultCard.tsx` | React search result component | PROF-02 list container restructure |
| `frontend/src/index.css` | All React component CSS | PROF-01, PROF-02 CSS updates |
| `chat_app/templates/splash.html` | Jinja2 splash page template | SPLA-01 markup update |
| `chat_app/static/style.css` | Flask app CSS (has `--color-*` tokens) | SPLA-01 token mapping and splash class updates |
| `chat_app/graph_client.py` | Graph API client | DEBT-04 dead code removal |
| `exchange_mcp/tools.py` | MCP tool definitions | DEBT-05 schema description fix |
| `tests/test_exchange_client.py` | Exchange client unit tests | DEBT-03 test assertion fixes |
| `tests/test_tools_flow.py` | Mail flow tool tests | DEBT-03 test assertion fixes |
| `tests/test_tools_hybrid.py` | Hybrid connector tests | DEBT-03 test assertion fixes |
| `tests/test_graph_client.py` | Graph client tests | DEBT-04 — tests reference dead function, need update |

### Supporting
None required. All work is CSS, HTML, Python source edits.

### Alternatives Considered
None — no alternative libraries needed; all work is in existing files.

**Installation:**
```bash
# No new installs required
```

## Architecture Patterns

### Recommended Project Structure
No structure changes. All edits are to existing files.

### Pattern 1: Fluent 2 Elevated Surface Card
**What:** A card using `--atlas-bg-elevated` background with `--atlas-stroke-1` border and 8px border-radius. Padding 12px. No box-shadow.
**When to use:** Profile card, search results container, any "lifted" informational surface in chat context.
**Example:**
```css
/* Source: frontend/src/index.css (established in Phase 15-02) */
.profile-card {
  background-color: var(--atlas-bg-elevated);
  border: 1px solid var(--atlas-stroke-1);
  border-radius: 8px;
  padding: 12px;
  max-width: 320px;
}
```

### Pattern 2: Fluent 2 List Container with Row Dividers
**What:** One outer elevated container with `--atlas-stroke-2` horizontal dividers between rows, no individual card borders per item.
**When to use:** Search results list — reduces border noise, matches Fluent 2 List component pattern.
**Example:**
```css
/* Outer container — single elevated surface */
.search-results {
  background-color: var(--atlas-bg-elevated);
  border: 1px solid var(--atlas-stroke-1);
  border-radius: 8px;
  padding: 0 12px;
  max-height: 280px;  /* ~5 rows at 8px vertical padding each */
  overflow-y: auto;
}

/* Row within list — no individual border, just bottom divider */
.search-result-row {
  padding: 8px 0;
  border-bottom: 1px solid var(--atlas-stroke-2);
}

.search-result-row:last-child {
  border-bottom: none;
}
```

### Pattern 3: Flask/Jinja2 Splash Page with Atlas Tokens
**What:** The splash page uses `chat_app/static/style.css`. The React app uses `frontend/src/index.css`. They are separate files with separate token namespaces. The splash page currently uses `--color-*` tokens. CONTEXT decision requires `--atlas-*` equivalent values to be added to `style.css` for the splash page classes.
**When to use:** Any Flask-rendered page that needs visual parity with the React app.
**Implementation approach:**
- Add `--atlas-*` variable declarations to the `:root {}` block in `chat_app/static/style.css` (matching same values as `frontend/src/index.css`)
- Update splash-specific classes (`.splash-container`, `.splash-card`, `.splash-icon`, `.btn-signin`, etc.) to use `--atlas-*` tokens
- OR simply remap the splash classes to the numeric token values matching the React design tokens

### Pattern 4: Fluent 2 Persona Component Geometry (Profile Card)
**What:** Photo 48px circle (left), info column right. Info hierarchy: name 14px semibold > title 12px regular > department 12px tertiary color > email 12px accent link.
**When to use:** Profile card only (not search results).
**Key measurements from CONTEXT:**
- Photo: 48px × 48px, `border-radius: 50%`, initials fallback
- Info gap: 12px between photo and info column
- Name: `var(--atlas-text-body)` (14px), `font-weight: 600`
- Job title: `var(--atlas-text-caption1)` (12px), `color: var(--atlas-text-secondary)`
- Department: `var(--atlas-text-caption1)` (12px), `color: var(--atlas-text-tertiary)`
- Email: `var(--atlas-text-caption1)` (12px), `color: var(--atlas-accent)`, underline on hover

### Anti-Patterns to Avoid
- **Individual card borders per search result:** Results in border noise. Use a single container + row dividers.
- **box-shadow on Fluent 2 surfaces:** Fluent 2 prefers `border: 1px solid var(--atlas-stroke-1)` over shadows for contained surfaces.
- **Using `--color-*` tokens on the splash page:** The splash page's CSS lives in `style.css` — it needs the `--atlas-*` token values either imported or declared there.
- **Removing `get_user_photo_bytes` without updating its tests:** `tests/test_graph_client.py` has 4 tests that call `gc.get_user_photo_bytes()`. These must be updated or removed when the function is deleted.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSS token sync between Flask and React apps | Custom build script to extract tokens | Manually declare `--atlas-*` in `style.css` | Only the splash page needs sync; it's 6-8 values |
| Search results virtualization | Custom scroll handler | CSS `max-height` + `overflow-y: auto` | Max 5 rows is a small fixed list |
| Microsoft logo in sign-in button | External icon library | Inline SVG already in splash.html | SVG is already correct; keep it |

**Key insight:** This phase is pure CSS/HTML/Python edits. No new abstractions needed.

## Common Pitfalls

### Pitfall 1: `style.css` Token Namespace Mismatch
**What goes wrong:** Developer updates `--atlas-*` tokens in `frontend/src/index.css` (React) but the splash page uses `chat_app/static/style.css` which has `--color-*` tokens. The splash page won't pick up changes.
**Why it happens:** Two separate CSS files serve two separate apps (Flask pre-auth, React post-auth).
**How to avoid:** For the splash page updates, either (a) add `--atlas-*` declarations to `style.css`'s `:root` block, or (b) update splash classes to use hardcoded values matching the atlas palette. Option (a) is more maintainable.
**Warning signs:** Splash page looks correct in one theme but wrong in another; dark mode doesn't work for splash.

### Pitfall 2: Removing Dead Code Without Updating Tests
**What goes wrong:** `get_user_photo_bytes()` is removed from `chat_app/graph_client.py` but `tests/test_graph_client.py` still imports and tests it — 4 tests fail with `AttributeError`.
**Why it happens:** Dead code removal is incomplete if the test file isn't updated.
**How to avoid:** After removing the function, search for all test references (`grep -n "get_user_photo_bytes" tests/test_graph_client.py`) and delete or replace those 4 tests.
**Warning signs:** `AttributeError: module 'chat_app.graph_client' has no attribute 'get_user_photo_bytes'`

### Pitfall 3: DEBT-03 Test Regressions Scope
**What goes wrong:** There are 16 failing tests total in the test suite. DEBT-03 says "fix 3 test regressions (description phrasing, tool count assertion)". The 3 regressions that match this description are:
- `test_build_cmdlet_script_interactive` — expects `"Disconnect-ExchangeOnline"` in script's `finally` block (the finally block comment was changed to say disconnect is not needed)
- `test_build_cmdlet_script_cba` — same; also expects `$env:AZURE_CERT_THUMBPRINT` in script
- The test_server.py module docstring says "15 tools" but `test_list_tools_returns_all_17` checks for 17 (description phrasing in docstring, not a failing test)

The remaining 13 failures (test_tools_flow, test_tools_hybrid, test_integration) appear to be pre-existing regressions from earlier phases, NOT in scope for DEBT-03. The planner must be careful to only fix the 3 matching the phase description.

**How to avoid:** Run `python -m pytest tests/test_exchange_client.py -v` first to confirm the 2 cmdlet script tests fail. Check if DEBT-03 needs both exchange_client failures + one docstring fix, or a different subset.
**Warning signs:** Attempting to fix all 16 failures when only 3 are in scope.

### Pitfall 4: Profile Card `max-width` on Outer Container vs Inner Info
**What goes wrong:** `max-width: 320px` set on `.profile-card` prevents the card from stretching, but the info column text needs `overflow: hidden; text-overflow: ellipsis` for long names/titles.
**Why it happens:** Long email addresses or display names overflow if truncation isn't applied.
**How to avoid:** Add `overflow: hidden; text-overflow: ellipsis; white-space: nowrap` to `.profile-card-name` and `.profile-card-field` (already present for name; verify for email link).

### Pitfall 5: Search Results Scroll with Max 5 Rows
**What goes wrong:** Container `max-height` set to an arbitrary pixel value that doesn't correspond to "5 rows" when row height changes.
**Why it happens:** Row height is determined by padding (8px top + 8px bottom = 16px) + line-height (body: 20px + caption: 16px if email present = 36px with email, 20px without).
**How to avoid:** Use `max-height: 280px` (generous for 5 rows of mixed height) + `overflow-y: auto`. A scroll track will appear only when needed. Verify visually.

## Code Examples

Verified patterns from codebase inspection:

### Current Profile Card CSS (needs these specific changes)
```css
/* Source: frontend/src/index.css (current state) */
.profile-card {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 12px 16px;        /* CHANGE TO: padding: 12px */
  margin: 8px 0;
  background-color: var(--atlas-bg-elevated);
  border: 1px solid var(--atlas-stroke-2);  /* CHANGE TO: --atlas-stroke-1 */
  border-radius: 8px;
  /* ADD: max-width: 320px; */
}
```

### Target Search Results HTML Structure (React component change)
```tsx
// Source: frontend/src/components/ChatPane/SearchResultCard.tsx
// CHANGE: replace per-item .search-result-card divs
// WITH: single container + row divs

return (
  <div className="search-results">
    {data.results.slice(0, 5).map((item, idx) => (
      <div key={idx} className="search-result-row">
        <div className="search-result-primary-line">
          {item.name && <span className="search-result-name">{item.name}</span>}
          {item.jobTitle && <><span className="search-result-sep">·</span><span className="search-result-title">{item.jobTitle}</span></>}
          {item.department && <><span className="search-result-sep">·</span><span className="search-result-dept">{item.department}</span></>}
        </div>
        {item.email && (
          <div className="search-result-email-row">
            <a className="search-result-email" href={`mailto:${item.email}`}>{item.email}</a>
          </div>
        )}
      </div>
    ))}
  </div>
);
```

### Splash Page Atlas Token Declaration in style.css
```css
/* Add to :root block in chat_app/static/style.css */
/* Atlas Fluent 2 tokens for splash page parity */
--atlas-bg-canvas: #ffffff;
--atlas-bg-elevated: #f5f5f5;
--atlas-text-primary: #242424;
--atlas-text-secondary: #424242;
--atlas-text-tertiary: #616161;
--atlas-stroke-1: #d1d1d1;
--atlas-accent: #0f6cbd;
--atlas-accent-text: #ffffff;
--atlas-font-base: "Segoe UI Variable", "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", sans-serif;

/* And in [data-theme="dark"] block: */
--atlas-bg-canvas: #292929;
--atlas-bg-elevated: #141414;
--atlas-text-primary: #ffffff;
--atlas-text-secondary: #d6d6d6;
--atlas-stroke-1: #666666;
--atlas-accent: #115ea3;
```

### Dead Code Function Location
```python
# Source: chat_app/graph_client.py lines 274-305
def get_user_photo_bytes(user_id: str) -> bytes | None:
    """..."""
    # This function is NOT called anywhere in the application.
    # get_user_photo_96() at line 347 is the active photo function.
    # Remove lines 274-305 entirely.
```

### Schema Description Fix (DEBT-05)
```python
# Source: exchange_mcp/tools.py lines 414-417
# Current (incorrect):
"user_id": {
    "type": "string",
    "description": "The colleague's user ID from search results",  # vague
}
# The description should clarify this is a Graph API user object ID (GUID),
# not an email or UPN, to prevent LLM from passing wrong format.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-item card borders for search results | Single container + row dividers | This phase | Less border noise, matches Fluent 2 List |
| Lightning emoji (`⚡`) in splash | Geometric logo mark / wordmark | This phase | More professional, enterprise-appropriate |
| box-shadow on splash card | Border-only surface | This phase | Fluent 2 compliant |
| `--color-*` tokens on splash | `--atlas-*` tokens on splash | This phase | Visual parity with React app |

**Deprecated/outdated in this phase:**
- `.splash-icon` with emoji: replaced by SVG or CSS-drawn wordmark
- `.splash-card` with `box-shadow` and `border-radius: 16px`: replaced with Fluent 2 border + 12px radius
- `get_user_photo_bytes()`: dead function, replaced by `get_user_photo_96()` long ago

## Open Questions

1. **Which exact 3 tests are DEBT-03?**
   - What we know: 16 tests currently fail. DEBT-03 says "description phrasing, tool count assertion". Two are confirmed: `test_build_cmdlet_script_interactive` and `test_build_cmdlet_script_cba` (both expect `Disconnect-ExchangeOnline` in finally block). The third may be the `test_server.py` module docstring saying "15" instead of "17" (a documentation fix, not a code fix).
   - What's unclear: Whether "tool count assertion" refers to a live test failure or a comment/docstring inconsistency. Run `python -m pytest tests/ -v --tb=line 2>&1 | grep FAILED` to confirm.
   - Recommendation: In 18-03 plan, fix the 2 confirmed exchange_client test failures and the docstring inconsistency in test_server.py. Do NOT attempt to fix the test_tools_flow or test_tools_hybrid failures (13 tests) as those appear to be pre-existing regressions from earlier phases outside this scope.

2. **Atlas wordmark/logo for splash page**
   - What we know: CONTEXT says "replace lightning emoji with Atlas wordmark or simple geometric logo mark using `--atlas-accent` color". No SVG asset exists in the project.
   - What's unclear: Whether to use CSS-only (e.g., styled "A" text in accent color) or create an inline SVG.
   - Recommendation: Use a CSS-styled letter "A" or atlas wordmark rendered in `--atlas-accent` via CSS (no image assets needed). This is "Claude's Discretion" per CONTEXT.

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection:
  - `frontend/src/index.css` — all atlas CSS tokens and component classes
  - `frontend/src/components/ChatPane/ProfileCard.tsx` — current React component
  - `frontend/src/components/ChatPane/SearchResultCard.tsx` — current React component
  - `chat_app/templates/splash.html` — Jinja2 template
  - `chat_app/static/style.css` — Flask CSS with `--color-*` tokens
  - `chat_app/graph_client.py` — dead code location confirmed
  - `exchange_mcp/tools.py` — schema description for `get_colleague_profile`
  - `tests/test_exchange_client.py` — failing test assertions confirmed
  - `tests/test_graph_client.py` — 4 tests reference `get_user_photo_bytes`
  - `tests/test_tools_flow.py`, `tests/test_tools_hybrid.py` — pre-existing failures NOT in DEBT-03 scope

- Live test run: `python -m pytest tests/ --tb=short` — 16 failures confirmed

### Secondary (MEDIUM confidence)
- Fluent 2 design guidelines (training knowledge, March 2026): border-not-shadow for contained surfaces, 8px border-radius for cards, Segoe UI Variable font family
- Fluent 2 Persona component geometry (training knowledge): 48px photo, horizontal layout, name/title/dept/contact hierarchy

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all files directly inspected
- Architecture: HIGH — CSS classes and token usage directly read
- Pitfalls: HIGH — confirmed by live test runs and code inspection
- DEBT-03 scope: MEDIUM — 2 of 3 failing tests confirmed; third test unclear

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable — no fast-moving dependencies)
