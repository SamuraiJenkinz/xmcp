import type { User, ForbiddenResponse } from '../types/index.ts';

type FetchMeResult =
  | { status: 'ok'; user: User }
  | { status: 'unauth'; user: null }
  | { status: 'forbidden'; user: null; upn: string };

export async function fetchMe(): Promise<FetchMeResult> {
  const res = await fetch('/api/me');
  if (res.status === 401) return { status: 'unauth', user: null };
  if (res.status === 403) {
    // Try to extract UPN from 403 JSON body
    let upn = '';
    try {
      const body = await res.json() as ForbiddenResponse;
      upn = body.upn ?? '';
    } catch { /* ignore parse errors */ }
    return { status: 'forbidden', user: null, upn };
  }
  if (!res.ok) throw new Error(`fetchMe failed: ${res.status}`);
  const contentType = res.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) throw new Error('fetchMe: unexpected content type');
  const data = await res.json() as User;
  return { status: 'ok', user: data };
}
