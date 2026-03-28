import type { ToolPanelData } from '../../types/index.ts';
import { CopyButton } from '../shared/CopyButton.tsx';

type Props = ToolPanelData;

function prettyResult(result: string): string {
  try {
    return JSON.stringify(JSON.parse(result), null, 2);
  } catch {
    return result;
  }
}

export function ToolPanel({ name, status, params, result }: Props) {
  const hasParams = Object.keys(params).length > 0;

  return (
    <details className="tool-panel">
      <summary className="tool-panel-summary">
        <span className="tool-panel-icon" />
        <span className="tool-panel-name">{name}</span>
        <span className={`tool-panel-status ${status === 'success' ? 'status-success' : 'status-error'}`}>
          {status}
        </span>
      </summary>
      <div className="tool-panel-body">
        {hasParams && (
          <>
            <div className="tool-panel-label">Parameters</div>
            <pre className="tool-panel-json">{JSON.stringify(params, null, 2)}</pre>
          </>
        )}
        {result !== null && (
          <>
            <div className="tool-panel-label">Exchange Result</div>
            <pre className="tool-panel-json tool-panel-result">{prettyResult(result)}</pre>
            <CopyButton getText={() => result} />
          </>
        )}
      </div>
    </details>
  );
}
