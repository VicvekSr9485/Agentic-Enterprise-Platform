import React, { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const MARKDOWN_COMPONENTS = {
  h1: (props) => <h1 className="text-lg font-semibold mt-3 mb-2" {...props} />,
  h2: (props) => <h2 className="text-base font-semibold mt-3 mb-2" {...props} />,
  h3: (props) => <h3 className="text-sm font-semibold mt-3 mb-1" {...props} />,
  p: (props) => <p className="mb-2 last:mb-0" {...props} />,
  ul: (props) => <ul className="list-disc pl-5 space-y-1 mb-2 last:mb-0" {...props} />,
  ol: (props) => <ol className="list-decimal pl-5 space-y-1 mb-2 last:mb-0" {...props} />,
  li: (props) => <li className="leading-relaxed" {...props} />,
  table: (props) => (
    <div className="overflow-x-auto my-2">
      <table className="min-w-full text-xs border-collapse" {...props} />
    </div>
  ),
  thead: (props) => <thead className="bg-slate-100" {...props} />,
  th: (props) => <th className="border border-slate-200 px-2 py-1 text-left font-medium" {...props} />,
  td: (props) => <td className="border border-slate-200 px-2 py-1 align-top" {...props} />,
  strong: (props) => <strong className="font-semibold" {...props} />,
  em: (props) => <em className="italic" {...props} />,
  code: ({ inline, ...props }) =>
    inline ? (
      <code className="px-1 py-0.5 rounded bg-slate-100 text-[0.85em] font-mono" {...props} />
    ) : (
      <code className="block p-3 rounded-lg bg-slate-100 text-[0.85em] font-mono overflow-x-auto" {...props} />
    ),
  pre: (props) => <pre className="my-2" {...props} />,
  a: (props) => (
    <a
      className="text-indigo-600 underline hover:text-indigo-800"
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    />
  ),
  hr: (props) => <hr className="my-3 border-slate-200" {...props} />,
};

function AssistantMarkdown({ children }) {
  return (
    <div className="leading-relaxed">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
        {children}
      </ReactMarkdown>
    </div>
  );
}

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
              {m.role === 'user' ? (
                <div className="whitespace-pre-wrap leading-relaxed">{m.content}</div>
              ) : (
                <AssistantMarkdown>{m.content}</AssistantMarkdown>
              )}
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
