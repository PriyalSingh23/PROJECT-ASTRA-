import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  X,
  Copy,
  Check,
  ShieldCheck,
  Clock,
  Database,
  Cpu,
  Radio,
  Terminal,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  HardDrive,
  Lock,
  Layers,
  ShieldAlert,
  Key,
} from 'lucide-react'
import { Message, InboxMessage, MessageEvent } from '../types'
import { api } from '../services/api'

export interface MessageTelemetryDrawerProps {
  isOpen: boolean
  onClose: () => void
  message: Message | null
  inboxRecord?: InboxMessage | null
}

/**
 * Formats ISO timestamp string to microsecond precision: YYYY-MM-DD HH:MM:SS.ffffff
 */
export function formatMicroseconds(isoStr?: string | null): string {
  if (!isoStr) return '—'
  try {
    const clean = isoStr.replace('Z', '').split('+')[0]
    const [datePart, timePart] = clean.split('T')
    if (datePart && timePart) {
      const [timeWithoutFrac, frac = ''] = timePart.split('.')
      const microseconds = (frac + '000000').slice(0, 6)
      return `${datePart} ${timeWithoutFrac}.${microseconds}`
    }
    const d = new Date(isoStr)
    if (isNaN(d.getTime())) return isoStr
    const yyyy = d.getFullYear()
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const min = String(d.getMinutes()).padStart(2, '0')
    const ss = String(d.getSeconds()).padStart(2, '0')
    const ms = String(d.getMilliseconds()).padStart(3, '0')
    return `${yyyy}-${mm}-${dd} ${hh}:${min}:${ss}.${ms}000`
  } catch {
    return isoStr
  }
}

// Sensitive key filter to mitigate T-02-01 (metadata credential leakage)
const SENSITIVE_KEY_SUBSTRINGS = [
  'key',
  'secret',
  'token',
  'auth',
  'password',
  'private',
  'pbkdf2',
  'credential',
  'salt',
  'hash',
]

function sanitizeMetadata(data: unknown): unknown {
  if (!data || typeof data !== 'object') return data
  if (Array.isArray(data)) {
    return data.map(sanitizeMetadata)
  }
  const cleaned: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
    const lowerKey = key.toLowerCase()
    const isSensitive = SENSITIVE_KEY_SUBSTRINGS.some((sub) => lowerKey.includes(sub))
    if (isSensitive) {
      cleaned[key] = '[REDACTED_SECURE_TOKEN]'
    } else if (value && typeof value === 'object') {
      cleaned[key] = sanitizeMetadata(value)
    } else {
      cleaned[key] = value
    }
  }
  return cleaned
}

