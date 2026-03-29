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

  const isButtonDisabled = disabled || message.trim() === '';

  return (
    <div className="input-area">
      <textarea
        ref={textareaRef}
        className="chat-input"
        placeholder="Ask Atlas anything about Exchange..."
        rows={1}
        value={message}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        readOnly={isStreaming}
        disabled={disabled && !isStreaming}
      />
      {isStreaming ? (
        <button
          className="stop-btn"
          onClick={onCancel}
          aria-label="Stop generating"
          type="button"
        />
      ) : (
        <button className="send-btn" onClick={handleSubmit} disabled={isButtonDisabled} type="button">
          Send
        </button>
      )}
    </div>
  );
}
