import React, { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, Clock, Loader2, RefreshCw, X } from 'lucide-react'
import { api } from '../services/api'
import { Endpoint, Message, MessageEvent, MessageState } from '../types'

export interface DrawerStation {
  id: string
  label: string
}

interface MessageDrawerProps {
  station: DrawerStation | null
  endpoints: Endpoint[]
  onClose: () => void
}

const STATE_TONE: Record<string, string> = {
  DELIVERED: 'text-emerald-300 border-emerald-800/60 bg-emerald-950/40',
  RECEIVED: 'text-emerald-300 border-emerald-800/60 bg-emerald-950/40',
  ACCEPTED: 'text-cyan-300 border-cyan-800/60 bg-cyan-950/40',
  SENDING: 'text-cyan-300 border-cyan-800/60 bg-cyan-950/40',
  AWAITING_ACK: 'text-cyan-300 border-cyan-800/60 bg-cyan-950/40',
  QUEUED: 'text-zinc-300 border-zinc-700 bg-zinc-900',
  LOCAL_QUEUED: 'text-zinc-300 border-zinc-700 bg-zinc-900',
  FAILED_RETRYABLE: 'text-amber-300 border-amber-800/60 bg-amber-950/40',
  FAILED_FINAL: 'text-rose-300 border-rose-800/60 bg-rose-950/40',
  EXPIRED: 'text-rose-300 border-rose-800/60 bg-rose-950/40',
  CANCELLED: 'text-zinc-400 border-zinc-700 bg-zinc-900',
}

function tone(state: MessageState | string): string {
  return STATE_TONE[state] || 'text-zinc-300 border-zinc-700 bg-zinc-900'
}

