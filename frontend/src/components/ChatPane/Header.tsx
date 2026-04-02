import { useAuth } from '../../contexts/AuthContext.tsx';
import { useChat } from '../../contexts/ChatContext.tsx';
import { useThreads } from '../../contexts/ThreadContext.tsx';
import { messagesToMarkdown } from '../../utils/exportMarkdown.ts';
import { exportFilename } from '../../utils/slugify.ts';
import { downloadBlob } from '../../utils/downloadBlob.ts';
import { ExportMenu } from './ExportMenu.tsx';

interface HeaderProps {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export function Header({ theme, onToggleTheme }: HeaderProps) {
  const { user } = useAuth();
  const { messages, isStreaming } = useChat();
  const { threads, activeThreadId } = useThreads();

  const displayName = user?.displayName || user?.email || '';

  // Match app.js exactly: crescent moon in dark mode, sun in light mode
  const themeIcon = theme === 'dark' ? '☾' : '☀';

  const exportDisabled = isStreaming || messages.length === 0;

  function handleExportMarkdown() {
    const threadName = threads.find((t) => t.id === activeThreadId)?.name ?? 'conversation';
    const dateStr = new Date().toISOString().slice(0, 10);
    const markdown = messagesToMarkdown(messages, threadName, dateStr);
    downloadBlob(markdown, exportFilename(threadName));
  }

  return (
    <header className="chat-header">
      <span className="user-info">{displayName}</span>
      <ExportMenu onExportMarkdown={handleExportMarkdown} disabled={exportDisabled} />
      <button className="theme-toggle-btn" onClick={onToggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`} title="Toggle theme">
        {themeIcon}
      </button>
      <a className="logout-btn" href="/logout">
        Logout
      </a>
    </header>
  );
}
