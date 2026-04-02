import React from 'react';
import { SearchBox, Spinner, CounterBadge } from '@fluentui/react-components';
import type { SearchBoxChangeEvent, InputOnChangeData } from '@fluentui/react-components';
import type { SearchResult } from '../../api/threads.ts';

interface SearchInputProps {
  query: string;
  onQueryChange: (q: string) => void;
  ftsResults: SearchResult[];
  ftsLoading: boolean;
  onSelectResult: (threadId: number) => void;
  inputRef: React.RefObject<HTMLInputElement | null>;
}

export function SearchInput({
  query,
  onQueryChange,
  ftsResults,
  ftsLoading,
  onSelectResult,
  inputRef,
}: SearchInputProps) {
  function handleChange(_e: SearchBoxChangeEvent, data: InputOnChangeData) {
    onQueryChange(data.value);
  }

  const showFtsSection = query.trim().length >= 2;

  return (
    <div className="search-input-container">
      <SearchBox
        ref={inputRef}
        value={query}
        onChange={handleChange}
        placeholder="Search threads..."
        aria-label="Search threads"
        className="search-box"
      />

      {showFtsSection && (
        <div className="search-fts-results" role="listbox" aria-label="Message matches">
          {ftsLoading && (
            <div className="search-fts-loading">
              <Spinner size="extra-small" label="Searching..." labelPosition="after" />
            </div>
          )}

          {!ftsLoading && ftsResults.length > 0 && (
            <>
              <div className="search-fts-heading">
                <span className="search-fts-label">Message matches</span>
                <CounterBadge
                  count={ftsResults.length}
                  size="small"
                  color="informative"
                  aria-label={`${ftsResults.length} message matches`}
                />
              </div>
              {ftsResults.map((result) => (
                <button
                  key={result.id}
                  className="search-fts-item"
                  role="option"
                  aria-selected={false}
                  onClick={() => onSelectResult(result.id)}
                >
                  <span className="search-fts-item-name">{result.name || 'New Chat'}</span>
                  {result.snippet && (
                    <span className="search-fts-item-snippet">{result.snippet}</span>
                  )}
                </button>
              ))}
            </>
          )}

          {!ftsLoading && ftsResults.length === 0 && (
            <div className="search-fts-empty">No message matches</div>
          )}
        </div>
      )}
    </div>
  );
}
