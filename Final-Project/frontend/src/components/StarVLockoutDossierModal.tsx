import React, { useState, useEffect, useCallback } from 'react'
import {
  X,
  ShieldAlert,
  Lock,
  RotateCcw,
  FileWarning,
  Radio,
  FileText,
  Key,
  ShieldX,
} from 'lucide-react'
import { api } from '../services/api'
import { StarVTestResult } from '../types'

export interface StarVLockoutDossierModalProps {
  isOpen: boolean
  onClose: () => void
}

export const StarVLockoutDossierModal: React.FC<StarVLockoutDossierModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [loadingTest, setLoadingTest] = useState<'soft_refusal' | 'hard_command' | null>(null)
  const [testResult, setTestResult] = useState<StarVTestResult | null>(null)
  const [testError, setTestError] = useState<string | null>(null)

  // Handle escape key
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

  const runTest = useCallback(async (testType: 'soft_refusal' | 'hard_command') => {
    setLoadingTest(testType)
    setTestError(null)
    try {
      const res = await api.testStarVLockout(testType)
      setTestResult(res)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Lockout test failed'
      setTestError(msg)
    } finally {
      setLoadingTest(null)
    }
  }, [])

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-[#131B2E] border border-rose-500/60 shadow-[0_4px_30px_rgba(239,68,68,0.3)] rounded-xl max-w-2xl w-full p-6 text-zinc-100 font-mono space-y-5 overflow-y-auto max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b border-rose-500/30 pb-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="px-2 py-0.5 rounded bg-rose-950/80 border border-rose-500/80 text-rose-400 text-[10px] font-bold flex items-center space-x-1 shadow-[0_0_10px_rgba(244,63,94,0.3)]">
                <ShieldAlert className="w-3 h-3 text-rose-400" />
                <span>PERMANENT SAFETY LOCKOUT ENFORCED</span>
              </span>
              <span className="text-[10px] text-zinc-500 font-semibold tracking-wider">
                HARDWARE DEFENSE SAFEGUARD
              </span>
            </div>
            <h2 className="text-base font-bold text-zinc-100 tracking-tight">
              STAR-V Mk III Tactical SDR — Hardware Safety Dossier
            </h2>
            <p className="text-xs text-rose-300/80 font-sans">
              Permanent software safety lockout enforced. Physical RF transmission strictly prohibited.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Safety Rationale */}
        <div className="bg-[#1C1318] border border-rose-900/60 rounded-lg p-3.5 space-y-2 text-xs">
          <div className="flex items-center space-x-2 text-rose-400 font-bold text-xs uppercase tracking-wider">
            <FileWarning className="w-4 h-4 text-rose-400" />
            <span>Operational & Regulatory Safety Rationale</span>
          </div>
          <p className="text-zinc-300 font-sans text-xs leading-relaxed">
            The STAR-V Mk III tactical software-defined radio operates high-power frequency-hopping ECCM waveforms with TRANSEC hardware crypto. Uncoordinated physical keying or unvalidated commanding carries extreme risks of transmitter final-stage amplifier burnout, frequency-hopping desynchronization, and statutory regulatory/defense radio authorization violations.
          </p>
        </div>

        {/* 4 Statutory Prerequisites Checklist */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between text-xs font-bold text-zinc-300 uppercase tracking-wider">
            <span className="flex items-center space-x-1.5">
              <Lock className="w-3.5 h-3.5 text-rose-400" />
              <span>Statutory Prerequisites Checklist (0/4 Verified)</span>
            </span>
            <span className="text-[10px] text-rose-400 font-mono">[LOCKED BY POLICY]</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            {/* Prereq 1 */}
            <div className="p-3 rounded-lg bg-zinc-900/70 border border-zinc-800 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-zinc-200 flex items-center space-x-1.5">
                  <FileText className="w-3.5 h-3.5 text-zinc-400" />
                  <span>1. Vendor ICD Specification</span>
                </span>
                <span className="px-1.5 py-0.5 rounded bg-rose-950/60 border border-rose-800 text-[9px] text-rose-400 font-bold">
                  MISSING - LOCKED
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 font-sans leading-tight">
                Vendor Interface Control Document with hardware pinouts, baud rate, and command frame structure.
              </p>
            </div>

            {/* Prereq 2 */}
            <div className="p-3 rounded-lg bg-zinc-900/70 border border-zinc-800 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-zinc-200 flex items-center space-x-1.5">
                  <ShieldX className="w-3.5 h-3.5 text-zinc-400" />
                  <span>2. Defense Authorization</span>
                </span>
                <span className="px-1.5 py-0.5 rounded bg-rose-950/60 border border-rose-800 text-[9px] text-rose-400 font-bold">
                  UNAUTHORIZED
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 font-sans leading-tight">
                Classified security authorization from Ministry of Defense for external serial/IP commanding.
              </p>
            </div>

            {/* Prereq 3 */}
            <div className="p-3 rounded-lg bg-zinc-900/70 border border-zinc-800 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-zinc-200 flex items-center space-x-1.5">
                  <Radio className="w-3.5 h-3.5 text-zinc-400" />
                  <span>3. Station RF License</span>
                </span>
                <span className="px-1.5 py-0.5 rounded bg-rose-950/60 border border-rose-800 text-[9px] text-rose-400 font-bold">
                  UNLICENSED
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 font-sans leading-tight">
                Valid operational radio spectrum frequency assignment and station transmission license.
              </p>
            </div>

            {/* Prereq 4 */}
            <div className="p-3 rounded-lg bg-zinc-900/70 border border-zinc-800 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-zinc-200 flex items-center space-x-1.5">
                  <Key className="w-3.5 h-3.5 text-zinc-400" />
                  <span>4. COMSEC Protocol Keying</span>
                </span>
                <span className="px-1.5 py-0.5 rounded bg-rose-950/60 border border-rose-800 text-[9px] text-rose-400 font-bold">
                  ZEROIZED
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 font-sans leading-tight">
                Operational TRANSEC cryptographic keying material and fill device handshake zeroized.
              </p>
            </div>
          </div>
        </div>

        {/* Live Dry-Run Test Bench */}
        <div className="space-y-3 pt-3 border-t border-zinc-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-zinc-200 uppercase tracking-wider flex items-center space-x-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-cyan-400" />
              <span>Safety Verification Test Bench (Zero RF Keying)</span>
            </span>
            <span className="text-[10px] text-zinc-500 font-mono">DRY-RUN PROBE</span>
          </div>

          <div className="flex flex-wrap gap-2.5">
            <button
              type="button"
              onClick={() => runTest('soft_refusal')}
              disabled={loadingTest !== null}
              className="px-3 py-2 rounded-lg bg-rose-950/60 hover:bg-rose-900/70 border border-rose-700/80 text-rose-200 text-xs font-bold flex items-center space-x-1.5 transition-all disabled:opacity-50 shadow-sm cursor-pointer"
            >
              {loadingTest === 'soft_refusal' ? (
                <RotateCcw className="w-3.5 h-3.5 animate-spin text-rose-400" />
              ) : (
                <Lock className="w-3.5 h-3.5 text-rose-400" />
              )}
              <span>Simulate Soft Refusal (send)</span>
            </button>

            <button
              type="button"
              onClick={() => runTest('hard_command')}
              disabled={loadingTest !== null}
              className="px-3 py-2 rounded-lg bg-red-950/80 hover:bg-red-900/90 border border-red-600 text-red-200 text-xs font-bold flex items-center space-x-1.5 transition-all disabled:opacity-50 shadow-sm cursor-pointer"
            >
              {loadingTest === 'hard_command' ? (
                <RotateCcw className="w-3.5 h-3.5 animate-spin text-red-400" />
              ) : (
                <ShieldAlert className="w-3.5 h-3.5 text-red-400" />
              )}
              <span>Simulate Hard Command Lockout (command_transmit)</span>
            </button>
          </div>

          {/* Test Error */}
          {testError && (
            <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-500/60 text-rose-300 text-xs">
              {testError}
            </div>
          )}

          {/* Test Outcome Banner */}
          {testResult && (
            <div className="p-3.5 rounded-lg bg-[#0B0F17] border border-rose-500/70 space-y-2 shadow-[0_0_15px_rgba(244,63,94,0.2)]">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-rose-400">
                  {testResult.test_type === 'soft_refusal'
                    ? '[TEST OUTCOME: BLOCKED • Soft Refusal Verified]'
                    : '[TEST OUTCOME: BLOCKED • Exception StarVSafetyLockoutError Caught]'}
                </span>
                {testResult.audit_logged && (
                  <span className="px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-500/60 text-emerald-300 text-[10px] font-bold shadow-[0_0_8px_rgba(16,185,129,0.2)]">
                    [AUDIT LOGGED: HIGH SEVERITY EVENT RECORDED]
                  </span>
                )}
              </div>
              <p className="text-[11px] text-zinc-300 font-sans leading-relaxed">
                {testResult.details}
              </p>
              <div className="text-[10px] text-zinc-500 font-mono">
                Mechanism: <span className="text-zinc-300">{testResult.mechanism}</span> • Status:{' '}
                <span className="text-rose-400 font-bold">{testResult.status}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
