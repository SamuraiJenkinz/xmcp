# Phase 12: Profile Card Frontend + System Prompt - Research

**Researched:** 2026-03-25
**Domain:** Vanilla JS DOM construction, CSS layout with CSS variables, SSE event handling, OpenAI system prompt design
**Confidence:** HIGH

---

## Summary

Phase 12 is entirely frontend-and-prompt work. The backend (Phase 11) is fully shipped: two MCP tools (`search_colleagues`, `get_colleague_profile`) are wired, `photo_url` is always `/api/photo/{user_id}?name=First+Last` in the profile result, and the photo proxy always returns HTTP 200. Phase 12 has three clean deliverables:

1. A `addProfileCard()` function in `app.js` that reads the `get_colleague_profile` tool result JSON and builds a DOM card. The card is injected into the assistant message via the existing `addToolPanel` / `createAssistantMessage` infrastructure.
2. New CSS classes in `style.css` for the horizontal card layout — photo circle on left, four text fields stacked right — using the existing CSS custom property (variable) system. Dark and light mode are free because variables are already defined.
3. A new "Colleague Lookup" block in `SYSTEM_PROMPT` in `openai_client.py` that tells Atlas when to call each tool, how to chain them (single result → auto-call get_colleague_profile), and what the card rendering means.

There are no new dependencies. No backend changes. No new Python files.

**Primary recommendation:** Inject the profile card into the assistant message content div using the same insertion point as tool panels (`insertBefore(details, textNode)`). The card sits above the streaming text, just like a tool panel does today.

---

## Standard Stack

### Already in place (no new deps)

| Component | Where | Role in Phase 12 |
|-----------|-------|-----------------|
| Vanilla JS (ES5) | `chat_app/static/app.js` | DOM builder for profile card |
| CSS custom properties | `chat_app/static/style.css` | Card styling via existing tokens |
| SSE `tool` event | `chat_app/chat.py` → `app.js` | Trigger point for card rendering |
| `get_colleague_profile` tool result | `exchange_mcp/tools.py` | JSON data source for card fields |
| `/api/photo/<user_id>?name=` route | `chat_app/app.py` | Photo `<img>` src |
| `SYSTEM_PROMPT` string | `chat_app/openai_client.py` | Where colleague lookup block is added |

**No new Python packages or npm modules required.**

---

## Architecture Patterns

### Pattern 1: SSE `tool` event payload (confirmed from source)

When the tool-calling loop finishes a `get_colleague_profile` call, `chat.py` emits:

```
data: {"type":"tool","name":"get_colleague_profile","status":"success","params":{"user_id":"alice@company.com"},"result":"{\"name\":\"Alice Chen\",\"jobTitle\":\"Engineer\",\"department\":\"IT\",\"email\":\"alice@company.com\",\"photo_url\":\"/api/photo/guid-here\"}"}
```

Key observations (verified in source):
- `event.result` is a **JSON string** (double-serialized: the tool handler dict is `json.dumps()`-ed into the SSE `result` field)
- `event.name` is the string `"get_colleague_profile"`
- The `photo_url` field is always present — it points to `/api/photo/{user_id}` without the `?name=` param
- The planner must note: `addProfileCard()` should append `?name=` with the profile's name before setting `img.src`

### Pattern 2: Existing `addToolPanel` injection point (confirmed from app.js lines 183–248)

The `createAssistantMessage()` closure returns an `addToolPanel` method that:
```javascript
els.content.insertBefore(details, textNode);  // inserts before the text node
```

Profile card injection must follow the **same `insertBefore(card, textNode)` pattern** so cards appear above the assistant text response. The `els.content` div is closed over inside `createAssistantMessage()` — the card builder must be called from within that closure as a new method, exactly like `addToolPanel`.

### Pattern 3: Detecting `get_colleague_profile` in the SSE handler

In `app.js` `processLine()`, the `tool` event branch currently calls `addToolPanel()` unconditionally for all tools. Phase 12 adds a conditional branch:

