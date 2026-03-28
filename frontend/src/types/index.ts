// Thread from GET /api/threads
export interface Thread {
  id: number;
  name: string;
  updated_at: string;
}

// Raw message from GET /api/threads/:id/messages (OpenAI format)
export interface RawMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string | null;
  tool_calls?: Array<{
    id: string;
    type: 'function';
    function: { name: string; arguments: string };
  }>;
  tool_call_id?: string;
  name?: string;
}

// Parsed tool panel data for rendering
export interface ToolPanelData {
  name: string;
  params: Record<string, unknown>;
  result: string | null;
  status: 'success' | 'error';
}

// Display-ready message after parsing raw messages
export interface DisplayMessage {
  type: 'user' | 'assistant';
  content: string;
  toolPanels?: ToolPanelData[];
}

// SSE event types from POST /chat/stream
export type SSEEvent =
  | { type: 'text'; delta: string }
  | { type: 'tool'; name: string; status: 'success' | 'error'; params: Record<string, unknown>; result: string | null }
  | { type: 'thread_named'; thread_id: number; name: string }
  | { type: 'done' }
  | { type: 'error'; message: string };

// Streaming message state (separate from messages array)
export interface StreamingMessageState {
  content: string;
  toolPanels: ToolPanelData[];
}

// User session from GET /api/me
export interface User {
  displayName: string;
  email: string;
  oid: string;
}
