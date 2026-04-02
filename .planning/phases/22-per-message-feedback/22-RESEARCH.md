# Phase 22: Per-Message Feedback - Research

**Researched:** 2026-04-02
**Domain:** React UI feedback patterns, SQLite schema, Flask REST API, Fluent UI v9 Popover
**Confidence:** HIGH (codebase verified) / MEDIUM (UX patterns)

---

## Summary

Phase 22 adds thumbs up/down feedback buttons to each completed assistant message,
persisted to a new SQLite `feedback` table keyed by `(thread_id, message_index, user_id)`.
The codebase is a Flask + React (Fluent UI v9) app using MSAL for auth and SQLite for
persistence. The copy button pattern in `AssistantMessage.tsx` is the direct model for
the feedback buttons — hover-only visibility, absolute-positioned in `.message-hover-actions`.

The standard approach for per-message feedback in conversational AI is: hover-reveal
icon-only buttons with filled/outline toggle states, thumbs-down opens an optional
comment popover, votes sent via JSON PATCH or POST to a feedback endpoint. All
evidence comes from direct codebase inspection and verified library APIs.

**Primary recommendation:** Build a `FeedbackButtons` component that slots into the
existing `.message-hover-actions` div alongside `CopyButton`, using Fluent UI's
`ThumbLike16Regular`/`ThumbLike16Filled` and `ThumbDislike16Regular`/`ThumbDislike16Filled`
icons with a `Popover` for the thumbs-down comment flow. Persist to a new `feedback`
table added to `schema.sql` via an inline migration script (no Alembic — project uses
raw SQLite).

---

## Standard Stack

### Core (already installed — no new deps needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@fluentui/react-components` | 9.73.5 | `Popover`, `PopoverTrigger`, `PopoverSurface`, `Textarea`, `Button`, `makeStyles`, `tokens` | Already in use for `AccessDenied` component |
| `@fluentui/react-icons` | bundled in react-components | `ThumbLike16Regular`, `ThumbLike16Filled`, `ThumbDislike16Regular`, `ThumbDislike16Filled`, `bundleIcon` | Confirmed present in `node_modules/@fluentui/react-icons/lib/atoms/fonts/thumb-like.js` and `thumb-dislike.js` |
| Flask | project version | `/api/feedback` blueprint | Matches existing `conversations_bp` pattern exactly |
| SQLite (via `chat_app/db.py`) | project version | `feedback` table | Existing `get_db()` pattern, `schema.sql` extension |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `bundleIcon` (from `@fluentui/react-icons`) | bundled | Compound icon with Regular + Filled variants controlled by `filled` prop | Use for thumb buttons so filled/outline swap without conditional icon rendering |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Fluent UI `Popover` for comment flow | Custom modal or `<details>` | Popover is already in the installed Fluent package, provides correct focus trap and positioning; no reason to deviate |
| `ThumbLike/ThumbDislike` icons | Unicode emoji (👍👎) or custom SVG | Fluent icons match the visual language of existing UI (copy button uses unicode now but the AccessDenied component uses Fluent icons — feedback should use Fluent) |
| `message_index` as vote key | UUID per message or content hash | Index is the simplest stable identifier given how messages are stored in `messages_json` as a flat JSON array. See "Message Index Key" section for caveats. |

**Installation:** No new packages needed.

---

## Architecture Patterns

### Recommended Project Structure

```
chat_app/
├── feedback.py          # New Flask blueprint — /api/feedback/* routes
├── schema.sql           # Add feedback table (IF NOT EXISTS, idempotent)
└── app.py               # Register feedback_bp

frontend/src/
├── api/
│   └── feedback.ts      # submitFeedback(), getFeedbackForThread()
├── components/
│   └── ChatPane/
│       ├── AssistantMessage.tsx   # Add messageIndex + threadId props, render FeedbackButtons
│       ├── FeedbackButtons.tsx    # New: thumbs up/down + popover comment
│       └── MessageList.tsx        # Pass messageIndex + threadId down to AssistantMessage
├── types/
│   └── index.ts          # Add Feedback, FeedbackVote types
└── contexts/
    └── ChatContext.tsx    # Add feedback state map (optional — see Pattern 2)
```

---

### Pattern 1: Message Index Identification