```javascript
if (event.type === 'tool') {
    assistantMsg.removeDots();
    if (activeChip) {
        assistantMsg.markToolDone(activeChip);
    }
    if (event.name === 'get_colleague_profile' && event.status === 'success') {
        // Parse result JSON and build profile card
        addProfileCard(assistantMsg, event.result);
        activeChip = null;  // No collapsible panel for profile tools
    } else {
        activeChip = assistantMsg.addToolPanel(
            event.name,
            event.params || {},
            event.result || null,
            event.status || 'success'
        );
    }
}
```

This keeps the existing tool panel behavior for all other tools and inserts the card for profile results.

### Pattern 4: `addProfileCard()` function structure

`addProfileCard` receives the assistantMsg object (to call `insertBeforeText`) and the raw `event.result` string.

```javascript
function addProfileCard(assistantMsg, resultJson) {
    var profile;
    try {
        profile = JSON.parse(resultJson);
    } catch (e) {
        return;  // Malformed result — fail silently, don't break the stream
    }
    if (!profile || typeof profile !== 'object' || !profile.name) {
        return;  // Not a profile result (e.g., error message dict)
    }

    var card = document.createElement('div');
    card.className = 'profile-card';

    // Photo
    var img = document.createElement('img');
    img.className = 'profile-card-photo';
    img.alt = profile.name || '';
    var photoSrc = profile.photo_url || '';
    if (photoSrc && profile.name) {
        photoSrc += '?name=' + encodeURIComponent(profile.name);
    }
    img.src = photoSrc;
    card.appendChild(img);

    // Text block
    var info = document.createElement('div');
    info.className = 'profile-card-info';

    var nameEl = document.createElement('div');
    nameEl.className = 'profile-card-name';
    nameEl.textContent = profile.name || '';
    info.appendChild(nameEl);

    if (profile.jobTitle) {
        var titleEl = document.createElement('div');
        titleEl.className = 'profile-card-field';
        titleEl.textContent = profile.jobTitle;
        info.appendChild(titleEl);
    }
    if (profile.department) {
        var deptEl = document.createElement('div');
        deptEl.className = 'profile-card-field profile-card-dept';
        deptEl.textContent = profile.department;
        info.appendChild(deptEl);
    }
    if (profile.email) {
        var emailEl = document.createElement('a');
        emailEl.className = 'profile-card-email';
        emailEl.href = 'mailto:' + profile.email;
        emailEl.textContent = profile.email;
        info.appendChild(emailEl);
    }

    card.appendChild(info);
    assistantMsg.insertCard(card);  // new method on assistantMsg closure
}
```

The `insertCard` method on the closure is minimal:
```javascript
insertCard: function(cardEl) {
    els.content.insertBefore(cardEl, textNode);
    scrollToBottom();
},
```

### Pattern 5: Photo URL with name query param

The Phase 11 proxy accepts `?name=First+Last`. The `get_colleague_profile` tool result includes `photo_url` as `/api/photo/{user_id}` (no name param — confirmed in `tools.py` line 1957). The card builder must append `?name=` before setting `img.src`. Use `encodeURIComponent(profile.name)` which encodes spaces as `%20` (valid, proxy uses `name.strip().split()` to parse).

### Pattern 6: CSS card layout using existing variables

The card uses only existing CSS custom properties — no new color values needed. Horizontal layout with flexbox:

```css
.profile-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    margin: 6px 0;
    border: 1px solid var(--color-border);
    border-radius: 10px;
    background: var(--color-bg-subtle);
    max-width: 360px;
    transition: background-color 0.2s ease, border-color 0.2s ease;
}

.profile-card-photo {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    object-fit: cover;
    flex-shrink: 0;
    background: var(--color-bg-muted);  /* while loading */
}

.profile-card-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
}

.profile-card-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.profile-card-field {
    font-size: 12px;
    color: var(--color-text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.profile-card-dept {
    color: var(--color-text-muted);
}

.profile-card-email {
    font-size: 12px;
    color: var(--color-brand);
    text-decoration: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.profile-card-email:hover {
    text-decoration: underline;
}
```

