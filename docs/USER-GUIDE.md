# Atlas User Guide

Atlas is an internal chat application that lets you query Exchange infrastructure and look up colleagues using natural language. Instead of writing PowerShell cmdlets or asking an Exchange engineer, you can ask Atlas questions like "What's the mailbox size for jane.doe@mmc.com?" or "Look up Jane Smith" and get an immediate answer from live data.

## Getting Started

### Signing In

1. Navigate to the Atlas URL provided by your team (e.g., `https://usdf11v1784.mercer.com:5000`)
2. Click **Sign in with Microsoft** on the splash page
3. Complete the Azure AD login with your MMC corporate credentials
4. You will be redirected to the Atlas chat interface

Your identity is verified server-side using Azure AD. All conversations are scoped to your account — no one else can see your threads.

### Your First Question

Once signed in, you will see a welcome screen with prompt suggestion chips — click any of them to get started, or type your own question in the text area at the bottom.

**Example questions you can ask:**

- "What's the mailbox size for john.smith@mmc.com?"
- "Who has access to the Finance shared mailbox?"
- "Is DAG01 healthy?"
- "Are there any mail queues backing up?"
- "Check DMARC and SPF for contoso.com"
- "Show me the hybrid connector status"
- "List all shared mailboxes on database MBX-DB01"
- "What mobile devices are connected to jane.doe@mmc.com?"
- "Look up Jane Smith"
- "Find someone in the IT department named Taylor"

### Understanding Responses

When you ask a question, Atlas:

1. **Identifies the right tool** — a tool panel appears showing which Exchange tool was invoked
2. **Queries live data** — the panel shows a status badge while the query runs (typically 2-4 seconds)
3. **Composes a response** — the answer streams in real-time with formatted text. For colleague lookups, inline profile cards or search result cards render automatically

Messages stream token-by-token in real-time. You can cancel a streaming response at any time by pressing **Escape** or clicking the **Stop** button.

## Features

### Chat Interface

Atlas uses a modern chat interface inspired by Microsoft Copilot:

- **Message bubbles** — your messages appear on the right with a distinct bubble style; Atlas responses appear on the left with a different style for clear role differentiation
- **Smooth animations** — new messages animate in with a subtle fade-in effect
- **Welcome state** — an empty conversation shows prompt suggestion chips to help you get started
- **Auto-resize input** — the text area grows as you type (up to ~5 lines)

### Tool Visibility Panels

Every response that involved an Exchange query includes a collapsible panel showing exactly what happened behind the scenes.

- Click the **chevron** to expand or collapse the panel
- **Status badge** — shows "Done" when the query completed successfully, or "Error" if something went wrong
- **Elapsed time** — shows how long the Exchange query took (e.g., "Ran in 1.2s")
- **Parameters** — what was sent to the Exchange tool
- **Exchange Result** — the raw JSON data, syntax-highlighted for readability
- Click **Copy** on the panel to copy the raw Exchange JSON to your clipboard

Panels are collapsed by default to keep the chat clean. Expand them when you need to verify the data or copy it for a ticket.

### Copy to Clipboard

- **Copy a response** — hover over any assistant message to reveal the **Copy** button and timestamp in the top-right corner. Click to copy the AI's text answer.
- **Copy Exchange JSON** — each tool panel has its own **Copy** button for the raw Exchange data.
- After copying, the button briefly confirms "Copied!" before reverting.

### Conversation Threads

Atlas supports multiple conversation threads:

- **New Chat** — click the **Compose** icon in the sidebar to start a fresh conversation
- **Switch threads** — click any thread in the sidebar to load its message history
- **Rename** — double-click a thread name to edit it inline. Press Enter to confirm or Escape to cancel.
- **Delete** — click the **x** button on a thread to remove it
- **Auto-naming** — new threads are automatically named from your first message
- **Recency grouping** — threads are organized under **Today**, **Yesterday**, **This Week**, and **Older** headings

Your conversations persist across browser sessions. Close the browser, come back later, and all your threads will still be there.

### Sidebar

The sidebar can be collapsed to icon-only mode for more chat space:

- Click the **collapse** icon in the sidebar header to shrink it
- Click the **expand** icon to restore the full sidebar
- Your collapse preference is saved and persists across sessions

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **Enter** | Send message |
| **Shift+Enter** | New line in the text area |
| **Escape** | Cancel an active streaming response |
| **Tab** | Navigate between interactive elements |

If you press Escape while a response is streaming, the partial text will remain visible with a "[response cancelled]" marker.

A **Skip to chat** link is available for keyboard users — press Tab at the top of the page to reveal it, then Enter to jump directly to the message area.

### Dark Mode

Click the theme toggle button (sun/moon icon) in the header to switch between light and dark themes. Your preference is saved and persists across sessions. On first visit, Atlas matches your operating system's theme preference.

Both themes use the Microsoft Fluent 2 design system with a consistent three-tier surface hierarchy for a professional appearance.

### Colleague Lookup

Atlas can search for colleagues by name and display their profile as an inline card.

- **Search** — ask "Look up Jane Smith" or "Find someone named Taylor". If multiple matches are found, Atlas displays search result cards showing each person's name, title, department, and email. Click an email to open a mailto link.
- **Profile card** — when Atlas identifies a specific colleague, a profile card renders inline with their photo, name, job title, department, and email. Colleagues without photos get an initials placeholder.
- **Disambiguation** — if your search returns multiple results, Atlas will ask you to clarify which person you mean before loading the full profile.

### Formatted Responses

Atlas renders assistant messages with formatted text:

- **Bold text**, *italic text*, and `inline code` render properly
- Bullet point and numbered lists display as structured lists
- Code blocks render with syntax highlighting
- Headers and horizontal rules create visual structure

