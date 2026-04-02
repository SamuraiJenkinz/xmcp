export function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')   // strip non-word chars except spaces and hyphens
    .replace(/[\s_]+/g, '-')    // spaces and underscores to hyphens
    .replace(/-{2,}/g, '-')     // collapse multiple hyphens
    .replace(/^-+|-+$/g, '');   // trim leading/trailing hyphens
}

export function exportFilename(threadName: string, date: Date = new Date()): string {
  const slug = slugify(threadName) || 'conversation';
  const dateStr = date.toISOString().slice(0, 10);
  return `${slug}-${dateStr}.md`;
}
