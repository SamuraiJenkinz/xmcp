# Phase 24: Conversation Export - Research

**Researched:** 2026-04-02
**Domain:** Client-side Markdown generation + Fluent UI Menu + Blob download
**Confidence:** HIGH

## Summary

Phase 24 requires exporting the active thread as a Markdown file suitable for Jira/incident reports. The core requirement is client-side-only Markdown generation (EXPT-04), meaning no server round-trip for the Markdown format. All required data -- `DisplayMessage[]` with `ToolPanelData[]` -- already exists in `ChatContext` React state.

The Fluent UI v9 `Menu`, `MenuTrigger`, `MenuPopover`, `MenuList`, and `MenuItem` components are already available via `@fluentui/react-components` (v9.73.5) and require no additional dependencies. The `ArrowDownloadRegular` icon is available from `@fluentui/react-icons`. The Blob + `URL.createObjectURL` + anchor `download` attribute pattern is the standard approach for client-side file downloads.

**Primary recommendation:** Build a pure function `messagesToMarkdown(messages, threadName, threadDate)` that converts `DisplayMessage[]` to a Markdown string, then trigger download via Blob. Add a `Menu` with `MenuButton` to the existing `Header` component.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@fluentui/react-components` | ^9.73.5 | Menu, MenuTrigger, MenuPopover, MenuList, MenuItem | Already installed; project standard |
| `@fluentui/react-icons` | (transitive) | ArrowDownloadRegular, DocumentTextRegular icons | Already available as transitive dep |
| Browser Blob API | native | Create downloadable file from string | No library needed; universal browser support |
| URL.createObjectURL | native | Generate download URL for Blob | No library needed; universal browser support |

### Supporting

No additional libraries needed. Everything is already in the dependency tree.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Client-side Blob | Server endpoint returning `Content-Disposition` | Violates EXPT-04; adds latency; server already has the data but requirement explicitly says no round-trip for Markdown |
| Hand-rolled Markdown | `turndown` or `showdown` | Not needed -- we are generating Markdown from structured data, not converting HTML |
| `file-saver` npm package | Browser Blob API | `file-saver` is a polyfill for old IE; unnecessary for modern browsers |

**Installation:**
```bash
# No new packages required
```

## Architecture Patterns

### Recommended Project Structure

```
frontend/src/
  utils/
    exportMarkdown.ts       # Pure function: DisplayMessage[] -> Markdown string
    slugify.ts              # Thread name -> filename-safe slug
    downloadBlob.ts         # Blob creation + anchor click + cleanup
  components/
    ChatPane/
      Header.tsx            # Modified: add export Menu
      ExportMenu.tsx        # New: Menu component with format options
```

### Pattern 1: Pure Markdown Generation Function

**What:** A pure function with no side effects that transforms `DisplayMessage[]` into a Markdown string.
**When to use:** Always -- separation of generation from download trigger enables testing and reuse for future JSON export.

```typescript
// frontend/src/utils/exportMarkdown.ts

import type { DisplayMessage, ToolPanelData } from '../types';

export function messagesToMarkdown(
  messages: DisplayMessage[],
  threadName: string,
  exportDate: string,
): string {
  const lines: string[] = [];

  // Header
  lines.push(`# ${threadName}`);
  lines.push('');
  lines.push(`**Exported:** ${exportDate}`);
  lines.push('');
  lines.push('---');
  lines.push('');

  for (const msg of messages) {
    if (msg.type === 'user') {
      lines.push(`## User`);
      lines.push('');
      lines.push(msg.content);
      lines.push('');
    } else {
      lines.push(`## Assistant`);
      lines.push('');
      // Tool panels before content (mirrors UI order)
      if (msg.toolPanels && msg.toolPanels.length > 0) {
        for (const tool of msg.toolPanels) {
          lines.push(formatToolPanel(tool));
          lines.push('');
        }
      }
      lines.push(msg.content);
      lines.push('');
    }
    lines.push('---');
    lines.push('');
  }

  return lines.join('\n');
}