function shortTime(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

/**
 * Read-only message inspector. Opened by clicking a station node in the 3D
 * link view; shows that station's sent and received traffic plus the full
 * lifecycle timeline for whichever message is selected.
 */
export const MessageDrawer: React.FC<MessageDrawerProps> = ({ station, endpoints, onClose }) => {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Message | null>(null)
  const [events, setEvents] = useState<MessageEvent[]>([])
  const [eventsLoading, setEventsLoading] = useState(false)

  const nameOf = useMemo(() => {
    const map = new Map<string, string>()
    endpoints.forEach((e) => map.set(e.endpoint_id, e.display_name || e.endpoint_id))
    return (id: string) => map.get(id) || id
  }, [endpoints])

  // Escape closes the drawer.
  useEffect(() => {
    if (!station) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [station, onClose])

  const load = React.useCallback(async () => {
    if (!station) return
    setLoading(true)
    setError(null)
    try {
      const [sent, received] = await Promise.all([
        api.getMessages({ sender: station.id }).catch(() => [] as Message[]),
        api.getMessages({ recipient: station.id }).catch(() => [] as Message[]),
      ])
      const byId = new Map<string, Message>()
      ;[...sent, ...received].forEach((m) => byId.set(m.message_id, m))
      const merged = Array.from(byId.values()).sort((a, b) =>
        (b.created_at || '').localeCompare(a.created_at || ''),
      )
      setMessages(merged)
      setSelected((prev) => (prev ? merged.find((m) => m.message_id === prev.message_id) || null : null))
    } catch (err: any) {
      setError(err?.message || 'Could not load messages')
    } finally {
      setLoading(false)
    }
  }, [station])

  useEffect(() => {
    if (!station) {
      setMessages([])
      setSelected(null)
      setEvents([])
      return
    }
    load()
  }, [station, load])

  useEffect(() => {
    if (!selected) {
      setEvents([])
      return
    }
    let cancelled = false
    setEventsLoading(true)
    api
      .getMessageEvents(selected.message_id)
      .then((evts) => {
        if (!cancelled) setEvents(evts)
      })
      .catch(() => {
        if (!cancelled) setEvents([])
      })
      .finally(() => {
        if (!cancelled) setEventsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selected])

  if (!station) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative h-full w-full max-w-3xl bg-zinc-950 border-l border-zinc-800 shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">Station inspector</div>
            <div className="text-sm font-mono font-bold text-zinc-100">{station.label}</div>
            <div className="text-[10px] font-mono text-zinc-500">{station.id}</div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={load}
              className="flex items-center space-x-1 px-2 py-1 rounded border border-zinc-700 text-[11px] font-mono text-zinc-300 hover:border-zinc-500"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
              <span>refresh</span>
            </button>
            <button onClick={onClose} className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400" aria-label="Close">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 grid grid-cols-1 md:grid-cols-2 overflow-hidden">
          {/* Message list */}
          <div className="border-r border-zinc-800 overflow-y-auto">
            <div className="px-3 py-2 text-[10px] font-mono uppercase text-zinc-500 border-b border-zinc-800 flex items-center justify-between">
              <span>Traffic</span>
              <span className="tabular-nums">{messages.length}</span>
            </div>
            {error && <div className="p-3 text-[11px] font-mono text-rose-300">{error}</div>}
            {loading && messages.length === 0 && (
              <div className="p-3 text-[11px] font-mono text-zinc-500 flex items-center space-x-2">
                <Loader2 className="w-3 h-3 animate-spin" /> <span>loading…</span>
              </div>
            )}
            {!loading && messages.length === 0 && !error && (
              <div className="p-3 text-[11px] font-mono text-zinc-500">No traffic for this station yet.</div>
            )}
            <ul className="divide-y divide-zinc-800/60">
              {messages.map((m) => {
                const outbound = m.sender_endpoint_id === station.id
                const active = selected?.message_id === m.message_id
                return (
                  <li key={m.message_id}>
                    <button
                      onClick={() => setSelected(m)}
                      className={`w-full text-left px-3 py-2 hover:bg-zinc-900/60 ${active ? 'bg-zinc-900' : ''}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="flex items-center space-x-1 text-[10px] font-mono text-zinc-400">
                          {outbound ? <ArrowRight className="w-3 h-3 text-cyan-400" /> : <ArrowLeft className="w-3 h-3 text-emerald-400" />}
                          <span className="truncate">
                            {outbound ? `to ${nameOf(m.recipient_endpoint_id)}` : `from ${nameOf(m.sender_endpoint_id)}`}
                          </span>
                        </span>
                        <span className={`px-1.5 py-0.5 rounded border text-[9px] font-mono ${tone(m.current_state)}`}>
                          {m.current_state}
                        </span>
                      </div>
                      <div className="mt-1 text-[11px] font-mono text-zinc-300 truncate">{m.payload}</div>
                      <div className="mt-0.5 flex items-center space-x-2 text-[9px] font-mono text-zinc-500">
                        <Clock className="w-2.5 h-2.5" />
                        <span className="tabular-nums">{shortTime(m.created_at)}</span>
                        {m.retry_count > 0 && <span className="text-amber-400">retries {m.retry_count}</span>}
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>

          {/* Detail + timeline */}
          <div className="overflow-y-auto">
            {!selected ? (
              <div className="p-4 text-[11px] font-mono text-zinc-500">
                Select a message to inspect its payload, state and full lifecycle timeline.
              </div>
            ) : (
              <div className="p-4 space-y-4">
                <div>
                  <div className="text-[10px] font-mono uppercase text-zinc-500">Message</div>
                  <div className="text-[10px] font-mono text-zinc-500 break-all">{selected.message_id}</div>
                  <div className="mt-2 flex flex-wrap gap-2 text-[10px] font-mono">
                    <span className={`px-1.5 py-0.5 rounded border ${tone(selected.current_state)}`}>
                      {selected.current_state}
                    </span>
                    <span className="px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-300">
                      {selected.message_type}
                    </span>
                    <span className="px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-300">
                      retries {selected.retry_count}/{selected.max_retries}
                    </span>
                  </div>
                </div>

                <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-3">
                  <div className="text-[10px] font-mono uppercase text-zinc-500 mb-1">Payload</div>
                  <div className="text-[11px] font-mono text-zinc-200 whitespace-pre-wrap break-words">
                    {selected.payload}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
                  <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-2">
                    <div className="text-zinc-500 uppercase">From</div>
                    <div className="text-zinc-200 truncate">{nameOf(selected.sender_endpoint_id)}</div>
                  </div>
                  <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-2">
                    <div className="text-zinc-500 uppercase">To</div>
                    <div className="text-zinc-200 truncate">{nameOf(selected.recipient_endpoint_id)}</div>
                  </div>
                  <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-2">
                    <div className="text-zinc-500 uppercase">Created</div>
                    <div className="text-zinc-200 tabular-nums">{shortTime(selected.created_at)}</div>
                  </div>
                  <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-2">
                    <div className="text-zinc-500 uppercase">Delivered</div>
                    <div className="text-zinc-200 tabular-nums">
                      {selected.delivered_at ? shortTime(selected.delivered_at) : '—'}
                    </div>
                  </div>
                </div>

                <div>
                  <div className="text-[10px] font-mono uppercase text-zinc-500 mb-2">
                    Lifecycle timeline {eventsLoading ? '(loading…)' : `(${events.length})`}
                  </div>
                  <ol className="relative border-l border-zinc-800 ml-1.5 space-y-3">
                    {events.map((evt) => (
                      <li key={evt.event_id} className="pl-3">
                        <span className="absolute -left-[3px] mt-1 w-1.5 h-1.5 rounded-full bg-emerald-400" />
                        <div className="text-[11px] font-mono text-zinc-200">{evt.event_type}</div>
                        <div className="text-[10px] font-mono text-zinc-500 tabular-nums">{shortTime(evt.timestamp)}</div>
                        {evt.details && Object.keys(evt.details).length > 0 && (
                          <div className="text-[10px] font-mono text-zinc-500 break-all">
                            {Object.entries(evt.details)
                              .filter(([k]) => k !== 'transport_mode')
                              .map(([k, v]) => `${k}=${String(v)}`)
                              .join(' · ')}
                            {typeof evt.details.transport_mode === 'string' && (
                              <span className="text-amber-400"> · via {evt.details.transport_mode}</span>
                            )}
                          </div>
                        )}
                      </li>
                    ))}
                    {!eventsLoading && events.length === 0 && (
                      <li className="pl-3 text-[11px] font-mono text-zinc-500">No events recorded.</li>
                    )}
                  </ol>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default MessageDrawer
