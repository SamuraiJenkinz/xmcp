import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { fetchMe } from '../api/me.ts';
import type { User, AuthStatus } from '../types/index.ts';

interface AuthState {
  status: AuthStatus;
  user: User | null;
  upn: string | null;    // populated on 403 from the backend response
  error: string | null;
}

interface AuthContextValue extends AuthState {}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    status: 'loading',
    user: null,
    upn: null,
    error: null,
  });

  useEffect(() => {
    fetchMe()
      .then((result) => {
        if (result.status === 'ok') {
          setState({ status: 'authenticated', user: result.user, upn: null, error: null });
        } else if (result.status === 'forbidden') {
          setState({ status: 'forbidden', user: null, upn: result.upn, error: null });
        } else {
          setState({ status: 'unauthenticated', user: null, upn: null, error: null });
        }
      })
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : String(err);
        setState({ status: 'error', user: null, upn: null, error: message });
      });
  }, []);

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
