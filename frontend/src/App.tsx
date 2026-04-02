import { useState } from 'react';
import { FluentProvider, webDarkTheme, webLightTheme } from '@fluentui/react-components';
import { AuthProvider, useAuth } from './contexts/AuthContext.tsx';
import { ThreadProvider } from './contexts/ThreadContext.tsx';
import { ChatProvider } from './contexts/ChatContext.tsx';
import { AppLayout } from './components/AppLayout.tsx';
import { AccessDenied } from './components/AccessDenied.tsx';

// Set data-theme attribute immediately from localStorage so CSS variables
// apply before React renders.
const storedTheme = (localStorage.getItem('atlas-theme') as 'light' | 'dark') || 'light';
document.documentElement.setAttribute('data-theme', storedTheme);

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { status, upn } = useAuth();

  if (status === 'loading') {
    return <div className="loading">Loading...</div>;
  }
  if (status === 'unauthenticated' || status === 'error') {
    window.location.href = '/login';
    return null;
  }
  if (status === 'forbidden') {
    return <AccessDenied upn={upn} />;
  }
  // status === 'authenticated'
  return <>{children}</>;
}

export default function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>(storedTheme);

  function handleToggleTheme() {
    const newTheme: 'light' | 'dark' = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem('atlas-theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  }

  return (
    <FluentProvider theme={theme === 'dark' ? webDarkTheme : webLightTheme}>
      <AuthProvider>
        <AuthGuard>
          <ThreadProvider>
            <ChatProvider>
              <AppLayout theme={theme} onToggleTheme={handleToggleTheme} />
            </ChatProvider>
          </ThreadProvider>
        </AuthGuard>
      </AuthProvider>
    </FluentProvider>
  );
}
