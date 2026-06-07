import { useState } from 'react';

// Stub for Phase 2. Phase 6 will implement SSE streaming here.
export function useQueryStream() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [response, setResponse] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const sendQuery = async (audioBlob: Blob) => {
    setIsProcessing(true);
    setResponse(null);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'query.webm');

      // Uses the proxy configured in vite.config.ts
      const res = await fetch('/query', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Server error: ${res.statusText}`);
      }

      const data = await res.json();
      console.log('Query Response:', data);
      setResponse(data);
    } catch (err: any) {
      console.error('Query failed:', err);
      setError(err.message || 'Failed to communicate with the server.');
    } finally {
      setIsProcessing(false);
    }
  };

  return {
    isProcessing,
    response,
    error,
    sendQuery,
  };
}
