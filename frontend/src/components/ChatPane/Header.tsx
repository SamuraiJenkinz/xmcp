import { useAuth } from '../../contexts/AuthContext.tsx';

interface HeaderProps {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export function Header({ theme, onToggleTheme }: HeaderProps) {
  const { user } = useAuth();

  const displayName = user?.displayName || user?.email || '';

  // Match app.js exactly: crescent moon in dark mode, sun in light mode
  const themeIcon = theme === 'dark' ? '☾' : '☀';

  return (
    <header className="chat-header">
      <span className="user-info">{displayName}</span>
      <button className="theme-toggle-btn" onClick={onToggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`} title="Toggle theme">
        {themeIcon}
      </button>
      <a className="logout-btn" href="/logout">
        Logout
      </a>
    </header>
  );
}