**What:** Each `AssistantMessage` needs to know its position in the raw `messages_json`
array (not the `DisplayMessage[]` index) to uniquely identify it for the feedback key.

**The problem:** `parseHistoricalMessages` in `parseHistoricalMessages.ts` filters and
collapses raw messages. The `DisplayMessage[]` index does NOT equal the raw array index.
The `messages_json` array contains `system`, `user`, `assistant` (with tool_calls),
`tool`, and `assistant` (content) messages — multiple raw entries per displayed message.

**Recommended approach:** Track the raw array index of each content-bearing assistant
message during `parseHistoricalMessages` and attach it to `DisplayMessage`. Then pass
it through `MessageList → AssistantMessage → FeedbackButtons` as `rawMessageIndex`.

During streaming, new messages are appended to `messages_json` at positions we can
calculate: `rawMessageCount` from the last `GET /api/threads/:id/messages` call + offset
of new messages added in this stream. The simplest approach: after `FINALIZE_STREAMING`,
fetch the updated message count or include `raw_message_index` in the `done` SSE event.

**Alternative (simpler):** Store `messageIndex` as the count of assistant messages
seen so far (0-indexed) rather than the raw array index. The backend feedback table
stores `assistant_message_index` — counting only assistant messages with content.
This is stable regardless of tool-call messages and easier to compute on both sides.

**Recommendation:** Use assistant-message ordinal (0, 1, 2...) not raw array index.
Both frontend (count assistant messages seen) and backend (count assistant messages
in stored JSON) produce the same value deterministically.

---

### Pattern 2: Feedback State in React

**What:** The UI needs to know the current vote state for each message to render
filled vs outline icons. This state must:
- Be loaded when switching threads (restore from backend)
- Update optimistically on click

**Recommended approach:** Local state in `FeedbackButtons` component, populated
by a `GET /api/threads/:threadId/feedback` call triggered from `ThreadList.handleSelectThread`
alongside `getMessages`. Pass the vote map down through context or as a prop.

The cleanest integration: extend `ChatContext` with a `feedbackMap: Record<number, 'up' | 'down' | null>`
action `SET_FEEDBACK_MAP` and `SET_FEEDBACK_VOTE`. This mirrors the existing
`SET_MESSAGES` pattern precisely.

---

### Pattern 3: Fluent UI Popover for Comment Flow

**What:** On thumbs-down click, open a `Popover` anchored to the thumbs-down button
with a `Textarea` for optional comment, plus Submit and Cancel buttons.

**API verified from `Popover.types.ts` (GitHub source):**

```typescript
// Source: github.com/microsoft/fluentui Popover.types.ts
<Popover
  open={isCommentOpen}
  onOpenChange={(_, data) => setIsCommentOpen(data.open)}
  positioning="above-start"
  trapFocus
>
  <PopoverTrigger disableButtonEnhancement>
    <Button
      icon={<ThumbDislike16Filled />}
      appearance="subtle"
      size="small"
      aria-label="Thumbs down"
      aria-pressed={vote === 'down'}
    />
  </PopoverTrigger>
  <PopoverSurface>
    <Textarea
      placeholder="What went wrong? (optional)"
      value={comment}
      onChange={(_, d) => setComment(d.value)}
      resize="vertical"
    />
    <Button onClick={handleSubmit}>Submit</Button>
    <Button appearance="subtle" onClick={() => setIsCommentOpen(false)}>Cancel</Button>
  </PopoverSurface>
</Popover>
```

**Key props confirmed:**
- `open` / `onOpenChange` — controlled mode
- `trapFocus` — required for a11y; focus stays in popover
- `positioning` — `PositioningShorthand`, accepts strings like `"above-start"`
- `size` — `'small' | 'medium' | 'large'` (default `medium`)
- `withArrow` — optional visual arrow

**`Textarea` is exported from `@fluentui/react-components`** — confirmed in `dist/index.d.ts` line 1387.

---

### Pattern 4: bundleIcon for Toggle State

**What:** `bundleIcon` creates a compound icon component where `filled={true/false}` 
controls which variant renders. This is cleaner than a conditional import.

