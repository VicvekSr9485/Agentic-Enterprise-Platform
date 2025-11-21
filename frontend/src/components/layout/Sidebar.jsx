import React from 'react';

const agents = [
  { name: 'Orchestrator', icon: '🧠', status: 'online', description: 'Intelligent routing & coordination' },
  { name: 'Inventory Agent', icon: '📦', status: 'online', description: 'Product data retrieval' },
  { name: 'Policy Agent', icon: '📋', status: 'online', description: 'Policy document search' },
  { name: 'Analytics Agent', icon: '📊', status: 'online', description: 'Trends, forecasts & reports' },
  { name: 'Order Agent', icon: '🛒', status: 'online', description: 'Purchase orders & procurement' },
  { name: 'Notification Agent', icon: '✉️', status: 'online', description: 'Email drafting & sending' }
];

export function Sidebar({ isOpen, onClose, onNewSession }) {
  return (
    <>
      {/* Overlay for mobile */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-20 lg:hidden" 
          onClick={onClose}
        />
      )}
      
      <aside className={`fixed inset-y-0 left-0 z-30 w-72 bg-white/80 backdrop-blur-xl border-r border-indigo-100 shadow-xl transform transition-transform duration-300 ease-in-out ${isOpen ? 'translate-x-0' : '-translate-x-full'} lg:static lg:translate-x-0`}>
        <div className="h-full flex flex-col">
          {/* Header */}
          <div className="px-5 py-4 border-b border-indigo-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg shadow-lg">
                E
              </div>
              <div>
                <h2 className="font-bold text-gray-900 text-sm">Enterprise Agents</h2>
                <p className="text-xs text-gray-500">Platform v1.0</p>
              </div>
            </div>
            <button 
              className="lg:hidden p-2 hover:bg-gray-100 rounded-lg transition-colors" 
              onClick={onClose}
            >
              <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* New Chat Button */}
          <div className="p-4 border-b border-indigo-100">
            <button
              onClick={() => {
                onNewSession();
                onClose();
              }}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-xl hover:from-indigo-700 hover:to-purple-700 transition-all shadow-md hover:shadow-lg font-medium"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Chat
            </button>
          </div>

          {/* Available Agents */}
          <div className="flex-1 overflow-y-auto p-4">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 px-2">Available Agents</h3>
            <div className="space-y-2">
              {agents.map((agent, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-gradient-to-r from-white to-indigo-50/50 border border-indigo-100 hover:border-indigo-200 hover:shadow-md transition-all group"
                >
                  <div className="flex items-start gap-3">
                    <div className="text-2xl flex-shrink-0">{agent.icon}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-semibold text-gray-900 text-sm truncate">{agent.name}</h4>
                        <span className="flex-shrink-0 w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                      </div>
                      <p className="text-xs text-gray-600 line-clamp-2">{agent.description}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-indigo-100">
            <div className="text-xs text-gray-500 text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="font-medium">All systems operational</span>
              </div>
              <p>Powered by Google ADK</p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
