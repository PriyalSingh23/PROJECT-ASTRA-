import React, { useState } from 'react'
import { Lock, User, Key, X, AlertCircle } from 'lucide-react'
import { api } from '../services/api'
import { User as UserType } from '../types'

interface SecurityModalProps {
  isOpen: boolean
  onClose: () => void
  onLoginSuccess: (user: UserType) => void
}

export const SecurityModal: React.FC<SecurityModalProps> = ({
  isOpen,
  onClose,
  onLoginSuccess,
}) => {
  const [username, setUsername] = useState('operator')
  const [password, setPassword] = useState('OperatorPassword123!')
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  if (!isOpen) return null

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setErrorMsg(null)
    try {
      const res = await api.login(username, password)
      onLoginSuccess(res.user)
      onClose()
    } catch (err: any) {
      setErrorMsg(err.message || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  const setCredentials = (u: string, p: string) => {
    setUsername(u)
    setPassword(p)
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl max-w-md w-full shadow-2xl p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center space-x-2 text-zinc-100 font-mono font-bold text-sm">
            <Lock className="w-4 h-4 text-emerald-400" />
            <span>SHADOWCOMM Operator Authentication</span>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleLogin} className="space-y-4 text-xs font-sans">
          <div className="space-y-1">
            <label className="text-[11px] font-mono uppercase text-zinc-400 block">
              Operator Username
            </label>
            <div className="relative">
              <User className="w-4 h-4 text-zinc-500 absolute left-3 top-2.5" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg pl-9 pr-3 py-2 text-zinc-100 focus:outline-none focus:border-emerald-500 font-mono"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-[11px] font-mono uppercase text-zinc-400 block">
              Passphrase
            </label>
            <div className="relative">
              <Key className="w-4 h-4 text-zinc-500 absolute left-3 top-2.5" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg pl-9 pr-3 py-2 text-zinc-100 focus:outline-none focus:border-emerald-500 font-mono"
              />
            </div>
          </div>

          {errorMsg && (
            <div className="p-2.5 bg-rose-950/40 border border-rose-800/60 rounded-lg text-rose-300 flex items-start space-x-2 text-xs">
              <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className={`w-full py-2.5 rounded-lg font-mono font-bold text-xs uppercase tracking-wider text-white transition-colors ${
              loading ? 'bg-zinc-800 cursor-not-allowed' : 'bg-emerald-600 hover:bg-emerald-500 shadow-lg'
            }`}
          >
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>

        {/* Quick Credentials Helper */}
        <div className="p-3 bg-zinc-950 border border-zinc-850 rounded-lg text-[11px] space-y-1.5 font-mono">
          <span className="text-zinc-500 uppercase text-[9px] block">Standard Seed Accounts:</span>
          <div className="flex items-center justify-between text-zinc-400">
            <span>Operator:</span>
            <button
              type="button"
              onClick={() => setCredentials('operator', 'OperatorPassword123!')}
              className="text-emerald-400 hover:underline"
            >
              operator / OperatorPassword123!
            </button>
          </div>
          <div className="flex items-center justify-between text-zinc-400">
            <span>Admin:</span>
            <button
              type="button"
              onClick={() => setCredentials('admin', 'FieldAdmin2026!')}
              className="text-cyan-400 hover:underline"
            >
              admin / FieldAdmin2026!
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
