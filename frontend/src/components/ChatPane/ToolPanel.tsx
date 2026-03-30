import { useState } from 'react';
import { ChevronRight16Regular } from '@fluentui/react-icons';
import type { ToolPanelData } from '../../types/index.ts';
import { CopyButton } from '../shared/CopyButton.tsx';
import { syntaxHighlightJson } from '../../utils/syntaxHighlightJson.ts';

type Props = ToolPanelData;

function formatElapsed(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function prettyJson(result: string): { plain: string; highlighted: string } {
  try {
    const parsed = JSON.stringify(JSON.parse(result), null, 2);
    return { plain: parsed, highlighted: syntaxHighlightJson(parsed) };
  } catch {
    return { plain: result, highlighted: result };
  }
}

export function ToolPanel({ name, status, params, result, startTime, endTime }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const hasParams = Object.keys(params).length > 0;

  const elapsedMs = (startTime != null && endTime != null)
    ? Math.round((endTime - startTime) * 1000)
    : null;

  const statusLabel = status === 'success' ? 'Done' : 'Error';

  const paramsJson = hasParams ? syntaxHighlightJson(JSON.stringify(params, null, 2)) : '';
  const resultData = result !== null ? prettyJson(result) : null;

  return (
    <details
      className="tool-panel"
      onToggle={(e) => setIsOpen((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="tool-panel-summary">
        <ChevronRight16Regular
          className={`tool-panel-chevron${isOpen ? ' tool-panel-chevron-open' : ''}`}
        />
        <span className="tool-panel-name">{name}</span>
        <span className={`tool-panel-badge tool-panel-badge-${status}`}>
          {statusLabel}
        </span>
        {elapsedMs !== null && (
          <span className="tool-panel-elapsed">Ran in {formatElapsed(elapsedMs)}</span>
        )}
      </summary>
      <div className="tool-panel-body">
        {hasParams && (
          <>
            <div className="tool-panel-label">Parameters</div>
            <pre
              className="tool-panel-json"
              dangerouslySetInnerHTML={{ __html: paramsJson }}
            />
          </>
        )}
        {resultData !== null && (
          <>
            <div className="tool-panel-label">Exchange Result</div>
            <pre
              className="tool-panel-json tool-panel-result"
              dangerouslySetInnerHTML={{ __html: resultData.highlighted }}
            />
            <CopyButton getText={() => resultData.plain} />
          </>
        )}
      </div>
    </details>
  );
}
