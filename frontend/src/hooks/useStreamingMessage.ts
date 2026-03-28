import { useRef, useState, useCallback, useEffect } from 'react';
import type { SSEEvent, ToolPanelData } from '../types';

interface UseStreamingMessageOptions {
  onText: (delta: string) => void;
  onTool: (event: ToolPanelData) => void;
  onThreadNamed: (threadId: number, name: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
  onCancel: () => void;
}

export function useStreamingMessage(options: UseStreamingMessageOptions): {
  startStream: (message: string, threadId: number) => void;
  cancelStream: () => void;
  isStreaming: boolean;
} {
  const [isStreaming, setIsStreaming] = useState(false);

  // AbortController MUST be in useRef — not useState. Storing in state would
  // trigger re-renders on assignment and cause stale closure issues with abort.
  const abortControllerRef = useRef<AbortController | null>(null);

  // rAF batching refs — accumulate text deltas and flush in animation frames
  const pendingTextRef = useRef('');
  const rafRef = useRef<number | null>(null);

  // Store options in a ref to avoid stale closures. The callbacks (onText,
  // onTool, etc.) change identity when context state updates, so we must
  // always read the latest versions via this ref.
  const optionsRef = useRef(options);
  useEffect(() => {
    optionsRef.current = options;
  });

  // Flush accumulated text via the onText callback and clear the buffer
  const flushPendingText = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (pendingTextRef.current) {
      optionsRef.current.onText(pendingTextRef.current);
      pendingTextRef.current = '';
    }
  }, []);

  // Schedule a rAF flush if not already scheduled
  const scheduleFlush = useCallback(() => {
    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        if (pendingTextRef.current) {
          optionsRef.current.onText(pendingTextRef.current);
          pendingTextRef.current = '';
        }
      });
    }
  }, []);

  const handleEvent = useCallback((event: SSEEvent) => {
    if (event.type === 'text') {
      pendingTextRef.current += event.delta;
      scheduleFlush();
    } else if (event.type === 'tool') {
      // Flush any pending text before reporting a tool event
      flushPendingText();
      optionsRef.current.onTool({
        name: event.name,
        params: event.params,
        result: event.result,
        status: event.status,
      });
    } else if (event.type === 'thread_named') {
      optionsRef.current.onThreadNamed(event.thread_id, event.name);
    } else if (event.type === 'done') {
      flushPendingText();
      optionsRef.current.onDone();
      setIsStreaming(false);
    } else if (event.type === 'error') {
      flushPendingText();
      optionsRef.current.onError(event.message);
      setIsStreaming(false);
    }
  }, [flushPendingText, scheduleFlush]);

  const startStream = useCallback((message: string, threadId: number) => {
    // Abort any existing stream before starting a new one
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;
    const { signal } = controller;

    setIsStreaming(true);

    (async () => {
      try {
        const res = await fetch('/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, thread_id: threadId }),
          signal,
        });

        if (!res.ok) {
          const text = await res.text().catch(() => `HTTP ${res.status}`);
          flushPendingText();
          optionsRef.current.onError(text || `HTTP ${res.status}`);
          setIsStreaming(false);
          return;
        }

        const reader = res.body!.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        // Pump loop — port of app.js readSSEStream pump()
        const pump = async (): Promise<void> => {
          if (signal.aborted) {
            flushPendingText();
            optionsRef.current.onCancel();
            setIsStreaming(false);
            return;
          }

          const { done, value } = await reader.read();

          if (done) {
            // Flush remaining buffer
            if (buffer.trim()) {
              for (const line of buffer.split('\n')) {
                if (line.startsWith('data: ')) {
                  const json = line.slice(6).trim();
                  if (json) {
                    try {
                      const event: SSEEvent = JSON.parse(json);
                      handleEvent(event);
                    } catch {
                      // Malformed line — skip
                    }
                  }
                }
              }
            }
            flushPendingText();
            setIsStreaming(false);
            return;
          }

          // { stream: true } is CRITICAL — tells TextDecoder this is not the
          // final chunk, so it preserves incomplete multi-byte sequences in
          // its internal buffer rather than emitting replacement characters.
          buffer += decoder.decode(value, { stream: true });

          // SSE events are delimited by double newlines
          const parts = buffer.split('\n\n');
          buffer = parts.pop() ?? '';

          for (const block of parts) {
            for (const line of block.split('\n')) {
              if (line.startsWith('data: ')) {
                const json = line.slice(6).trim();
                if (json) {
                  try {
                    const event: SSEEvent = JSON.parse(json);
                    handleEvent(event);
                  } catch {
                    // Malformed line — skip
                  }
                }
              }
            }
          }

          return pump();
        };

        await pump();
      } catch (err) {
        flushPendingText();
        if (err instanceof Error && err.name === 'AbortError') {
          optionsRef.current.onCancel();
        } else {
          const message = err instanceof Error ? err.message : 'Connection interrupted. Please try again.';
          optionsRef.current.onError(message);
        }
        setIsStreaming(false);
      } finally {
        abortControllerRef.current = null;
      }
    })();
  }, [flushPendingText, handleEvent]);

  const cancelStream = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    // Cancel any queued rAF and flush remaining text before cancelling
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (pendingTextRef.current) {
      optionsRef.current.onText(pendingTextRef.current);
      pendingTextRef.current = '';
    }
  }, []);

  // Cleanup on unmount — abort any in-flight stream and cancel pending rAF
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, []);

  return { startStream, cancelStream, isStreaming };
}
