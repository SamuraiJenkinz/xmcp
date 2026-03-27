# Phase 13: Infrastructure Scaffold - Research

**Researched:** 2026-03-27
**Domain:** React 19 + Vite 8 + Fluent UI v9 + Tailwind v4 hybrid SPA wired into Flask
**Confidence:** HIGH (all major stack items verified via official docs or current npm/GitHub)

## Summary

Phase 13 scaffolds a React 19 + TypeScript frontend inside the existing Flask app using Vite 8 as the build tool, Fluent UI v9 for components, and Tailwind v4 for layout utilities. The architecture is a hybrid SPA: Flask serves a Jinja2 shell at `/chat` and React mounts on `#app`. During development, Vite runs on :5173 and proxies `/api/*`, `/login`, `/logout`, `/auth/*` to Flask on :5000. Production is served by Flask's catch-all route from `frontend_dist/` when `ATLAS_UI=react` env var is set.

The most significant finding is that Tailwind v4 changed prefix syntax from v3. The CONTEXT.md specifies `tw-` prefix notation, but Tailwind v4 uses `tw:` (colon-variant syntax) — e.g., `tw:flex` not `tw-flex`. This is a locked user decision that needs reconciliation: either accept the v4 colon syntax or use a different collision strategy. The research recommends accepting v4 colon syntax and updating the convention.

Fluent UI v9 uses Griffel (CSS-in-JS) for internal styling. Tailwind classes applied via `className` prop work on Fluent components but specificity ordering can cause conflicts. Because Tailwind v4 with a prefix generates CSS variables prefixed with `--tw-` automatically, CSS variable collisions with Fluent tokens are minimal.

**Primary recommendation:** Scaffold with `npm create vite@latest frontend -- --template react-ts`, install `@fluentui/react-components@^9`, install `tailwindcss @tailwindcss/vite`, use `@import "tailwindcss" prefix(tw)` in the CSS, accept that classes are `tw:flex` not `tw-flex`, configure `build.outDir: '../frontend_dist'`, and add proxy config for the five route prefixes.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| vite | ^8.0.2 | Build tool and dev server | Current major; Rolldown-based; official React plugin v6; fastest dev server |
| @vitejs/plugin-react | ^6.x | React HMR + Refresh | Official plugin; v6 uses Oxc not Babel; ships with Vite 8 |
| react | ^19.x | UI framework | Locked decision; Fluent UI v9 is React-only |
| react-dom | ^19.x | DOM renderer | Peer of react |
| typescript | ^5.x | Type checking | Vite react-ts template default |
| @fluentui/react-components | ^9.73.x | Component library | Locked decision; Microsoft's Fluent 2 for React; v9 is current stable |
| tailwindcss | ^4.x | Layout utilities | Locked decision; v4 stable |
| @tailwindcss/vite | ^4.x | Vite plugin for Tailwind v4 | Official v4 integration; replaces PostCSS config approach from v3 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @types/react | ^19.x | React type definitions | TypeScript support; install alongside react |
| @types/react-dom | ^19.x | ReactDOM type definitions | TypeScript support |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| @tailwindcss/vite plugin | postcss + tailwindcss | v3 approach; v4 recommends Vite plugin for Vite projects |
| Vite 8 | Vite 6/7 | v8 is current; Rolldown bundler; v6/7 would need upgrade soon |
| npm | pnpm | Claude's discretion — npm is simpler for this project's current setup |

**Installation:**
```bash
# Scaffold (run from project root)
npm create vite@latest frontend -- --template react-ts

# Inside frontend/
cd frontend
npm install @fluentui/react-components
npm install tailwindcss @tailwindcss/vite
```

## Architecture Patterns

### Recommended Project Structure
```
frontend/
├── index.html               # Vite entry; <div id="app"></div>
├── vite.config.ts           # Proxy + outDir config
├── tsconfig.json            # TypeScript root config (references app + node)
├── tsconfig.app.json        # Browser target; strict; moduleResolution: bundler
├── package.json
└── src/
    ├── main.tsx             # ReactDOM.createRoot('#app')
    ├── App.tsx              # FluentProvider + webDarkTheme wrapper
    ├── index.css            # @import "tailwindcss" prefix(tw)
    ├── components/          # Empty in Phase 13; populated in Phase 14
    ├── hooks/               # SSE hooks in later phases
    └── api/                 # fetch wrappers in later phases
```

