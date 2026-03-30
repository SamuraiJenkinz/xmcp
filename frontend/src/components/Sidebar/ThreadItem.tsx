import { useEffect, useRef, useState } from 'react';
import type { Thread } from '../../types/index.ts';

interface ThreadItemProps {
  thread: Thread;
  isActive: boolean;
  tabIndexValue: 0 | -1;
  itemRef: (el: HTMLButtonElement | null) => void;
  onFocusInList: () => void;
  onSelect: (threadId: number) => void;
  onRename: (threadId: number, newName: string) => void;
  onDelete: (threadId: number) => void;
}

export function ThreadItem({
  thread,
  isActive,
  tabIndexValue,
  itemRef,
  onFocusInList,
  onSelect,
  onRename,
  onDelete,
}: ThreadItemProps) {
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

  function handleInputKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    // Stop propagation so arrow keys / Enter don't bubble up to the listbox handler
    e.stopPropagation();
    if (e.key === 'Enter') {
      commitRename();
    } else if (e.key === 'Escape') {
      setIsEditing(false);
    }
  }

  const displayName = thread.name || 'New Chat';
  const itemClass = `thread-item${isActive ? ' thread-item-active' : ''}`;

  return (
    <button
      role="option"
      aria-selected={isActive}
      tabIndex={tabIndexValue}
      ref={itemRef}
      className={itemClass}
      onClick={() => onSelect(thread.id)}
      onFocus={onFocusInList}
    >
      {isEditing ? (
        <input
          ref={inputRef}
          className="thread-item-name thread-item-name-input"
          value={editName}
          onChange={(e) => setEditName(e.target.value)}
          onBlur={handleBlur}
          onKeyDown={handleInputKeyDown}
          onClick={(e) => e.stopPropagation()}
          tabIndex={-1}
        />
      ) : (
        <span className="thread-item-name">{displayName}</span>
      )}
      <div className="thread-actions">
        <span
          role="button"
          tabIndex={-1}
          className="thread-action-btn"
          aria-label="Rename conversation"
          title="Rename"
          onClick={handleRenameClick}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              handleRenameClick(e as unknown as React.MouseEvent);
            }
          }}
        >
          ✏️
        </span>
        <span
          role="button"
          tabIndex={-1}
          className="thread-action-btn"
          aria-label="Delete conversation"
          title="Delete"
          onClick={handleDeleteClick}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              handleDeleteClick(e as unknown as React.MouseEvent);
            }
          }}
        >
          🗑️
        </span>
      </div>
    </button>
  );
}
