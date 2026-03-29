import { CopyButton } from '../shared/CopyButton.tsx';
import { formatTimestamp } from '../../utils/formatTimestamp.ts';

interface Props {
  content: string;
  timestamp?: string;
}

export function UserMessage({ content, timestamp }: Props) {
  return (
    <div className="message user-message">
      {content}
      <div className="message-hover-actions">
        <CopyButton getText={() => content} />
      </div>
      {timestamp && (
        <div className="message-timestamp-overlay">
          {formatTimestamp(timestamp)}
        </div>
      )}
    </div>
  );
}