Dark mode is fully automatic — all values reference existing `--color-*` variables that already have `[data-theme="dark"]` overrides in `style.css`.

### Pattern 7: System prompt structure (existing SYSTEM_PROMPT in openai_client.py)

The current prompt is a single string with numbered rules (lines 35–45 in `openai_client.py`). The "Colleague Lookup" block must be appended as a new section after the existing rules. This keeps existing Exchange rules intact.

Structure of new block:
```
## Colleague Lookup

You have two tools for finding colleagues:
- search_colleagues: Use when asked to find a colleague by name or email (e.g., 'find Jane Smith', 'who is alice@company.com?'). Returns a list of up to 10 matches with name, title, department, and email. Does NOT return photos — call get_colleague_profile for that.
- get_colleague_profile: Use when you have a specific email or ID and want the full profile card with photo. Requires a user_id (email address or Azure AD GUID).

Rules:
7. When search_colleagues returns exactly 1 match, immediately call get_colleague_profile with that result's email as user_id — do not ask the user to confirm first.
8. When search_colleagues returns multiple matches, list them as a numbered list (name, title, department) and ask which person the user wants the full profile for.
9. Never call get_colleague_profile speculatively. Only call it when you have a specific user email or ID.
10. After retrieving a profile with get_colleague_profile, do NOT reproduce the card fields in your text response — the UI renders the card automatically from the tool result. Just confirm briefly (e.g., "Here's Jane Smith's profile.").
```

### Recommended Project Structure Changes

```
chat_app/
├── static/
│   ├── app.js        # ADD: addProfileCard(), insertCard method on createAssistantMessage, branch in processLine
│   └── style.css     # ADD: .profile-card, .profile-card-photo, .profile-card-info, .profile-card-name, .profile-card-field, .profile-card-dept, .profile-card-email
└── openai_client.py  # MODIFY: SYSTEM_PROMPT — append Colleague Lookup section, renumber rules 7-10
```

### Anti-Patterns to Avoid

- **Rendering profile cards from markdown text:** The LLM must not be relied upon to format the card. The card must come from the tool result JSON. System prompt rule 10 enforces this.
- **Showing a collapsible tool panel for profile results:** Profile cards replace the standard `<details>` panel for `get_colleague_profile`. Show the card instead.
- **Showing a tool panel AND a card:** Only one or the other. Skip `addToolPanel` for `get_colleague_profile` success events.
- **Setting `img.src` to bare `/api/photo/{user_id}` without `?name=`:** Works (proxy returns `?` placeholder), but initials avatar is better UX. Always append `?name=`.
- **Hardcoding colors in card CSS:** Every color must use a `var(--color-*)` token. The dark mode toggle (`data-theme="dark"`) already handles all token overrides.
- **Relying on `event.result` being a parsed object:** `event.result` in the SSE stream is always a JSON string (`chat.py` puts the tool result dict through `json.dumps`). Must call `JSON.parse()` inside `addProfileCard`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dark mode card styling | New color variables | Existing `--color-*` tokens | Already have 15+ tokens covering border, bg, text, brand for both modes |
| Photo fallback | Frontend `onerror` handler | Existing proxy always returns 200 | Phase 11 proxy absorbs 404, returns SVG, no frontend error path needed |
| Multiple-card layout | Custom grid/masonry | DOM sequence: call addProfileCard once per profile | Multiple profiles = multiple cards stacked vertically in the message |
| Photo URL construction | Complex URL builder | Simple string concat + `encodeURIComponent` | Only one query param, no library needed |

---

## Common Pitfalls

### Pitfall 1: `event.result` is double-serialized

**What goes wrong:** Code tries to access `event.result.name` directly, gets `undefined`.

