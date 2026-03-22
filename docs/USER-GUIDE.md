# Atlas User Guide

Atlas is an internal chat application that lets you query Exchange infrastructure using natural language. Instead of writing PowerShell cmdlets or asking an Exchange engineer, you can ask Atlas questions like "What's the mailbox size for jane.doe@mmc.com?" and get an immediate answer from live Exchange data.

## Getting Started

### Signing In

1. Navigate to the Atlas URL provided by your team (e.g., `http://exchange-mcp.internal:5000`)
2. Click **Sign in with Microsoft** on the landing page
3. Complete the Azure AD login with your MMC corporate credentials
4. You will be redirected to the Atlas chat interface

Your identity is verified server-side using Azure AD. All conversations are scoped to your account — no one else can see your threads.

### Your First Question

Once signed in, you will see a welcome screen with four example queries. Click any of them to get started, or type your own question in the text box at the bottom.

**Example questions you can ask:**

- "What's the mailbox size for john.smith@mmc.com?"
- "Who has access to the Finance shared mailbox?"
- "Is DAG01 healthy?"
- "Are there any mail queues backing up?"
- "Check DMARC and SPF for contoso.com"
- "Show me the hybrid connector status"
- "List all shared mailboxes on database MBX-DB01"
- "What mobile devices are connected to jane.doe@mmc.com?"

### Understanding Responses

When you ask a question, Atlas:

1. **Identifies the right Exchange tool** — you will see a tool chip appear (e.g., "get_mailbox_stats")
2. **Queries live Exchange data** — a loading indicator shows while the query runs (typically 2-4 seconds)
3. **Composes a natural language answer** — the response streams in real-time, summarizing what was found

## Features

### Tool Visibility Panels

Every response that involved an Exchange query includes a collapsible panel showing exactly what happened behind the scenes.

- Click the panel header to expand it
- **Parameters** — what was sent to the Exchange tool
- **Exchange Result** — the raw JSON data returned from Exchange
- Both sections have syntax-highlighted JSON for readability
- Click **Copy JSON** on the panel to copy the raw Exchange result to your clipboard

Panels are collapsed by default to keep the chat clean. Expand them when you need to verify the data or copy it for a ticket.

### Copy to Clipboard

- **Copy a response** — hover over any assistant message to reveal the **Copy** button in the top-right corner. Click it to copy the AI's text answer.
- **Copy Exchange JSON** — each tool panel has its own **Copy JSON** button that copies the raw Exchange data.
- After copying, the button shows "Copied!" for 1.5 seconds, then reverts.

### Conversation Threads

Atlas supports multiple conversation threads, similar to ChatGPT:

- **New Chat** — click the **+ New Chat** button in the sidebar to start a fresh conversation
- **Switch threads** — click any thread in the sidebar to load its message history
- **Rename** — click a thread name in the sidebar to edit it inline. Press Enter to confirm or Escape to cancel.
- **Delete** — click the **x** button on a thread. A confirmation dialog will appear before deletion.
- **Auto-naming** — new threads are automatically named from the first 30 characters of your first message

Your conversations persist across browser sessions. Close the browser, come back later, and all your threads will still be there.

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **Enter** | New line in the text box |
| **Ctrl+Enter** (or Cmd+Enter on Mac) | Send message |
| **Escape** | Cancel an active streaming response |

If you press Escape while a response is streaming, the partial text will remain visible with a "[response cancelled]" marker.

### Dark Mode

Click the theme toggle button (sun/moon icon) in the top-right corner of the header to switch between light and dark themes. Your preference is saved and will persist across sessions. On your first visit, Atlas will match your operating system's theme preference.

## Available Exchange Tools

Atlas has access to 15 Exchange tools, organized by category:

### Mailbox Tools

| Tool | What it does | Example question |
|------|-------------|-----------------|
| **get_mailbox_stats** | Size, quota, last logon, database for one mailbox | "What's the mailbox size for alice@mmc.com?" |
| **search_mailboxes** | Find mailboxes by database, type, or name pattern | "List all shared mailboxes on MBX-DB01" |
| **get_shared_mailbox_owners** | Full access, send-as, and send-on-behalf delegates | "Who has access to the HR shared mailbox?" |

### DAG and Database Tools

| Tool | What it does | Example question |
|------|-------------|-----------------|
| **list_dag_members** | Server inventory for a DAG | "Which servers are in DAG01?" |
| **get_dag_health** | Replication health, queue lengths, content index state | "Is DAG01 healthy?" |
| **get_database_copies** | All copies of a database with activation preferences | "Show copies of MBX-DB01 across servers" |

### Mail Flow Tools

| Tool | What it does | Example question |
|------|-------------|-----------------|
| **check_mail_flow** | Trace routing path between sender and recipient | "Can alice@mmc.com email bob@external.com?" |
| **get_transport_queues** | Queue depths and backlog detection | "Are there any mail queues backing up?" |
| **get_smtp_connectors** | Send and receive connector configuration | "Show me the SMTP connector settings" |

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
| **get_connector_status** | Hybrid connector health and TLS certificate status | "Are the hybrid connectors up?" |

### Connectivity

| Tool | What it does | Example question |
|------|-------------|-----------------|
| **ping** | Test server connectivity | "Is the Exchange server connected?" |

## Tips

- **Be specific** — "Check mailbox for alice@mmc.com" works better than "Check a mailbox"
- **Ask follow-up questions** — Atlas maintains conversation context, so you can say "Now check her mobile devices" after asking about a mailbox
- **Use the tool panels** — expand them to verify the raw Exchange data if something looks unexpected
- **Copy for tickets** — use the Copy buttons to grab data for ServiceNow tickets or reports
- **One topic per thread** — start a New Chat when switching to a different topic for cleaner conversation history

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| "Sign in with Microsoft" loops back to login page | Session expired or cookies blocked | Clear browser cookies for the Atlas URL and try again |
| Tool call takes more than 10 seconds | Exchange server under load or network issue | Wait for it to complete; Atlas has a 60-second timeout |
| "Exchange error: not found" | Mailbox or DAG name does not exist | Double-check the email address or DAG name spelling |
| Response is blank | Network interruption during streaming | Refresh the page and try again in a new message |
| Dark mode reverts on reload | localStorage is disabled in your browser | Enable localStorage or use the toggle each time |

## Data Privacy

- Atlas only performs **read-only** queries against Exchange. It cannot create, modify, or delete mailboxes, rules, or any Exchange objects.
- Atlas does **not** read email content or attachments.
- Your conversation history is stored in a local SQLite database on the Atlas server, scoped to your Azure AD identity. Other users cannot see your threads.
- Exchange queries run under the Atlas service account's permissions, not your personal Exchange permissions. The service account has view-only access.
