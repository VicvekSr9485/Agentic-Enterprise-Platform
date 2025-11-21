import React, { useState } from 'react';

export function ChatInput({ onSendMessage, disabled }) {
  const [value, setValue] = useState('');

  const send = async () => {
    const text = value.trim();
    if (!text) return;
    setValue('');
    await onSendMessage(text);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="border-t border-indigo-100 bg-white/80 backdrop-blur-xl p-4">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea
              className="w-full resize-none rounded-2xl border-2 border-indigo-100 bg-white p-4 pr-12 focus:outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 transition-all shadow-sm"
              rows={1}
              placeholder="Ask about inventory, policies, or request actions..."
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              onInput={(e) => {
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 150) + 'px';
              }}
            />
          </div>
          <button
            onClick={send}
            disabled={disabled || !value.trim()}
            className="flex-shrink-0 w-12 h-12 rounded-2xl bg-gradient-to-r from-indigo-600 to-purple-600 text-white disabled:opacity-50 disabled:cursor-not-allowed hover:from-indigo-700 hover:to-purple-700 transition-all shadow-md hover:shadow-lg flex items-center justify-center"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
        <div className="mt-2 text-xs text-gray-500 text-center">
          Press Enter to send • Shift + Enter for new line
        </div>
      </div>
    </div>
  );
}
