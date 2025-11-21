import React from 'react';

export function Header({ onMenuClick }) {
  return (
    <header className="w-full bg-white/80 backdrop-blur-xl border-b border-indigo-100 px-4 py-4 flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-2 hover:bg-indigo-50 rounded-lg transition-colors"
        >
          <svg className="w-6 h-6 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold shadow-md">
            E
          </div>
          <h1 className="text-lg font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent hidden sm:block">
            Enterprise Agents Platform
          </h1>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className="px-3 py-1 bg-green-50 text-green-700 text-xs font-medium rounded-full border border-green-200 hidden md:flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          Online
        </span>
      </div>
    </header>
  );
}
