import { useChat } from '../../contexts/ChatContext.tsx';
import { useThreads } from '../../contexts/ThreadContext.tsx';
import { createThread, deleteThread, getMessages, renameThread } from '../../api/threads.ts';
import { parseHistoricalMessages } from '../../utils/parseHistoricalMessages.ts';
import { ThreadItem } from './ThreadItem.tsx';

interface ThreadListProps {
  onCancelStream?: () => void;
}

export function ThreadList({ onCancelStream }: ThreadListProps) {
  const { threads, activeThreadId, dispatch: threadDispatch } = useThreads();
  const { isStreaming, dispatch: chatDispatch } = useChat();

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
  }

  async function handleRename(threadId: number, newName: string) {
    await renameThread(threadId, newName);
    threadDispatch({ type: 'RENAME_THREAD', threadId, name: newName });
  }

  async function handleDelete(threadId: number) {
    await deleteThread(threadId);
    threadDispatch({ type: 'REMOVE_THREAD', threadId });

    if (threadId === activeThreadId) {
      const remaining = threads.filter((t) => t.id !== threadId);
      if (remaining.length > 0) {
        const next = remaining[0];
        threadDispatch({ type: 'SET_ACTIVE', threadId: next.id });
        chatDispatch({ type: 'SET_MESSAGES', messages: [] });
        const { messages: rawMessages } = await getMessages(next.id);
        const parsed = parseHistoricalMessages(rawMessages);
        chatDispatch({ type: 'SET_MESSAGES', messages: parsed });
      } else {
        threadDispatch({ type: 'SET_ACTIVE', threadId: null });
        chatDispatch({ type: 'SET_MESSAGES', messages: [] });
      }
    }
  }

  return (
    <div className="thread-list">
      <button className="new-chat-btn" onClick={handleNewChat}>
        + New Chat
      </button>
      {threads.map((thread) => (
        <ThreadItem
          key={thread.id}
          thread={thread}
          isActive={thread.id === activeThreadId}
          onSelect={handleSelectThread}
          onRename={handleRename}
          onDelete={handleDelete}
        />
      ))}
    </div>
  );
}