```typescript
// Source: @fluentui/react-icons bundleIcon export confirmed in lib/index.d.ts
import { bundleIcon, ThumbLike16Filled, ThumbLike16Regular } from '@fluentui/react-icons';

const ThumbLikeIcon = bundleIcon(ThumbLike16Filled, ThumbLike16Regular);
const ThumbDislikeIcon = bundleIcon(ThumbDislike16Filled, ThumbDislike16Regular);

// Usage:
<ThumbLikeIcon filled={vote === 'up'} />
```

---

### Pattern 5: Flask Feedback Blueprint

**What:** A new `feedback.py` blueprint following the exact pattern of `conversations.py`.

```python
# Pattern: mirrors conversations_bp exactly
from chat_app.auth import role_required
from chat_app.db import get_db

feedback_bp = Blueprint("feedback_bp", __name__)

@feedback_bp.route("/api/threads/<int:thread_id>/feedback", methods=["GET"])
@role_required
def get_feedback(thread_id: int):
    """Return all feedback votes for the thread owned by current user."""
    ...

@feedback_bp.route("/api/threads/<int:thread_id>/feedback/<int:message_index>", methods=["POST"])
@role_required
def submit_feedback(thread_id: int, message_index: int):
    """Upsert a vote. Body: {"vote": "up"|"down"|null, "comment": "..."}"""
    # vote=null means retract
    ...
```

Register in `app.py` the same way `conversations_bp` is registered.

---

### Pattern 6: SQLite Schema

**What:** New `feedback` table in `schema.sql`. Uses `IF NOT EXISTS` (idempotent).
The project auto-bootstraps schema on first run; for existing databases an inline
migration in `db.py` or a separate migration script handles adding the table.

```sql
-- Feedback votes on individual assistant messages.
-- assistant_message_index: 0-based ordinal of assistant messages (content-bearing)
--   within the thread's messages_json array. Does NOT count system/user/tool messages.
-- vote: 'up' | 'down' — NULL-ability preserved in case of retraction (DELETE preferred
--   over NULL to keep table lean).
-- comment: freetext from thumbs-down popover (max 500 chars enforced at API layer).

CREATE TABLE IF NOT EXISTS feedback (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id             INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    assistant_message_idx INTEGER NOT NULL,
    user_id               TEXT    NOT NULL,
    vote                  TEXT    NOT NULL CHECK(vote IN ('up', 'down')),
    comment               TEXT,
    created_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(thread_id, assistant_message_idx, user_id)
);

-- Analytics query support: vote breakdown by thread, by user, by time period
CREATE INDEX IF NOT EXISTS idx_feedback_thread
    ON feedback(thread_id, assistant_message_idx);

CREATE INDEX IF NOT EXISTS idx_feedback_user_vote
    ON feedback(user_id, vote, created_at DESC);
```

**Retraction:** DELETE the row rather than setting `vote = NULL` (keeps table lean, 
avoids NULL handling in analytics). `UNIQUE` constraint enables upsert via 
`INSERT OR REPLACE` or `INSERT ... ON CONFLICT DO UPDATE`.

**UPSERT pattern (SQLite 3.24+, available in Python 3.x):**
```sql
INSERT INTO feedback (thread_id, assistant_message_idx, user_id, vote, comment, updated_at)
VALUES (?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
ON CONFLICT(thread_id, assistant_message_idx, user_id)
DO UPDATE SET vote=excluded.vote, comment=excluded.comment, updated_at=excluded.updated_at;
```

---

### Pattern 7: ARIA Live Region for Screen Reader Announcement

**What:** FEED-06 requires "Feedback submitted" announced to screen readers.

**Implementation:** A visually-hidden `aria-live="polite"` region in `AssistantMessage`
(or a shared one in `AppLayout`). After successful vote submission, set the region's
text to "Feedback submitted" and clear after 1-2 seconds.

```tsx
// In AssistantMessage or a shared FeedbackAnnouncer
<span
  role="status"
  aria-live="polite"
  aria-atomic="true"
  className="sr-only"  // visually hidden via CSS
>
  {announcement}
</span>
```

The `.sr-only` CSS pattern (position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0)) should be added to `index.css` since the project uses custom CSS (no Tailwind utility classes for this).

---

### Anti-Patterns to Avoid

