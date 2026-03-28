import { useEffect, useRef, useState } from 'react';
import type { Thread } from '../../types/index.ts';

interface ThreadItemProps {
  thread: Thread;
  isActive: boolean;
  onSelect: (threadId: number) => void;
  onRename: (threadId: number, newName: string) => void;
  onDelete: (threadId: number) => void;
}

export function ThreadItem({ thread, isActive, onSelect, onRename, onDelete }: ThreadItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-focus input when entering edit mode
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  function handleRenameClick(e: React.MouseEvent) {
    e.stopPropagation();
    setEditName(thread.name);
    setIsEditing(true);
  }

  function handleDeleteClick(e: React.MouseEvent) {
    e.stopPropagation();
    if (window.confirm(`Delete "${thread.name || 'New Chat'}"? This cannot be undone.`)) {
      onDelete(thread.id);
    }
  }

  function commitRename() {
    const trimmed = editName.trim();
    if (trimmed !== thread.name) {
      onRename(thread.id, trimmed);
    }
    setIsEditing(false);
  }

  function handleBlur() {
    commitRename();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      commitRename();
    } else if (e.key === 'Escape') {
      setIsEditing(false);
    }
  }

  const displayName = thread.name || 'New Chat';
  const itemClass = `thread-item${isActive ? ' thread-item-active' : ''}`;

  return (
    <div className={itemClass} onClick={() => onSelect(thread.id)}>
      {isEditing ? (
        <input
          ref={inputRef}
          className="thread-item-name thread-item-name-input"
          value={editName}
          onChange={(e) => setEditName(e.target.value)}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          onClick={(e) => e.stopPropagation()}
        />
      ) : (
        <span className="thread-item-name">{displayName}</span>
      )}
      <div className="thread-actions">
        <button
          className="thread-action-btn"
          title="Rename"
          onClick={handleRenameClick}
        >
          ✏️
        </button>
        <button
          className="thread-action-btn"
          title="Delete"
          onClick={handleDeleteClick}
        >
          🗑️
        </button>
      </div>
    </div>
  );
}
