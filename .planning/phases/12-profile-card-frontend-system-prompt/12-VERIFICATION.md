---
phase: 12-profile-card-frontend-system-prompt
verified: 2026-03-25T11:28:15Z
status: passed
score: 4/4 must-haves verified
gaps: []
human_verification:
  - test: Ask about a colleague by name in the chat
    expected: An inline profile card renders inside the assistant message with photo/initials, bold name, job title, department, and clickable mailto email - not markdown, not a collapsible tool panel
    why_human: Requires live Graph API connectivity and a real chat session to exercise the full SSE pipeline end-to-end
  - test: Ask about a user who has no Azure AD photo
    expected: Profile card renders with a colored SVG circle showing initials, no broken image icon
    why_human: Requires a real tenant user account without a photo set
  - test: Ask a query that returns multiple search results
    expected: Atlas lists all matches with name, title, department and asks which person to fetch the full profile for - no profile card until user identifies a specific person
    why_human: Requires live Graph search returning multiple results and tests multi-turn rule 8 behavior
  - test: Toggle dark mode while a profile card is visible
    expected: Card background, border, and text colors transition smoothly to dark CSS variable values
    why_human: Visual appearance and transition smoothness cannot be verified from source alone
---

# Phase 12: Profile Card Frontend + System Prompt Verification Report

**Phase Goal:** Users see inline profile cards with photo, name, title, department, and email when they ask about colleagues, and Atlas consistently selects the right tool.
**Verified:** 2026-03-25T11:28:15Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Asking about a colleague renders an inline profile card built from DOM elements, not markdown | VERIFIED | addProfileCard() at app.js:273-325 builds div.profile-card with img.profile-card-photo, div.profile-card-name, div.profile-card-field (jobTitle), div.profile-card-field.profile-card-dept, and a.profile-card-email with href=mailto:. Wired via exclusive processLine branch at app.js:374-376 |
| 2 | Profile cards for users without photos display a fallback initials avatar, not a broken image | VERIFIED | img.src=(profile.photo_url or "")+?name=+encodeURIComponent(profile.name) at app.js:290. /api/photo/ route at app.py:175-201 always returns HTTP 200 - JPEG if photo exists, SVG with initials if not. _generate_placeholder_svg() at app.py:62-76 computes initials from displayName |
| 3 | Multiple get_colleague_profile results in one message render multiple stacked cards | VERIFIED | Each success SSE event independently calls addProfileCard(assistantMsg,...) at app.js:375. insertCard uses els.content.insertBefore(cardEl,textNode) so multiple calls stack cards before the assistant text node |
| 4 | Atlas reliably selects search_colleagues for name queries and get_colleague_profile for ID-specific lookups | VERIFIED | SYSTEM_PROMPT Colleague Lookup section at openai_client.py:47-57 contains rules 7-10: auto-chain on single result (7), numbered list on multiple results (8), no speculative calls (9), no text duplication after card renders (10) |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| chat_app/static/app.js | addProfileCard function and insertCard method on createAssistantMessage | VERIFIED | 810 lines. addProfileCard at line 273 (53-line implementation). insertCard method at lines 250-253 inside createAssistantMessage return object. Conditional processLine branch at line 374. No stub patterns found |
| chat_app/static/style.css | .profile-card-* CSS classes using --color-* tokens only | VERIFIED | 1060 lines. 8 profile-card class definitions at lines 992-1053. All colors use CSS custom properties confirmed present in :root and [data-theme=dark] overrides. No hardcoded hex colors in profile card rules |
| chat_app/openai_client.py | SYSTEM_PROMPT with Colleague Lookup section containing rules 7-10 | VERIFIED | 369 lines. Colleague Lookup section at line 47. Rules 7-10 at lines 54-57. Rule 1 updated to include colleague lookups in scope and redirect message |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| app.js processLine | addProfileCard() | event.name===get_colleague_profile AND event.status===success | WIRED | Exclusive branch at app.js:374 - success events route to card builder; errors and all other tool names fall through to addToolPanel |
| addProfileCard() | /api/photo/ proxy | img.src = (profile.photo_url or "") + ?name= + encodeURIComponent(profile.name) | WIRED | photo_url is /api/photo/{user_id} always set by tools.py:1957. ?name= param consumed by request.args.get(name) at app.py:187 and 199 for initials generation |
| addProfileCard() | profile object fields | JSON.parse(resultJson) applied to event.result string | WIRED | Correct double-deserialization: MCP server does json.dumps(dict) to TextContent, SSE outer json.dumps encodes it as a string value, processLine JSON.parse gives the string as event.result, addProfileCard JSON.parse gives the profile dict |
| SYSTEM_PROMPT Colleague Lookup section | Atlas tool selection behavior | build_system_message() injects SYSTEM_PROMPT as the system turn | WIRED | build_system_message() at openai_client.py:154-167 returns system turn dict. Injected in chat.py when conversation is empty, establishing the routing rules before Atlas sees any user message |
| get_colleague_profile MCP handler | photo_url in profile JSON | profile[photo_url] = f/api/photo/{user_id} at tools.py:1957 | WIRED | photo_url is always set regardless of whether Graph returned a real photo. This ensures the img.src fallback logic always has a proxy URL to append ?name= to |

