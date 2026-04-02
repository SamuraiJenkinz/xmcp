import type { DisplayMessage, ToolPanelData } from '../types/index.ts';

function formatToolPanel(tool: ToolPanelData): string {
  const lines: string[] = [];

  // Heading with timing if available
  const hasElapsed = tool.startTime != null && tool.endTime != null;
  const elapsed = hasElapsed ? Math.round((tool.endTime! - tool.startTime!) * 1000) : null;
  const timingStr = elapsed != null ? `, ${elapsed}ms` : '';
  lines.push(`### Tool: ${tool.name} (${tool.status}${timingStr})`);
  lines.push('');

  // Parameters block (skip if empty object)
  if (Object.keys(tool.params).length > 0) {
    lines.push('**Parameters:**');
    lines.push('```json');
    lines.push(JSON.stringify(tool.params, null, 2));
    lines.push('```');
    lines.push('');
  }

  // Result block (skip if null)
  if (tool.result !== null) {
    lines.push('**Result:**');
    lines.push('```json');
    try {
      const parsed = JSON.parse(tool.result);
      lines.push(JSON.stringify(parsed, null, 2));
    } catch {
      lines.push(tool.result);
    }
    lines.push('```');
    lines.push('');
  }

  return lines.join('\n');
}

export function messagesToMarkdown(
  messages: DisplayMessage[],
  threadName: string,
  exportDate: string,
): string {
  const lines: string[] = [];

  // Header
  lines.push(`# ${threadName}`);
  lines.push('');
  lines.push(`Export date: ${exportDate}`);
  lines.push('');
  lines.push('---');
  lines.push('');

  // Message turns
  for (const message of messages) {
    if (message.type === 'user') {
      lines.push('## User');
      lines.push('');
      lines.push(message.content);
      lines.push('');
      lines.push('---');
      lines.push('');
    } else {
      lines.push('## Assistant');
      lines.push('');

      // Tool panels BEFORE content (mirrors UI order)
      if (message.toolPanels && message.toolPanels.length > 0) {
        for (const tool of message.toolPanels) {
          lines.push(formatToolPanel(tool));
        }
      }

      lines.push(message.content);
      lines.push('');
      lines.push('---');
      lines.push('');
    }
  }

  return lines.join('\n');
}
