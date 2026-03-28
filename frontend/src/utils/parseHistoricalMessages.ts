import { RawMessage, DisplayMessage, ToolPanelData } from '../types';

/**
 * DEBT-01 frontend fix: Parse raw OpenAI-format messages into display-ready
 * messages with tool panels re-attached.
 *
 * Tool messages (role: "assistant" with tool_calls + role: "tool") are already
 * persisted in messages_json. This function pairs each tool_call with its
 * matching tool result via tool_call_id and attaches accumulated tool panels
 * to the subsequent content-bearing assistant message.
 *
 * This handles multi-turn tool loops correctly: an assistant message may have
 * tool_calls but no content (model is invoking tools), followed by one or more
 * role:"tool" result messages, followed by another assistant message that has
 * the final content. All tool panels from the loop are collected and attached
 * to the final content-bearing assistant message.
 */
export function parseHistoricalMessages(raw: RawMessage[]): DisplayMessage[] {
  const result: DisplayMessage[] = [];
  let pendingToolPanels: ToolPanelData[] = [];
  let i = 0;

  while (i < raw.length) {
    const msg = raw[i];

    if (msg.role === 'system') {
      i++;
      continue;
    }

    if (msg.role === 'user') {
      result.push({ type: 'user', content: msg.content ?? '' });
      i++;
      continue;
    }

    if (msg.role === 'assistant') {
      if (msg.tool_calls) {
        // Collect tool panels for each tool call in this assistant message
        for (const tc of msg.tool_calls) {
          let params: Record<string, unknown> = {};
          try {
            params = JSON.parse(tc.function.arguments);
          } catch {
            // Malformed arguments — keep empty params
          }

          // Look ahead for the matching tool result message
          let toolResult: string | null = null;
          for (let j = i + 1; j < raw.length; j++) {
            if (raw[j].role === 'tool' && raw[j].tool_call_id === tc.id) {
              toolResult = raw[j].content ?? '';
              break;
            }
            // Stop looking if we hit the next assistant message — the tool
            // result for this call should always precede the next assistant turn
            if (raw[j].role === 'assistant') break;
          }

          pendingToolPanels.push({
            name: tc.function.name,
            params,
            result: toolResult,
            status: 'success',
          });
        }
      }

      if (msg.content) {
        // Content-bearing assistant message — attach all accumulated tool panels
        result.push({
          type: 'assistant',
          content: msg.content,
          toolPanels: pendingToolPanels.length > 0 ? [...pendingToolPanels] : undefined,
        });
        pendingToolPanels = [];
      }

      i++;
      continue;
    }

    if (msg.role === 'tool') {
      // Tool results are consumed during the assistant+tool_calls scan above;
      // we skip them here to avoid double-processing.
      i++;
      continue;
    }

    // Unknown role — skip
    i++;
  }

  return result;
}
