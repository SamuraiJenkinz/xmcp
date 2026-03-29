# Phase 15: Design System - Research

**Researched:** 2026-03-29
**Domain:** Fluent 2 semantic color tokens, CSS custom properties, Tailwind v4 @theme, Segoe UI Variable typography
**Confidence:** HIGH (all key claims verified against installed package source or official docs)

---

## Summary

Phase 15 establishes a `--atlas-` semantic token layer mapped to Fluent 2 color values, applied globally to the React SPA. The core technical approach is straightforward: define `--atlas-*` CSS custom properties on `:root` (scoped by `[data-theme="dark"]` override), then use `@theme inline` in Tailwind v4 to expose select tokens as utility classes. Fluent UI's `FluentProvider` already injects its own CSS variables (e.g., `--colorNeutralBackground1`) on the provider's class — those can be referenced as the source-of-truth values inside the `--atlas-` layer.

The Fluent 2 dark theme surface hierarchy uses `colorNeutralBackground1-6` in descending lightness order: bg1 is the primary surface (#292929), bg2 is slightly deeper (#1f1f1f), bg3 deepest (#141414), creating a natural three-tier layering. Light mode inverts this: bg1 = white, bg2 = #fafafa, bg3 = #f5f5f5. These values are verified directly from the installed `@fluentui/tokens` source.

Segoe UI Variable is a Windows 11 system font (variable font with weight and opsz axes). It is NOT in the Fluent tokens `fontFamilyBase` string. To use it properly, the CSS font stack must be `"Segoe UI Variable", "Segoe UI", -apple-system, ...` with `font-optical-sizing: auto` for automatic opsz. The planner must decide where this override goes (body/`:root` layer, not inside `@theme`).

**Primary recommendation:** Define `--atlas-*` tokens in `index.css` on `:root`/`[data-theme="dark"]`, reference Fluent CSS variables where FluentProvider scope overlaps, keep Tailwind's `@theme inline` for bridging only color/font utilities that React components will use as classes. Legacy `style.css` (vanilla JS) keeps its existing `--color-*` tokens and is NOT migrated in Phase 15.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@fluentui/tokens` | 1.0.0-alpha.23 | Source of webDarkTheme/webLightTheme values and typographyStyles | Already installed; provides `colorNeutralBackground*`, font scale, brand colors |
| `@fluentui/react-components` | 9.73.5 | FluentProvider injects CSS variables at runtime | Already wired in App.tsx |
| `tailwindcss` | 4.2.2 | `@theme inline` directive bridges `--atlas-*` to utility classes | Already installed via @tailwindcss/vite |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@tailwindcss/vite` | 4.2.2 | Vite plugin for Tailwind v4 CSS-first config | Already in vite.config.ts |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| CSS custom properties on `:root` | `makeStyles` from Fluent | makeStyles is per-component; global token layer needs CSS variables |
| `@theme inline` for token bridge | Tailwind `extend` JS config | v4 is CSS-first; no tailwind.config.js needed |
| `--atlas-` prefix | `--fluent-` or raw Fluent var names | `--atlas-` creates the namespace boundary per requirements |

**Installation:** No new packages needed. All dependencies already installed.

---

## Architecture Patterns

### Recommended Project Structure

```
frontend/src/
├── index.css                  # PRIMARY: @import "tailwindcss", @theme inline, --atlas- tokens
├── styles/
│   └── tokens.css             # OPTIONAL: extract token definitions if index.css grows large
└── components/...             # Use --atlas- vars via className, no inline styles
```

```
chat_app/static/
└── style.css                  # UNCHANGED in Phase 15: retains --color-* tokens
```

### Pattern 1: --atlas- Token Layer on :root

**What:** Define semantic `--atlas-*` CSS custom properties on `:root` (light defaults) and `[data-theme="dark"]` (dark overrides). Values reference Fluent's computed color scale directly.

**When to use:** This is the only pattern for Phase 15. All styling in React components should consume `var(--atlas-*)`.

**Example:**
```css
/* index.css */
@import "tailwindcss" prefix(tw);

/* ── Atlas semantic tokens ── */
:root {
  /* Surface hierarchy (3 tiers) — Fluent 2 webLightTheme values */
  --atlas-bg-canvas:       #ffffff;   /* colorNeutralBackground1 light */
  --atlas-bg-surface:      #fafafa;   /* colorNeutralBackground2 light */
  --atlas-bg-elevated:     #f5f5f5;   /* colorNeutralBackground3 light */

  /* Text */
  --atlas-text-primary:    #242424;   /* colorNeutralForeground1 light = grey[14] */
  --atlas-text-secondary:  #424242;   /* colorNeutralForeground2 light = grey[26] */
  --atlas-text-tertiary:   #616161;   /* colorNeutralForeground3 light = grey[38] */
  --atlas-text-disabled:   #707070;   /* colorNeutralForeground4 light = grey[44] */

  /* Strokes */
  --atlas-stroke-1:        #d1d1d1;   /* colorNeutralStroke1 light = grey[82] */
  --atlas-stroke-2:        #e0e0e0;   /* colorNeutralStroke2 light = grey[88] */

  /* Brand accent (Microsoft blue) */
  --atlas-accent:          #0f6cbd;   /* colorBrandBackground light = brandWeb[80] */
  --atlas-accent-text:     #ffffff;   /* text on accent */
  --atlas-accent-subtle:   #ebf3fc;   /* brandWeb[160] — light tint for chips/hover */

  /* Status */
  --atlas-status-success:  var(--colorStatusSuccessForeground2, #107c10);
  --atlas-status-warning:  var(--colorStatusWarningForeground2, #bc4b09);
  --atlas-status-error:    var(--colorStatusDangerForeground2, #c50f1f);

  /* Typography */
  --atlas-font-base:       "Segoe UI Variable", "Segoe UI", "Segoe UI Web (West European)",
                           -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", sans-serif;
  --atlas-font-mono:       Consolas, "Courier New", Courier, monospace;

  /* Font sizes (Fluent 2 type ramp) */
  --atlas-text-caption2:   10px;
  --atlas-text-caption1:   12px;
  --atlas-text-body:       14px;
  --atlas-text-body2:      16px;
  --atlas-text-subtitle2:  16px;
  --atlas-text-subtitle1:  20px;
  --atlas-text-title3:     24px;
  --atlas-text-title2:     28px;
  --atlas-text-title1:     32px;

  /* Line heights (Fluent 2) */
  --atlas-lh-caption2:     14px;
  --atlas-lh-caption1:     16px;
  --atlas-lh-body:         20px;
  --atlas-lh-body2:        22px;
  --atlas-lh-subtitle2:    22px;
  --atlas-lh-subtitle1:    28px;
  --atlas-lh-title3:       32px;
  --atlas-lh-title2:       36px;
  --atlas-lh-title1:       40px;
}

[data-theme="dark"] {
  /* Surface hierarchy — Fluent 2 webDarkTheme values */
  --atlas-bg-canvas:       #292929;   /* colorNeutralBackground1 dark = grey[16] */
  --atlas-bg-surface:      #1f1f1f;   /* colorNeutralBackground2 dark = grey[12] */
  --atlas-bg-elevated:     #141414;   /* colorNeutralBackground3 dark = grey[8]  */

  /* Text */
  --atlas-text-primary:    #ffffff;   /* colorNeutralForeground1 dark = white */
  --atlas-text-secondary:  #d6d6d6;   /* colorNeutralForeground2 dark = grey[84] */
  --atlas-text-tertiary:   #adadad;   /* colorNeutralForeground3 dark = grey[68] */
  --atlas-text-disabled:   #999999;   /* colorNeutralForeground4 dark = grey[60] */

  /* Strokes */
  --atlas-stroke-1:        #666666;   /* colorNeutralStroke1 dark = grey[40] */
  --atlas-stroke-2:        #525252;   /* colorNeutralStroke2 dark = grey[32] */

  /* Brand accent (lighter for dark bg) */
  --atlas-accent:          #115ea3;   /* colorBrandBackground dark = brandWeb[70] */
  --atlas-accent-text:     #ffffff;
  --atlas-accent-subtle:   #061724;   /* brandWeb[10] — deep dark tint */
}

/* ── Base styles using Atlas tokens ── */
@layer base {
  html, body {
    font-family: var(--atlas-font-base);
    font-size: var(--atlas-text-body);
    line-height: var(--atlas-lh-body);
    color: var(--atlas-text-primary);
    background-color: var(--atlas-bg-canvas);
    font-optical-sizing: auto;
    -webkit-font-smoothing: antialiased;
  }

  code, pre, kbd {
    font-family: var(--atlas-font-mono);
  }
}

/* ── Tailwind @theme inline bridge (generates tw-utility classes) ── */
@theme inline {
  --color-atlas-canvas:   var(--atlas-bg-canvas);
  --color-atlas-surface:  var(--atlas-bg-surface);
  --color-atlas-elevated: var(--atlas-bg-elevated);
  --color-atlas-primary:  var(--atlas-text-primary);
  --color-atlas-accent:   var(--atlas-accent);
  --font-atlas:           var(--atlas-font-base);
  --font-atlas-mono:      var(--atlas-font-mono);
}
```

### Pattern 2: FluentProvider CSS Variables as Source of Truth

**What:** FluentProvider injects CSS variables onto its root element class (a generated class like `.r123`). The variable names are camelCase token names with `--` prefix: `--colorNeutralBackground1`, `--colorBrandBackground`, etc. These are available as `var(--colorNeutralBackground1)` inside the FluentProvider subtree.

**When to use:** When using Fluent-native components (Button, Input, etc.), they already consume `--colorNeutralBackground1` etc. via `makeStyles`. For custom components that exist inside FluentProvider, you can reference both `var(--atlas-*)` and `var(--colorNeutralBackground1)` — they are set in the same DOM context.

**Key insight:** `--atlas-*` values ARE the Fluent values — just aliased with the Atlas namespace. They don't need to reference `var(--colorNeutralBackground1)` dynamically because Phase 15 hard-codes the same values from source.

### Pattern 3: Tailwind `prefix(tw)` Isolation

**What:** The current `index.css` uses `@import "tailwindcss" prefix(tw)` — all Tailwind utilities are prefixed `tw-` (e.g., `tw-flex`, `tw-hidden`). This avoids collisions with the existing plain-class system from the vanilla JS CSS.

**When to use:** This prefix MUST be maintained. React components that currently use unprefixed class names (`.sidebar`, `.chat-header`, etc.) rely on CSS rules defined explicitly — they are NOT Tailwind utility classes.

**Example:**
```css
/* CORRECT in Tailwind v4 with prefix */
@import "tailwindcss" prefix(tw);
/* generates: tw-flex, tw-bg-atlas-canvas, etc. */
```

### Anti-Patterns to Avoid

- **Hardcoding hex values in components:** Never use `style={{ color: '#292929' }}` or `className="bg-[#292929]"` — always `var(--atlas-*)`.
- **Defining --atlas- tokens inside @theme:** `@theme` is for Tailwind utility generation only. Semantic token definitions belong on `:root`.
- **Using @theme (non-inline) with var() references:** Use `@theme inline` when a CSS variable reference is needed in generated utilities; plain `@theme` would resolve at build time against undefined variables.
- **Migrating style.css in Phase 15:** The legacy `style.css` uses `--color-*` naming and is consumed by vanilla JS templates (`splash.html`, `chat.html`). Phase 15 scope is React only.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Theme token values | Copy-paste Fluent hex values from memory | Use values verified from `@fluentui/tokens/lib` source | Training data lag; source is installed locally |
| Dark/light switching | Custom CSS class toggle | `[data-theme="dark"]` selector already functional from Phase 14 | Works with FluentProvider theme prop already set |
| Segoe UI Variable loading | @font-face rules | System font — available on Windows 11 by default, no loading needed | It's a built-in variable font on Windows 11; add to font-family stack |
| Typography scale | Custom ad-hoc sizes | Fluent 2 type ramp: 10/12/14/16/20/24/28/32/40/68px | Verified from `@fluentui/tokens/lib/global/fonts.js` |
| Color contrast validation | Manual calculation | Fluent 2 tokens are WCAG AA verified by Microsoft | The grey[14]/grey[84] on grey[16]/grey[12] surfaces meet 4.5:1 by design |

**Key insight:** The Fluent token values are hard numbers in installed source files — don't rely on training data when you can read the files directly.

---

## Common Pitfalls

### Pitfall 1: Fluent CSS Variables Are Scoped, Not Global

**What goes wrong:** Developer writes `background: var(--colorNeutralBackground1)` in a CSS rule applied outside the FluentProvider element. Variable is undefined; falls back to unset.

**Why it happens:** FluentProvider writes tokens to a CSS class on its wrapper `<div>`, not to `:root`. Variables are scoped to that subtree.

**How to avoid:** Use `var(--atlas-*)` tokens everywhere — these ARE on `:root`. Only use `var(--colorNeutralBackground1)` etc. inside components that are guaranteed children of FluentProvider (i.e., all React components in this app, since FluentProvider wraps the entire tree in App.tsx).

**Warning signs:** Color appears as white or transparent on elements outside React root.

### Pitfall 2: Tailwind Preflight Conflicts with Existing Styles

**What goes wrong:** Tailwind's preflight reset (via `@import "tailwindcss"`) zeroes out margins, makes headings unstyled, etc. This may conflict with styles in `index.css` that assume browser defaults.

**Why it happens:** `@import "tailwindcss" prefix(tw)` still injects preflight even with prefix. Preflight affects `h1-h6`, `ol`, `ul`, `img` globally.

**How to avoid:** Write explicit `@layer base` rules for elements that need styling. Headings inside React components must get explicit font-size/weight. Currently all component styling uses className with CSS rules in `index.css` — those rules will still apply and override preflight since they're more specific.

**Warning signs:** Heading text appears body-sized; list markers disappear.

### Pitfall 3: @theme inline Scope for Variable Resolution

**What goes wrong:** `@theme inline { --color-atlas-canvas: var(--atlas-bg-canvas); }` — if `--atlas-bg-canvas` is not defined on `:root` at the time Tailwind processes the CSS, the generated utility will embed an unresolved `var()`.

**Why it happens:** `@theme inline` resolves references when generating utilities. The `:root` definition must precede `@theme inline` in the CSS file.

**How to avoid:** Always define `--atlas-*` tokens on `:root` before the `@theme inline` block in `index.css`.

**Warning signs:** Tailwind utility classes like `tw-bg-atlas-canvas` appear transparent or incorrect.

### Pitfall 4: Segoe UI Variable Not Rendering on Non-Windows Systems

**What goes wrong:** Font stack falls through to `-apple-system` on macOS, Roboto on Android. This is expected and correct behavior. Optical sizing is automatic on all variable fonts.

**Why it happens:** Segoe UI Variable is a Windows 11 system font only. It is not available on other platforms without being shipped.

**How to avoid:** This is intentional for an enterprise Windows deployment. Ensure the fallback chain degrades gracefully: `"Segoe UI Variable", "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", sans-serif`.

**Warning signs:** None — fallback is expected and acceptable.

### Pitfall 5: Dark Mode Surface Hierarchy Inversion

**What goes wrong:** Developer uses background1 (lightest in dark mode = bg-canvas) where bg-elevated is expected. Surfaces appear flatter or inverted compared to Fluent 2 convention.

**Why it happens:** In light mode, bg1=white is the "top" surface and bg3 is recessed. In dark mode, bg1=#292929 is also the "top" surface (canvas) and bg3=#141414 is deeper/recessed. The naming is consistent: bg1 is always the primary interactive surface.

**How to avoid:**
- `--atlas-bg-canvas` (bg1): Main page background, message list background
- `--atlas-bg-surface` (bg2): Sidebar, panels, cards
- `--atlas-bg-elevated` (bg3): Elevated elements, modals, tooltips (appears darker/deeper in dark mode)

**Warning signs:** Sidebar appears brighter than main content area in dark mode.

---

## Code Examples

Verified patterns from installed source:

### Verified Dark Theme Background Values

From `@fluentui/tokens@1.0.0-alpha.23` lib source:
```
colorNeutralBackground1 dark = grey[16] = #292929   ← page canvas
colorNeutralBackground2 dark = grey[12] = #1f1f1f   ← surface / sidebar
colorNeutralBackground3 dark = grey[8]  = #141414   ← elevated / modal
colorNeutralBackground4 dark = grey[4]  = #0a0a0a   ← deep (rarely needed)
colorNeutralBackground5 dark = black    = #000000   ← deepest
```

### Verified Light Theme Background Values

From `@fluentui/tokens@1.0.0-alpha.23` lib source:
```
colorNeutralBackground1 light = white   = #ffffff   ← page canvas
colorNeutralBackground2 light = grey[98]= #fafafa   ← surface / sidebar
colorNeutralBackground3 light = grey[96]= #f5f5f5   ← elevated / recessed
colorNeutralBackground4 light = grey[94]= #f0f0f0   ← deeper recessed
```

### Verified Text Token Values

```
Dark mode:
  colorNeutralForeground1 = white    = #ffffff   ← primary
  colorNeutralForeground2 = grey[84] = #d6d6d6   ← secondary
  colorNeutralForeground3 = grey[68] = #adadad   ← tertiary/muted
  colorNeutralForeground4 = grey[60] = #999999   ← disabled/faint

Light mode:
  colorNeutralForeground1 = grey[14] = #242424   ← primary
  colorNeutralForeground2 = grey[26] = #424242   ← secondary
  colorNeutralForeground3 = grey[38] = #616161   ← tertiary/muted
  colorNeutralForeground4 = grey[44] = #707070   ← disabled/faint
```

### Verified Brand Accent Values

```
brandWeb palette (Microsoft blue):
  [70] = #115ea3   ← used for colorBrandBackground in dark mode
  [80] = #0f6cbd   ← used for colorBrandBackground in light mode
  [100]= #479ef5   ← lighter blue, used for colorBrandForeground1 in dark mode
  [160]= #ebf3fc   ← very light tint, useful for subtle backgrounds in light mode
  [10] = #061724   ← very dark tint, useful for subtle backgrounds in dark mode
```

### Verified Fluent 2 Type Ramp

From `@fluentui/tokens/lib/global/fonts.js`:
```
fontSizeBase100: '10px'   lineHeightBase100: '14px'   ← caption2
fontSizeBase200: '12px'   lineHeightBase200: '16px'   ← caption1
fontSizeBase300: '14px'   lineHeightBase300: '20px'   ← body1 (default)
fontSizeBase400: '16px'   lineHeightBase400: '22px'   ← body2
fontSizeBase500: '20px'   lineHeightBase500: '28px'   ← subtitle1
fontSizeBase600: '24px'   lineHeightBase600: '32px'   ← title3
fontSizeHero700: '28px'   lineHeightHero700: '36px'   ← title2
fontSizeHero800: '32px'   lineHeightHero800: '40px'   ← title1
fontSizeHero900: '40px'   lineHeightHero900: '52px'   ← largeTitle
fontSizeHero1000:'68px'   lineHeightHero1000:'92px'   ← display
```

Font weights: regular=400, medium=500, semibold=600, bold=700

### Segoe UI Variable CSS

```css
/* For HTML/web use with optical size auto-scaling */
body {
  font-family: "Segoe UI Variable", "Segoe UI", "Segoe UI Web (West European)",
               -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", sans-serif;
  font-optical-sizing: auto;  /* enables opsz axis automatically at each font-size */
}

/* Monospace for code blocks */
code, pre {
  font-family: Consolas, "Courier New", Courier, monospace;
}
```

Note: Fluent's `fontFamilyBase` does NOT include "Segoe UI Variable". To use it per success criteria, override the base font-family with the stack above, with "Segoe UI Variable" first.

### FluentProvider CSS Variable Injection (verified from source)

From `createCSSRuleFromTheme.js`:
```javascript
// FluentProvider writes: .r123abc { --colorNeutralBackground1: #292929; --colorBrandBackground: #115ea3; ... }
// Variable names are: '--' + camelCaseTockenName
// Example: tokens.colorNeutralBackground1 = 'var(--colorNeutralBackground1)'
```

These are scoped to the FluentProvider wrapper class, NOT on `:root`. Since the entire React app is wrapped, all React components can access them via `var(--colorNeutralBackground1)` — but the `--atlas-*` layer is more explicit and portable.

### Token Counting / Migration Blast Radius

Current CSS files:
- `frontend/src/index.css`: 1 line (`@import "tailwindcss" prefix(tw)`) — greenfield for Phase 15
- `chat_app/static/style.css`: ~80 `--color-*` token definitions + ~1180 lines of CSS rules — NOT in scope for Phase 15

React components use class names (`className="message assistant-message"`) that currently have no CSS rules defined in `index.css` — these are carried forward from the vanilla JS `style.css` pattern but will not be styled by `style.css` in React mode. The React components need their own CSS rules which will be added in Phase 16+.

**Phase 15 scope conclusion:** Write `--atlas-*` tokens into `index.css` + `@layer base` for body/typography. No React component styling required in this phase. Style.css migration deferred to Phase 18 or later.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `tailwind.config.js` JS config | `@theme` CSS-first in v4 | Tailwind v4 (2024) | No config file needed; `@theme inline` for variable refs |
| `@fluentui/react-components` inline `makeStyles` only | CSS variables from FluentProvider accessible globally | v9 (2022+) | Can use Fluent tokens in plain CSS via `var(--colorNeutralBackground1)` |
| `fontFamilyBase` without variable font | Still no Segoe UI Variable in Fluent tokens (v1.0.0-alpha.23) | Not changed yet | Must manually override font stack for Windows 11 variable font |

**Deprecated/outdated:**
- `tailwind.config.js`: Not used in v4, no file exists in project
- `@apply` directive: Still available but not recommended for custom token definitions

---

## Open Questions

1. **Accent color personality: strict neutral vs brand injection**
   - What we know: brandWeb palette is Microsoft's blue (#0f6cbd light, #115ea3 dark). The current vanilla JS `style.css` uses `#2563eb` (a brighter blue, not from brandWeb). Fluent 2 recommendations use brand color sparingly (interactive elements, focus indicators, selected states).
   - What's unclear: Whether "Atlas" should introduce any brand differentiation or stay strict Microsoft blue.
   - Recommendation: Stay with brandWeb[80] (#0f6cbd) for light and brandWeb[70] (#115ea3) for dark. This is the true Fluent 2 value and looks identical to Microsoft 365/Copilot. No custom brand injection in Phase 15.

2. **Code block background in dark mode**
   - What we know: The existing `style.css` uses Catppuccin Mocha (#1e1e2e) for JSON code blocks — intentionally dark even in light mode.
   - What's unclear: Should `--atlas-bg-code` follow Fluent neutral or stay Catppuccin?
   - Recommendation: Keep a dedicated `--atlas-bg-code` token. Default to colorNeutralBackground4 (very dark in both modes) but the exact value is a discretionary call for Phase 16 when code block styling is implemented.

3. **Sidebar vs canvas surface assignment**
   - What we know: In Fluent 2 Teams/Copilot, the sidebar typically uses bg2 (slightly recessed) and the main content area uses bg1 (lightest). This gives the sidebar a slightly darker appearance.
   - Recommendation: Assign canvas = bg1 to chat pane background, surface = bg2 to sidebar and panels. This matches Copilot's pattern.

---

## Sources

### Primary (HIGH confidence)
- `@fluentui/tokens@1.0.0-alpha.23` lib source files (installed locally):
  - `lib/global/colors.js` — grey scale hex values
  - `lib/alias/darkColor.js` — dark theme token mappings
  - `lib/alias/lightColor.js` — light theme token mappings
  - `lib/global/brandColors.js` — brandWeb palette
  - `lib/global/fonts.js` — font sizes, line heights, font families
  - `lib/global/typographyStyles.js` — named type styles (body1, caption1, etc.)
  - `lib/tokens.js` — CSS variable name strings (e.g., `'var(--colorNeutralBackground1)'`)
  - `react-provider/lib/components/FluentProvider/createCSSRuleFromTheme.js` — variable injection mechanism

- Tailwind CSS v4 official docs (https://tailwindcss.com/docs/configuration, https://tailwindcss.com/docs/preflight):
  - `@theme inline` behavior verified
  - Preflight behavior verified (does NOT set font-family on body)
  - `prefix(tw)` already in use confirmed

- Microsoft Windows typography docs (https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/typography):
  - Segoe UI Variable is a Windows 11 system font
  - Weight axis (wght) and optical size axis (opsz)
  - `font-optical-sizing: auto` is correct for web use

### Secondary (MEDIUM confidence)
- Fluent 2 typography page (https://fluent2.microsoft.design/typography): Confirmed type ramp structure matches Fluent tokens source

### Tertiary (LOW confidence)
- Fluent 2 surface hierarchy layer naming: The mapping of bg1=canvas, bg2=sidebar, bg3=elevated is derived from inspecting token values and comparing with visual conventions in Microsoft 365 products. Not explicitly documented in a fetched source.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified from installed node_modules source
- Token values: HIGH — read directly from installed package lib files
- Architecture patterns: HIGH — verified Tailwind v4 @theme inline behavior from official docs
- Segoe UI Variable: HIGH — verified from official Microsoft docs
- Surface hierarchy layer names: MEDIUM — inferred from values + Microsoft product observation
- Status colors: MEDIUM — token names verified, exact values depend on sharedColorMapping at runtime

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (Fluent tokens in alpha; check if breaking changes if >30 days)
