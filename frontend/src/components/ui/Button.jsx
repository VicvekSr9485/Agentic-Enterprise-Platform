import React from 'react';

export function Button({ children, onClick, variant = 'primary', className = '', disabled }) {
  const base = 'inline-flex items-center justify-center rounded-lg px-3 py-2 text-sm transition-colors';
  const styles = variant === 'secondary'
    ? 'bg-white text-gray-900 border border-gray-300 hover:bg-gray-50'
    : 'bg-gray-900 text-white hover:bg-black';
  return (
    <button onClick={onClick} disabled={disabled} className={`${base} ${styles} ${className} disabled:opacity-50`}>
      {children}
    </button>
  );
}
