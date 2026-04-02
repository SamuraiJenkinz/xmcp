import { useEffect, useRef, useState } from 'react';

/**
 * Generic debounce hook. Returns a debounced copy of `value` that only
 * updates after `delay` milliseconds have elapsed since the last change.
 *
 * Uses useRef for the timer so timer mutations don't trigger re-renders.
 * Consistent with the rafRef/abortControllerRef patterns in useStreamingMessage.ts.
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // Clear any pending timer before setting a new one
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
    }
    timerRef.current = setTimeout(() => {
      setDebouncedValue(value);
      timerRef.current = null;
    }, delay);

    // Cleanup: clear timer on unmount or before next effect run
    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [value, delay]);

  return debouncedValue;
}