### Pattern 1: Vite Proxy Configuration
**What:** All `/api/*`, `/login`, `/logout`, `/auth/*` requests from Vite dev server are forwarded to Flask on :5000.
**When to use:** Dev mode only. In production, Flask serves everything directly.
**Example:**
```typescript
// Source: https://vite.dev/config/server-options
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: '../frontend_dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/login': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/logout': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/auth': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
})
```

### Pattern 2: Flask Catch-All Route with Feature Flag
**What:** Flask serves `frontend_dist/index.html` for all non-API routes when `ATLAS_UI=react`. Otherwise falls through to existing Jinja2 routes.
**When to use:** Production deployment; also dev if testing the built bundle.

```python
# In create_app() in chat_app/app.py
import os
from flask import send_from_directory

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), '..', 'frontend_dist')

@app.route('/react', defaults={'path': ''})
@app.route('/react/<path:path>')
def react_spa(path):
    """Catch-all for React SPA when ATLAS_UI=react."""
    if os.environ.get('ATLAS_UI') != 'react':
        # Fall through — handled by existing routes
        return redirect(url_for('index'))
    # Serve static assets if they exist
    full_path = os.path.join(FRONTEND_DIST, path)
    if path and os.path.exists(full_path):
        return send_from_directory(FRONTEND_DIST, path)
    return send_from_directory(FRONTEND_DIST, 'index.html')
```

**NOTE:** The catch-all pattern must NOT intercept `/api/*` routes — place it after the API blueprints. The recommended approach is a separate route prefix or an explicit check:

```python
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('api/') or path in ('login', 'logout') or path.startswith('auth/'):
        return 'Not found', 404
    if os.environ.get('ATLAS_UI') == 'react':
        return send_from_directory(FRONTEND_DIST, 'index.html')
    return redirect(url_for('index'))
```

### Pattern 3: FluentProvider Root Wrapper
**What:** `App.tsx` wraps the entire React tree in `FluentProvider` with `webDarkTheme`.
**When to use:** Always — components will not render correctly without it.

```typescript
// Source: https://fluent2.microsoft.design/get-started/develop
// src/App.tsx
import { FluentProvider, webDarkTheme } from '@fluentui/react-components'

export default function App() {
  return (
    <FluentProvider theme={webDarkTheme}>
      {/* Phase 14+ content */}
      <div className="tw:flex tw:min-h-screen">
        <p>Atlas React shell</p>
      </div>
    </FluentProvider>
  )
}
```

