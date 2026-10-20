import React, { useEffect, useState } from 'react'
import {
  FileText,
  AlertTriangle,
  RotateCcw,
  CheckCircle,
  HelpCircle,
  Shield,
  Search,
  BookOpen,
} from 'lucide-react'
import { AuditLogEntry } from '../types'
import { api } from '../services/api'

export const DiagnosticsAuditPanel: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')

  const fetchLogs = async () => {
    setLoading(true)
    try {
      const data = await api.getAuditLogs()
      setLogs(data)
    } catch (err) {
      console.error('Failed to fetch audit logs', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
  }, [])

  const filteredLogs = logs.filter(
    (l) =>
      l.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
      l.actor_user.toLowerCase().includes(searchTerm.toLowerCase()) ||
      l.outcome.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const TROUBLESHOOTING_GUIDE = [
    {
      code: 'ERR_LINK_OFFLINE',
      description: 'Simulated or physical RF transport severed; channel is unavailable.',
      action: 'Check Simulation Controls bar or verify RF hardware power & cable connection.',
    },
    {
      code: 'ERR_ACK_TIMEOUT',
      description: 'Receiver did not return receipt acknowledgement within timeout window.',
      action: 'Worker will auto-schedule exponential backoff retry up to max_retries limit.',
    },
    {
      code: 'ERR_MAX_RETRIES_EXCEEDED',
      description: 'Message exhausted retry ceiling without receiving valid receipt ACK.',
      action: 'State transitioned to FAILED_FINAL. Operator can click "Manual Retry" to reset ceiling.',
    },
    {
      code: 'ERR_HARDWARE_LOCKOUT',
      description: 'Radio adapter requested RF transmission on an uncertified hardware path.',
      action: 'Safety lockouts are intentional. Star-V and experimental SDR modules require certified authorization.',
    },
    {
      code: 'ERR_TTL_EXPIRED',
      description: 'Message lived past its configured time-to-live seconds before delivery.',
      action: 'System discards expired tactical data to prevent stale decisions.',
    },
  ]

  return (
    <div className="space-y-6">
      {/* Diagnostics & Troubleshooting Reference */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
        <div className="flex items-center gap-3 pb-3 border-b border-slate-800">
          <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wider font-mono">
              Diagnostic Error Codes & Recovery Reference
            </h2>
            <p className="text-xs text-slate-400">
              Standard operating procedures for tactical radio operators during outages.
            </p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {TROUBLESHOOTING_GUIDE.map((item) => (
            <div
              key={item.code}
              className="p-3 bg-slate-950 rounded-lg border border-slate-800/80 space-y-1.5"
            >
              <div className="flex items-center gap-1.5 text-amber-400 font-mono text-xs font-bold">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>{item.code}</span>
              </div>
              <p className="text-[11px] text-slate-300 font-mono leading-relaxed">
                {item.description}
              </p>
              <div className="text-[10px] text-emerald-400 font-mono pt-1 border-t border-slate-900">
                &rarr; Action: {item.action}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Audit Logs Stream */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wider font-mono">
                System Audit Trail & Security Log
              </h2>
              <p className="text-xs text-slate-400">
                Immutable, sanitized audit log of transmissions, user authentications, and state transitions.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-500" />
              <input
                type="text"
                placeholder="Search audit actions..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-slate-950 border border-slate-800 rounded pl-8 pr-3 py-1.5 text-xs text-slate-200 font-mono focus:border-cyan-500 focus:outline-none w-48"
              />
            </div>
            <button
              onClick={fetchLogs}
              className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              title="Refresh Logs"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Logs Table */}
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead className="bg-slate-950 text-slate-500 border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Timestamp</th>
                <th className="py-2.5 px-3">Action</th>
                <th className="py-2.5 px-3">Actor</th>
                <th className="py-2.5 px-3">Resource</th>
                <th className="py-2.5 px-3">Outcome</th>
                <th className="py-2.5 px-3">Sanitized Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">
                    No matching audit records found.
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr key={log.audit_id} className="hover:bg-slate-950/40 transition">
                    <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="py-2.5 px-3 text-slate-200 font-semibold">
                      {log.action}
                    </td>
                    <td className="py-2.5 px-3 text-cyan-400">
                      {log.actor_user}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">
                      {log.resource_type}
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          log.outcome === 'SUCCESS'
                            ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                            : 'bg-rose-950 text-rose-400 border border-rose-800'
                        }`}
                      >
                        {log.outcome}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 text-[11px] max-w-xs truncate">
                      {log.details ? JSON.stringify(log.details) : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
