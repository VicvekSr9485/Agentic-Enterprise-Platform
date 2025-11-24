import { useCallback, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export function useChat(sessionId) {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingApproval, setPendingApproval] = useState(null);

  const sendMessage = useCallback(async (text) => {
    setIsLoading(true);
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    try {
      const res = await fetch(`${API_BASE}/orchestrator/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, prompt: text })
      });
      
      if (!res.ok) {
        throw new Error(`Server error: ${res.status} ${res.statusText}`);
      }
      
      const data = await res.json();
      const responseText = data.response || '';
      setMessages((prev) => [...prev, { role: 'assistant', content: responseText }]);

      // Handle approval workflow state
      if (data.pending_approval) {
        setPendingApproval({ type: data.approval_type, content: responseText });
      } else {
        // Clear pending approval when approval is processed or no approval needed
        setPendingApproval(null);
      }
    } catch (e) {
      setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${e.message}` }]);
      setPendingApproval(null); // Clear approval state on error
    } finally {
      // Always clear loading state
      setIsLoading(false);
    }
  }, [sessionId]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setPendingApproval(null);
  }, []);

  return { messages, isLoading, sendMessage, clearMessages, pendingApproval };
}
