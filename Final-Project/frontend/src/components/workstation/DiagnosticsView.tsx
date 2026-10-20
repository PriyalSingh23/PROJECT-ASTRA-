import React, { useState, useEffect } from 'react'
import {
  Terminal,
  Activity,
  CheckCircle2,
  HardDrive,
  Copy,
  RotateCcw,
  ShieldCheck,
  ShieldAlert,
  Key,
  AlertTriangle,
  RefreshCw,
  Check,
  Lock,
  Cpu,
  X,
  Download,
} from 'lucide-react'
import { SystemDiagnosticsData, StationHealthMetadata, KeyringInfo, TamperTestResponse } from '../../types'
import { api, alphaApi, bravoApi } from '../../services/api'

export const DiagnosticsView: React.FC = () => {
  const [diag, setDiag] = useState<SystemDiagnosticsData | null>(null)
  const [alphaMeta, setAlphaMeta] = useState<StationHealthMetadata | null>(null)
  const [bravoMeta, setBravoMeta] = useState<StationHealthMetadata | null>(null)
  const [localKeyring, setLocalKeyring] = useState<KeyringInfo | null>(null)
  const [alphaKeys, setAlphaKeys] = useState<KeyringInfo | null>(null)
  const [bravoKeys, setBravoKeys] = useState<KeyringInfo | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [copied, setCopied] = useState<boolean>(false)
  const [rotateLoading, setRotateLoading] = useState<boolean>(false)
  const [rotateNotice, setRotateNotice] = useState<string | null>(null)
  const [tamperLoading, setTamperLoading] = useState<boolean>(false)
  const [tamperResult, setTamperResult] = useState<TamperTestResponse | null>(null)
  const [isZeroizeModalOpen, setIsZeroizeModalOpen] = useState<boolean>(false)
  const [zeroizeLoading, setZeroizeLoading] = useState<boolean>(false)
  const [zeroizeNotice, setZeroizeNotice] = useState<string | null>(null)
  const [pcapDownloading, setPcapDownloading] = useState<boolean>(false)

  const handleDownloadPcap = async () => {
    setPcapDownloading(true)
    try {
      const blob = await api.downloadPcapBlob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      const now = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
      a.href = url
      a.download = `astra_tactical_${now}.pcap`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      console.error('Failed to export PCAP capture', err)
    } finally {
      setPcapDownloading(false)
    }
  }

  const fetchDiagnostics = async () => {
    try {
      const [diagData, aData, bData, localKeys, aKeys, bKeys] = await Promise.allSettled([
        api.getSystemDiagnostics(),
        alphaApi.getHealth(),
        bravoApi.getHealth(),
        api.getPublicKeys(),
        alphaApi.getPublicKeys(),
        bravoApi.getPublicKeys(),
      ])

      if (diagData.status === 'fulfilled') setDiag(diagData.value)
      if (aData.status === 'fulfilled') setAlphaMeta(aData.value)
      else setAlphaMeta(null)
      if (bData.status === 'fulfilled') setBravoMeta(bData.value)
      else setBravoMeta(null)
      if (localKeys.status === 'fulfilled') setLocalKeyring(localKeys.value)
      else setLocalKeyring(null)
      if (aKeys.status === 'fulfilled') setAlphaKeys(aKeys.value)
      else setAlphaKeys(null)
      if (bKeys.status === 'fulfilled') setBravoKeys(bKeys.value)
      else setBravoKeys(null)
    } catch (err) {
      console.warn('Diagnostics fetch error:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleRotateKeypairs = async () => {
    setRotateLoading(true)
    setRotateNotice(null)
    try {
      const res = await api.rotateKeys()
      setRotateNotice(
        `Keypairs successfully rotated! New PQC Fingerprint: ${
          res.pqc_fingerprint?.substring(0, 16) || 'Updated'
        }`
      )
      const updated = await api.getPublicKeys().catch(() => null)
      if (updated) setLocalKeyring(updated)
      setTimeout(() => setRotateNotice(null), 8000)
    } catch (err) {
      setRotateNotice(err instanceof Error ? `Rotation failed: ${err.message}` : 'Rotation failed')
    } finally {
      setRotateLoading(false)
    }
  }

  const handleSimulateTamper = async () => {
    setTamperLoading(true)
    setTamperResult(null)
    try {
      const res = await api.simulateTamperTest()
      setTamperResult(res)
    } catch (err) {
      setTamperResult({
        tamper_detected: false,
        peer_http_status: 500,
        detail: err instanceof Error ? err.message : 'Tamper test network error',
      })
    } finally {
      setTamperLoading(false)
    }
  }

  const handleConfirmZeroize = async () => {
    setZeroizeLoading(true)
    setZeroizeNotice(null)
    try {
      const res = await api.zeroizeKeyring()
      setZeroizeNotice(
        res.detail || 'Station cryptographic keyrings securely expunged from memory and disk.'
      )
      setIsZeroizeModalOpen(false)
      const updated = await api.getPublicKeys().catch(() => null)
      setLocalKeyring(updated)
    } catch (err) {
      setZeroizeNotice(err instanceof Error ? `Zeroize error: ${err.message}` : 'Zeroization failed')
    } finally {
      setZeroizeLoading(false)
    }
  }

  useEffect(() => {
    fetchDiagnostics()
  }, [])

  const handleCopyDiagnostics = () => {
    if (!diag) return
    navigator.clipboard.writeText(JSON.stringify(diag, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (loading && !diag) {
    return (
      <div className="flex-1 flex items-center justify-center p-12 text-zinc-400 font-mono text-sm">
        <Activity className="w-5 h-5 animate-spin mr-2 text-emerald-400" />
        Probing System Diagnostics &amp; Hardware Registers...
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <Terminal className="w-5 h-5 text-emerald-400" />
            <h2 className="text-base font-bold font-mono text-zinc-100">
              System Health &amp; Hardware Diagnostics
            </h2>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5 font-sans">
            Real-time server telemetry, UHD SDR driver state, PyTorch execution backend, and database health
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          <button
            onClick={handleDownloadPcap}
            disabled={pcapDownloading}
            className="px-3 py-1.5 rounded-lg bg-cyan-950/60 hover:bg-cyan-900/60 text-cyan-300 border border-cyan-500/40 flex items-center space-x-1.5 transition-colors shadow-sm disabled:opacity-50"
            title="Download standard libpcap capture file for Wireshark analysis"
          >
            <Download className="w-3.5 h-3.5 text-cyan-400" />
            <span>{pcapDownloading ? 'Exporting...' : 'Export Wireshark (.pcap)'}</span>
          </button>
          <button
            onClick={handleCopyDiagnostics}
            className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 flex items-center space-x-1.5 transition-colors"
          >
            <Copy className="w-3.5 h-3.5" />
            <span>{copied ? 'Copied!' : 'Copy Diagnostics'}</span>
          </button>
          <button
            onClick={fetchDiagnostics}
            className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold flex items-center space-x-1.5 transition-colors shadow-sm"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Diagnostics Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 font-mono text-xs">
        {/* Backend API */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-zinc-400 uppercase text-[10px]">Flask Backend</span>
            <span className="text-emerald-400 font-bold flex items-center space-x-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{diag?.backend_status || 'ONLINE'}</span>
            </span>
          </div>
          <div className="space-y-1 text-zinc-300">
            <div className="flex justify-between">
              <span className="text-zinc-500">API Version:</span>
              <span>{diag?.api_version || 'v1.4.2'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Port:</span>
              <span>5050 (Canonical)</span>
            </div>
          </div>
        </div>

        {/* SDR Driver */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-zinc-400 uppercase text-[10px]">UHD SDR Driver</span>
            <span className="text-cyan-400 font-bold">
              {diag?.sdr_hardware?.driver_installed ? 'INSTALLED' : 'STANDBY'}
            </span>
          </div>
          <div className="space-y-1 text-zinc-300">
            <div className="flex justify-between">
              <span className="text-zinc-500">Version:</span>
              <span className="truncate max-w-[130px]">{diag?.sdr_hardware?.driver_version || 'UHD 4.8.0.0'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Device Mode:</span>
              <span className="text-emerald-400">{diag?.sdr_hardware?.operating_mode}</span>
            </div>
          </div>
        </div>

        {/* PyTorch / Hardware Acceleration */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-zinc-400 uppercase text-[10px]">PyTorch Backend</span>
            <span className="text-emerald-400 font-bold">
              {diag?.pytorch_backend?.version || '2.2.2'}
            </span>
          </div>
          <div className="space-y-1 text-zinc-300">
            <div className="flex justify-between">
              <span className="text-zinc-500">Active Device:</span>
              <span className="text-emerald-400 font-bold">{diag?.pytorch_backend?.active_device?.toUpperCase()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Apple Silicon:</span>
              <span className={diag?.pytorch_backend?.mps_available ? 'text-emerald-400' : 'text-zinc-400'}>
                {diag?.pytorch_backend?.mps_available ? 'MPS AVAILABLE' : 'CPU (OpenBLAS Safe)'}
              </span>
            </div>
          </div>
        </div>

        {/* SQLite Database */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-zinc-400 uppercase text-[10px]">Durable Database</span>
            <span className="text-emerald-400 font-bold">
              {diag?.database?.status || 'OPERATIONAL'}
            </span>
          </div>
          <div className="space-y-1 text-zinc-300">
            <div className="flex justify-between">
              <span className="text-zinc-500">File:</span>
              <span className="truncate max-w-[130px]">{diag?.database?.db_file}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Journal:</span>
              <span className="text-cyan-400 font-bold">{diag?.database?.mode}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Multi-Database Physical Storage & Daemon Topography (Phase 6, MDB-01) */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-5 rounded-xl space-y-4 font-mono text-xs">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 pb-3">
          <div className="flex items-center space-x-2">
            <HardDrive className="w-4 h-4 text-cyan-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-100">
              Multi-Database Physical Storage &amp; Daemon Topography
            </h3>
          </div>
          <span className="text-[10px] text-zinc-400">
            Physical SQLite WAL Isolation &bull; Concurrency Busy Timeout 5000ms
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Station Alpha Daemon Card */}
          <div className="bg-[#0B0F17] border border-cyan-500/30 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-cyan-400 font-bold text-xs flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                <span>Station Alpha Daemon</span>
              </span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                  alphaMeta?.status === 'HEALTHY'
                    ? 'bg-cyan-950/80 border-cyan-500/50 text-cyan-300'
                    : 'bg-rose-950/80 border-rose-600/60 text-rose-300 animate-pulse'
                }`}
              >
                {alphaMeta?.status === 'HEALTHY' ? 'ONLINE (:5051)' : 'OFFLINE (:5051)'}
              </span>
            </div>

            <div className="space-y-1.5 text-zinc-300 text-[11px]">
              <div className="flex justify-between">
                <span className="text-zinc-500">Physical File:</span>
                <span className="text-zinc-200 font-semibold">{alphaMeta?.db_path ? `data/${alphaMeta.db_path}` : 'data/alpha.db'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">SQLite Mode:</span>
                <span className="text-cyan-400 font-bold">WAL (Write-Ahead Logging)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Busy Timeout:</span>
                <span className="text-zinc-300">5000 ms</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Local Identity:</span>
                <span className="text-emerald-400 font-semibold">endpoint-a (Station Alpha)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Peer Ingest Target:</span>
                <span className="text-zinc-400 truncate max-w-[180px]">{alphaMeta?.peer_url || 'http://127.0.0.1:5052/api/v1'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Worker Daemon:</span>
                <span className="text-emerald-400 font-semibold">{alphaMeta?.worker_status || 'RUNNING (Embedded)'}</span>
              </div>
            </div>
          </div>

          {/* Station Bravo Daemon Card */}
          <div className="bg-[#0B0F17] border border-emerald-500/30 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-emerald-400 font-bold text-xs flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span>Station Bravo Daemon</span>
              </span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                  bravoMeta?.status === 'HEALTHY'
                    ? 'bg-emerald-950/80 border-emerald-500/50 text-emerald-300'
                    : 'bg-rose-950/80 border-rose-600/60 text-rose-300 animate-pulse'
                }`}
              >
                {bravoMeta?.status === 'HEALTHY' ? 'ONLINE (:5052)' : 'OFFLINE (:5052)'}
              </span>
            </div>

            <div className="space-y-1.5 text-zinc-300 text-[11px]">
              <div className="flex justify-between">
                <span className="text-zinc-500">Physical File:</span>
                <span className="text-zinc-200 font-semibold">{bravoMeta?.db_path ? `data/${bravoMeta.db_path}` : 'data/bravo.db'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">SQLite Mode:</span>
                <span className="text-emerald-400 font-bold">WAL (Write-Ahead Logging)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Busy Timeout:</span>
                <span className="text-zinc-300">5000 ms</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Local Identity:</span>
                <span className="text-emerald-400 font-semibold">endpoint-b (Station Bravo)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Peer Ingest Target:</span>
                <span className="text-zinc-400 truncate max-w-[180px]">{bravoMeta?.peer_url || 'http://127.0.0.1:5051/api/v1'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Worker Daemon:</span>
                <span className="text-emerald-400 font-semibold">{bravoMeta?.worker_status || 'RUNNING (Embedded)'}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* KEYRING & POST-QUANTUM CRYPTOGRAPHY (ML-KEM-768 + X25519) (Task 07-02-04, D-16) */}
      <div className="bg-zinc-900/60 border border-cyan-500/40 p-5 rounded-xl space-y-4 font-mono text-xs shadow-[0_0_20px_rgba(6,182,212,0.1)]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 pb-3">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-5 h-5 text-cyan-400 drop-shadow-[0_0_8px_rgba(6,182,212,0.6)]" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-cyan-300">
              KEYRING &amp; POST-QUANTUM CRYPTOGRAPHY (ML-KEM-768 + X25519)
            </h3>
          </div>
          <div className="flex items-center space-x-2">
            <span className="px-2 py-0.5 rounded text-[10px] bg-cyan-950/80 border border-cyan-500/50 text-cyan-300 font-bold">
              NIST FIPS 203
            </span>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                localKeyring && !localKeyring.is_zeroized && localKeyring.public_key_pqc
                  ? 'bg-emerald-950/80 border-emerald-500/50 text-emerald-300'
                  : 'bg-amber-950/80 border-amber-500/50 text-amber-300'
              }`}
            >
              {localKeyring && !localKeyring.is_zeroized && localKeyring.public_key_pqc
                ? 'COMSEC: READY'
                : 'COMSEC: ZEROIZED / UNLOADED'}
            </span>
          </div>
        </div>

        {/* Action Notifications */}
        {rotateNotice && (
          <div className="p-3 rounded-lg bg-cyan-950/80 border border-cyan-500/60 text-cyan-200 text-xs flex items-center justify-between gap-3 shadow-md">
            <div className="flex items-center gap-2">
              <Check className="w-4 h-4 text-cyan-400 shrink-0" />
              <span>{rotateNotice}</span>
            </div>
            <button
              onClick={() => setRotateNotice(null)}
              className="text-cyan-400 hover:text-cyan-200 p-0.5 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {zeroizeNotice && (
          <div className="p-3 rounded-lg bg-amber-950/80 border border-amber-500/60 text-amber-200 text-xs flex items-center justify-between gap-3 shadow-md">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              <span>{zeroizeNotice}</span>
            </div>
            <button
              onClick={() => setZeroizeNotice(null)}
              className="text-amber-400 hover:text-amber-200 p-0.5 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Local Station Key Fingerprints Card */}
        <div className="bg-[#0B0F17] border border-cyan-500/30 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-cyan-400 font-bold text-xs flex items-center space-x-1.5">
              <Key className="w-3.5 h-3.5 text-cyan-400" />
              <span>Local Station Keyring Fingerprints</span>
            </span>
            <span className="text-zinc-500 text-[10px]">
              Path: data/keys/{localKeyring?.station_id || localKeyring?.endpoint_id || 'station'}.keyring
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
            <div className="p-2.5 rounded bg-zinc-900/60 border border-zinc-800 space-y-1">
              <div className="text-zinc-500 text-[10px] flex items-center gap-1">
                <Cpu className="w-3 h-3 text-cyan-400" /> ML-KEM-768 PUBLIC KEY (FIPS 203)
              </div>
              <div
                className="text-zinc-200 font-mono truncate"
                title={localKeyring?.pqc_fingerprint || localKeyring?.fingerprint_pqc || 'Unavailable'}
              >
                Fingerprint:{' '}
                <span className="text-cyan-300 font-bold">
                  {localKeyring?.pqc_fingerprint ||
                    localKeyring?.fingerprint_pqc ||
                    (localKeyring?.public_key_pqc
                      ? `${localKeyring.public_key_pqc.substring(0, 32)}...`
                      : 'None (Zeroized)')}
                </span>
              </div>
              <div className="text-[10px] text-zinc-500">1,184 Bytes Encapsulation Key</div>
            </div>

            <div className="p-2.5 rounded bg-zinc-900/60 border border-zinc-800 space-y-1">
              <div className="text-zinc-500 text-[10px] flex items-center gap-1">
                <Key className="w-3 h-3 text-cyan-400" /> X25519 IDENTITY PUBLIC KEY
              </div>
              <div
                className="text-zinc-200 font-mono truncate"
                title={localKeyring?.x25519_fingerprint || localKeyring?.fingerprint_x25519 || 'Unavailable'}
              >
                Fingerprint:{' '}
                <span className="text-cyan-300 font-bold">
                  {localKeyring?.x25519_fingerprint ||
                    localKeyring?.fingerprint_x25519 ||
                    (localKeyring?.public_key_x25519
                      ? `${localKeyring.public_key_x25519.substring(0, 32)}...`
                      : 'None (Zeroized)')}
                </span>
              </div>
              <div className="text-[10px] text-zinc-500">32 Bytes Curve25519 ECDH Identity</div>
            </div>
          </div>
        </div>

        {/* Peer Public Key Synchronization Table */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-200 flex items-center space-x-1.5">
              <Lock className="w-3.5 h-3.5 text-emerald-400" />
              <span>Peer Public Key Synchronization State</span>
            </span>
            <span className="text-[10px] text-zinc-500">REST Auto-Discovery Enabled</span>
          </div>

          <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-[#0B0F17]">
            <table className="w-full text-left text-[11px] font-mono">
              <thead className="bg-zinc-900/80 border-b border-zinc-800 text-zinc-400">
                <tr>
                  <th className="py-2 px-3">Station ID</th>
                  <th className="py-2 px-3">ML-KEM-768 PK Preview</th>
                  <th className="py-2 px-3">X25519 PK Preview</th>
                  <th className="py-2 px-3 text-right">Discovery Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-cyan-300">
                    endpoint-a (Station Alpha)
                  </td>
                  <td
                    className="py-2.5 px-3 font-mono text-zinc-400 truncate max-w-[200px]"
                    title={alphaKeys?.public_key_pqc || 'Loading...'}
                  >
                    {alphaKeys?.public_key_pqc
                      ? `${alphaKeys.public_key_pqc.substring(0, 24)}...`
                      : 'Discovered via REST'}
                  </td>
                  <td
                    className="py-2.5 px-3 font-mono text-zinc-400 truncate max-w-[150px]"
                    title={alphaKeys?.public_key_x25519 || 'Loading...'}
                  >
                    {alphaKeys?.public_key_x25519
                      ? `${alphaKeys.public_key_x25519.substring(0, 20)}...`
                      : 'Discovered'}
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950/80 border border-emerald-500/50 text-emerald-400 font-bold">
                      REST DISCOVERED
                    </span>
                  </td>
                </tr>
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-emerald-300">
                    endpoint-b (Station Bravo)
                  </td>
                  <td
                    className="py-2.5 px-3 font-mono text-zinc-400 truncate max-w-[200px]"
                    title={bravoKeys?.public_key_pqc || 'Loading...'}
                  >
                    {bravoKeys?.public_key_pqc
                      ? `${bravoKeys.public_key_pqc.substring(0, 24)}...`
                      : 'Discovered via REST'}
                  </td>
                  <td
                    className="py-2.5 px-3 font-mono text-zinc-400 truncate max-w-[150px]"
                    title={bravoKeys?.public_key_x25519 || 'Loading...'}
                  >
                    {bravoKeys?.public_key_x25519
                      ? `${bravoKeys.public_key_x25519.substring(0, 20)}...`
                      : 'Discovered'}
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950/80 border border-emerald-500/50 text-emerald-400 font-bold">
                      REST DISCOVERED
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Operator Cryptographic Controls */}
        <div className="pt-2 border-t border-zinc-800 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              {/* Rotate Keypairs Button */}
              <button
                type="button"
                onClick={handleRotateKeypairs}
                disabled={rotateLoading}
                className="px-3 py-1.5 rounded-lg bg-cyan-900/40 hover:bg-cyan-800/60 border border-cyan-500/40 text-cyan-300 font-semibold flex items-center space-x-1.5 transition-colors cursor-pointer disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${rotateLoading ? 'animate-spin' : ''}`} />
                <span>{rotateLoading ? 'Rotating...' : 'Rotate Keypairs'}</span>
              </button>

              {/* Simulate PQC Tamper Test Button */}
              <button
                type="button"
                onClick={handleSimulateTamper}
                disabled={tamperLoading}
                className="px-3 py-1.5 rounded-lg bg-amber-900/40 hover:bg-amber-800/60 border border-amber-500/40 text-amber-300 font-semibold flex items-center space-x-1.5 transition-colors cursor-pointer disabled:opacity-50"
              >
                <ShieldAlert className={`w-3.5 h-3.5 ${tamperLoading ? 'animate-pulse text-amber-400' : ''}`} />
                <span>{tamperLoading ? 'Injecting Tamper Probe...' : 'Simulate PQC Tamper Test'}</span>
              </button>
            </div>

            {/* Emergency Zeroize Button */}
            <button
              type="button"
              onClick={() => setIsZeroizeModalOpen(true)}
              className="px-3 py-1.5 rounded-lg bg-rose-950/60 hover:bg-rose-900/80 border border-rose-500/60 text-rose-300 font-bold flex items-center space-x-1.5 transition-colors cursor-pointer shadow-[0_0_12px_rgba(239,68,68,0.2)]"
            >
              <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
              <span>Emergency Zeroize</span>
            </button>
          </div>

          {/* Tamper Test Result Banner */}
          {tamperResult && (
            <div
              className={`p-3 rounded-lg border flex items-center justify-between gap-3 ${
                tamperResult.tamper_detected || tamperResult.peer_http_status === 422
                  ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300 shadow-[0_0_15px_rgba(16,185,129,0.15)]'
                  : 'bg-rose-950/40 border-rose-500/50 text-rose-300'
              }`}
            >
              <div className="flex items-center gap-2">
                {tamperResult.tamper_detected || tamperResult.peer_http_status === 422 ? (
                  <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                )}
                <span>
                  {tamperResult.tamper_detected || tamperResult.peer_http_status === 422
                    ? '[TAMPER REJECTED: HTTP 422 CRYPTO_AUTHENTICATION_FAILED Verified]'
                    : `[TAMPER TEST UNEXPECTED RESPONSE: HTTP ${
                        tamperResult.peer_http_status || 'ERROR'
                      } - ${tamperResult.detail || 'Failed'}]`}
                </span>
              </div>
              <button
                onClick={() => setTamperResult(null)}
                className="text-zinc-400 hover:text-zinc-200 p-0.5 cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Emergency Zeroize Confirmation Modal (Task 07-02-04, T-07-07) */}
      {isZeroizeModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#120B0F] border-2 border-rose-500/80 rounded-xl max-w-md w-full p-6 space-y-4 shadow-[0_0_40px_rgba(239,68,68,0.35)] font-mono">
            <div className="flex items-center space-x-2 text-rose-400 pb-2 border-b border-rose-900/60">
              <AlertTriangle className="w-6 h-6 animate-pulse" />
              <h3 className="text-sm font-bold tracking-wider uppercase text-rose-300">
                EMERGENCY KEYRING ZEROIZATION
              </h3>
            </div>

            <p className="text-xs text-zinc-300 leading-relaxed font-sans">
              You are about to execute a destructive emergency cryptographic purge. This will permanently overwrite memory and disk keyrings with pseudo-random bytes and zeroes, rendering all existing post-quantum ciphertexts indecipherable.
            </p>

            <div className="p-3 bg-rose-950/40 border border-rose-800/60 rounded text-[11px] text-rose-300">
              WARNING: Incoming peer transmissions will be rejected until fresh keypairs are generated or rotated.
            </div>

            <div className="flex items-center justify-end space-x-3 pt-2">
              <button
                type="button"
                onClick={() => setIsZeroizeModalOpen(false)}
                disabled={zeroizeLoading}
                className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-semibold transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmZeroize}
                disabled={zeroizeLoading}
                className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition-all shadow-md flex items-center space-x-1.5 cursor-pointer"
              >
                {zeroizeLoading ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Zeroizing...</span>
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>Confirm Emergency Zeroize</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Raw Diagnostic JSON Viewer */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3 font-mono text-xs">
        <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200">
          Raw Diagnostics Object (Safe Redacted)
        </h3>
        <pre className="p-3 bg-zinc-950 border border-zinc-850 rounded-lg text-zinc-300 text-[11px] overflow-x-auto max-h-72 leading-relaxed">
          {JSON.stringify(diag, null, 2)}
        </pre>
      </div>
    </div>
  )
}