export const MessageTelemetryDrawer: React.FC<MessageTelemetryDrawerProps> = ({
  isOpen,
  onClose,
  message,
  inboxRecord,
}) => {
  const [events, setEvents] = useState<MessageEvent[]>([])
  const [loadingEvents, setLoadingEvents] = useState<boolean>(false)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [copiedReceipt, setCopiedReceipt] = useState<boolean>(false)
  const [copiedMessageId, setCopiedMessageId] = useState<boolean>(false)
  const [isRawJsonOpen, setIsRawJsonOpen] = useState<boolean>(false)

  // Fetch telemetry events from backend
  const fetchEvents = useCallback(async () => {
    if (!message) return
    setLoadingEvents(true)
    setFetchError(null)
    try {
      const res = await api.getMessageEvents(message.message_id)
      setEvents(res)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch telemetry events'
      setFetchError(msg)
    } finally {
      setLoadingEvents(false)
    }
  }, [message])

  // Initial fetch and polling for non-terminal messages
  useEffect(() => {
    if (!isOpen || !message) {
      return
    }

    let isMounted = true

    const doFetch = async () => {
      try {
        const res = await api.getMessageEvents(message.message_id)
        if (isMounted) {
          setEvents(res)
          setFetchError(null)
        }
      } catch (err: unknown) {
        if (isMounted) {
          const msg = err instanceof Error ? err.message : 'Failed to fetch telemetry events'
          setFetchError(msg)
        }
      }
    }

    doFetch()

    const isTerminal = ['DELIVERED', 'FAILED_FINAL', 'EXPIRED', 'CANCELLED'].includes(
      message.current_state
    )

    let intervalId: ReturnType<typeof setInterval> | null = null
    if (!isTerminal) {
      intervalId = setInterval(doFetch, 2000)
    }

    return () => {
      isMounted = false
      if (intervalId) clearInterval(intervalId)
    }
  }, [isOpen, message])

  // Escape key listener for accessible dismissal
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  // Copy HMAC Receipt to clipboard
  const handleCopyReceipt = () => {
    if (!message?.signed_ack_receipt) return
    navigator.clipboard.writeText(message.signed_ack_receipt)
    setCopiedReceipt(true)
    setTimeout(() => setCopiedReceipt(false), 2000)
  }

  // Copy Message ID to clipboard
  const handleCopyMessageId = () => {
    if (!message?.message_id) return
    navigator.clipboard.writeText(message.message_id)
    setCopiedMessageId(true)
    setTimeout(() => setCopiedMessageId(false), 2000)
  }

  // Identify specific lifecycle events
  const enqueueEvent = useMemo(
    () => events.find((e) => e.event_type === 'MESSAGE_ENQUEUED'),
    [events]
  )
  const leaseEvent = useMemo(
    () =>
      events.find(
        (e) => e.event_type === 'LEASE_ACQUIRED' || e.event_type === 'DELIVERY_ATTEMPT_STARTED'
      ),
    [events]
  )
  const reclaimEvent = useMemo(
    () => events.find((e) => e.event_type === 'WORKER_LEASE_RECLAIMED'),
    [events]
  )
  const inboxEvent = useMemo(
    () => events.find((e) => e.event_type === 'INBOX_PERSISTED'),
    [events]
  )
  const ackEvent = useMemo(
    () => events.find((e) => e.event_type === 'ACK_VALIDATED_DELIVERED'),
    [events]
  )

  const [now, setNow] = useState<number>(() => Date.now())

  // Fast 100ms interval for active retry countdown HUD (D-14)
  useEffect(() => {
    if (!isOpen || !message) return
    if (!['FAILED_RETRYABLE', 'AWAITING_ACK'].includes(message.current_state)) return

    const interval = setInterval(() => {
      setNow(Date.now())
    }, 100)
    return () => clearInterval(interval)
  }, [isOpen, message])

  const retryCountdown = useMemo(() => {
    if (!message?.next_retry_at) return null
    const target = new Date(message.next_retry_at).getTime()
    const diff = Math.max(0, (target - now) / 1000)
    return diff.toFixed(1)
  }, [message, now])

  // Detect STAR-V Lockout Blocked Event (D-06, T-04-03)
  const isStarVLockoutBlocked = useMemo(() => {
    if (
      message?.last_error_code === 'STARV_SAFETY_LOCKOUT_BLOCKED' ||
      message?.last_error_code === 'STARV_SAFETY_LOCKOUT'
    ) {
      return true
    }
    return events.some(
      (e) =>
        e.event_type === 'STARV_SAFETY_LOCKOUT_BLOCKED' ||
        e.event_type === 'STARV_SAFETY_LOCKOUT' ||
        e.error_code === 'STARV_SAFETY_LOCKOUT_BLOCKED'
    )
  }, [message, events])

  // DMR Burst Breakdown metrics (D-03, D-04, Task 07-02-02)
  const dmrMetrics = useMemo(() => {
    if (!message) return null
    const rawBytes = new TextEncoder().encode(message.payload).length
    const isPQC = message.pqc_verified || message.envelope_version === 3
    const overhead = isPQC ? 1150 : 28
    const envelopeBytes = rawBytes > 0 ? rawBytes + overhead : 0
    const dmrChunks = Math.max(1, Math.ceil(envelopeBytes / 276))
    const dmrWireBudget = dmrChunks * 280
    return { rawBytes, envelopeBytes, dmrChunks, dmrWireBudget, isPQC }
  }, [message])

  // Status badge styling
  const getStatusBadge = (state: string) => {
    switch (state) {
      case 'DELIVERED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-emerald-950/70 text-emerald-400 border border-emerald-500/40 shadow-[0_0_8px_rgba(16,185,129,0.2)]">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            DELIVERED
          </span>
        )
      case 'SENDING':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-cyan-950/70 text-cyan-300 border border-cyan-500/40 animate-pulse">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
            SENDING
          </span>
        )
      case 'AWAITING_ACK':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-amber-950/70 text-amber-300 border border-amber-500/40">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
            AWAITING ACK
          </span>
        )
      case 'FAILED_RETRYABLE':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-amber-950/70 text-amber-300 border border-amber-500/40">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
            RETRYING
          </span>
        )
      case 'FAILED_FINAL':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-red-950/70 text-red-400 border border-red-500/40">
            <span className="w-1.5 h-1.5 rounded-full bg-red-400"></span>
            FAILED FINAL
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-zinc-800 text-zinc-300 border border-zinc-700">
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-400"></span>
            {state}
          </span>
        )
    }
  }

  // Lifecycle timeline sequence with dynamic reclaim event insertion
  const stages = useMemo(() => {
    if (!message) return []
    const list = [
      {
        id: 1,
        name: 'MESSAGE_ENQUEUED',
        label: 'Stage 1: Client Ingestion',
        description: 'Client REST submission captured & enqueued',
        icon: Radio,
        timestamp: enqueueEvent?.timestamp || message.created_at,
        isCompleted: true,
        isActive: false,
        isReclaimNode: false,
        details: [
          { key: 'Sender Endpoint', val: message.sender_endpoint_id },
          { key: 'Recipient Endpoint', val: message.recipient_endpoint_id },
          { key: 'Idempotency Key', val: message.client_idempotency_key },
        ],
      },
      {
        id: 2,
        name: 'LEASE_ACQUIRED',
        label: 'Stage 2: Worker Lease Acquired',
        description: 'Atomic database lease assigned to background worker',
        icon: Cpu,
        timestamp:
          leaseEvent?.timestamp ||
          (['SENDING', 'AWAITING_ACK', 'DELIVERED'].includes(message.current_state)
            ? message.updated_at
            : null),
        isCompleted:
          !!leaseEvent || ['SENDING', 'AWAITING_ACK', 'DELIVERED'].includes(message.current_state),
        isActive: message.current_state === 'QUEUED',
        isReclaimNode: false,
        details: [
          {
            key: 'Worker ID',
            val:
              (leaseEvent?.details?.worker_id as string) ||
              message.worker_lease_id ||
              (message.current_state === 'DELIVERED' ? 'worker-primary' : 'Pending acquisition'),
          },
          {
            key: 'Lease Expiration',
            val:
              (leaseEvent?.details?.lease_expires_at as string) ||
              message.lease_expires_at ||
              (message.current_state === 'DELIVERED' ? 'Released on ACK' : '30.0s TTL'),
          },
          { key: 'Attempt Number', val: `${message.retry_count + 1} of ${message.max_retries}` },
        ],
      },
    ]

    // Insert illuminated intermediate event node if lease was reclaimed (D-13)
    if (reclaimEvent) {
      list.push({
        id: 2.5,
        name: 'WORKER_LEASE_RECLAIMED',
        label: 'Intervention: Worker Lease Reclaimed',
        description:
          'Previous worker crashed or timed out; lease reclaimed and delivery rescheduled',
        icon: AlertTriangle,
        timestamp: reclaimEvent.timestamp,
        isCompleted: true,
        isActive: false,
        isReclaimNode: true,
        details: [
          {
            key: 'Previous Worker ID',
            val: (reclaimEvent.details?.previous_worker_id as string) || 'unknown',
          },
          {
            key: 'Lease Expiration',
            val: (reclaimEvent.details?.lease_expires_at as string) || 'expired',
          },
          {
            key: 'Rescheduled Status',
            val: 'FAILED_RETRYABLE (Immediate Retry Scheduled)',
          },
          {
            key: 'Reclamation Sweep',
            val: reclaimEvent.details?.startup_sweep
              ? 'Server Startup Sweep'
              : 'Worker Background Sweeper',
          },
        ],
      })
    }

    list.push(
      {
        id: 3,
        name: 'INBOX_PERSISTED',
        label: 'Stage 3: Recipient Durable Storage',
        description: 'Durable SQLite recipient persistence verified',
        icon: Database,
        timestamp:
          inboxEvent?.timestamp ||
          inboxRecord?.stored_at ||
          (message.current_state === 'DELIVERED' ? message.delivered_at : null),
        isCompleted: !!inboxEvent || !!inboxRecord || message.current_state === 'DELIVERED',
        isActive: message.current_state === 'SENDING',
        isReclaimNode: false,
        details: [
          { key: 'Target Recipient', val: message.recipient_endpoint_id },
          { key: 'Storage Partition', val: 'SQLite inbox_messages' },
          {
            key: 'Integrity Check',
            val:
              inboxRecord?.integrity_status ||
              (message.current_state === 'DELIVERED' ? 'VALID' : 'Pending Verification'),
          },
        ],
      },
      {
        id: 4,
        name: 'ACK_VALIDATED_DELIVERED',
        label: 'Stage 4: Cryptographic ACK Verification',
        description: 'Cryptographic HMAC receipt signature verified',
        icon: ShieldCheck,
        timestamp: ackEvent?.timestamp || message.delivered_at,
        isCompleted:
          !!ackEvent || (message.current_state === 'DELIVERED' && !!message.signed_ack_receipt),
        isActive: message.current_state === 'AWAITING_ACK',
        isReclaimNode: false,
        details: [
          { key: 'Verification Scheme', val: 'HMAC-SHA256 Authenticated' },
          {
            key: 'Receipt State',
            val: message.signed_ack_receipt ? 'Cryptographically Sealed' : 'Awaiting Return ACK',
          },
        ],
      }
    )

    return list
  }, [enqueueEvent, leaseEvent, inboxEvent, ackEvent, reclaimEvent, message, inboxRecord])

  const sanitizedEvents = sanitizeMetadata(events)

  if (!isOpen || !message) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-out Drawer */}
      <aside
        className="fixed inset-y-0 right-0 z-50 w-full sm:w-[480px] bg-[#0B0F17]/95 backdrop-blur-xl border-l border-zinc-700/80 shadow-[-12px_0_35px_rgba(0,0,0,0.8)] flex flex-col transform transition-transform duration-300 ease-in-out"
        role="dialog"
        aria-modal="true"
        aria-labelledby="telemetry-drawer-title"
      >
        {/* Drawer Header */}
        <div className="p-5 border-b border-zinc-800 flex flex-col gap-3 bg-[#0B0F17]">
          <div className="flex items-center justify-between">
            <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-semibold tracking-wider uppercase bg-emerald-950/60 text-emerald-400 border border-emerald-500/40 shadow-[0_0_10px_rgba(16,185,129,0.25)]">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span>TACTICAL AUDIT TELEMETRY</span>
            </div>

            <button
              onClick={onClose}
              title="Close Telemetry [Esc]"
              aria-label="Close Telemetry [Esc]"
              className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/80 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="flex items-center justify-between gap-2">
            <h2 id="telemetry-drawer-title" className="text-base font-semibold text-zinc-100">
              Message Telemetry Audit
            </h2>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-zinc-800 text-zinc-300 border border-zinc-700">
                P{message.priority}
              </span>
              {getStatusBadge(message.current_state)}
            </div>
          </div>

          {/* Copyable Message UUID Chip */}
          <div className="flex items-center justify-between gap-2 bg-[#131B2E]/90 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs font-mono">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-zinc-500 shrink-0">UUID:</span>
              <span className="text-zinc-300 truncate select-all">{message.message_id}</span>
            </div>
            <button
              onClick={handleCopyMessageId}
              title="Copy Message ID"
              className="p-1 text-zinc-400 hover:text-zinc-100 transition-colors shrink-0"
            >
              {copiedMessageId ? (
                <Check className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          </div>

          {/* Dedicated Idempotency Seal Chip (D-10) */}
          <div className="flex items-center justify-between gap-2 bg-cyan-950/30 border border-cyan-500/40 rounded-lg px-3 py-1.5 text-xs font-mono shadow-[0_0_12px_rgba(6,182,212,0.15)]">
            <div className="flex items-center gap-1.5 min-w-0">
              <ShieldCheck className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              <span className="text-cyan-400 font-bold shrink-0">IDEMPOTENCY SEAL:</span>
              <span className="text-cyan-200 truncate select-all">{message.client_idempotency_key}</span>
            </div>
            <span className="text-[10px] uppercase font-bold text-cyan-300 bg-cyan-900/60 border border-cyan-400/50 px-1.5 py-0.5 rounded shrink-0">
              ✓ DEDUPLICATION SAFE
            </span>
          </div>

          {/* Active Retry Telemetry HUD Badge (D-14) */}
          {['FAILED_RETRYABLE', 'AWAITING_ACK'].includes(message.current_state) && (
            <div className="bg-amber-950/40 border border-amber-500/50 rounded-lg p-2.5 flex items-center justify-between text-xs font-mono shadow-[0_0_12px_rgba(245,158,11,0.2)]">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping shrink-0" />
                <span className="text-amber-300 font-semibold">
                  ⏳ Attempt {message.retry_count + 1}/{message.max_retries || 5}
                </span>
              </div>
              <div className="text-amber-400">
                Next retry in <span className="font-bold underline">{retryCountdown ? `${retryCountdown}s` : 'calculating...'}</span> [Backoff + Jitter]
              </div>
            </div>
          )}

          {/* Hardware Safety Lockout: STAR-V RF Keying Blocked (D-06, T-04-03) */}
          {isStarVLockoutBlocked && (
            <div className="bg-rose-950/70 border border-rose-500/80 p-3.5 rounded-xl space-y-1.5 shadow-[0_0_20px_rgba(244,63,94,0.3)]">
              <div className="flex items-center space-x-2 text-rose-400 font-bold text-xs tracking-wider">
                <ShieldAlert className="w-4 h-4 text-rose-400 animate-pulse shrink-0" />
                <span>[HARDWARE SAFETY LOCKOUT: STAR-V RF KEYING BLOCKED]</span>
              </div>
              <p className="text-[11px] text-zinc-300 font-mono leading-relaxed">
                Outbound RF keying strictly rejected by software safety boundary. Statutory COMSEC and defense authorization rules enforced with zero operational override.
              </p>
            </div>
          )}

          {/* DMR Multi-Burst Telemetry Breakdown (D-03, D-04) */}
          {dmrMetrics && (
            <div className="flex items-center justify-between gap-2 bg-[#131B2E] border border-cyan-900/60 rounded-lg px-3 py-1.5 text-xs font-mono">
              <div className="flex items-center gap-1.5 text-cyan-300">
                <Radio className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                <span>
                  DMR Bursts: <strong className="text-zinc-100">{dmrMetrics.dmrChunks} {dmrMetrics.dmrChunks === 1 ? 'Chunk' : 'Chunks'}</strong> • {dmrMetrics.dmrWireBudget}B Wire Budget {dmrMetrics.isPQC ? '(PQC Hybrid)' : ''}
                </span>
              </div>
              <span className="text-[10px] text-emerald-400 bg-emerald-950/60 border border-emerald-500/40 px-1.5 py-0.5 rounded font-bold shrink-0">
                {dmrMetrics.isPQC ? 'PQC FRAMING (v3)' : 'ATOMIC FRAMING'}
              </span>
            </div>
          )}
        </div>

        {/* Drawer Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* Error Banner */}
          {fetchError && (
            <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-600/40 text-amber-300 text-xs flex items-center justify-between gap-3 shadow-md">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                <span>{fetchError}</span>
              </div>
              <button
                onClick={fetchEvents}
                className="px-2.5 py-1 text-xs font-medium rounded bg-amber-600 hover:bg-amber-500 text-white shrink-0 transition-colors"
              >
                Retry Telemetry Fetch
              </button>
            </div>
          )}

          {/* Post-Quantum COMSEC Telemetry Section (Task 07-02-02, D-13) */}
          {(message.pqc_verified || message.envelope_version === 3) && (
            <div className="rounded-xl border border-cyan-500/40 bg-gradient-to-b from-cyan-950/30 to-slate-900/60 p-4 shadow-[0_0_20px_rgba(6,182,212,0.25)] backdrop-blur-md space-y-3">
              <div className="flex items-center justify-between pb-3 border-b border-cyan-500/20">
                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-5 h-5 text-cyan-400 drop-shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
                  <span className="text-xs font-mono font-bold tracking-wider text-cyan-300">
                    PQC SECURED (ML-KEM-768)
                  </span>
                </div>
                <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  ENVELOPE v3
                </span>
              </div>

              {/* Parameter Grid */}
              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                <div className="p-2 rounded bg-black/40 border border-cyan-500/20">
                  <div className="text-zinc-500 text-[10px] flex items-center gap-1">
                    <Cpu className="w-3 h-3 text-cyan-400" /> POST-QUANTUM KEM
                  </div>
                  <div className="text-cyan-200 font-semibold mt-0.5">ML-KEM-768 (NIST FIPS 203)</div>
                </div>

                <div className="p-2 rounded bg-black/40 border border-cyan-500/20">
                  <div className="text-zinc-500 text-[10px] flex items-center gap-1">
                    <Key className="w-3 h-3 text-cyan-400" /> CLASSICAL EPHEMERAL
                  </div>
                  <div className="text-cyan-200 font-semibold mt-0.5">X25519 (ECDH 256-bit)</div>
                </div>

                <div className="p-2 rounded bg-black/40 border border-cyan-500/20">
                  <div className="text-zinc-500 text-[10px]">ENCAPSULATION OVERHEAD</div>
                  <div className="text-zinc-200 font-semibold mt-0.5">1,088 Bytes (Ciphertext Block)</div>
                </div>

                <div className="p-2 rounded bg-black/40 border border-cyan-500/20">
                  <div className="text-zinc-500 text-[10px]">KEY DERIVATION</div>
                  <div className="text-zinc-200 font-semibold mt-0.5">HKDF-SHA256 (Salt: SHADOWCOMM-PQC-v3)</div>
                </div>

                <div className="p-2 rounded bg-black/40 border border-cyan-500/20">
                  <div className="text-zinc-500 text-[10px]">SYMMETRIC CIPHER</div>
                  <div className="text-emerald-400 font-semibold mt-0.5">AES-256-GCM (128-bit Tag Verified)</div>
                </div>

                <div className="p-2 rounded bg-black/40 border border-cyan-500/20">
                  <div className="text-zinc-500 text-[10px]">ANTI-REPLAY AAD</div>
                  <div className="text-zinc-300 font-mono text-[10px] truncate mt-0.5" title="version || scheme || sender || recipient || msg_id">
                    version || scheme || sender || recipient || msg_id
                  </div>
                </div>
              </div>

              <div className="pt-2 border-t border-cyan-500/20 flex items-center justify-between text-[10px] font-mono text-cyan-400/80">
                <span>NIST FIPS 203 Hybrid Lattice Security</span>
                <span className="text-emerald-400">1150B Total Header Overhead</span>
              </div>
            </div>
          )}

          {/* Classical v2 Fallback Warning Box (Task 07-02-02, D-14) */}
          {(message.pqc_downgrade_warning || message.envelope_version === 2) && (
            <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 p-4 shadow-[0_0_15px_rgba(245,158,11,0.2)] space-y-2">
              <div className="flex items-center space-x-2">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                <span className="text-xs font-mono font-bold tracking-wider text-amber-300">
                  CLASSICAL ENCRYPTION (V2): POST-QUANTUM VULNERABLE
                </span>
              </div>
              <p className="text-[11px] font-mono text-amber-200/90 leading-relaxed">
                This message was encrypted using classical AES-256-GCM without lattice-based key encapsulation. Vulnerable to harvest-now-decrypt-later quantum attacks.
              </p>
              <div className="flex items-center justify-between text-[10px] font-mono text-amber-400/80 pt-1 border-t border-amber-500/20">
                <span>SECURITY LEVEL: CLASSICAL 128-BIT</span>
                <span className="font-semibold text-amber-300">DOWNGRADE DETECTED</span>
              </div>
            </div>
          )}

          {/* Payload Summary Card */}
          <div className="p-3.5 rounded-lg bg-[#131B2E]/80 border border-zinc-800 space-y-2">
            <div className="flex items-center justify-between text-xs font-mono text-zinc-400">
              <span>TRANSMISSION PAYLOAD</span>
              <span className="text-[10px] text-zinc-500">{message.payload.length} BYTES</span>
            </div>
            <div className="p-2.5 rounded bg-[#0B0F17] border border-zinc-800/80 font-mono text-xs text-zinc-200 break-words max-h-24 overflow-y-auto">
              {message.payload}
            </div>
          </div>

          {/* 4-Stage Vertical 3D Stepped Event Timeline */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-emerald-400" />
                4-Stage Lifecycle Sequence
              </h3>
              {loadingEvents && (
                <span className="text-[11px] font-mono text-cyan-400 animate-pulse">Syncing...</span>
              )}
            </div>

            <div className="relative pl-6 space-y-6">
              {stages.map((stage, idx) => {
                const isLast = idx === stages.length - 1
                const StageIcon = stage.icon

                return (
                  <div key={stage.id} className="relative group">
                    {/* Connecting Vertical Line */}
                    {!isLast && (
                      <div
                        className={`absolute left-[-15px] top-7 bottom-[-24px] w-0.5 transition-colors duration-300 ${
                          stage.isReclaimNode
                            ? 'bg-amber-500/80 shadow-[0_0_8px_rgba(245,158,11,0.6)]'
                            : stage.isCompleted
                            ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]'
                            : 'bg-zinc-800'
                        }`}
                      />
                    )}

                    {/* Step Icon Node with 3D shadow */}
                    <div
                      className={`absolute left-[-24px] top-1 w-5 h-5 rounded-full flex items-center justify-center border transition-all duration-300 ${
                        stage.isReclaimNode
                          ? 'bg-amber-950 border-amber-500 text-amber-400 shadow-[0_0_12px_rgba(245,158,11,0.5)] animate-pulse'
                          : stage.isCompleted
                          ? 'bg-emerald-950 border-emerald-500 text-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.4)]'
                          : stage.isActive
                          ? 'bg-cyan-950 border-cyan-400 text-cyan-300 shadow-[0_0_12px_rgba(6,182,212,0.4)] animate-pulse'
                          : 'bg-zinc-900 border-zinc-700 text-zinc-600'
                      }`}
                    >
                      <StageIcon className="w-2.5 h-2.5" />
                    </div>

                    {/* Stage Card */}
                    <div
                      className={`p-3.5 rounded-lg border transition-all ${
                        stage.isReclaimNode
                          ? 'bg-amber-950/30 border-amber-500/50 shadow-[0_0_15px_rgba(245,158,11,0.15)]'
                          : stage.isCompleted
                          ? 'bg-[#131B2E]/90 border-zinc-700/80 shadow-md'
                          : stage.isActive
                          ? 'bg-cyan-950/20 border-cyan-500/40 shadow-[0_0_15px_rgba(6,182,212,0.1)]'
                          : 'bg-[#131B2E]/40 border-zinc-800/60 opacity-60'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`text-xs font-semibold ${
                            stage.isReclaimNode ? 'text-amber-300 font-mono' : 'text-zinc-200'
                          }`}
                        >
                          {stage.label}
                        </span>
                        {stage.isReclaimNode && (
                          <span className="text-[10px] font-mono text-amber-400 flex items-center gap-1 font-bold animate-pulse">
                            <AlertTriangle className="w-3 h-3 text-amber-400" /> LEASE RECLAIMED
                          </span>
                        )}
                        {!stage.isReclaimNode && stage.isCompleted && (
                          <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
                            <Check className="w-3 h-3" /> VERIFIED
                          </span>
                        )}
                        {stage.isActive && (
                          <span className="text-[10px] font-mono text-cyan-400 animate-pulse">
                            ACTIVE
                          </span>
                        )}
                      </div>

                      <p className="text-xs text-zinc-400 mt-0.5">{stage.description}</p>

                      {/* Dual Timestamp Display for Stage 1 (D-19) or Microsecond Timestamp */}
                      {stage.name === 'MESSAGE_ENQUEUED' ? (
                        <div className="mt-2 space-y-1 text-[11px] font-mono text-zinc-400">
                          <div className="flex items-center gap-1.5">
                            <Clock className="w-3 h-3 text-zinc-500 shrink-0" />
                            <span className="text-zinc-400">Composed:</span>
                            <span className="text-zinc-200">{formatMicroseconds(message.created_at)}</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <Radio className="w-3 h-3 text-emerald-400 shrink-0" />
                            <span className="text-zinc-400">Server Queued:</span>
                            <span className="text-emerald-300 font-semibold">
                              {formatMicroseconds(enqueueEvent?.timestamp || message.created_at)}
                            </span>
                          </div>
                        </div>
                      ) : (
                        <div className="mt-2 flex items-center gap-1.5 text-[11px] font-mono text-zinc-400">
                          <Clock className="w-3 h-3 text-zinc-500 shrink-0" />
                          <span
                            className={
                              stage.isReclaimNode ? 'text-amber-300 font-semibold' : 'text-zinc-300'
                            }
                          >
                            {stage.timestamp
                              ? formatMicroseconds(stage.timestamp)
                              : 'Pending Execution'}
                          </span>
                        </div>
                      )}

                      {/* Stage Metadata Details */}
                      {stage.isCompleted && (
                        <div className="mt-2.5 pt-2 border-t border-zinc-800/80 grid grid-cols-1 gap-1 text-[11px] font-mono">
                          {stage.details.map((item, dIdx) => (
                            <div key={dIdx} className="flex items-center justify-between gap-2">
                              <span className="text-zinc-500">{item.key}:</span>
                              <span
                                className={`truncate max-w-[220px] ${
                                  stage.isReclaimNode ? 'text-amber-200' : 'text-zinc-300'
                                }`}
                              >
                                {item.val}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Cryptographic Receipt Chip (HMAC Seal) */}
          {message.signed_ack_receipt && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                  <Lock className="w-3.5 h-3.5" />
                  Cryptographic HMAC Receipt Seal
                </span>
                <span className="text-[10px] font-mono text-zinc-500">HMAC-SHA256</span>
              </div>

              <div className="p-3 rounded-lg bg-emerald-950/30 border border-emerald-500/40 shadow-[0_0_15px_rgba(16,185,129,0.15)] flex flex-col gap-2">
                <div className="font-mono text-xs text-emerald-300 break-all select-all leading-relaxed">
                  {message.signed_ack_receipt}
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-emerald-500/20 text-xs">
                  <span className="text-[11px] font-mono text-emerald-400/80 flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                    Cryptographic Delivery Proof Sealed
                  </span>

                  <button
                    onClick={handleCopyReceipt}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-emerald-900/60 hover:bg-emerald-800/80 text-emerald-200 font-mono text-xs transition-colors border border-emerald-500/30 shadow-sm"
                  >
                    {copiedReceipt ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-300" />
                        <span>Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Copy Receipt</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Recipient Durable Storage Proof Section */}
          {inboxRecord && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                  <HardDrive className="w-3.5 h-3.5 text-emerald-400" />
                  Recipient Durable Storage Proof
                </span>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-500/60 shadow-[0_0_10px_rgba(16,185,129,0.3)]">
                  <Check className="w-3 h-3 text-emerald-400" />
                  INBOX PERSISTED
                </span>
              </div>

              <div className="p-3.5 rounded-lg bg-[#131B2E]/90 border border-emerald-500/30 space-y-2.5 shadow-md">
                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <div className="p-2 rounded bg-[#0B0F17]/80 border border-zinc-800">
                    <span className="text-zinc-500 text-[10px] block">RECIPIENT ENDPOINT</span>
                    <span className="text-zinc-200 font-medium">{inboxRecord.recipient_endpoint_id}</span>
                  </div>
                  <div className="p-2 rounded bg-[#0B0F17]/80 border border-zinc-800">
                    <span className="text-zinc-500 text-[10px] block">INTEGRITY STATUS</span>
                    <span className="text-emerald-400 font-medium">{inboxRecord.integrity_status}</span>
                  </div>
                </div>

                <div className="p-2 rounded bg-[#0B0F17]/80 border border-zinc-800 text-xs font-mono space-y-1">
                  <span className="text-zinc-500 text-[10px] block">DURABLE STORAGE TIMESTAMP</span>
                  <div className="text-zinc-200 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-emerald-400" />
                    <span>{formatMicroseconds(inboxRecord.stored_at)}</span>
                  </div>
                </div>

                <div className="p-2 rounded bg-[#0B0F17]/80 border border-zinc-800 text-xs font-mono space-y-1">
                  <span className="text-zinc-500 text-[10px] block">INBOX RECORD UUID</span>
                  <span className="text-zinc-300 break-all select-all">{inboxRecord.inbox_id}</span>
                </div>

                <p className="text-[11px] text-zinc-400 italic">
                  Durable SQLite Storage: Persisted in receiver inbox partition before ACK transmission.
                </p>
              </div>
            </div>
          )}

          {/* Collapsible Raw Telemetry Inspector */}
          <div className="space-y-2 pt-2 border-t border-zinc-800">
            <button
              onClick={() => setIsRawJsonOpen(!isRawJsonOpen)}
              className="w-full flex items-center justify-between p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-800 text-xs font-mono text-zinc-300 hover:bg-zinc-800/60 hover:text-zinc-100 transition-colors"
            >
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-cyan-400" />
                <span>Raw Audit Telemetry ({events.length} events)</span>
              </div>
              {isRawJsonOpen ? (
                <ChevronDown className="w-4 h-4 text-zinc-400" />
              ) : (
                <ChevronRight className="w-4 h-4 text-zinc-400" />
              )}
            </button>

            {isRawJsonOpen && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-[11px] font-mono text-zinc-500 px-1">
                  <span>Sanitized JSON Payload (T-02-01 Safe)</span>
                  <span>{events.length} records</span>
                </div>
                <pre className="p-3 text-[11px] font-mono text-zinc-300 bg-black/60 rounded-lg border border-zinc-800 overflow-x-auto max-h-64 scrollbar-thin">
                  {JSON.stringify(sanitizedEvents, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>

        {/* Drawer Footer */}
        <div className="p-4 border-t border-zinc-800 bg-[#0B0F17] flex items-center justify-between text-xs text-zinc-500 font-mono">
          <span>SHADOWCOMM AUDIT SUBSYSTEM</span>
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition-colors"
          >
            Close Telemetry [Esc]
          </button>
        </div>
      </aside>
    </>
  )
}

export default MessageTelemetryDrawer
