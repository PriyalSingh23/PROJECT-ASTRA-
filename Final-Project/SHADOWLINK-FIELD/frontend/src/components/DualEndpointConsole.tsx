import React, { useState, useEffect } from 'react'
import {
  Send,
  Inbox,
  SendHorizontal,
  Clock,
  CheckCircle,
  AlertCircle,
  RotateCcw,
  Ban,
  ShieldCheck,
  Radio,
  FileText,
  Database,
  ArrowUpRight,
  HardDrive,
} from 'lucide-react'
import { Message, LocalOutboxItem } from '../types'
import { api } from '../services/api'
import { outboxDb } from '../services/outboxDb'

interface DualEndpointConsoleProps {
  messages: Message[]
  isBackendHealthy: boolean
  onRefresh: () => void
  onInspectTimeline: (msg: Message) => void
}

export const DualEndpointConsole: React.FC<DualEndpointConsoleProps> = ({
  messages,
  isBackendHealthy,
  onRefresh,
  onInspectTimeline,
}) => {
  // Compose form state
  const [recipient, setRecipient] = useState('endpoint-b')
  const [payload, setPayload] = useState('')
  const [priority, setPriority] = useState<number>(3)
  const [expiresIn, setExpiresIn] = useState<number>(300)
  const [submitting, setSubmitting] = useState(false)
  const [composeError, setComposeError] = useState<string | null>(null)

  // Local IndexedDB outbox items
  const [localOutbox, setLocalOutbox] = useState<LocalOutboxItem[]>([])

  // Refresh local outbox from IndexedDB
  const refreshLocalOutbox = async () => {
    try {
      const items = await outboxDb.getAllMessages()
      setLocalOutbox(items)
    } catch (e) {
      console.error('Error fetching local IndexedDB outbox', e)
    }
  }

  useEffect(() => {
    refreshLocalOutbox()
  }, [])

  // Auto-sync local outbox when backend is online
  useEffect(() => {
    if (!isBackendHealthy) return

    const syncPending = async () => {
      const items = await outboxDb.getAllMessages()
      const pending = items.filter((i) => i.sync_status === 'PENDING_LOCAL')

      for (const item of pending) {
        try {
          await api.submitMessage({
            client_idempotency_key: item.client_idempotency_key,
            sender_endpoint_id: item.sender_endpoint_id,
            recipient_endpoint_id: item.recipient_endpoint_id,
            payload: item.payload,
            priority: item.priority,
            expires_in_seconds: item.expires_in_seconds,
          })
          await outboxDb.updateSyncStatus(item.client_idempotency_key, 'SYNCED')
        } catch (err: any) {
          await outboxDb.updateSyncStatus(
            item.client_idempotency_key,
            'FAILED_SYNC',
            err.message
          )
        }
      }
      refreshLocalOutbox()
      onRefresh()
    }

    syncPending()
  }, [isBackendHealthy])

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!payload.trim()) return

    setSubmitting(true)
    setComposeError(null)

    const idempotencyKey = `sl-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`
    const localItem: LocalOutboxItem = {
      client_idempotency_key: idempotencyKey,
      sender_endpoint_id: 'endpoint-a',
      recipient_endpoint_id: recipient,
      payload: payload.trim(),
      priority,
      expires_in_seconds: expiresIn,
      created_at: new Date().toISOString(),
      sync_status: 'PENDING_LOCAL',
    }

    try {
      // 1. Mandatory requirement: Persist in browser IndexedDB first!
      await outboxDb.saveMessage(localItem)
      await refreshLocalOutbox()

      // 2. If backend is reachable, synchronize immediately
      if (isBackendHealthy) {
        await api.submitMessage({
          client_idempotency_key: idempotencyKey,
          sender_endpoint_id: localItem.sender_endpoint_id,
          recipient_endpoint_id: localItem.recipient_endpoint_id,
          payload: localItem.payload,
          priority: localItem.priority,
          expires_in_seconds: localItem.expires_in_seconds,
        })
        await outboxDb.updateSyncStatus(idempotencyKey, 'SYNCED')
        await refreshLocalOutbox()
        onRefresh()
      }

      setPayload('')
    } catch (err: any) {
      console.warn('Sync failed, persisted in IndexedDB local outbox', err)
      await outboxDb.updateSyncStatus(idempotencyKey, 'FAILED_SYNC', err.message)
      await refreshLocalOutbox()
    } finally {
      setSubmitting(false)
    }
  }

  const handleRetry = async (msgId: string) => {
    try {
      await api.retryMessage(msgId)
      onRefresh()
    } catch (err: any) {
      alert(`Retry failed: ${err.message}`)
    }
  }

  const handleCancel = async (msgId: string) => {
    try {
      await api.cancelMessage(msgId)
      onRefresh()
    } catch (err: any) {
      alert(`Cancel failed: ${err.message}`)
    }
  }

  // Filter messages for Endpoint A (Outbox) and Endpoint B (Inbox)
  const endpointAOutbox = messages.filter((m) => m.sender_endpoint_id === 'endpoint-a')
  const endpointBInbox = messages.filter(
    (m) => m.recipient_endpoint_id === 'endpoint-b' && m.current_state === 'DELIVERED'
  )

  const pendingLocalCount = localOutbox.filter((i) => i.sync_status === 'PENDING_LOCAL').length

  const getStatusBadge = (state: string) => {
    switch (state) {
      case 'DELIVERED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950/60 border border-emerald-800 text-emerald-400">
            <CheckCircle className="w-3 h-3" /> DELIVERED (ACK)
          </span>
        )
      case 'SENDING':
      case 'LEASED':
      case 'SENT_AWAITING_ACK':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-950/60 border border-cyan-800 text-cyan-400 animate-pulse">
            <Radio className="w-3 h-3" /> {state}
          </span>
        )
      case 'FAILED_RETRYABLE':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-950/60 border border-amber-800 text-amber-400">
            <RotateCcw className="w-3 h-3" /> RETRY QUEUED
          </span>
        )
      case 'FAILED_FINAL':
      case 'EXPIRED':
      case 'CANCELLED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-950/60 border border-rose-800 text-rose-400">
            <AlertCircle className="w-3 h-3" /> {state}
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 border border-slate-700 text-slate-300">
            <Clock className="w-3 h-3" /> {state}
          </span>
        )
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* ======================================================== */}
      {/* ENDPOINT A: DISPATCH / TRANSMITTER NODE                  */}
      {/* ======================================================== */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col shadow-xl">
        {/* Endpoint A Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold font-mono">
              A
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-mono font-bold text-slate-100 text-sm">
                  ENDPOINT A (ECHO-ALPHA)
                </h3>
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
              </div>
              <p className="text-xs text-slate-400 font-mono">
                Transmitter / Dispatcher Console
              </p>
            </div>
          </div>

          {/* Local IndexedDB Pill */}
          <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1 rounded border border-slate-800 text-[11px] font-mono">
            <HardDrive className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-slate-400">LOCAL OUTBOX:</span>
            <span
              className={`font-bold ${
                pendingLocalCount > 0 ? 'text-amber-400 animate-pulse' : 'text-slate-300'
              }`}
            >
              {pendingLocalCount} PENDING
            </span>
          </div>
        </div>

        {/* Compose Form */}
        <form onSubmit={handleSendMessage} className="mt-4 space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">
                Recipient
              </label>
              <select
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono focus:border-emerald-500 focus:outline-none"
              >
                <option value="endpoint-b">ENDPOINT-B (BRAVO-BASE)</option>
                <option value="motorola-radio-01">MOTOROLA-RADIO-01</option>
                <option value="broadcast-all">BROADCAST-ALL</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">
                Priority
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
                className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono focus:border-emerald-500 focus:outline-none"
              >
                <option value={1}>1 - CRITICAL (Rapid Backoff)</option>
                <option value={2}>2 - HIGH</option>
                <option value={3}>3 - NORMAL</option>
                <option value={4}>4 - ROUTINE</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">
                TTL Expiry
              </label>
              <select
                value={expiresIn}
                onChange={(e) => setExpiresIn(Number(e.target.value))}
                className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono focus:border-emerald-500 focus:outline-none"
              >
                <option value={60}>60 Seconds</option>
                <option value={300}>5 Minutes</option>
                <option value={1800}>30 Minutes</option>
                <option value={86400}>24 Hours</option>
              </select>
            </div>
          </div>

          <div>
            <textarea
              rows={2}
              value={payload}
              onChange={(e) => setPayload(e.target.value)}
              placeholder="Enter tactical message or structured status report..."
              className="w-full bg-slate-950 border border-slate-800 rounded p-2.5 text-xs text-slate-100 placeholder-slate-600 font-mono focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div className="flex justify-between items-center">
            <span className="text-[11px] font-mono text-slate-500 flex items-center gap-1">
              <Database className="w-3 h-3 text-emerald-400" />
              Persists to IndexedDB before delivery attempt
            </span>
            <button
              type="submit"
              disabled={submitting || !payload.trim()}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded font-mono text-xs font-semibold flex items-center gap-1.5 transition shadow-sm"
            >
              <Send className="w-3.5 h-3.5" />
              {submitting ? 'Persisting...' : 'Enqueue Durable Message'}
            </button>
          </div>
        </form>

        {/* Endpoint A Outbox Stream */}
        <div className="mt-6 flex-1 flex flex-col">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800 text-xs font-mono text-slate-400">
            <span className="flex items-center gap-1.5">
              <SendHorizontal className="w-4 h-4 text-emerald-400" />
              Durable Outbox Queue ({endpointAOutbox.length})
            </span>
            <button
              onClick={onRefresh}
              className="text-slate-400 hover:text-slate-200 flex items-center gap-1 text-[11px]"
            >
              <RotateCcw className="w-3 h-3" /> Refresh
            </button>
          </div>

          <div className="mt-2 space-y-2.5 overflow-y-auto max-h-[360px] pr-1">
            {endpointAOutbox.length === 0 ? (
              <div className="py-12 text-center text-xs font-mono text-slate-500">
                Outbox is empty. Submit a message above.
              </div>
            ) : (
              endpointAOutbox.map((msg) => (
                <div
                  key={msg.message_id}
                  className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 hover:border-slate-700 transition space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getStatusBadge(msg.current_state)}
                      <span className="text-[11px] font-mono text-slate-400">
                        &rarr; {msg.recipient_endpoint_id}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-slate-500">
                      {new Date(msg.created_at).toLocaleTimeString()}
                    </span>
                  </div>

                  <p className="text-xs font-mono text-slate-200 break-words bg-slate-900/60 p-2 rounded border border-slate-800/40">
                    {msg.payload}
                  </p>

                  <div className="flex items-center justify-between text-[11px] font-mono text-slate-500 pt-1">
                    <div className="flex items-center gap-2">
                      <span>Retries: {msg.retry_count}/{msg.max_retries}</span>
                      {msg.delivered_at && (
                        <span className="text-emerald-400">
                          ACK: {new Date(msg.delivered_at).toLocaleTimeString()}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      {['FAILED_RETRYABLE', 'FAILED_FINAL'].includes(msg.current_state) && (
                        <button
                          onClick={() => handleRetry(msg.message_id)}
                          className="text-cyan-400 hover:underline flex items-center gap-0.5"
                        >
                          <RotateCcw className="w-3 h-3" /> Retry
                        </button>
                      )}
                      {['QUEUED', 'SENDING'].includes(msg.current_state) && (
                        <button
                          onClick={() => handleCancel(msg.message_id)}
                          className="text-rose-400 hover:underline flex items-center gap-0.5"
                        >
                          <Ban className="w-3 h-3" /> Cancel
                        </button>
                      )}
                      <button
                        onClick={() => onInspectTimeline(msg)}
                        className="text-emerald-400 hover:underline flex items-center gap-0.5"
                      >
                        <FileText className="w-3 h-3" /> Timeline
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* ======================================================== */}
      {/* ENDPOINT B: RECEIVER / FIELD OPERATOR NODE              */}
      {/* ======================================================== */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col shadow-xl">
        {/* Endpoint B Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 font-bold font-mono">
              B
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-mono font-bold text-slate-100 text-sm">
                  ENDPOINT B (BRAVO-BASE)
                </h3>
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              </div>
              <p className="text-xs text-slate-400 font-mono">
                Tactical Field Receiver / Durable Inbox
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1 rounded border border-slate-800 text-[11px] font-mono">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-slate-400">DEDUPLICATION:</span>
            <span className="text-emerald-400 font-bold">ACTIVE</span>
          </div>
        </div>

        {/* Endpoint B Inbox Stream */}
        <div className="mt-4 flex-1 flex flex-col">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800 text-xs font-mono text-slate-400">
            <span className="flex items-center gap-1.5">
              <Inbox className="w-4 h-4 text-cyan-400" />
              Durable Inbox ({endpointBInbox.length} Delivered Messages)
            </span>
            <button
              onClick={onRefresh}
              className="text-slate-400 hover:text-slate-200 flex items-center gap-1 text-[11px]"
            >
              <RotateCcw className="w-3 h-3" /> Refresh
            </button>
          </div>

          <div className="mt-3 space-y-3 overflow-y-auto max-h-[500px] pr-1">
            {endpointBInbox.length === 0 ? (
              <div className="py-20 text-center space-y-2">
                <Inbox className="w-8 h-8 text-slate-600 mx-auto" />
                <p className="text-xs font-mono text-slate-500">
                  Inbox is empty. Waiting for tactical transmissions from Endpoint A...
                </p>
              </div>
            ) : (
              endpointBInbox.map((msg) => (
                <div
                  key={msg.message_id}
                  className="p-3.5 rounded-lg bg-slate-950 border border-cyan-900/30 hover:border-cyan-800/60 transition space-y-2.5"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-950 text-cyan-300 border border-cyan-800">
                        FROM: {msg.sender_endpoint_id}
                      </span>
                      <span className="text-[10px] font-mono text-slate-500">
                        Priority {msg.priority}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-slate-400">
                      Delivered:{' '}
                      {msg.delivered_at
                        ? new Date(msg.delivered_at).toLocaleTimeString()
                        : 'N/A'}
                    </span>
                  </div>

                  {/* Decrypted Content Box */}
                  <div className="bg-slate-900 p-2.5 rounded border border-slate-800">
                    <p className="text-xs font-mono text-slate-100 break-words">
                      {msg.payload}
                    </p>
                  </div>

                  {/* Receipt & Verification Bar */}
                  <div className="flex items-center justify-between text-[10px] font-mono bg-slate-900/40 p-2 rounded border border-slate-800/60">
                    <div className="flex items-center gap-1 text-emerald-400">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      <span>Durable Receipt ACK Generated</span>
                    </div>
                    <button
                      onClick={() => onInspectTimeline(msg)}
                      className="text-cyan-400 hover:underline flex items-center gap-1"
                    >
                      Audit Details <ArrowUpRight className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