**Why it happens:** The SSE `result` field is a JSON-encoded string of the tool handler's return dict. `event.result` is a raw string like `"{\"name\":\"Alice Chen\",...}"`. It must be parsed with `JSON.parse()` first.

**How to avoid:** Always do `var profile = JSON.parse(event.result)` inside `addProfileCard`. Wrap in try/catch — malformed JSON should fail silently.

**Warning signs:** `profile.name` is `undefined` even though the raw result contains the name.

### Pitfall 2: Profile card shows on `get_colleague_profile` error results

**What goes wrong:** The tool returns `{"message": "No profile found for user ID '...'."}` on failure. If `addProfileCard` is called for all `get_colleague_profile` events regardless of `status`, it tries to build a card from a `message`-only object and renders a blank/broken card.

**How to avoid:** Only call `addProfileCard` when `event.status === 'success'`. For error status, fall back to the standard `addToolPanel` to show the error message in the collapsible panel.

**Warning signs:** Empty profile card with no name rendered when a lookup fails.

### Pitfall 3: Photo `<img>` broken during SSE stream before finalize

**What goes wrong:** The browser fetches `/api/photo/...` immediately when `img.src` is set. If the session has expired (user navigated away and back), the proxy returns a 302 redirect to `/` which renders HTML as a broken image.

**Why it happens:** `@login_required` on the photo proxy redirects unauthenticated requests.

**How to avoid:** This is unavoidable and acceptable — if the session expired, the whole page redirects to login. The broken image only appears briefly before redirect.

### Pitfall 4: System prompt rule 10 not specific enough — Atlas still narrates card fields

**What goes wrong:** Atlas says "Jane Smith is a Software Engineer in the IT department. Her email is jane@company.com." after the profile card is rendered, duplicating information.

**Why it happens:** Without explicit instruction, the LLM defaults to summarizing tool results in text.

**How to avoid:** Rule 10 must explicitly say "do NOT reproduce the card fields in your text response — the UI renders the card automatically." Include a concrete example of what Atlas should say instead.

### Pitfall 5: `?name=` query param encoding

**What goes wrong:** Names with special characters (e.g., `O'Brien`, `García`) break the URL.

**How to avoid:** Use `encodeURIComponent(profile.name)` — not `encodeURI` or manual space-to-`+` replacement. `encodeURIComponent` encodes all non-alphanumeric characters safely.

### Pitfall 6: Tool panel shown briefly before card for fast results

**What goes wrong:** `activeChip = assistantMsg.addToolPanel(...)` creates the `<details>` element before the tool result arrives. For the existing pattern, this is fine. But if the card branch mistakenly calls `addToolPanel` first, then the card, both appear.

**How to avoid:** For `get_colleague_profile` success events, skip `addToolPanel` entirely. The branch must be exclusive: either panel or card, never both.

### Pitfall 7: Auto-call rule conflicts with explicit multi-result scenarios

**What goes wrong:** System prompt tells Atlas to auto-call `get_colleague_profile` on single results, but Atlas sometimes auto-calls it for the first result of multi-result searches.

**How to avoid:** Rule 7 is conditional: "exactly 1 match." Rule 8 covers "multiple matches." The phrasing must be unambiguous. Test with: "Find people named Smith" (expect list) vs "Find Jane Smith" (expect card).

---

## Code Examples

### Complete `addProfileCard` function and `insertCard` method (verified pattern)

