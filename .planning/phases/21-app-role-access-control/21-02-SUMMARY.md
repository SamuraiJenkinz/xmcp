---
phase: 21
plan: "02"
name: "Frontend Auth Status Discrimination and AccessDenied Component"
subsystem: "frontend-auth"
one-liner: "AuthContext status discriminator (loading/authenticated/unauthenticated/forbidden/error) with AccessDenied Fluent 2 card showing UPN copy and mailto to admin"
tags: [react, typescript, fluent2, auth, access-control, sse]

dependency-graph:
  requires:
    - "21-01: role_required decorator — provides structured 403 JSON with upn field"
  provides:
    - "fetchMe discriminated result distinguishing 401 from 403"
    - "AuthContext with AuthStatus union and forbidden state carrying UPN"
    - "AccessDenied component: Fluent 2 centered card with UPN copy button and mailto"
    - "AuthGuard with distinct forbidden branch rendering AccessDenied"
    - "SSE hook 401/403 handling via page reload to re-trigger AuthGuard"
  affects:
    - "All future frontend auth consumers — useAuth() now returns status instead of loading boolean"

tech-stack:
  added: []
  patterns:
    - "Discriminated union for auth state (status field replaces loading boolean)"
    - "AuthGuard renders AccessDenied outside ThreadProvider/ChatProvider to prevent cascading 403s"
    - "SSE hook reload on 401/403 avoids mid-session auth failure being surfaced as stream error"
    - "Fluent 2 makeStyles with tokens for dark/light mode support"

file-tracking:
  created:
    - frontend/src/components/AccessDenied.tsx
  modified:
    - frontend/src/types/index.ts
    - frontend/src/api/me.ts
    - frontend/src/contexts/AuthContext.tsx
    - frontend/src/App.tsx
    - frontend/src/hooks/useStreamingMessage.ts

decisions:
  - id: "D-21-02-A"
    choice: "AuthStatus discriminated union on AuthContext instead of boolean flags"
    rationale: "Single status field is exhaustive — compiler enforces all branches are handled; extensible without adding new booleans"
    alternatives: ["Separate loading/forbidden/error booleans"]
  - id: "D-21-02-B"
    choice: "error status redirects to /login rather than showing error UI"
    rationale: "Network failure on /api/me is indistinguishable from session expiry from user's perspective; re-auth is the safe recovery path"
    alternatives: ["Show error banner and retry button"]
  - id: "D-21-02-C"
    choice: "AccessDenied renders before ThreadProvider/ChatProvider mount"
    rationale: "Providers make API calls that would 403 — rendering them for a forbidden user would cascade errors into the context layer"
    alternatives: ["Render providers and handle errors inside them"]
  - id: "D-21-02-D"
    choice: "SSE 401/403 triggers window.location.reload() instead of calling onError"
    rationale: "A role revocation or session expiry mid-stream should show AuthGuard state (login or AccessDenied), not an error toast inside the chat UI"
    alternatives: ["Show error message in chat and let user manually refresh"]

metrics:
  duration: "~12 minutes"
  tasks-completed: 2
  tasks-total: 2
  completed: "2026-04-02"
---

# Phase 21 Plan 02: Frontend Auth Status Discrimination and AccessDenied Component Summary

## What Was Built

Extended the React frontend to distinguish 401 (unauthenticated) from 403 (authenticated but missing Atlas.User role) and render a clear, actionable AccessDenied page for the 403 case.

**Task 1: fetchMe, types, AuthContext**

- `types/index.ts`: Added `roles: string[]` to `User`, added `AuthStatus` discriminated union (`loading | authenticated | unauthenticated | forbidden | error`), added `ForbiddenResponse` interface matching the 21-01 backend 403 JSON shape
- `api/me.ts`: Rewrote `fetchMe` to return a discriminated result — `{ status: 'ok'; user }`, `{ status: 'unauth' }`, or `{ status: 'forbidden'; upn }` — extracting the UPN from the 403 body
- `contexts/AuthContext.tsx`: Replaced `loading` boolean with `status` field; added `upn: string | null` populated on forbidden state; `useAuth()` hook interface preserved for all consumers

**Task 2: AccessDenied component, AuthGuard, SSE hook**

- `components/AccessDenied.tsx`: Fluent 2 centered card on full viewport — ShieldKeyhole24Regular icon, "Access Denied" title, explanatory body text, UPN display with inline copy button (checkmark feedback for 1500ms, same pattern as CopyButton.tsx), "Request Access" primary button as mailto anchor with pre-filled subject and UPN body. `VITE_ADMIN_EMAIL` env var with `it-admin@mercer.com` fallback. Dark/light mode via Fluent tokens.
- `App.tsx`: Added AccessDenied import; AuthGuard now switches on `status` — loading spinner, forbidden → AccessDenied, unauthenticated/error → /login redirect, authenticated → children. AccessDenied renders before ThreadProvider/ChatProvider mount.
- `hooks/useStreamingMessage.ts`: Added 401/403 branch in `!res.ok` block — calls `window.location.reload()` so AuthGuard re-evaluates and shows correct UI; non-401/403 errors still surface via `onError` callback.

## Verification Results

- `npx tsc --noEmit` — zero errors
- `npm run build` — succeeded (559 KB bundle, chunk size warning is pre-existing)
- AccessDenied in App.tsx: import and two render sites confirmed
- `'forbidden'` in fetchMe, AuthContext, AuthGuard, types — all confirmed
- `VITE_ADMIN_EMAIL` in AccessDenied — confirmed
- `window.location.reload` in SSE hook — confirmed

## Decisions Made

| Decision | Choice | Rationale |
|---|---|---|
| D-21-02-A | AuthStatus discriminated union | Exhaustive — compiler enforces all branches |
| D-21-02-B | error → /login redirect | Network failure is indistinguishable from session expiry |
| D-21-02-C | AccessDenied before providers | Prevents cascading 403s from ThreadProvider/ChatProvider API calls |
| D-21-02-D | SSE 401/403 → reload | Shows correct AuthGuard state rather than error toast in chat UI |

## Deviations from Plan

None — plan executed exactly as written. Icon `ShieldKeyhole24Regular` was confirmed available in @fluentui/react-icons v2.0.323 before writing the component.

## Next Phase Readiness

Phase 21 is complete. The full access control chain is now implemented:
- Backend: `role_required` decorator enforces Atlas.User on all 9 protected routes (21-01)
- Frontend: `fetchMe` discriminates 401/403, AuthGuard renders AccessDenied for 403 (21-02)

**Remaining admin dependency:** Atlas.User App Role must be created in Entra admin center and the IT engineers group assigned before end-to-end testing is possible. This is an external dependency, not a code blocker.
