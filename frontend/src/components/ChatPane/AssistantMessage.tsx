import { useRef, useEffect } from 'react';
import type { ToolPanelData } from '../../types/index.ts';
import { MarkdownRenderer } from './MarkdownRenderer.tsx';
import { CopyButton } from '../shared/CopyButton.tsx';
import { ToolPanel } from './ToolPanel.tsx';
import { ProfileCard } from './ProfileCard.tsx';
import { SearchResultCard } from './SearchResultCard.tsx';
import { formatTimestamp } from '../../utils/formatTimestamp.ts';

interface Props {
  content: string;
  toolPanels?: ToolPanelData[];
  isStreaming?: boolean;
  timestamp?: string;
}

function renderToolPanel(panel: ToolPanelData, idx: number) {
  if (panel.status === 'success') {
    if (panel.name === 'get_colleague_profile') {
      return <ProfileCard key={idx} resultJson={panel.result ?? ''} />;
    }
    if (panel.name === 'search_colleagues') {
      return <SearchResultCard key={idx} resultJson={panel.result ?? ''} />;
    }
  }
  return <ToolPanel key={idx} {...panel} />;
}

export function AssistantMessage({ content, toolPanels, isStreaming, timestamp }: Props) {
  // Track latest content in a ref so CopyButton's getText() always reads current value
  const contentRef = useRef(content);
  useEffect(() => {
    contentRef.current = content;
  }, [content]);

  return (
    <div className="message assistant-message">
      {toolPanels && toolPanels.length > 0 && (
        <div className="tool-panels">
          {toolPanels.map((panel, idx) => renderToolPanel(panel, idx))}
        </div>
      )}
      <MarkdownRenderer content={content} />
      {isStreaming && <span className="streaming-cursor" aria-hidden="true" />}
      {!isStreaming && (
        <div className="message-hover-actions">
          <CopyButton getText={() => contentRef.current} />
        </div>
      )}
      {!isStreaming && timestamp && (
        <div className="message-timestamp-overlay">
          {formatTimestamp(timestamp)}
        </div>
      )}
    </div>
  );
}
