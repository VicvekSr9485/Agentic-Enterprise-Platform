import React, { useEffect, useRef } from 'react';

export function MessageList({ messages = [], isLoading }) {
  const endRef = useRef(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
      {messages.length === 0 && !isLoading && (
        <div className="flex items-center justify-center h-full">
          <div className="text-center max-w-md mx-auto px-4">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-3xl shadow-lg">
              💬
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Start a Conversation</h3>
            <p className="text-gray-600 text-sm">Ask about inventory, policies, or request to send emails. The orchestrator will coordinate the right agents for you.</p>
          </div>
        </div>
      )}
      
      {messages.map((m, idx) => (
        <div key={idx} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div className={`max-w-[85%] sm:max-w-2xl ${m.role === 'user' ? 'ml-auto' : ''}`}>
            <div className={`rounded-2xl p-4 shadow-md ${
              m.role === 'user' 
                ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white' 
                : 'bg-white/80 backdrop-blur-sm border border-indigo-100 text-gray-900'
            }`}>
              <div className={`text-xs font-medium mb-2 ${
                m.role === 'user' ? 'text-indigo-100' : 'text-gray-500'
              }`}>
                {m.role === 'user' ? '👤 You' : '🤖 AGENT'}
              </div>
              <div className="whitespace-pre-wrap leading-relaxed">{m.content}</div>
            </div>
          </div>
        </div>
      ))}
      
      {isLoading && (
        <div className="flex justify-start">
          <div className="bg-white/80 backdrop-blur-sm border border-indigo-100 rounded-2xl p-4 shadow-md">
            <div className="flex items-center gap-2">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-indigo-600 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-purple-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-indigo-600 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
              <span className="text-sm text-gray-600">Thinking...</span>
            </div>
          </div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