- **Don't use `key={idx}` from `messages.map` as message_index.** The `DisplayMessage[]` index is not stable between thread loads and does not match the raw JSON array index.
- **Don't add feedback state to `messages_json`.** That column stores the OpenAI conversation format; mixing feedback metadata corrupts it.
- **Don't store vote state in component-local state only.** It won't survive thread switches. Load from backend on thread select.
- **Don't open the comment popover for thumbs-up.** Only thumbs-down triggers the comment flow (FEED-05).
- **Don't show feedback buttons while streaming** (FEED-04). The `isStreaming` prop already gates the `.message-hover-actions` div in `AssistantMessage.tsx` — feedback buttons must be inside the same guard.
- **Don't skip the UNIQUE constraint.** Without it, a user could vote multiple times on the same message.
- **Don't make `comment` required.** Empty comment on thumbs-down = valid vote, no comment stored.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Focused popover for comment entry | Custom modal or tooltip | Fluent `Popover` with `trapFocus` | Handles focus trap, keyboard dismiss, positioning, a11y — already installed |
| Icon toggle between filled/outline | Conditional import | `bundleIcon` from `@fluentui/react-icons` | Single import, `filled` prop controls state |
| SQLite upsert | SELECT then INSERT or UPDATE | `INSERT ... ON CONFLICT DO UPDATE` | Atomic, correct under concurrent access |
| Character limit enforcement | Frontend-only validation | Backend CHAR CHECK or truncation + frontend `maxLength` | Frontend can be bypassed |

**Key insight:** The Fluent UI stack already covers every UI primitive needed. No new libraries.

---

## Common Pitfalls

### Pitfall 1: Message Index Mismatch

**What goes wrong:** Frontend sends `messageIndex=2` (DisplayMessage array index) but
backend counts it as the 3rd raw JSON message (index 2 in `messages_json`). They differ
because `messages_json` includes system, tool_call, and tool messages that `parseHistoricalMessages`
skips.

**Why it happens:** Two different counting systems for the same conceptual "message".

**How to avoid:** Use assistant-message ordinal (count only `role: "assistant"` messages
with `content != null` in sequence). Both frontend (count assistant display messages seen)
and backend (iterate `messages_json`, count content-bearing assistant messages) produce
the same number. Document the counting convention in code comments.

**Warning signs:** Votes appearing on the wrong message after page reload.

---

### Pitfall 2: Feedback State Lost on Thread Switch

**What goes wrong:** User votes on a message, switches threads and back, votes are gone
(buttons show unvoted state).

**Why it happens:** Feedback state stored only in component state or ChatContext but not
reloaded when thread reactivates.

**How to avoid:** Fetch `GET /api/threads/:id/feedback` alongside `getMessages` in
`ThreadList.handleSelectThread`. Dispatch `SET_FEEDBACK_MAP` to ChatContext (or a new
FeedbackContext) so `FeedbackButtons` can read the restored state.

**Warning signs:** Votes visible immediately after clicking but gone after thread switch.

---

### Pitfall 3: Vote on Streaming Message

**What goes wrong:** Feedback buttons flash briefly or are interactable during streaming
if the `isStreaming` guard isn't correctly applied to the streaming message.

**Why it happens:** The streaming `AssistantMessage` renders without `isStreaming=true`
for a brief moment during state transition, or `isStreaming` prop is passed incorrectly.

**How to avoid:** The streaming message is rendered separately in `MessageList` with
`isStreaming={true}` explicitly. The `AssistantMessage` already guards `.message-hover-actions`
with `{!isStreaming && ...}`. Feedback buttons must be inside this same guard — never rendered for the streaming message.

---

### Pitfall 4: Schema Bootstrap Race