### Requirements Coverage

Phase 12 had no REQUIREMENTS.md mapping. Coverage assessed directly against phase goal.

| Requirement | Status | Notes |
|-------------|--------|-------|
| Profile card renders inline as DOM elements, not markdown | SATISFIED | addProfileCard builds DOM, bypasses addToolPanel entirely for get_colleague_profile success |
| Card fields: photo, name, title, department, email | SATISFIED | All five fields built in addProfileCard; optional fields (title, dept, email) guarded with if(profile.X) checks |
| Photo fallback for users without photos | SATISFIED | Proxy always returns HTTP 200 with SVG initials; ?name= parameter ensures correct initials are computed |
| Multiple cards per message | SATISFIED | Each success event independently calls addProfileCard; insertBefore(textNode) pattern stacks them correctly |
| Atlas routes search_colleagues vs get_colleague_profile correctly | SATISFIED | Rules 7-10 in SYSTEM_PROMPT cover all routing scenarios including auto-chaining |

### Anti-Patterns Found

None. No TODO/FIXME/placeholder comments found in the profile card implementation. No empty returns, no console.log-only handlers, no stub text in the CSS or JavaScript added by this phase.

### Human Verification Required

Automated structural verification passes completely. The following require a live browser session with Graph API connectivity:

#### 1. Full profile card render

**Test:** In a connected Atlas session, type a colleague name query (e.g. "look up Jane Smith")
**Expected:** An inline card appears inside the assistant message bubble showing circular photo or initials avatar, bold name, job title, department, and clickable mailto email link - no collapsed JSON panel, no markdown text listing the fields
**Why human:** Requires live SSE stream, real Graph API response, and visual inspection of the rendered DOM card

#### 2. Broken-image fallback

**Test:** Identify a tenant user with no Azure AD photo and ask Atlas to look them up
**Expected:** Profile card renders with a colored SVG circle containing initials - no broken image icon in the photo slot
**Why human:** Requires a specific tenant account state that cannot be simulated from source analysis

#### 3. Multiple-result disambiguation flow

**Test:** Ask a name query likely to return 2 or more matches
**Expected:** Atlas responds with a numbered list of name, title, department for each match and asks which person to pull the full profile for - no profile card renders until the user identifies a specific person
**Why human:** Requires live Graph search returning multiple results; tests the multi-turn behavior specified in rule 8

#### 4. Single-result auto-chain

**Test:** Ask with a full email address that resolves to exactly one user
**Expected:** Atlas silently calls search_colleagues then immediately calls get_colleague_profile and the card appears - no confirmation prompt ("do you want me to fetch the full profile?")
**Why human:** Requires a search that returns exactly 1 result to exercise the rule 7 auto-chain path

#### 5. Dark mode visual check

**Test:** Trigger a profile card render, then click the theme toggle
**Expected:** Card background, border, and text shift smoothly to dark CSS variable values in 0.2s - the transition property at .profile-card produces a visible animation
**Why human:** Visual appearance and animation quality cannot be assessed from source code alone

### Gaps Summary

No gaps found. All four must-have truths are fully implemented and correctly wired:

- addProfileCard() is a substantive 53-line function building a complete profile card DOM tree from the tool result JSON string. It handles optional fields with guards and always constructs the photo URL with the ?name= fallback parameter.
- The insertCard method is correctly placed on the createAssistantMessage return object and uses insertBefore(textNode) so multiple cards stack above the assistant text rather than appending after it.
- The processLine branch correctly routes get_colleague_profile success events to the card builder while all other tool events - including get_colleague_profile errors - fall through to the standard tool panel. The exclusivity of the branch prevents double-rendering.
- All 8 CSS classes use only existing --color-* custom properties that have both light and dark mode values, providing automatic dark mode support without any additional CSS overrides.
- The SYSTEM_PROMPT Colleague Lookup section (rules 7-10) provides complete tool routing guidance: auto-chain on single results, disambiguation list on multiple results, prohibition on speculative calls, and explicit suppression of text duplication after a card renders.

The four human verification items are runtime confirmations of working code - they test live API integration, real tenant data states, and visual rendering quality. None indicate code gaps.

---

_Verified: 2026-03-25T11:28:15Z_
_Verifier: Claude (gsd-verifier)_