```javascript
// Source: derived from existing addToolPanel pattern in app.js
function addProfileCard(assistantMsg, resultJson) {
    var profile;
    try {
        profile = JSON.parse(resultJson);
    } catch (e) {
        return;
    }
    // Guard: must have at minimum a name field
    if (!profile || typeof profile !== 'object' || !profile.name) {
        return;
    }

    var card = document.createElement('div');
    card.className = 'profile-card';

    // --- Photo ---
    var img = document.createElement('img');
    img.className = 'profile-card-photo';
    img.alt = profile.name;
    var src = profile.photo_url || '';
    if (src) {
        src += '?name=' + encodeURIComponent(profile.name);
    }
    img.src = src;
    card.appendChild(img);

    // --- Info block ---
    var info = document.createElement('div');
    info.className = 'profile-card-info';

    var nameEl = document.createElement('div');
    nameEl.className = 'profile-card-name';
    nameEl.textContent = profile.name;
    info.appendChild(nameEl);

    if (profile.jobTitle) {
        var titleEl = document.createElement('div');
        titleEl.className = 'profile-card-field';
        titleEl.textContent = profile.jobTitle;
        info.appendChild(titleEl);
    }
    if (profile.department) {
        var deptEl = document.createElement('div');
        deptEl.className = 'profile-card-field profile-card-dept';
        deptEl.textContent = profile.department;
        info.appendChild(deptEl);
    }
    if (profile.email) {
        var emailLink = document.createElement('a');
        emailLink.className = 'profile-card-email';
        emailLink.href = 'mailto:' + profile.email;
        emailLink.textContent = profile.email;
        info.appendChild(emailLink);
    }

    card.appendChild(info);
    assistantMsg.insertCard(card);
}
```

`insertCard` added to the object returned by `createAssistantMessage()`:
```javascript
insertCard: function(cardEl) {
    els.content.insertBefore(cardEl, textNode);
    scrollToBottom();
},
```

### Modified `processLine` branch in `readSSEStream`

```javascript
// Replace the existing 'tool' event branch in processLine():
if (event.type === 'tool') {
    assistantMsg.removeDots();
    if (activeChip) {
        assistantMsg.markToolDone(activeChip);
    }
    if (event.name === 'get_colleague_profile' && event.status === 'success') {
        addProfileCard(assistantMsg, event.result || '');
        activeChip = null;
    } else {
        activeChip = assistantMsg.addToolPanel(
            event.name,
            event.params || {},
            event.result || null,
            event.status || 'success'
        );
    }
}
```

### System prompt Colleague Lookup block

