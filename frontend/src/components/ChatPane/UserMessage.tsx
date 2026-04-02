import * as m from 'motion/react-m';
import { CopyButton } from '../shared/CopyButton.tsx';
import { formatTimestamp } from '../../utils/formatTimestamp.ts';

interface Props {
  content: string;
  isNew?: boolean;
  timestamp?: string;
}

export function UserMessage({ content, isNew, timestamp }: Props) {
  const Wrapper = isNew ? m.div : 'div';
  const motionProps = isNew ? {
    initial: { opacity: 0, y: 8 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.15, ease: 'easeOut' as const },
  } : {};

  return (
    <Wrapper className="message user-message" {...motionProps}>
      {content}
      <div className="message-hover-actions">
        <CopyButton getText={() => content} />
      </div>
      {timestamp && (
        <div className="message-timestamp-overlay">
          {formatTimestamp(timestamp)}
        </div>
      )}
    </Wrapper>
  );
}