### Pattern 4: React 19 Mount Point
**What:** `main.tsx` mounts React on `#app` (the element injected by Flask's Jinja2 template).

```typescript
// Source: https://react.dev/blog/2024/12/05/react-19
// src/main.tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('app')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
```

**Important:** The element ID is `app` (matching Flask's Jinja2 template `<div id="app">`), not Vite's default `root`.

### Pattern 5: Tailwind v4 with Prefix
**What:** v4 prefix syntax uses colon-variant, not hyphen.

```css
/* Source: https://tailwindcss.com/docs/upgrade-guide */
/* src/index.css */
@import "tailwindcss" prefix(tw);
```

HTML usage:
```html
<!-- v4 prefix syntax — colon NOT hyphen -->
<div class="tw:flex tw:gap-4 tw:min-h-screen">
  <aside class="tw:w-64 tw:shrink-0">...</aside>
  <main class="tw:flex-1">...</main>
</div>
```

### Pattern 6: /api/me Endpoint
**What:** New Flask endpoint returns current user's display name and email from MSAL session.

```python
# In create_app() in chat_app/app.py
from chat_app.auth import login_required

@app.route('/api/me')
@login_required
def api_me():
    """Return current user's display name and email."""
    user = session.get('user', {})
    return jsonify({
        'displayName': user.get('name', ''),
        'email': user.get('preferred_username', ''),
        'oid': user.get('oid', ''),
    })
```

### Pattern 7: TypeScript Config for Vite + React
**What:** `tsconfig.app.json` optimized for Vite bundler resolution.

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

### Anti-Patterns to Avoid
- **Tailwind v3 `tw-` prefix syntax:** Writing `tw-flex` in HTML will NOT work with v4. Must be `tw:flex`.
- **`createRoot(document.getElementById('root')`):** Vite template defaults to `root`, but this project mounts on `#app`. Wrong ID = blank page.
- **Placing catch-all before API blueprints:** Flask route registration order matters. The catch-all `/<path:path>` MUST be registered last, after `conversations_bp`, `auth_bp`, `chat_bp`.
- **Using `rewrite` in Vite proxy for `/api`:** The Flask routes already have `/api/` prefixes. Don't strip `/api` in the proxy rewrite — Flask expects the full path.
- **Importing `@fluentui/react-components` without FluentProvider:** Components render visually broken without the provider.
- **Setting `base: './'` in vite.config:** This breaks absolute asset paths. Use `base: '/'` (default) since Flask serves the SPA at the root URL.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dev proxy to Flask | Custom express proxy middleware | Vite's built-in `server.proxy` | Already built into Vite; handles cookies, headers correctly |
| CSS variable collision with Fluent | Manual renaming of Fluent CSS vars | Tailwind prefix + Fluent's Griffel isolation | Fluent manages its own CSS via Griffel; Tailwind prefix isolates utility classes |
| Component library dark mode | Custom CSS dark theme from scratch | Fluent `webDarkTheme` token system | Griffel handles selector specificity and all interactive states |
| Prefix configuration file | `tailwind.config.js` with prefix option | `@import "tailwindcss" prefix(tw)` in CSS | v4 eliminated the JS config file; prefix is CSS-native now |
| Auth state in React | New OAuth flow or localStorage JWT | Existing Flask MSAL session + `/api/me` | Session cookie already set by existing auth; no new auth needed in Phase 13 |

**Key insight:** This phase is wiring, not building. Every major concern (auth, CSS themes, build tooling, proxy) has an off-the-shelf solution.

## Common Pitfalls

### Pitfall 1: Tailwind v4 Prefix Breaking Change
**What goes wrong:** Developer writes `tw-flex` (v3 style) expecting the prefix to work. Classes are silently ignored — elements have no layout styles.
**Why it happens:** CONTEXT.md specified `tw-` prefix following v3 conventions. Tailwind v4 changed the prefix to be a variant, using colon notation.
**How to avoid:** Use `@import "tailwindcss" prefix(tw)` and write `tw:flex`, `tw:grid`, `tw:gap-4` in JSX className props.
**Warning signs:** Tailwind classes have no visual effect despite appearing in markup.

### Pitfall 2: React StrictMode Double Effects in Dev
**What goes wrong:** `useEffect` callbacks fire twice during development. SSE connections, timers, or fetch calls may appear to double in logs.
**Why it happens:** React 19 StrictMode intentionally mounts/unmounts components twice in dev to catch cleanup bugs.
**How to avoid:** Always return cleanup functions from `useEffect`. This is a dev-only behavior; production is unaffected.
**Warning signs:** Console shows duplicate API calls or two SSE connections; goes away when built for production.

### Pitfall 3: Catch-All Route Capturing API Routes
**What goes wrong:** Flask's `/<path:path>` catch-all intercepts `/api/me`, `/api/photo/*`, `/chat/stream` before the API blueprints respond.
**Why it happens:** Flask registers catch-all last but `/<path:path>` is greedy.
**How to avoid:** Register the catch-all route LAST in `create_app()` AND add explicit guards: `if path.startswith('api/') or path in ('login', 'logout') or path.startswith('auth/'): abort(404)`.
**Warning signs:** API calls return HTML (index.html content) instead of JSON.

### Pitfall 4: outDir Points Inside Vite Project
**What goes wrong:** If `build.outDir` is relative and not escaped correctly, `frontend_dist/` ends up inside `frontend/` instead of at project root.
**Why it happens:** Vite's `outDir` is relative to the project root (where `vite.config.ts` lives, i.e., `frontend/`). To output to the parent, use `'../frontend_dist'`.
**How to avoid:** Set `build.outDir: '../frontend_dist'` and `build.emptyOutDir: true`.
**Warning signs:** `npm run build` creates `frontend/frontend_dist/` rather than `/frontend_dist/`.

### Pitfall 5: Flask Can't Find frontend_dist
**What goes wrong:** `send_from_directory(FRONTEND_DIST, 'index.html')` raises `NotFound` because the path is wrong or the directory doesn't exist.
**Why it happens:** Relative paths in `os.path.join` are relative to cwd, which may differ between dev and production.
**How to avoid:** Use `os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend_dist'))` to get an absolute path anchored to `chat_app/`.
**Warning signs:** Flask throws 404 or `OSError` when `ATLAS_UI=react` is set.

### Pitfall 6: Vite Proxy Does Not Apply to Production Build
**What goes wrong:** Developer tests with `npm run build` + `python start.py`, notices that `/api/me` calls fail — Vite proxy only works with `npm run dev`.
**Why it happens:** `server.proxy` is a dev-server feature only. The built bundle in `frontend_dist/` makes direct fetch calls to the same origin.
**How to avoid:** In production, the browser fetches `/api/me` from Flask directly (same origin). No proxy needed. Ensure fetch calls use relative URLs like `/api/me`, never hardcode `localhost:5173`.
**Warning signs:** API calls work in dev but 404 in production build.

### Pitfall 7: IIS ARR Buffering Blocks SSE (Phase 14+ concern)
**What goes wrong:** SSE streams from `/chat/stream` are buffered by IIS ARR, causing the React UI to appear frozen until the buffer fills.
**Why it happens:** ARR's default `responseBufferLimit` buffers response bodies before forwarding.
**How to avoid:** This is flagged in CONTEXT.md's specifics. Must configure `responseBufferLimit="0"` in IIS ARR's `applicationHost.config` manually (UI doesn't allow 0). Also set response headers `X-Accel-Buffering: no` and `Cache-Control: no-cache, no-transform`.
**Warning signs:** SSE works in direct Flask access but stalls through IIS ARR.

## Code Examples

### Complete vite.config.ts
```typescript
// Source: https://vite.dev/config/server-options + https://vite.dev/config/build-options
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  build: {
    outDir: '../frontend_dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/login': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/logout': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/auth': { target: 'http://127.0.0.1:5000', changeOrigin: true },
    },
  },
})
```

### Complete src/index.css
```css
/* Source: https://tailwindcss.com/docs/upgrade-guide */
@import "tailwindcss" prefix(tw);
```

### Flask /api/me Endpoint
```python
# Source: existing MSAL session structure in chat_app/auth.py
# session["user"] = result.get("id_token_claims") contains:
#   "name"                -> display name
#   "preferred_username"  -> email/UPN
#   "oid"                 -> Azure AD object ID

@app.route('/api/me')
@login_required
def api_me():
    user = session.get('user', {})
    return jsonify({
        'displayName': user.get('name', ''),
        'email': user.get('preferred_username', ''),
        'oid': user.get('oid', ''),
    })
```

### Flask Config for ATLAS_UI Feature Flag
```python
# In chat_app/config.py — add to Config class
ATLAS_UI: str = os.environ.get('ATLAS_UI', 'classic')
```

```python
# In create_app() — MUST be registered last
FRONTEND_DIST = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'frontend_dist')
)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    # Guard: don't capture API or auth routes
    _api_prefixes = ('api/', 'auth/', 'login', 'logout', 'chat/')
    if any(path == p or path.startswith(p) for p in _api_prefixes):
        return 'Not found', 404
    if app.config.get('ATLAS_UI') == 'react':
        asset = os.path.join(FRONTEND_DIST, path)
        if path and os.path.isfile(asset):
            return send_from_directory(FRONTEND_DIST, path)
        return send_from_directory(FRONTEND_DIST, 'index.html')
    return redirect(url_for('index'))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `tailwind.config.js` with `prefix: 'tw-'` | `@import "tailwindcss" prefix(tw)` in CSS; classes are `tw:flex` | Tailwind v4 (stable 2025) | Class syntax changed from `tw-flex` to `tw:flex` |
| Vite + esbuild (dev) + Rollup (prod) | Vite 8 + Rolldown unified | Vite 8 (2026) | Single pipeline; 10-30x faster; fewer dev/prod divergence bugs |
| `@vitejs/plugin-react` with Babel transforms | v6 uses Oxc; no Babel dependency | Released with Vite 8 (2026) | Smaller install; faster HMR |
| `forwardRef()` wrapper for ref passing | `ref` as a prop in React 19 | React 19 (Dec 2024) | Simpler component authoring |
| PostCSS config for Tailwind v4 | `@tailwindcss/vite` Vite plugin | Tailwind v4 release | Simpler setup for Vite projects; no postcss.config.js needed |

**Deprecated/outdated:**
- `tailwind.config.js` with `prefix: 'tw-'`: v4 no longer uses this file for prefix configuration
- `esbuild`-based Vite production builds: replaced by Rolldown in Vite 8
- `forwardRef`: deprecated in React 19; refs pass as props directly
- `ReactDOM.render()`: removed in React 19; use `createRoot()` only

## Open Questions

1. **Prefix syntax reconciliation with CONTEXT.md**
   - What we know: CONTEXT.md specifies `tw-` prefix, but Tailwind v4 uses `tw:` colon syntax
   - What's unclear: Whether the user intended v3 or is comfortable with the v4 variant syntax
   - Recommendation: Plans should document `tw:` syntax as the correct v4 form. The collision-prevention goal is identical — only the class notation differs. If the user requires `tw-flex` syntax, they would need to pin Tailwind to v3, which conflicts with the locked decision to use Tailwind v4.

2. **Jinja2 shell template modification scope**
   - What we know: Phase 13 requires `<div id="app"></div>` in the Flask template for React to mount
   - What's unclear: Whether modifying `chat.html` template is in scope for Phase 13 or deferred to Phase 14
   - Recommendation: Phase 13 must add `<div id="app"></div>` to `chat.html` (or a new template) — React cannot mount without it. This is minimal: a single div addition, not a redesign.

3. **Node.js version on deployment server**
   - What we know: Vite 8 requires Node.js 20.19+ or 22.12+
   - What's unclear: What Node.js version is installed on `usdf11v1784.mercer.com`
   - Recommendation: Verify before starting. The build could run locally or in CI and only `frontend_dist/` deployed, avoiding the Node.js requirement on the server entirely.

## Sources

### Primary (HIGH confidence)
- https://vite.dev/guide/ — Vite 8 scaffold command confirmed as v8.0.2
- https://vite.dev/config/server-options — Proxy configuration syntax verified
- https://vite.dev/config/build-options — `build.outDir` and `build.emptyOutDir` verified
- https://vite.dev/blog/announcing-vite8 — Vite 8 architecture, `@vitejs/plugin-react` v6, Node.js requirements
- https://react.dev/blog/2024/12/05/react-19 — React 19 stable, `createRoot`, StrictMode behavior
- https://tailwindcss.com/docs/upgrade-guide — v4 prefix syntax `@import "tailwindcss" prefix(tw)` → `tw:flex`
- https://fluent2.microsoft.design/get-started/develop — FluentProvider + webLightTheme/webDarkTheme setup pattern
- https://github.com/microsoft/fluentui/discussions/29666 — Official confirmation: Tailwind className works on Fluent components via className prop

### Secondary (MEDIUM confidence)
- WebSearch: `@fluentui/react-components` current version 9.73.5 (npm, 2026-03-26)
- WebSearch: Tailwind v4 prefix colon syntax confirmed by multiple GitHub discussions (#15745, #16046)
- WebSearch + GitHub: Griffel CSS-in-JS specificity; mergeClasses() ordering matters for overrides
- WebSearch: Vite 8 uses Rolldown; @vitejs/plugin-react v6 ships with it; v5 still compatible

### Tertiary (LOW confidence)
- WebSearch: IIS ARR `responseBufferLimit=0` for SSE — confirmed as documented technique but performance tradeoffs noted; apply in Phase 14 SSE verification

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified via official Vite 8 blog, React 19 blog, Tailwind upgrade guide, npm search
- Architecture: HIGH — proxy config, FluentProvider pattern, and catch-all route pattern verified against official docs
- Pitfalls: HIGH for prefix change (verified), MEDIUM for IIS ARR (WebSearch with MSDN forum source)

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable stack; Fluent UI v9 patch releases weekly but API is stable)
