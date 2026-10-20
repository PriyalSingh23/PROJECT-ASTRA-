import React from 'react'
import { ShieldCheck, Database, Key, ArrowRight, AlertTriangle } from 'lucide-react'
import { InboxMessage } from '../types'
import { formatMicroseconds } from './MessageTelemetryDrawer'

export interface InboxReceiptCardProps {
  inboxItem: InboxMessage
  isSelected: boolean
  onClick: () => void
}

export const InboxReceiptCard: React.FC<InboxReceiptCardProps> = ({
  inboxItem,
  isSelected,
  onClick,
}) => {
  const isIntegrityValid =
    inboxItem.integrity_status?.toUpperCase() === 'VALID' ||
    inboxItem.integrity_status?.toUpperCase() === 'OK'

  const formattedTimestamp = formatMicroseconds(inboxItem.stored_at || inboxItem.created_at)

  const payloadSnippet =
    inboxItem.payload.length > 120
      ? `${inboxItem.payload.substring(0, 120)}...`
      : inboxItem.payload

  return (
    <div
      onClick={onClick}
      className={`rounded-lg p-3 transition-all cursor-pointer relative overflow-hidden group ${
        isSelected
          ? 'bg-[#1E293B] border border-emerald-400 ring-1 ring-emerald-400/50 shadow-[0_4px_24px_rgba(16,185,129,0.25)]'
          : 'bg-[#131B2E] hover:bg-[#1E293B] border border-emerald-500/40 shadow-[0_4px_20px_rgba(16,185,129,0.12)]'
      }`}
    >
      {/* Top Bar: Route, Type, and Emerald 3D Seal Badge */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center space-x-1.5 text-xs font-mono text-zinc-300 truncate">
          <span className="text-zinc-400 font-semibold">{inboxItem.sender_endpoint_id}</span>
          <ArrowRight className="w-3 h-3 text-emerald-400 shrink-0" />
          <span className="text-emerald-300 font-semibold">{inboxItem.recipient_endpoint_id}</span>
          {inboxItem.message_type && (
            <span className="ml-1 text-[10px] bg-zinc-800 border border-zinc-700 text-zinc-400 px-1.5 py-0.2 rounded font-sans uppercase">
              {inboxItem.message_type}
            </span>
          )}
          {(inboxItem.pqc_verified || inboxItem.envelope_version === 3) && (
            <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-mono border border-cyan-500/40 bg-cyan-950/30 text-cyan-300">
              <ShieldCheck className="w-3 h-3 text-cyan-400" />
              <span>PQC SECURED</span>
            </span>
          )}
          {(inboxItem.pqc_downgrade_warning || inboxItem.envelope_version === 2) && (
            <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-mono border border-amber-500/40 bg-amber-950/30 text-amber-300">
              <AlertTriangle className="w-3 h-3 text-amber-400" />
              <span>CLASSICAL V2</span>
            </span>
          )}
        </div>

        {/* Emerald 3D Seal Badge */}
        <div className="shrink-0 bg-emerald-950/80 border border-emerald-500/60 text-emerald-300 font-mono text-[9px] font-bold px-2 py-0.5 rounded shadow-[0_0_8px_rgba(16,185,129,0.3)] flex items-center space-x-1">
          <ShieldCheck className="w-3 h-3 text-emerald-400 shrink-0" />
          <span>INBOX PERSISTED</span>
        </div>
      </div>

      {/* Storage Timestamp */}
      <div className="text-[10px] font-mono text-zinc-400 mb-2 flex items-center space-x-1">
        <span className="text-zinc-500">Stored:</span>
        <span className="text-zinc-300">{formattedTimestamp}</span>
      </div>

      {/* Payload Preview */}
      <div className="bg-[#0B0F17]/70 rounded p-2 border border-zinc-800/80 mb-2.5">
        <p className="font-mono text-xs text-zinc-200 break-words whitespace-pre-wrap leading-relaxed line-clamp-3">
          {payloadSnippet}
        </p>
      </div>

      {/* Footer: Physical Storage Proof, Integrity Status & HMAC Signature */}
      <div className="flex flex-wrap items-center justify-between gap-1.5 pt-1 border-t border-zinc-800/60 text-[10px] font-mono">
        <div className="flex items-center space-x-2">
          {/* Storage Engine Tag */}
          <span className="flex items-center space-x-1 text-zinc-400 bg-zinc-900/80 border border-zinc-700/60 px-1.5 py-0.5 rounded">
            <Database className="w-2.5 h-2.5 text-emerald-400/80" />
            <span>SQLITE WAL STORAGE</span>
          </span>

          {/* Integrity Pill */}
          <span
            className={`px-1.5 py-0.5 rounded font-semibold border ${
              isIntegrityValid
                ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-400'
                : 'bg-amber-950/60 border-amber-500/40 text-amber-400'
            }`}
          >
            {isIntegrityValid ? 'VALID' : 'UNVERIFIED'}
          </span>
        </div>

        {/* Cryptographic Receipt Signature Pill */}
        {inboxItem.signed_ack_receipt && (
          <div
            className="flex items-center space-x-1 text-emerald-400/90 bg-emerald-950/40 border border-emerald-500/30 px-1.5 py-0.5 rounded truncate max-w-[170px]"
            title={inboxItem.signed_ack_receipt}
          >
            <Key className="w-2.5 h-2.5 shrink-0 text-emerald-400" />
            <span className="truncate">
              {inboxItem.signed_ack_receipt.length > 18
                ? `${inboxItem.signed_ack_receipt.substring(0, 18)}...`
                : inboxItem.signed_ack_receipt}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
