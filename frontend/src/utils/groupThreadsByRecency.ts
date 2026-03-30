import type { Thread } from '../types/index.ts';

export interface ThreadGroup {
  label: 'Today' | 'Yesterday' | 'This Week' | 'Older';
  threads: Thread[];
}

function getLocalMidnight(daysAgo: number): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - daysAgo);
  return d;
}

export function groupThreadsByRecency(threads: Thread[]): ThreadGroup[] {
  const todayMidnight = getLocalMidnight(0);
  const yesterdayMidnight = getLocalMidnight(1);
  // getDay() returns 0 for Sunday — use 7 so "This Week" looks back 7 days on Sunday
  const dayOfWeek = new Date().getDay();
  const weekStart = getLocalMidnight(dayOfWeek === 0 ? 7 : dayOfWeek);

  const groups: ThreadGroup[] = [
    { label: 'Today', threads: [] },
    { label: 'Yesterday', threads: [] },
    { label: 'This Week', threads: [] },
    { label: 'Older', threads: [] },
  ];

  for (const thread of threads) {
    const ts = new Date(thread.updated_at).getTime();
    if (ts >= todayMidnight.getTime()) {
      groups[0].threads.push(thread);
    } else if (ts >= yesterdayMidnight.getTime()) {
      groups[1].threads.push(thread);
    } else if (ts >= weekStart.getTime()) {
      groups[2].threads.push(thread);
    } else {
      groups[3].threads.push(thread);
    }
  }

  return groups.filter(g => g.threads.length > 0);
}