function formatToolPanel(tool: ToolPanelData): string {
  const lines: string[] = [];
  const elapsed = (tool.startTime != null && tool.endTime != null)
    ? `${Math.round((tool.endTime - tool.startTime) * 1000)}ms`
    : null;

  lines.push(`### Tool: ${tool.name} (${tool.status}${elapsed ? `, ${elapsed}` : ''})`);
  lines.push('');

  if (Object.keys(tool.params).length > 0) {
    lines.push('**Parameters:**');
    lines.push('```json');
    lines.push(JSON.stringify(tool.params, null, 2));
    lines.push('```');
    lines.push('');
  }

  if (tool.result !== null) {
    lines.push('**Result:**');
    lines.push('```json');
    // Pretty-print if valid JSON, otherwise raw
    try {
      lines.push(JSON.stringify(JSON.parse(tool.result), null, 2));
    } catch {
      lines.push(tool.result);
    }
    lines.push('```');
  }

  return lines.join('\n');
}
```

### Pattern 2: Client-Side Blob Download

**What:** Create a Blob from the Markdown string, generate an object URL, trigger download via programmatic anchor click, then revoke the URL.
**When to use:** For all client-side file downloads.

```typescript
// frontend/src/utils/downloadBlob.ts

export function downloadBlob(content: string, filename: string, mimeType = 'text/markdown'): void {
  const blob = new Blob([content], { type: `${mimeType};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  // Clean up after a tick to ensure download starts
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 0);
}
```

### Pattern 3: Fluent UI v9 Menu with MenuButton

**What:** A `Menu` component with `MenuTrigger` wrapping a `MenuButton`, and `MenuPopover` containing `MenuList` with `MenuItem` entries.
**When to use:** For the export format selection dropdown.

```typescript
// frontend/src/components/ChatPane/ExportMenu.tsx

import {
  Menu,
  MenuTrigger,
  MenuPopover,
  MenuList,
  MenuItem,
  MenuButton,
} from '@fluentui/react-components';
import { ArrowDownloadRegular } from '@fluentui/react-icons';

interface ExportMenuProps {
  onExportMarkdown: () => void;
  disabled?: boolean;
}

export function ExportMenu({ onExportMarkdown, disabled }: ExportMenuProps) {
  return (
    <Menu>
      <MenuTrigger disableButtonEnhancement>
        <MenuButton
          appearance="subtle"
          icon={<ArrowDownloadRegular />}
          disabled={disabled}
          aria-label="Export conversation"
        >
          Export
        </MenuButton>
      </MenuTrigger>
      <MenuPopover>
        <MenuList>
          <MenuItem onClick={onExportMarkdown}>
            Markdown (.md)
          </MenuItem>
          {/* Future: JSON format from EXPT-05 */}
        </MenuList>
      </MenuPopover>
    </Menu>
  );
}
```

### Pattern 4: Filename Slugification

**What:** Convert thread name to a URL/filename-safe slug with date appended.
**When to use:** Generating the download filename per EXPT-03.

```typescript
// frontend/src/utils/slugify.ts

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')  // Remove non-word chars except spaces and hyphens
    .replace(/[\s_]+/g, '-')   // Spaces/underscores to hyphens
    .replace(/-+/g, '-')       // Collapse multiple hyphens
    .replace(/^-+|-+$/g, '');  // Trim leading/trailing hyphens
}

export function exportFilename(threadName: string, date: Date = new Date()): string {
  const slug = slugify(threadName);
  const dateStr = date.toISOString().slice(0, 10); // YYYY-MM-DD
  return `${slug}-${dateStr}.md`;
}
```

### Anti-Patterns to Avoid

- **Server round-trip for Markdown:** EXPT-04 explicitly forbids this. The data is already in React state.
- **Building Markdown by string concatenation without a function:** Keep generation pure and testable; don't inline it in the click handler.
- **Forgetting URL.revokeObjectURL:** Leaks memory if not cleaned up. Always revoke after download starts.
- **Using `window.open()` for download:** Does not set filename; shows blank tab. Use anchor `download` attribute instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dropdown menu | Custom dropdown with state management | Fluent UI `Menu` + `MenuButton` | Accessibility, keyboard nav, focus management all handled |
| File download | Custom fetch + response handling | Blob + createObjectURL + anchor click | Standard pattern, no dependencies needed |
| Markdown escaping | Complex regex escaping | Code blocks for tool data (triple backtick) | Tool output goes in fenced code blocks, avoiding escaping issues entirely |
| Filename sanitization | Complex regex for all OS edge cases | Simple slugify (lowercase, alphanumeric, hyphens) | Thread names are already short and user-created; extreme edge cases unlikely |

**Key insight:** This phase requires zero new dependencies. Fluent UI v9 Menu and browser Blob API cover all needs.

## Common Pitfalls

### Pitfall 1: Exporting During Active Streaming

**What goes wrong:** If the user clicks Export while a response is still streaming, the `streamingMessage` in ChatContext is separate from `messages[]`. The export would miss the in-progress message.
**Why it happens:** `streamingMessage` is only moved to `messages[]` on `FINALIZE_STREAMING`.
**How to avoid:** Either (a) disable the export button while `isStreaming` is true, or (b) include `streamingMessage` in the export if present, with a `[response in progress]` marker.
**Warning signs:** Exported file is missing the last assistant turn.
**Recommendation:** Disable export during streaming -- simplest and least surprising.

### Pitfall 2: Empty Thread Export

**What goes wrong:** User clicks export on a newly created thread with no messages.
**Why it happens:** Thread is active but `messages.length === 0`.
**How to avoid:** Disable the export button when there are no messages to export.
**Warning signs:** Downloaded file contains only the header with no conversation.

### Pitfall 3: Memory Leak from Object URLs

**What goes wrong:** `URL.createObjectURL` allocates memory that persists until page unload or explicit revocation.
**Why it happens:** Forgetting `URL.revokeObjectURL` or calling it synchronously before the download triggers.
**How to avoid:** Use `setTimeout(() => URL.revokeObjectURL(url), 0)` to revoke after the click event completes.
**Warning signs:** Memory usage climbing after repeated exports.

### Pitfall 4: Special Characters in Thread Name

**What goes wrong:** Thread names with slashes, colons, or Unicode characters break filename generation.
**Why it happens:** OS filesystem restrictions on filenames.
**How to avoid:** The `slugify()` function strips all non-alphanumeric characters except hyphens.
**Warning signs:** Download fails silently or produces garbled filename.

### Pitfall 5: Large Conversations with Many Tool Panels

**What goes wrong:** Very long conversations with extensive tool output could produce very large Markdown files.
**Why it happens:** Tool results are full JSON responses that can be large.
**How to avoid:** For Phase 24, include full output. If performance becomes an issue, consider truncating tool results beyond a threshold (e.g., 10KB per result) in a future iteration.
**Warning signs:** Export takes noticeable time or browser briefly freezes.

### Pitfall 6: Thread Name Not Yet Set

**What goes wrong:** If thread was just created and auto-naming hasn't fired yet, the thread name may be a placeholder like "New conversation".
**Why it happens:** Thread naming happens via SSE `thread_named` event after first response.
**How to avoid:** Use whatever name is in `ThreadContext.threads` at export time. The `RENAME_THREAD` action updates it once naming occurs. If name is still default, that's acceptable -- the filename will reflect what the user sees.

## Code Examples

### Complete Export Flow (Wiring It Together)

```typescript
// In Header.tsx or AppLayout.tsx -- the export handler

import { useChat } from '../../contexts/ChatContext';
import { useThreads } from '../../contexts/ThreadContext';
import { messagesToMarkdown } from '../../utils/exportMarkdown';
import { exportFilename } from '../../utils/slugify';
import { downloadBlob } from '../../utils/downloadBlob';

function handleExportMarkdown() {
  const threadName = threads.find(t => t.id === activeThreadId)?.name ?? 'conversation';
  const markdown = messagesToMarkdown(messages, threadName, new Date().toLocaleDateString());
  const filename = exportFilename(threadName);
  downloadBlob(markdown, filename);
}
```

### Fluent UI Menu Import Pattern (Matching Project Conventions)

```typescript
// Project already imports from '@fluentui/react-components' for Fluent components
// and from '@fluentui/react-icons' for icons. Follow same pattern:

import {
  Menu,
  MenuTrigger,
  MenuPopover,
  MenuList,
  MenuItem,
  MenuButton,
} from '@fluentui/react-components';
import { ArrowDownloadRegular } from '@fluentui/react-icons';
```

### Markdown Output Example (What Gets Downloaded)

```markdown
# DAG Health Check

**Exported:** 4/2/2026

---

## User

Check the DAG health status for our Exchange environment.

---

## Assistant

### Tool: get_dag_health (success, 1250ms)

**Parameters:**
```json
{
  "server": "EXCH-DAG01"
}
```

**Result:**
```json
{
  "status": "healthy",
  "members": ["EXCH-MBX01", "EXCH-MBX02"],
  "copy_queue_length": 0
}
```

I checked the DAG health for your Exchange environment. Everything looks good:

- **Status:** Healthy
- **Members:** EXCH-MBX01, EXCH-MBX02
- **Copy queue length:** 0

All database copies are in a healthy state with no replication backlog.

---
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `file-saver` library for downloads | Native Blob + createObjectURL | 2020+ | No dependency needed; all modern browsers support it |
| Custom dropdown menus | Fluent UI v9 Menu component | Fluent v9 GA (2023) | Full accessibility, keyboard nav, focus trap built in |
| `navigator.msSaveOrOpenBlob` | Standard Blob API | IE/old Edge deprecated | No IE polyfill needed |

**Deprecated/outdated:**
- `file-saver` package: Only needed for IE11 compatibility; unnecessary for this project
- `navigator.msSaveOrOpenBlob`: Removed from modern browsers

## Open Questions

1. **Tool panel ordering relative to content**
   - What we know: In the UI, tool panels appear above the assistant's text content. In the Markdown export, we should mirror this order (tools first, then content).
   - What's unclear: Whether users prefer tools grouped separately (e.g., appendix-style) vs. inline with conversation flow.
   - Recommendation: Mirror the UI order (tools before content within each assistant turn). This matches what users see and is simplest.

2. **Markdown content inside assistant messages**
   - What we know: Assistant message `content` may already contain Markdown formatting (headings, lists, code blocks) since it's rendered with `react-markdown`.
   - What's unclear: Whether nested headings in assistant content will conflict with the `## User` / `## Assistant` heading structure.
   - Recommendation: Use `## User` and `## Assistant` as H2, and `### Tool:` as H3. Assistant content with its own headings may create conflicts, but this is acceptable for a Jira paste target. The content should be included as-is without modification.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `ChatContext.tsx`, `ThreadContext.tsx`, `types/index.ts` -- verified data shapes
- Codebase analysis: `Header.tsx`, `ToolPanel.tsx` -- verified UI structure and existing patterns
- Codebase analysis: `package.json` -- verified `@fluentui/react-components` v9.73.5 installed
- Codebase analysis: `@fluentui/react-icons` chunks -- verified `ArrowDownloadRegular` exists
- Codebase analysis: `@fluentui/react-components` index.js -- verified Menu, MenuTrigger, MenuPopover, MenuList, MenuItem, MenuButton all re-exported

### Secondary (MEDIUM confidence)
- [MDN Blob API](https://developer.mozilla.org/en-US/docs/Web/API/Blob) -- Blob constructor and usage
- [MDN URL.createObjectURL](https://developer.mozilla.org/en-US/docs/Web/API/URL/createObjectURL_static) -- Object URL lifecycle
- [Fluent UI React v9](https://react.fluentui.dev/) -- Menu component documentation
- [Ben Nadel: Downloading Text Using Blobs](https://www.bennadel.com/blog/3472-downloading-text-using-blobs-url-createobjecturl-and-the-anchor-download-attribute-in-javascript.htm) -- Blob download pattern

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All components verified in node_modules; no new deps needed
- Architecture: HIGH - Data shapes verified in codebase; pure function pattern is straightforward
- Pitfalls: HIGH - Verified streaming state separation in ChatContext reducer; edge cases identified from code review

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable -- no fast-moving dependencies)
