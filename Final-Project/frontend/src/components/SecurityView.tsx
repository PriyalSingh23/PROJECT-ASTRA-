import React, { useState, useEffect } from 'react'
import {
  Shield,
  ShieldAlert,
  Key,
  Lock,
  UserCheck,
  FileText,
  AlertTriangle,
  RotateCcw,
} from 'lucide-react'
import { User, AuditLogEntry } from '../types'
import { api } from '../services/api'

interface SecurityViewProps {
  currentUser: User | null
  onOpenAuth: () => void
}

export const SecurityView: React.FC<SecurityViewProps> = ({ currentUser, onOpenAuth }) => {
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [errorNotice, setErrorNotice] = useState<string | null>(null)

  const fetchLogs = async () => {
    setLoading(true)
    setErrorNotice(null)
    try {
      const logs = await api.getSecurityLogs(50)
      setAuditLogs(logs)
    } catch (err: any) {
      setErrorNotice(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
  }, [currentUser])

  return (
    <div className="max-w-7xl w-full mx-auto space-y-6">
      {/* Security Architecture Header */}
      <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold font-mono text-zinc-100 flex items-center space-x-2">
            <Shield className="w-5 h-5 text-emerald-400" />
            <span>Cryptographic Security & Access Control Subsystem</span>
          </h2>
          <p className="text-xs text-zinc-400 font-sans mt-0.5">
            Role-Based Access Control (RBAC), Versioned AES-256-GCM v2, and Security Audit Logging
          </p>
        </div>

        {!currentUser && (
          <button
            onClick={onOpenAuth}
            className="px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-semibold shadow"
          >
            Operator Sign In
          </button>
        )}
      </div>

      {/* Security Specifications Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 1. Authenticated Encryption v2 */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2">
          <div className="flex items-center space-x-2 text-emerald-400 font-mono text-xs font-bold">
            <Key className="w-4 h-4" />
            <span>Authenticated Encryption v2</span>
          </div>
          <p className="text-xs text-zinc-300 font-sans leading-relaxed">
            Every payload is encrypted using versioned AES-256-GCM with a cryptographically fresh 96-bit random nonce (<code className="text-emerald-400 font-mono">os.urandom(12)</code>) and 128-bit authentication tag.
          </p>
          <div className="pt-2 border-t border-zinc-800 text-[10px] font-mono text-zinc-500">
            Cipher: AES-256-GCM &bull; Nonce: 12 Bytes &bull; Version: 0x02
          </div>
        </div>

        {/* 2. Authentication & PBKDF2 */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2">
          <div className="flex items-center space-x-2 text-cyan-400 font-mono text-xs font-bold">
            <UserCheck className="w-4 h-4" />
            <span>PBKDF2 Password Derivation</span>
          </div>
          <p className="text-xs text-zinc-300 font-sans leading-relaxed">
            Operator passwords are protected using PBKDF2 with SHA-256 (100,000 iterations and 16-byte random salt). Automatic 5-attempt brute-force lockout with 15-minute cooldown.
          </p>
          <div className="pt-2 border-t border-zinc-800 text-[10px] font-mono text-zinc-500">
            KDF: PBKDF2-HMAC-SHA256 &bull; Salt: 16 Bytes &bull; Lockout: 5 Tries
          </div>
        </div>

        {/* 3. Session & RBAC Enforcement */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2">
          <div className="flex items-center space-x-2 text-amber-400 font-mono text-xs font-bold">
            <Lock className="w-4 h-4" />
            <span>Session & RBAC Permissions</span>
          </div>
          <p className="text-xs text-zinc-300 font-sans leading-relaxed">
            Stateless bearer tokens with 60-minute TTL. Role tiers enforce strict boundaries: <span className="text-zinc-200 font-semibold font-mono">ADMINISTRATOR</span> (user mgmt, logs), <span className="text-zinc-200 font-semibold font-mono">OPERATOR</span> (dispatch), and <span className="text-zinc-200 font-semibold font-mono">VIEWER</span>.
          </p>
          <div className="pt-2 border-t border-zinc-800 text-[10px] font-mono text-zinc-500">
            Token TTL: 3600s &bull; Roles: ADMIN, OPERATOR, VIEWER
          </div>
        </div>
      </div>

      {/* Security Audit Log Table */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono flex items-center space-x-2">
            <FileText className="w-4 h-4 text-emerald-400" />
            <span>Security & Authentication Audit Timeline</span>
          </h3>
          <button
            onClick={fetchLogs}
            className="text-xs font-mono text-zinc-400 hover:text-zinc-200 flex items-center space-x-1"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Refresh</span>
          </button>
        </div>

        {errorNotice ? (
          <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg text-center text-xs text-zinc-400">
            <p className="font-semibold text-amber-400 mb-1">Administrator Role Required</p>
            <p>{errorNotice}</p>
            <p className="text-zinc-500 mt-2 font-mono text-[11px]">
              Sign in as <code className="text-emerald-400">admin</code> to view confidential security audit events.
            </p>
          </div>
        ) : loading ? (
          <div className="py-8 text-center text-xs text-zinc-500 font-mono">Loading audit events...</div>
        ) : auditLogs.length === 0 ? (
          <div className="py-8 text-center text-xs text-zinc-500">No security audit logs recorded yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500 uppercase text-[10px]">
                  <th className="py-2.5">Timestamp</th>
                  <th className="py-2.5">User</th>
                  <th className="py-2.5">Action</th>
                  <th className="py-2.5">IP Address</th>
                  <th className="py-2.5">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/40 text-zinc-300">
                {auditLogs.map((log) => (
                  <tr key={log.log_id} className="hover:bg-zinc-850/40">
                    <td className="py-2.5 text-zinc-400">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="py-2.5 font-bold text-emerald-400">
                      {log.username || 'ANONYMOUS'}
                    </td>
                    <td className="py-2.5 text-zinc-200 font-bold">{log.action}</td>
                    <td className="py-2.5 text-zinc-400">{log.ip_address || '127.0.0.1'}</td>
                    <td className="py-2.5 text-[10px] text-zinc-500 truncate max-w-xs">
                      {log.details ? JSON.stringify(log.details) : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
