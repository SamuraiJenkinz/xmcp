import { createContext, useContext, useEffect, useReducer, type ReactNode } from 'react';
import { listThreads } from '../api/threads.ts';
import type { Thread } from '../types/index.ts';

// State

interface ThreadState {
  threads: Thread[];
  activeThreadId: number | null;
}

const initialState: ThreadState = {
  threads: [],
  activeThreadId: null,
};

// Actions

export type ThreadAction =
  | { type: 'SET_THREADS'; threads: Thread[] }
  | { type: 'ADD_THREAD'; thread: Thread }
  | { type: 'REMOVE_THREAD'; threadId: number }
  | { type: 'RENAME_THREAD'; threadId: number; name: string }
  | { type: 'SET_ACTIVE'; threadId: number | null }
  | { type: 'BUMP_THREAD'; threadId: number };

// Reducer

function threadReducer(state: ThreadState, action: ThreadAction): ThreadState {
  switch (action.type) {
    case 'SET_THREADS':
      return { ...state, threads: action.threads };

    case 'ADD_THREAD':
      return { ...state, threads: [action.thread, ...state.threads] };

    case 'REMOVE_THREAD':
      return {
        ...state,
        threads: state.threads.filter((t) => t.id !== action.threadId),
        activeThreadId:
          state.activeThreadId === action.threadId ? null : state.activeThreadId,
      };

    case 'RENAME_THREAD':
      return {
        ...state,
        threads: state.threads.map((t) =>
          t.id === action.threadId ? { ...t, name: action.name } : t
        ),
      };

    case 'SET_ACTIVE':
      return { ...state, activeThreadId: action.threadId };

    case 'BUMP_THREAD': {
      // Move the thread to the top by updating updated_at to now and re-sorting
      const now = new Date().toISOString();
      const updated = state.threads.map((t) =>
        t.id === action.threadId ? { ...t, updated_at: now } : t
      );
      updated.sort(
        (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      );
      return { ...state, threads: updated };
    }

    default:
      return state;
  }
}

// Context

interface ThreadContextValue {
  threads: Thread[];
  activeThreadId: number | null;
  dispatch: React.Dispatch<ThreadAction>;
}

const ThreadContext = createContext<ThreadContextValue | null>(null);

// Provider

export function ThreadProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(threadReducer, initialState);

  useEffect(() => {
    listThreads()
      .then((threads) => dispatch({ type: 'SET_THREADS', threads }))
      .catch(console.error);
  }, []);

  const value: ThreadContextValue = {
    threads: state.threads,
    activeThreadId: state.activeThreadId,
    dispatch,
  };

  return <ThreadContext.Provider value={value}>{children}</ThreadContext.Provider>;
}

// Hook

export function useThreads(): ThreadContextValue {
  const ctx = useContext(ThreadContext);
  if (ctx === null) {
    throw new Error('useThreads must be used within a ThreadProvider');
  }
  return ctx;
}