**What goes wrong:** Existing production database doesn't have the `feedback` table
because `schema.sql` only runs on first startup (when DB file didn't exist).

**Why it happens:** `db.py` auto-bootstraps only when `file_exists` is False. Existing
databases don't get schema updates.

**How to avoid:** Add a `migrate_db()` function to `db.py` that runs `CREATE TABLE IF NOT EXISTS`
statements for new tables, called from `init_app()` on every startup. This is idempotent
and safe. The existing `schema.sql` already uses `IF NOT EXISTS` throughout — extend this
pattern to the migration function.

**Warning signs:** `OperationalError: no such table: feedback` in logs on first deploy.

---

### Pitfall 5: Popover Positioning in Overflow-Clipped Containers

**What goes wrong:** The `Popover` surface is clipped by a parent with `overflow: hidden`
or `overflow: auto` (the `.chat-messages` scroll container).

**Why it happens:** By default `Popover` renders in a portal (`document.body`) avoiding
this, but if `inline={true}` is passed it won't.

**How to avoid:** Never pass `inline={true}` to the comment Popover. The default portal
behavior renders it above all clipping contexts. Confirmed by Fluent `PopoverProps`:
`inline?: boolean` defaults to false.

---

## Code Examples

Verified patterns from codebase and official library sources:

### FeedbackButtons Component Skeleton

```tsx
// frontend/src/components/ChatPane/FeedbackButtons.tsx
import { useState } from 'react';
import {
  bundleIcon,
  ThumbLike16Filled, ThumbLike16Regular,
  ThumbDislike16Filled, ThumbDislike16Regular,
} from '@fluentui/react-icons';
import {
  Popover, PopoverTrigger, PopoverSurface,
  Button, Textarea,
} from '@fluentui/react-components';
import { submitFeedback } from '../../api/feedback.ts';

const ThumbLikeIcon = bundleIcon(ThumbLike16Filled, ThumbLike16Regular);
const ThumbDislikeIcon = bundleIcon(ThumbDislike16Filled, ThumbDislike16Regular);

interface Props {
  threadId: number;
  messageIndex: number;   // assistant-message ordinal (0-based)
  initialVote?: 'up' | 'down' | null;
}

export function FeedbackButtons({ threadId, messageIndex, initialVote }: Props) {
  const [vote, setVote] = useState<'up' | 'down' | null>(initialVote ?? null);
  const [commentOpen, setCommentOpen] = useState(false);
  const [comment, setComment] = useState('');
  const [announcement, setAnnouncement] = useState('');

  function announce(msg: string) {
    setAnnouncement(msg);
    setTimeout(() => setAnnouncement(''), 1500);
  }

  async function handleThumbUp() {
    const newVote = vote === 'up' ? null : 'up';
    setVote(newVote);
    if (newVote === null) {
      await submitFeedback(threadId, messageIndex, null, null);
    } else {
      await submitFeedback(threadId, messageIndex, 'up', null);
      announce('Feedback submitted');
    }
  }

  async function handleThumbDown() {
    if (vote === 'down') {
      // Toggle retract
      setVote(null);
      setCommentOpen(false);
      await submitFeedback(threadId, messageIndex, null, null);
    } else {
      setVote('down');
      setCommentOpen(true); // Open comment popover
    }
  }

  async function handleCommentSubmit() {
    await submitFeedback(threadId, messageIndex, 'down', comment || null);
    setCommentOpen(false);
    setComment('');
    announce('Feedback submitted');
  }

  return (
    <>
      <Button
        className="feedback-btn"
        appearance="subtle"
        size="small"
        icon={<ThumbLikeIcon filled={vote === 'up'} />}
        onClick={handleThumbUp}
        aria-label={vote === 'up' ? 'Retract thumbs up' : 'Thumbs up'}
        aria-pressed={vote === 'up'}
      />
      <Popover
        open={commentOpen}
        onOpenChange={(_, d) => { if (!d.open) setCommentOpen(false); }}
        positioning="above-start"
        trapFocus
      >
        <PopoverTrigger disableButtonEnhancement>
          <Button
            className="feedback-btn"
            appearance="subtle"
            size="small"
            icon={<ThumbDislikeIcon filled={vote === 'down'} />}
            onClick={handleThumbDown}
            aria-label={vote === 'down' ? 'Retract thumbs down' : 'Thumbs down'}
            aria-pressed={vote === 'down'}
          />
        </PopoverTrigger>
        <PopoverSurface>
          <Textarea
            placeholder="What went wrong? (optional)"
            value={comment}
            onChange={(_, d) => setComment(d.value.slice(0, 500))}
            resize="vertical"
          />
          <div>
            <Button onClick={handleCommentSubmit}>Submit</Button>
            <Button appearance="subtle" onClick={() => setCommentOpen(false)}>Cancel</Button>
          </div>
        </PopoverSurface>
      </Popover>
      <span role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {announcement}
      </span>
    </>
  );
}
```

---

### SQLite Feedback Table Migration (safe for existing DBs)

```python
# In chat_app/db.py — add migrate_db() and call from init_app()
def migrate_db() -> None:
    """Apply additive schema migrations safe to run on every startup.

    Uses IF NOT EXISTS / ON CONFLICT patterns so this is idempotent.
    """
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS feedback (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id             INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
            assistant_message_idx INTEGER NOT NULL,
            user_id               TEXT    NOT NULL,
            vote                  TEXT    NOT NULL CHECK(vote IN ('up', 'down')),
            comment               TEXT,
            created_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            updated_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            UNIQUE(thread_id, assistant_message_idx, user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_feedback_thread
            ON feedback(thread_id, assistant_message_idx);
        CREATE INDEX IF NOT EXISTS idx_feedback_user_vote
            ON feedback(user_id, vote, created_at DESC);
    """)
    db.commit()
```

---

### Frontend API Module

```typescript
// frontend/src/api/feedback.ts
export interface FeedbackVote {
  message_index: number;
  vote: 'up' | 'down';
  comment?: string;
}

export async function getFeedbackForThread(threadId: number): Promise<FeedbackVote[]> {
  const res = await fetch(`/api/threads/${threadId}/feedback`);
  if (!res.ok) throw new Error(`getFeedback failed: ${res.status}`);
  return res.json() as Promise<FeedbackVote[]>;
}

export async function submitFeedback(
  threadId: number,
  messageIndex: number,
  vote: 'up' | 'down' | null,
  comment: string | null,
): Promise<void> {
  if (vote === null) {
    // Retraction — delete the vote
    await fetch(`/api/threads/${threadId}/feedback/${messageIndex}`, { method: 'DELETE' });
    return;
  }
  await fetch(`/api/threads/${threadId}/feedback/${messageIndex}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vote, comment }),
  });
}
```

---

### AssistantMessage Integration Point

```tsx
// Modified AssistantMessage.tsx — add messageIndex + threadId props
interface Props {
  content: string;
  toolPanels?: ToolPanelData[];
  isStreaming?: boolean;
  timestamp?: string;
  threadId?: number;         // NEW
  messageIndex?: number;     // NEW — assistant-message ordinal
  initialVote?: 'up' | 'down' | null;  // NEW — restored from backend
}

