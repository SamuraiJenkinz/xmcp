import { useCallback, useState } from 'react';
import { createThread } from '../api/threads.ts';
import { useChat } from '../contexts/ChatContext.tsx';
import { useThreads } from '../contexts/ThreadContext.tsx';
import { useStreamingMessage } from '../hooks/useStreamingMessage.ts';
import { ThreadList } from './Sidebar/ThreadList.tsx';
import { MessageList } from './ChatPane/MessageList.tsx';
import { InputArea } from './ChatPane/InputArea.tsx';
import { Header } from './ChatPane/Header.tsx';

interface AppLayoutProps {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export function AppLayout({ theme, onToggleTheme }: AppLayoutProps) {
  const { activeThreadId, dispatch: threadDispatch } = useThreads();
  const { isStreaming, dispatch: chatDispatch } = useChat();

  const { startStream, cancelStream } = useStreamingMessage({
    onText: useCallback(
      (delta: string) => {
        chatDispatch({ type: 'APPEND_STREAMING_CHUNK', delta });
      },
      [chatDispatch]
    ),
    onTool: useCallback(
      (tool) => {
        chatDispatch({ type: 'ADD_TOOL_EVENT', tool });
      },
      [chatDispatch]
    ),
    onThreadNamed: useCallback(
      (threadId: number, name: string) => {
        threadDispatch({ type: 'RENAME_THREAD', threadId, name });
        threadDispatch({ type: 'BUMP_THREAD', threadId });
      },
      [threadDispatch]
    ),
    onDone: useCallback(() => {
      chatDispatch({ type: 'FINALIZE_STREAMING' });
    }, [chatDispatch]),
    onError: useCallback(
      (message: string) => {
        chatDispatch({ type: 'SET_ERROR', error: message });
      },
      [chatDispatch]
    ),
    onCancel: useCallback(() => {
      chatDispatch({ type: 'CANCEL_STREAMING' });
    }, [chatDispatch]),
  });

  const handleSend = useCallback(
    async (message: string) => {
      let threadId = activeThreadId;

      if (threadId === null) {
        // Create a new thread before sending
        const newThread = await createThread();
        const thread = {
          id: newThread.id,
          name: newThread.name,
          updated_at: new Date().toISOString(),
        };
        threadDispatch({ type: 'ADD_THREAD', thread });
        threadDispatch({ type: 'SET_ACTIVE', threadId: thread.id });
        chatDispatch({ type: 'SET_MESSAGES', messages: [] });
        threadId = thread.id;
      }

      chatDispatch({ type: 'ADD_USER_MESSAGE', content: message });
      startStream(message, threadId);
    },
    [activeThreadId, chatDispatch, threadDispatch, startStream]
  );

  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem('atlas-sidebar-collapsed') === 'true'
  );

  function handleToggleSidebar() {
    const next = !sidebarCollapsed;
    setSidebarCollapsed(next);
    localStorage.setItem('atlas-sidebar-collapsed', String(next));
  }

  const handleCancel = useCallback(() => {
    cancelStream();
  }, [cancelStream]);

  return (
    <div className="app-container">
      <aside className="sidebar" data-collapsed={sidebarCollapsed ? 'true' : undefined}>
        <ThreadList
          onCancelStream={handleCancel}
          collapsed={sidebarCollapsed}
          onToggleCollapse={handleToggleSidebar}
        />
      </aside>
      <main className="chat-pane">
        <Header theme={theme} onToggleTheme={onToggleTheme} />
        <MessageList onChipSend={handleSend} />
        <InputArea
          onSend={handleSend}
          onCancel={handleCancel}
          isStreaming={isStreaming}
          disabled={!activeThreadId}
        />
      </main>
    </div>
  );
}
