import { useEffect, useRef, useState } from 'react';

interface InputAreaProps {
  onSend: (message: string) => void;
  onCancel: () => void;
  isStreaming: boolean;
  disabled?: boolean;
}

export function InputArea({ onSend, onCancel, isStreaming, disabled }: InputAreaProps) {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-focus on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  function adjustHeight() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }

  function resetHeight() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
  }

  function handleSubmit() {
    const trimmed = message.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setMessage('');
    resetHeight();
    textareaRef.current?.focus();
  }

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setMessage(e.target.value);
    adjustHeight();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === 'Escape') {
      if (isStreaming) {
        onCancel();
      }
    }
    // Shift+Enter: default behavior (newline) — do nothing
  }

  const isButtonDisabled = disabled || (!isStreaming && message.trim() === '');

  return (
    <div className="input-area">
      <textarea
        ref={textareaRef}
        className="chat-input"
        placeholder="Type a message..."
        rows={1}
        value={message}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        disabled={disabled}
      />
      {isStreaming ? (
        <button className="send-btn" onClick={onCancel} disabled={isButtonDisabled}>
          Stop
        </button>
      ) : (
        <button className="send-btn" onClick={handleSubmit} disabled={isButtonDisabled}>
          Send
        </button>
      )}
    </div>
  );
}
