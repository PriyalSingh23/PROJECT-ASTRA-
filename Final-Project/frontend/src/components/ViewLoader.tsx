import React from 'react'

/**
 * Suspense fallback shown while a code-split view chunk loads.
 * Layout-matched (not a spinner-only flash) so the console does not jump.
 */
export const ViewLoader: React.FC<{ label?: string }> = ({ label = 'Loading module' }) => (
  <div className="w-full flex flex-col items-center justify-center py-24 space-y-3 text-zinc-500">
    <div className="flex items-center space-x-1.5">
      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse [animation-delay:150ms]" />
      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse [animation-delay:300ms]" />
    </div>
    <div className="text-xs font-mono uppercase tracking-widest">{label}…</div>
  </div>
)
