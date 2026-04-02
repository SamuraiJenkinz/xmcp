import type { Thread, RawMessage } from '../types/index.ts';

export interface SearchResult {
  id: number;
  name: string;
  updated_at: string;
  snippet: string;
}

export async function searchThreads(q: string): Promise<SearchResult[]> {
  const res = await fetch(`/api/threads/search?q=${encodeURIComponent(q)}`);
  if (!res.ok) throw new Error(`searchThreads failed: ${res.status}`);
  return res.json() as Promise<SearchResult[]>;
}

export async function listThreads(): Promise<Thread[]> {
  const res = await fetch('/api/threads');
  if (!res.ok) throw new Error(`listThreads failed: ${res.status}`);
  return res.json() as Promise<Thread[]>;
}

export async function createThread(): Promise<{ id: number; name: string }> {
  const res = await fetch('/api/threads', { method: 'POST' });
  if (!res.ok) throw new Error(`createThread failed: ${res.status}`);
  return res.json() as Promise<{ id: number; name: string }>;
}

export async function renameThread(id: number, name: string): Promise<{ id: number; name: string }> {
  const res = await fetch(`/api/threads/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`renameThread failed: ${res.status}`);
  return res.json() as Promise<{ id: number; name: string }>;
}

export async function deleteThread(id: number): Promise<{ deleted: true }> {
  const res = await fetch(`/api/threads/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`deleteThread failed: ${res.status}`);
  return res.json() as Promise<{ deleted: true }>;
}

export async function getMessages(threadId: number): Promise<{ messages: RawMessage[] }> {
  const res = await fetch(`/api/threads/${threadId}/messages`);
  if (!res.ok) throw new Error(`getMessages failed: ${res.status}`);
  return res.json() as Promise<{ messages: RawMessage[] }>;
}
