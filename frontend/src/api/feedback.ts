import type { FeedbackVote } from '../types/index.ts';

export async function getFeedbackForThread(threadId: number): Promise<FeedbackVote[]> {
  const res = await fetch(`/api/threads/${threadId}/feedback`);
  if (!res.ok) throw new Error(`getFeedback failed: ${res.status}`);
  return res.json() as Promise<FeedbackVote[]>;
}

export async function submitFeedback(
  threadId: number,
  messageIndex: number,
  vote: 'up' | 'down' | null,
  comment: string | null,
): Promise<void> {
  if (vote === null) {
    // Retraction — delete the vote
    await fetch(`/api/threads/${threadId}/feedback/${messageIndex}`, {
      method: 'DELETE',
    });
    return;
  }
  await fetch(`/api/threads/${threadId}/feedback/${messageIndex}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vote, comment }),
  });
}
