import { useRef, useEffect } from 'react';
import { useChat } from '../../contexts/ChatContext.tsx';
import { UserMessage } from './UserMessage.tsx';
import { AssistantMessage } from './AssistantMessage.tsx';

export function MessageList() {
  const { messages, streamingMessage } = useChat();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // Only auto-scroll if the user is already near the bottom
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    if (isNearBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, streamingMessage]);

  return (
    <div className="chat-messages" ref={containerRef}>
      {messages.map((msg, idx) => {
        if (msg.type === 'user') {
          return <UserMessage key={idx} content={msg.content} timestamp={msg.timestamp} />;
        }
        return (
          <AssistantMessage
            key={idx}
            content={msg.content}
            toolPanels={msg.toolPanels}
            timestamp={msg.timestamp}
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
