export function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  const diffHours = Math.floor(diffMs / 3_600_000);

  if (diffMs < 60_000) return 'just now';
  if (diffHours < 24) {
    const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
    if (diffMins < 60) return rtf.format(-diffMins, 'minute');
    return rtf.format(-diffHours, 'hour');
  }
  return date.toLocaleString('en', {
    month: 'short', day: 'numeric',
    hour: 'numeric', minute: '2-digit',
  });
}