## Available Tools

Atlas has access to 17 tools, organized by category:

### Mailbox Tools

| Tool | What it does | Example question |
|------|-------------|-----------------|
| **get_mailbox_stats** | Size, quota, last logon, database for one mailbox | "What's the mailbox size for alice@mmc.com?" |
| **search_mailboxes** | Find mailboxes by database, type, or name pattern | "List all shared mailboxes on MBX-DB01" |
| **get_shared_mailbox_owners** | Full access, send-as, and send-on-behalf delegates | "Who has access to the HR shared mailbox?" |

### DAG and Database Tools (On-Premises Only)

| Tool | What it does | Example question |
|------|-------------|-----------------|
| **list_dag_members** | Server inventory for a DAG | "Which servers are in DAG01?" |
| **get_dag_health** | Replication health, queue lengths, content index state | "Is DAG01 healthy?" |
| **get_database_copies** | All copies of a database with activation preferences | "Show copies of MBX-DB01 across servers" |

### Mail Flow Tools

| Tool | What it does | Example question |
|------|-------------|-----------------|
| **check_mail_flow** | Trace routing path between sender and recipient | "Can alice@mmc.com email bob@external.com?" |
| **get_transport_queues** | Queue depths and backlog detection (on-prem only) | "Are there any mail queues backing up?" |
| **get_smtp_connectors** | On-prem Send/Receive connector configuration (on-prem only) | "Show me the on-prem SMTP connector settings" |

### Security Tools

| Tool | What it does | Example question |
|------|-------------|-----------------|
| **get_dkim_config** | DKIM signing configuration and DNS CNAME validation | "Is DKIM enabled for mmc.com?" |
| **get_dmarc_status** | DMARC policy and SPF record via live DNS lookup | "Check DMARC and SPF for contoso.com" |
| **check_mobile_devices** | ActiveSync device partnerships and sync status | "What phones does alice@mmc.com have connected?" |

### Hybrid Tools

| Tool | What it does | Example question |
|------|-------------|-----------------|
| **get_hybrid_config** | Full hybrid topology and federation trust details | "How is Exchange hybrid configured?" |
| **get_connector_status** | Exchange Online inbound/outbound connectors | "Show EXO outbound connectors" |

### Colleague Lookup Tools

| Tool | What it does | Example question |
|------|-------------|-----------------|
| **search_colleagues** | Search for colleagues by name via Microsoft Graph | "Look up Jane Smith" |
| **get_colleague_profile** | Detailed profile with photo for a specific colleague | "Show me Jane's full profile" |

### Connectivity

| Tool | What it does | Example question |
|------|-------------|-----------------|
| **ping** | Test server connectivity | "Is the Exchange server connected?" |

> **Note:** Some tools are on-premises only (DAG, database copies, transport queues, SMTP connectors). If you are connected to Exchange Online and try these tools, Atlas will let you know they require an on-premises connection. For connectors, Atlas will ask whether you want on-premises or Exchange Online connectors.

## Tips

- **Be specific** — "Check mailbox for alice@mmc.com" works better than "Check a mailbox"
- **Ask follow-up questions** — Atlas maintains conversation context, so you can say "Now check her mobile devices" after asking about a mailbox
- **Use the tool panels** — expand them to verify the raw Exchange data if something looks unexpected
- **Copy for tickets** — use the Copy buttons to grab data for ServiceNow tickets or reports
- **One topic per thread** — start a New Chat when switching to a different topic for cleaner conversation history
- **Colleague lookup** — just say "Look up" followed by a name. If multiple results appear, tell Atlas which person you want (e.g., "the one in IT" or "Kevin Taylor")
- **Connector queries** — Atlas will ask you to clarify on-premises vs Exchange Online when you ask about connectors
- **Keyboard navigation** — Tab through the interface to reach any element; all buttons and controls are keyboard-accessible

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| "Sign in with Microsoft" loops back to login page | Session expired or cookies blocked | Clear browser cookies for the Atlas URL and try again |
| Tool call takes more than 10 seconds | Exchange server under load or network issue | Wait for it to complete; Atlas has a 60-second timeout |
| "Exchange error: not found" | Mailbox or DAG name does not exist | Double-check the email address or DAG name spelling |
| "This tool requires an on-premises Exchange connection" | You used a DAG/queue/SMTP connector tool against Exchange Online | These tools only work with on-prem Exchange; use EXO equivalents |
| Colleague search returns "Graph API not configured" | Microsoft Graph credentials are missing or invalid | Contact your admin to verify Azure AD app permissions (User.Read.All, ProfilePhoto.Read.All) |
| Profile card shows initials instead of photo | The colleague has no photo in Azure AD | This is expected — initials are shown as a fallback |
| Response is blank | Network interruption during streaming | Refresh the page and try again in a new message |
| Dark mode reverts on reload | localStorage is disabled in your browser | Enable localStorage or use the toggle each time |
| Stop button doesn't appear during streaming | Browser may be caching old assets | Hard refresh (Ctrl+Shift+R) to load latest version |

## Data Privacy

- Atlas only performs **read-only** queries against Exchange. It cannot create, modify, or delete mailboxes, rules, or any Exchange objects.
- Atlas does **not** read email content or attachments.
- Your conversation history is stored in a local SQLite database on the Atlas server, scoped to your Azure AD identity. Other users cannot see your threads.
- Exchange queries run under the Atlas service account's permissions, not your personal Exchange permissions. The service account has view-only access.
- Colleague lookups use Microsoft Graph API with application-level permissions (User.Read.All, ProfilePhoto.Read.All). Atlas can view directory profiles and photos but cannot modify any Azure AD data.
- Colleague photos are served through a secure proxy route that requires authentication. Photo data never enters the AI model context.
