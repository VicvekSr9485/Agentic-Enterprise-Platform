import { useCallback, useEffect, useRef, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const API_TOKEN = import.meta.env.VITE_API_TOKEN || '';

const STORAGE_PREFIX = 'eap.chat.';
const MAX_STORED_MESSAGES = 200;

function storageKey(sessionId) {
  return `${STORAGE_PREFIX}${sessionId}`;
}

function loadFromStorage(sessionId) {
  if (typeof window === 'undefined') return { messages: [], pendingApproval: null };
  try {
    const raw = window.localStorage.getItem(storageKey(sessionId));
    if (!raw) return { messages: [], pendingApproval: null };
    const parsed = JSON.parse(raw);
    return {
      messages: Array.isArray(parsed.messages) ? parsed.messages : [],
      pendingApproval: parsed.pendingApproval || null,
    };
  } catch {
    return { messages: [], pendingApproval: null };
  }
}

function saveToStorage(sessionId, messages, pendingApproval) {
  if (typeof window === 'undefined') return;
  try {
    const trimmed = messages.length > MAX_STORED_MESSAGES
      ? messages.slice(messages.length - MAX_STORED_MESSAGES)
      : messages;
    window.localStorage.setItem(
      storageKey(sessionId),
      JSON.stringify({ messages: trimmed, pendingApproval }),
    );
  } catch {
    // Quota exceeded or storage disabled; non-fatal.
  }
}

async function postChat(payload, signal) {
  const headers = { 'Content-Type': 'application/json' };
  if (API_TOKEN) headers.Authorization = `Bearer ${API_TOKEN}`;

  const res = await fetch(`${API_BASE}/orchestrator/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
    signal,
  });

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const errBody = await res.json();
      if (errBody?.message) detail = errBody.message;
      else if (errBody?.detail) detail = errBody.detail;
    } catch {
      // ignore body parse failures
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }

  return res.json();
}

export function useChat(sessionId) {
  const [messages, setMessages] = useState(() => loadFromStorage(sessionId).messages);
  const [pendingApproval, setPendingApproval] = useState(() => loadFromStorage(sessionId).pendingApproval);
  const [isLoading, setIsLoading] = useState(false);
  const abortRef = useRef(null);

  // Re-hydrate when session changes; cancel any in-flight request.
  // Setting state in an effect is intentional here: the persistence layer
  // (localStorage) is an external system and the session id key is part of
  // the synchronisation contract.
  useEffect(() => {
    const stored = loadFromStorage(sessionId);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMessages(stored.messages);
    setPendingApproval(stored.pendingApproval);
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, [sessionId]);

  // Persist on every change.
  useEffect(() => {
    saveToStorage(sessionId, messages, pendingApproval);
  }, [sessionId, messages, pendingApproval]);

  const sendMessage = useCallback(async (text) => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setMessages((prev) => [...prev, { role: 'user', content: text }]);

    const payload = { session_id: sessionId, prompt: text };
    let attempt = 0;
    const maxAttempts = 2;

    while (attempt < maxAttempts) {
      attempt += 1;
      try {
        const data = await postChat(payload, controller.signal);
        const responseText = data.response || '';
        setMessages((prev) => [...prev, { role: 'assistant', content: responseText }]);

        if (data.pending_approval) {
          setPendingApproval({ type: data.approval_type, content: responseText });
        } else {
          setPendingApproval(null);
        }
        setIsLoading(false);
        abortRef.current = null;
        return;
      } catch (e) {
        if (e?.name === 'AbortError') {
          setIsLoading(false);
          abortRef.current = null;
          return;
        }
        const status = e?.status;
        const isRetryable = !status || status === 502 || status === 503 || status === 504;
        if (attempt < maxAttempts && isRetryable) {
          await new Promise((r) => setTimeout(r, 800));
          continue;
        }
        const friendly =
          status === 401
            ? 'Authentication required. Set VITE_API_TOKEN to a valid bearer token.'
            : status === 429
              ? 'Rate limit reached. Please wait a moment before retrying.'
              : `Error: ${e.message}`;
        setMessages((prev) => [...prev, { role: 'assistant', content: friendly }]);
        setPendingApproval(null);
        setIsLoading(false);
        abortRef.current = null;
        return;
      }
    }
  }, [sessionId]);

  const clearMessages = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setMessages([]);
    setPendingApproval(null);
    if (typeof window !== 'undefined') {
      try { window.localStorage.removeItem(storageKey(sessionId)); } catch { /* ignore */ }
    }
  }, [sessionId]);

  return { messages, isLoading, sendMessage, clearMessages, pendingApproval };
}