// In JSX, inside the {!isStreaming && ...} guard:
<div className="message-hover-actions">
  {threadId !== undefined && messageIndex !== undefined && (
    <FeedbackButtons
      threadId={threadId}
      messageIndex={messageIndex}
      initialVote={initialVote}
    />
  )}
  <CopyButton getText={() => contentRef.current} />
</div>
```

---

### MessageList Integration Point

```tsx
// Modified MessageList.tsx — pass index and threadId to AssistantMessage
const { messages, streamingMessage } = useChat();
const { activeThreadId } = useThreads();
// feedbackMap from ChatContext (or FeedbackContext)

{messages.map((msg, displayIdx) => {
  if (msg.type === 'user') return <UserMessage key={displayIdx} ... />;
  // assistantIdx = count of assistant messages up to this point
  const assistantIdx = messages.slice(0, displayIdx + 1).filter(m => m.type === 'assistant').length - 1;
  return (
    <AssistantMessage
      key={displayIdx}
      messageIndex={assistantIdx}
      threadId={activeThreadId ?? undefined}
      initialVote={feedbackMap?.[assistantIdx] ?? null}
      ...
    />
  );
})}
```

---

### parseHistoricalMessages Extension (for rawMessageIndex if preferred)

If the assistant-message ordinal approach is used (recommended), no change to
`parseHistoricalMessages` is needed — the ordinal can be computed inline in
`MessageList` by counting assistant messages in `DisplayMessage[]`.

If raw index approach is needed later, extend `DisplayMessage` in `types/index.ts`:
```typescript
export interface DisplayMessage {
  type: 'user' | 'assistant';
  content: string;
  toolPanels?: ToolPanelData[];
  timestamp?: string;
  rawMessageIndex?: number;  // index in messages_json array
}
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Emoji unicode buttons (like existing CopyButton) | Fluent icon buttons with `bundleIcon` for filled/regular toggle | Consistent visual language with AccessDenied and other Fluent components |
| Custom focus trap in modal | Fluent `Popover` with `trapFocus` | Zero custom a11y code needed |
| Manual SQLite INSERT/SELECT/UPDATE for upsert | `INSERT ... ON CONFLICT DO UPDATE` (SQLite 3.24+, Python 3.8+) | Atomic, race-condition safe |

