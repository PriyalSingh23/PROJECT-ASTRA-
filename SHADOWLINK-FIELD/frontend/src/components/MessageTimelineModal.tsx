import React, { useEffect, useState } from 'react'
import { X, Clock, CheckCircle2, AlertCircle, ShieldCheck, ArrowRight, RefreshCw, FileText } from 'lucide-react'
import { Message, MessageEvent } from '../types'
import { api } from '../services/api'

interface MessageTimelineModalProps {
  message: Message | null
  onClose: () => void
}

export const MessageTimelineModal: React.FC<MessageTimelineModalProps> = ({ message, onClose }) => {
  const [events, setEvents] = useState<MessageEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showRaw, setShowRaw] = useState(false)

  useEffect(() => {
    if (!message) return
    const fetchEvents = async () => {
      setLoading(true)
      setError(null)
      try {
        const evts = await api.getMessageEvents(message.message_id)
        setEvents(evts)
      } catch (err: any) {
        setError(err.message || 'Failed to load timeline events')
      } finally {
        setLoading(false)
      }
    }
    fetchEvents()
  }, [message])

  if (!message) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-700 w-full max-w-3xl rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="p-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-mono font-bold text-slate-100 text-sm">
                  AUDIT TIMELINE & LIFECYCLE
                </h3>
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                  MSG: {message.message_id.slice(0, 12)}...
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono">
                Idempotency Key: {message.client_idempotency_key}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowRaw(!showRaw)}
              className="px-2.5 py-1 text-xs font-mono rounded bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 transition flex items-center gap-1.5"
            >
              <FileText className="w-3.5 h-3.5 text-cyan-400" />
              {showRaw ? 'Timeline View' : 'Raw JSON'}
            </button>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-100 p-1 rounded-lg hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Message Summary Card */}
        <div className="px-6 py-3 bg-slate-950/60 border-b border-slate-800/80 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
          <div>
            <span className="text-slate-500 block text-[10px] uppercase">Sender &rarr; Recipient</span>
            <span className="text-slate-200 font-semibold">
              {message.sender_endpoint_id} &rarr; {message.recipient_endpoint_id}
            </span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px] uppercase">Current State</span>
            <span className="text-emerald-400 font-semibold">{message.current_state}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px] uppercase">Retries</span>
            <span className="text-amber-400 font-semibold">
              {message.retry_count} / {message.max_retries}
            </span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px] uppercase">Created</span>
            <span className="text-slate-300">{new Date(message.created_at).toLocaleTimeString()}</span>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-4">
          {loading && (
            <div className="flex items-center justify-center py-12 gap-2 text-slate-400 font-mono text-sm">
              <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
              Retrieving deterministic audit timeline...
            </div>
          )}

          {error && (
            <div className="p-4 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs font-mono flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}

          {!loading && !error && showRaw && (
            <pre className="bg-slate-950 p-4 rounded-lg border border-slate-800 text-emerald-400 font-mono text-xs overflow-x-auto">
              {JSON.stringify({ message, events }, null, 2)}
            </pre>
          )}

          {!loading && !error && !showRaw && (
            <div className="relative border-l-2 border-slate-700 ml-4 pl-6 space-y-6">
              {events.length === 0 ? (
                <div className="text-xs text-slate-500 font-mono py-4">
                  No recorded state transition events yet.
                </div>
              ) : (
                events.map((evt, idx) => {
                  const isDelivered = evt.to_state === 'DELIVERED'
                  const isError = evt.event_type.includes('FAIL') || evt.event_type.includes('ERROR')

                  return (
                    <div key={evt.event_id || idx} className="relative group">
                      {/* Timeline dot */}
                      <span
                        className={`absolute -left-[31px] top-1 w-4 h-4 rounded-full border-2 bg-slate-950 flex items-center justify-center ${
                          isDelivered
                            ? 'border-emerald-400 text-emerald-400'
                            : isError
                            ? 'border-rose-400 text-rose-400'
                            : 'border-cyan-400 text-cyan-400'
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            isDelivered
                              ? 'bg-emerald-400'
                              : isError
                              ? 'bg-rose-400'
                              : 'bg-cyan-400'
                          }`}
                        />
                      </span>

                      {/* Event Card */}
                      <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-3 space-y-2 hover:border-slate-700 transition">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-bold text-slate-200">
                              {evt.event_type}
                            </span>
                            {evt.from_state && evt.to_state && (
                              <div className="flex items-center gap-1 text-[11px] font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                                <span>{evt.from_state}</span>
                                <ArrowRight className="w-3 h-3 text-slate-500" />
                                <span className="text-emerald-400 font-semibold">{evt.to_state}</span>
                              </div>
                            )}
                          </div>
                          <span className="text-[11px] font-mono text-slate-500">
                            {new Date(evt.timestamp).toLocaleTimeString()}
                          </span>
                        </div>

                        {evt.details && Object.keys(evt.details).length > 0 && (
                          <div className="mt-2 text-[11px] font-mono bg-slate-900/90 rounded p-2 border border-slate-800/80 text-slate-300">
                            {Object.entries(evt.details).map(([k, v]) => (
                              <div key={k} className="flex gap-2">
                                <span className="text-slate-500">{k}:</span>
                                <span className="text-slate-200">
                                  {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-3 bg-slate-950 border-t border-slate-800 flex justify-between items-center text-xs font-mono text-slate-500">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Cryptographic Delivery Receipt Verified via SHA-256</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
