import type { User } from '../types/index.ts';

export async function fetchMe(): Promise<User | null> {
  const res = await fetch('/api/me');
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`fetchMe failed: ${res.status}`);
  return res.json() as Promise<User>;
}