**Note:** The project's `CopyButton` uses Unicode emoji rather than Fluent icons — this
is a known inconsistency. The feedback buttons should use Fluent icons to match the
`AccessDenied` component style. A follow-up cleanup of `CopyButton` is outside this phase.

---

## Open Questions

1. **New assistant message index during live session**
   - What we know: After `FINALIZE_STREAMING`, the new assistant message is appended
     to `messages[]` in ChatContext. Its ordinal = number of previous assistant messages.
   - What's unclear: The `threadId` and `messageIndex` for the just-finalized message
     need to reach `AssistantMessage`. This is computable from `messages[]` length at
     `FINALIZE_STREAMING` time, but requires `activeThreadId` to be available in the
     component.
   - Recommendation: Pass `threadId={activeThreadId}` from `MessageList` (which already
     has access via `useThreads()`), and compute `messageIndex` inline in the render loop.

2. **Feedback state on page reload without thread switch**
   - What we know: On initial page load, the last active thread's messages are loaded
     in `ThreadList` initial mount. Feedback for that thread needs to be fetched too.
   - What's unclear: `AppLayout` or `ThreadList` needs to also dispatch `SET_FEEDBACK_MAP`
     after the initial thread load (not just on explicit thread switch).
   - Recommendation: Call `getFeedbackForThread` wherever `getMessages` is called
     (both initial mount in `ThreadList` and `handleSelectThread`).

3. **Character limit for comment**
   - What we know: Requirement is silent on this. Common patterns use 500-1000 chars.
   - What's unclear: No explicit requirement.
   - Recommendation: 500 chars. Enforce at both frontend (`maxLength` on Textarea,
     frontend slice) and backend (truncate to 500 before INSERT).

---

## Sources

### Primary (HIGH confidence — direct code inspection)
- `/c/xmcp/frontend/src/components/ChatPane/AssistantMessage.tsx` — existing hover actions pattern
- `/c/xmcp/frontend/src/components/shared/CopyButton.tsx` — button placement reference
- `/c/xmcp/frontend/src/components/AccessDenied.tsx` — Fluent UI v9 usage pattern
- `/c/xmcp/chat_app/schema.sql` — existing table schema and conventions
- `/c/xmcp/chat_app/db.py` — `get_db()`, auto-bootstrap pattern
- `/c/xmcp/chat_app/conversations.py` — blueprint pattern to mirror
- `/c/xmcp/chat_app/auth.py` — `role_required`, `_user_id()` pattern
- `/c/xmcp/frontend/src/utils/parseHistoricalMessages.ts` — message index complexity
- `/c/xmcp/frontend/node_modules/@fluentui/react-icons/lib/atoms/fonts/thumb-like.js` — confirmed icon exports
- `/c/xmcp/frontend/node_modules/@fluentui/react-icons/lib/atoms/fonts/thumb-dislike.js` — confirmed icon exports
- `/c/xmcp/frontend/node_modules/@fluentui/react-icons/lib/index.d.ts` — `bundleIcon` confirmed exported
- `/c/xmcp/frontend/node_modules/@fluentui/react-components/dist/index.d.ts` — `Popover`, `PopoverSurface`, `PopoverTrigger`, `Textarea` confirmed exported

### Secondary (MEDIUM confidence — official source, WebFetch)
- `github.com/microsoft/fluentui Popover.types.ts` — `PopoverProps` interface: `open`, `onOpenChange`, `trapFocus`, `positioning`, `size`, `inline`
- `github.com/microsoft/fluentui react-popover/library/src/index.ts` — exported component names confirmed

### Tertiary (LOW confidence — WebSearch, unverified)
- WebSearch: thumbs up/down is established pattern across ChatGPT, Copilot, IBM watsonx — not directly verified from these UIs, but consistent with CONTEXT.md's stated intent

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified from installed `node_modules`
- Architecture patterns: HIGH — modelled directly on existing codebase conventions
- Fluent Popover API: HIGH — verified from GitHub source file
- Icon names: HIGH — verified from `node_modules` JS and d.ts files
- UX/interaction patterns: MEDIUM — consistent with industry pattern, not directly pulled from ChatGPT source
- SQLite upsert syntax: HIGH — standard SQLite 3.24+ syntax

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable libraries, low churn expected)
