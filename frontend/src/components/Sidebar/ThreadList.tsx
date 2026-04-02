import { useEffect, useRef, useState } from 'react';
import { useChat } from '../../contexts/ChatContext.tsx';
import { useThreads } from '../../contexts/ThreadContext.tsx';
import { createThread, deleteThread, getMessages, renameThread, searchThreads } from '../../api/threads.ts';
import type { SearchResult } from '../../api/threads.ts';
import { getFeedbackForThread } from '../../api/feedback.ts';
import { parseHistoricalMessages } from '../../utils/parseHistoricalMessages.ts';
import { groupThreadsByRecency } from '../../utils/groupThreadsByRecency.ts';
import { ThreadItem } from './ThreadItem.tsx';
import { SearchInput } from './SearchInput.tsx';
import { useDebounce } from '../../hooks/useDebounce.ts';
import { ComposeRegular, PanelLeftContractRegular, PanelLeftExpandRegular } from '@fluentui/react-icons';

interface ThreadListProps {
  onCancelStream?: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export function ThreadList({ onCancelStream, collapsed, onToggleCollapse }: ThreadListProps) {
  const { threads, activeThreadId, dispatch: threadDispatch } = useThreads();
  const { isStreaming, dispatch: chatDispatch } = useChat();

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedQuery = useDebounce(searchQuery, 300);
  const [ftsResults, setFtsResults] = useState<SearchResult[]>([]);
  const [ftsLoading, setFtsLoading] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Roving tabindex state
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const newChatBtnRef = useRef<HTMLButtonElement>(null);
  const newChatBtnCollapsedRef = useRef<HTMLButtonElement>(null);
  const [focusAfterDeletion, setFocusAfterDeletion] = useState<number | null>(null);

  // Client-side title filter — does NOT pin active thread
  const filteredThreads = searchQuery.trim()
    ? threads.filter((t) =>
        (t.name || 'New Chat').toLowerCase().includes(searchQuery.trim().toLowerCase())
      )
    : threads;

  const groups = groupThreadsByRecency(filteredThreads);
  const flatThreads = groups.flatMap((g) => g.threads);

  // Clamp focusedIndex when list changes
  useEffect(() => {
    if (flatThreads.length > 0) {
      setFocusedIndex((prev) => Math.min(prev, flatThreads.length - 1));
    }
  }, [flatThreads.length]);

  // Post-delete focus management
  useEffect(() => {
    if (focusAfterDeletion !== null) {
      const clamped = Math.min(focusAfterDeletion, itemRefs.current.length - 1);
      if (clamped >= 0) {
        itemRefs.current[clamped]?.focus();
        setFocusedIndex(clamped);
      }
      setFocusAfterDeletion(null);
    }
  }, [focusAfterDeletion, threads]);

  // FTS5 backend search — triggered by debounced query with 2-char minimum
  useEffect(() => {
    const trimmed = debouncedQuery.trim();
    if (trimmed.length < 2) {
      setFtsResults([]);
      setFtsLoading(false);
      return;
    }

    let cancelled = false;
    setFtsLoading(true);

    searchThreads(trimmed)
      .then((results) => {
        if (!cancelled) {
          setFtsResults(results);
          setFtsLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFtsResults([]);
          setFtsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [debouncedQuery]);

  // Ctrl+K / Cmd+K global shortcut — focus search, expanding sidebar if collapsed
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        if (collapsed) {
          onToggleCollapse();
          // Defer focus until sidebar DOM has expanded
          setTimeout(() => {
            searchInputRef.current?.focus();
          }, 0);
        } else {
          searchInputRef.current?.focus();
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [collapsed, onToggleCollapse]);

  async function handleNewChat() {
    const newThread = await createThread();
    const thread = {
      id: newThread.id,
      name: newThread.name,
      updated_at: new Date().toISOString(),
    };
    threadDispatch({ type: 'ADD_THREAD', thread });
    threadDispatch({ type: 'SET_ACTIVE', threadId: thread.id });
    chatDispatch({ type: 'SET_MESSAGES', messages: [] });
    chatDispatch({ type: 'SET_FEEDBACK_MAP', votes: [] });
  }

  async function handleSelectThread(threadId: number) {
    if (threadId === activeThreadId) return;

    // Abort any in-flight stream before switching threads
    if (isStreaming && onCancelStream) {
      onCancelStream();
    }

    threadDispatch({ type: 'SET_ACTIVE', threadId });
    // Clear messages immediately for responsiveness
    chatDispatch({ type: 'SET_MESSAGES', messages: [] });

    // Load thread history
    const { messages: rawMessages } = await getMessages(threadId);
    const parsed = parseHistoricalMessages(rawMessages);
    chatDispatch({ type: 'SET_MESSAGES', messages: parsed });

    // Load feedback state for the selected thread
    try {
      const votes = await getFeedbackForThread(threadId);
      chatDispatch({ type: 'SET_FEEDBACK_MAP', votes });
    } catch {
      chatDispatch({ type: 'SET_FEEDBACK_MAP', votes: [] });
    }
  }

  async function handleRename(threadId: number, newName: string) {
    await renameThread(threadId, newName);
    threadDispatch({ type: 'RENAME_THREAD', threadId, name: newName });
  }

  async function handleDelete(threadId: number) {
    const deletedIndex = flatThreads.findIndex((t) => t.id === threadId);
    await deleteThread(threadId);
    threadDispatch({ type: 'REMOVE_THREAD', threadId });

    if (threadId === activeThreadId) {
      const remaining = threads.filter((t) => t.id !== threadId);
      if (remaining.length > 0) {
        const nextIndex = Math.min(deletedIndex, remaining.length - 1);
        const next = remaining[nextIndex];
        threadDispatch({ type: 'SET_ACTIVE', threadId: next.id });
        chatDispatch({ type: 'SET_MESSAGES', messages: [] });
        const { messages: rawMessages } = await getMessages(next.id);
        const parsed = parseHistoricalMessages(rawMessages);
        chatDispatch({ type: 'SET_MESSAGES', messages: parsed });
        try {
          const votes = await getFeedbackForThread(next.id);
          chatDispatch({ type: 'SET_FEEDBACK_MAP', votes });
        } catch {
          chatDispatch({ type: 'SET_FEEDBACK_MAP', votes: [] });
        }
        setFocusAfterDeletion(nextIndex);
      } else {
        threadDispatch({ type: 'SET_ACTIVE', threadId: null });
        chatDispatch({ type: 'SET_MESSAGES', messages: [] });
        const btn = collapsed ? newChatBtnCollapsedRef.current : newChatBtnRef.current;
        btn?.focus();
      }
    }
  }

  async function handleSelectSearchResult(threadId: number) {
    await handleSelectThread(threadId);
    // Clear search state after navigating to result
    setSearchQuery('');
    setFtsResults([]);
  }

  function handleListKeyDown(e: React.KeyboardEvent) {
    const len = flatThreads.length;
    if (len === 0) return;
    let next = focusedIndex;
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        next = (focusedIndex + 1) % len;
        break;
      case 'ArrowUp':
        e.preventDefault();
        next = (focusedIndex - 1 + len) % len;
        break;
      case 'Home':
        e.preventDefault();
        next = 0;
        break;
      case 'End':
        e.preventDefault();
        next = len - 1;
        break;
      default:
        return;
    }
    setFocusedIndex(next);
    itemRefs.current[next]?.focus();
  }

  return (
    <div className="thread-list">
      <div className="thread-list-header">
        <button
          className="sidebar-toggle-btn"
          onClick={onToggleCollapse}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <PanelLeftExpandRegular /> : <PanelLeftContractRegular />}
        </button>
        {!collapsed && (
          <button
            ref={newChatBtnRef}
            className="new-chat-btn"
            onClick={handleNewChat}
            aria-label="New chat"
          >
            <ComposeRegular />
            <span>New Chat</span>
          </button>
        )}
      </div>
      {!collapsed && (
        <>
          <SearchInput
            query={searchQuery}
            onQueryChange={setSearchQuery}
            ftsResults={ftsResults}
            ftsLoading={ftsLoading}
            onSelectResult={handleSelectSearchResult}
            inputRef={searchInputRef}
          />
          <div role="listbox" aria-label="Conversations" onKeyDown={handleListKeyDown}>
            {flatThreads.length === 0 && searchQuery.trim() ? (
              <div className="search-no-threads">No threads match</div>
            ) : (
              groups.map((group) => (
                <div key={group.label} className="thread-group">
                  <div className="thread-group-heading" role="presentation">{group.label}</div>
                  {group.threads.map((thread) => {
                    const globalIndex = flatThreads.findIndex((t) => t.id === thread.id);
                    return (
                      <ThreadItem
                        key={thread.id}
                        thread={thread}
                        isActive={thread.id === activeThreadId}
                        tabIndexValue={globalIndex === focusedIndex ? 0 : -1}
                        itemRef={(el) => { itemRefs.current[globalIndex] = el; }}
                        onFocusInList={() => setFocusedIndex(globalIndex)}
                        onSelect={handleSelectThread}
                        onRename={handleRename}
                        onDelete={handleDelete}
                      />
                    );
                  })}
                </div>
              ))
            )}
          </div>
        </>
      )}
      {collapsed && (
        <button
          ref={newChatBtnCollapsedRef}
          className="new-chat-btn-collapsed"
          onClick={handleNewChat}
          aria-label="New chat"
        >
          <ComposeRegular />
        </button>
      )}
    </div>
  );
}