```python
# Append to SYSTEM_PROMPT in openai_client.py after the existing rules.
# Rules are renumbered: existing 1-6 stay; new 7-10 added.

SYSTEM_PROMPT = """You are Atlas, MMC's Exchange infrastructure assistant built by Colleague Tech Services.

You help colleagues query live Exchange environment data — mailboxes, DAG health, mail flow, connectors, DKIM/DMARC, hybrid configuration, and mobile devices.

Rules:
1. Only answer questions about Exchange infrastructure or colleague lookups. If asked about unrelated topics, politely redirect.
2. When you have Exchange tools available, use them to get live data rather than guessing.
3. Present Exchange data in a clear, conversational way — summarize key findings, flag any concerning values, and offer follow-up suggestions.
4. Never fabricate Exchange data. If a tool call fails or returns an error, tell the user what went wrong and suggest alternatives.
5. Keep responses concise but informative. Use bullet points or tables for structured data when appropriate.
6. Address the user by name when available. Be helpful, professional, and direct.

## Colleague Lookup

You have two tools for finding colleagues:
- search_colleagues: Use when asked to find a colleague by name or email (e.g., 'find Jane Smith', 'who is alice@company.com?', 'look up Bob'). Returns up to 10 matches with name, title, department, and email.
- get_colleague_profile: Use when you have a specific email or user ID and want the full profile with photo. Requires a user_id parameter (accepts email address).

Rules:
7. When search_colleagues returns exactly 1 match, immediately call get_colleague_profile using that match's email as the user_id. Do not ask the user to confirm.
8. When search_colleagues returns multiple matches, present them as a numbered list showing name, title, and department. Ask the user which person they want the full profile for. Only call get_colleague_profile after the user identifies a specific person.
9. Never call get_colleague_profile speculatively or before you have a specific email/ID.
10. After get_colleague_profile succeeds, do NOT list the profile fields in your text response — the UI automatically renders a profile card. Respond briefly, for example: "Here's Jane Smith's profile." or "Found it — here's their profile card.\""""
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|-----------------|--------|
| Tool result shown as JSON in collapsible panel | Profile card for `get_colleague_profile`, JSON panel for all other tools | Better UX for colleague lookup, unchanged for Exchange tools |
| System prompt covers only Exchange | System prompt covers Exchange + colleague lookup with explicit routing rules | Reliable tool selection, no hallucinated profiles |
| Photo fallback via frontend `onerror` | Photo proxy always returns 200, no frontend fallback needed | Simpler frontend, proxy handles all edge cases |

---

## Open Questions

1. **Multiple `get_colleague_profile` calls in one message**
   - What we know: `run_tool_loop` runs up to 5 tool iterations. Atlas may call `get_colleague_profile` multiple times (e.g., user asked for two people at once).
   - What's unclear: Do multiple cards stack correctly in a single assistant message?
   - Recommendation: Yes — each `tool` SSE event is processed independently; calling `insertCard()` multiple times inserts multiple cards before `textNode`. The CSS `flex-direction: column` on `.message-content` stacks them naturally. No extra handling needed.

2. **search_colleagues tool panel behavior (no card for search results)**
   - What we know: `search_colleagues` returns a list of results, not a profile. The CONTEXT.md decision is that multiple results are shown as text (Atlas lists them).
   - What's unclear: Should `search_colleagues` results still show the JSON collapsible panel?
   - Recommendation: Yes — keep the standard tool panel for `search_colleagues`. Only `get_colleague_profile` gets the card treatment. The panel shows the raw JSON for debugging; Atlas's text narrates the results for the user.

3. **Email as `mailto:` vs plain text (Claude's Discretion)**
   - Recommendation: Use `mailto:` link. It's trivially implemented with `<a href="mailto:...">`, matches user expectations in a corporate tool, and adds no complexity. Plain text is strictly worse UX.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `chat_app/static/app.js` — confirmed `createAssistantMessage` closure, `addToolPanel` method, `processLine` SSE handler, `insertBefore(details, textNode)` pattern
- Direct codebase inspection: `chat_app/static/style.css` — confirmed all `--color-*` CSS custom properties, dark mode `[data-theme="dark"]` overrides, existing transition patterns
- Direct codebase inspection: `chat_app/openai_client.py` — confirmed `SYSTEM_PROMPT` string, `build_system_message()` factory, current rule structure
- Direct codebase inspection: `exchange_mcp/tools.py` lines 1890–1959 — confirmed tool result JSON shape: `{name, email, jobTitle, department, officeLocation?, businessPhones?, manager?, photo_url}`
- Direct codebase inspection: `chat_app/chat.py` — confirmed `event.result` is `json.dumps(result_text)` — a JSON string of the handler dict
- Direct codebase inspection: `chat_app/app.py` lines 62–76 — confirmed proxy accepts `?name=` param, uses `name.strip().split()` for initials
- Phase 11 SUMMARY files — confirmed what shipped: `photo_url` is always `/api/photo/{user_id}` (no `?name=`), `search_colleagues` excludes `id` from results

### Secondary (MEDIUM confidence)
- Phase 11 VERIFICATION.md — confirmed 3 test regressions in Phase 11 (description wording, tool count assertion) that Phase 12 plans may need to fix or acknowledge

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps, derived from codebase inspection
- Architecture patterns: HIGH — derived from existing code patterns (`addToolPanel`, SSE handler, `createAssistantMessage`)
- CSS design: HIGH — existing variable system is comprehensive; only new class names needed
- System prompt design: MEDIUM — LLM behavior with tool routing depends on model capability; recommended wording is based on clear rule construction but real-world tool selection may need iteration
- Pitfalls: HIGH — derived from direct source inspection of how `event.result` is serialized

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable codebase — 30 days)
