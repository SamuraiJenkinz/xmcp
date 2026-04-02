import { useRef, useEffect } from 'react';
import { useChat } from '../../contexts/ChatContext.tsx';
import { useThreads } from '../../contexts/ThreadContext.tsx';
import { UserMessage } from './UserMessage.tsx';
import { AssistantMessage } from './AssistantMessage.tsx';

interface MessageListProps {
  onChipSend?: (text: string) => void;
}

export function MessageList({ onChipSend }: MessageListProps) {
  const { messages, streamingMessage } = useChat();
  const { activeThreadId } = useThreads();
  const containerRef = useRef<HTMLDivElement>(null);
  // Snapshot the message count at the time of last thread load so that
  // only messages added after the switch animate (ANIM historical gate).
  const loadedCountRef = useRef(messages.length);

  useEffect(() => {
    // When thread changes, SET_MESSAGES has already run, so messages.length
    // reflects the historical count. Any messages added after this are "new".
    loadedCountRef.current = messages.length;
  }, [activeThreadId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // Only auto-scroll if the user is already near the bottom
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    if (isNearBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, streamingMessage]);

  if (messages.length === 0 && streamingMessage === null) {
    return (
      <div className="chat-messages" id="chat-messages" tabIndex={-1} ref={containerRef}>
        <div className="welcome-state">
          <div className="welcome-icon" aria-hidden="true">&#9889;</div>
          <h2 className="welcome-heading">How can I help with Exchange today?</h2>
          <div className="prompt-chips-grid">
            <button className="prompt-chip" onClick={() => onChipSend?.('Check mailbox quota')}>
              <span className="prompt-chip-icon" aria-hidden="true">&#128231;</span>
              Check mailbox quota
            </button>
            <button className="prompt-chip" onClick={() => onChipSend?.('Trace a message')}>
              <span className="prompt-chip-icon" aria-hidden="true">&#128269;</span>
              Trace a message
            </button>
            <button className="prompt-chip" onClick={() => onChipSend?.('DAG health status')}>
              <span className="prompt-chip-icon" aria-hidden="true">&#128421;</span>
              DAG health status
            </button>
            <button className="prompt-chip" onClick={() => onChipSend?.('Look up a colleague')}>
              <span className="prompt-chip-icon" aria-hidden="true">&#128100;</span>
              Look up a colleague
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-messages" id="chat-messages" tabIndex={-1} ref={containerRef}>
      {messages.map((msg, idx) => {
        const isNew = idx >= loadedCountRef.current;
        if (msg.type === 'user') {
          return <UserMessage key={idx} content={msg.content} timestamp={msg.timestamp} isNew={isNew} />;
        }
        // Compute assistant-message ordinal (0-based) for feedback keying
        const assistantIdx = messages
          .slice(0, idx + 1)
          .filter(m => m.type === 'assistant').length - 1;
        return (
          <AssistantMessage
            key={idx}
            content={msg.content}
            toolPanels={msg.toolPanels}
            timestamp={msg.timestamp}
            threadId={activeThreadId ?? undefined}
            messageIndex={assistantIdx}
            isNew={isNew}
          />
        );
      })}
      {streamingMessage !== null && (
        <AssistantMessage
          content={streamingMessage.content}
          toolPanels={streamingMessage.toolPanels}
          isStreaming={true}
        />
      )}
    </div>
  );
}
