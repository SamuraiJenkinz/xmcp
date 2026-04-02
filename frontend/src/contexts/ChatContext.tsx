import { createContext, useContext, useReducer, type ReactNode } from 'react';
import type { DisplayMessage, FeedbackVote, StreamingMessageState, ToolPanelData } from '../types/index.ts';

// State

interface ChatState {
  messages: DisplayMessage[];
  streamingMessage: StreamingMessageState | null;
  isStreaming: boolean;
  error: string | null;
  feedbackMap: Record<number, 'up' | 'down'>;
}

const initialState: ChatState = {
  messages: [],
  streamingMessage: null,
  isStreaming: false,
  error: null,
  feedbackMap: {},
};

// Actions

export type ChatAction =
  | { type: 'SET_MESSAGES'; messages: DisplayMessage[] }
  | { type: 'APPEND_STREAMING_CHUNK'; delta: string }
  | { type: 'ADD_TOOL_EVENT'; tool: ToolPanelData }
  | { type: 'FINALIZE_STREAMING' }
  | { type: 'CANCEL_STREAMING' }
  | { type: 'SET_STREAMING'; isStreaming: boolean }
  | { type: 'SET_ERROR'; error: string }
  | { type: 'ADD_USER_MESSAGE'; content: string }
  | { type: 'CLEAR_ERROR' }
  | { type: 'SET_FEEDBACK_MAP'; votes: FeedbackVote[] }
  | { type: 'SET_FEEDBACK_VOTE'; messageIndex: number; vote: 'up' | 'down' | null };

// Reducer

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'SET_MESSAGES':
      return { ...state, messages: action.messages };

    case 'APPEND_STREAMING_CHUNK': {
      const existing = state.streamingMessage ?? { content: '', toolPanels: [] };
      return {
        ...state,
        streamingMessage: {
          ...existing,
          content: existing.content + action.delta,
        },
      };
    }

    case 'ADD_TOOL_EVENT': {
      const existing = state.streamingMessage ?? { content: '', toolPanels: [] };
      return {
        ...state,
        streamingMessage: {
          ...existing,
          toolPanels: [...existing.toolPanels, action.tool],
        },
      };
    }

    case 'FINALIZE_STREAMING': {
      if (state.streamingMessage === null) {
        return { ...state, isStreaming: false };
      }
      const finalized: DisplayMessage = {
        type: 'assistant',
        content: state.streamingMessage.content,
        toolPanels:
          state.streamingMessage.toolPanels.length > 0
            ? state.streamingMessage.toolPanels
            : undefined,
        timestamp: new Date().toISOString(),
      };
      return {
        ...state,
        messages: [...state.messages, finalized],
        streamingMessage: null,
        isStreaming: false,
      };
    }

    case 'CANCEL_STREAMING': {
      if (state.streamingMessage === null) {
        return { ...state, isStreaming: false };
      }
      const cancelled: DisplayMessage = {
        type: 'assistant',
        content: state.streamingMessage.content + '[response cancelled]',
        toolPanels:
          state.streamingMessage.toolPanels.length > 0
            ? state.streamingMessage.toolPanels
            : undefined,
        timestamp: new Date().toISOString(),
      };
      return {
        ...state,
        messages: [...state.messages, cancelled],
        streamingMessage: null,
        isStreaming: false,
      };
    }

    case 'SET_STREAMING':
      return { ...state, isStreaming: action.isStreaming };

    case 'SET_ERROR':
      return { ...state, error: action.error };

    case 'ADD_USER_MESSAGE':
      return {
        ...state,
        messages: [...state.messages, {
          type: 'user',
          content: action.content,
          timestamp: new Date().toISOString(),
        }],
      };

    case 'CLEAR_ERROR':
      return { ...state, error: null };

    case 'SET_FEEDBACK_MAP': {
      const map: Record<number, 'up' | 'down'> = {};
      for (const v of action.votes) {
        map[v.assistant_message_idx] = v.vote;
      }
      return { ...state, feedbackMap: map };
    }

    case 'SET_FEEDBACK_VOTE': {
      const next = { ...state.feedbackMap };
      if (action.vote === null) {
        delete next[action.messageIndex];
      } else {
        next[action.messageIndex] = action.vote;
      }
      return { ...state, feedbackMap: next };
    }

    default:
      return state;
  }
}

// Context

interface ChatContextValue {
  messages: DisplayMessage[];
  streamingMessage: StreamingMessageState | null;
  isStreaming: boolean;
  error: string | null;
  feedbackMap: Record<number, 'up' | 'down'>;
  dispatch: React.Dispatch<ChatAction>;
}

const ChatContext = createContext<ChatContextValue | null>(null);

// Provider

export function ChatProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(chatReducer, initialState);

  const value: ChatContextValue = {
    messages: state.messages,
    streamingMessage: state.streamingMessage,
    isStreaming: state.isStreaming,
    error: state.error,
    feedbackMap: state.feedbackMap,
    dispatch,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

// Hook

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (ctx === null) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return ctx;
}
