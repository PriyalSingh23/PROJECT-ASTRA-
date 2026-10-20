import React, { useState, useEffect } from 'react'
import { Radio, Activity, Signal, Zap, ChevronDown, ChevronUp, ShieldCheck, ShieldAlert } from 'lucide-react'
import { api } from '../../services/api'
import { LinkBudgetResult } from '../../types'

interface LinkBudgetHUDProps {
  currentDistanceKm?: number
  activeHopName?: string
}

export const LinkBudgetHUD: React.FC<LinkBudgetHUDProps> = ({
  currentDistanceKm = 8.5,
  activeHopName = 'Alpha -> UAV Alpha -> Convoy -> Bravo',
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const [selectedPreset, setSelectedPreset] = useState<string>('UHF_MOTOTRBO')
  const [budget, setBudget] = useState<LinkBudgetResult | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchBudget = async (preset: string, dist: number) => {
    setLoading(true)
    try {
      const res = await api.calculateLinkBudget({
        preset,
        distance_km: dist,
      })
      setBudget(res)
    } catch (e) {
      console.error('Failed to compute link budget', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchBudget(selectedPreset, currentDistanceKm)
  }, [selectedPreset, currentDistanceKm])

  return (
    <div className="absolute top-20 right-4 z-20 w-80 font-mono text-xs">
      <div className="bg-white/95 dark:bg-slate-900/90 text-slate-800 dark:text-slate-100 backdrop-blur-md border border-slate-200 dark:border-cyan-500/30 rounded-xl shadow-xl overflow-hidden transition-all duration-200">
        {/* Header */}
        <div
          className="flex items-center justify-between px-3 py-2 bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-cyan-500/20 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800/80"
          onClick={() => setIsOpen(!isOpen)}
        >
          <div className="flex items-center space-x-2">
            <Radio className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400 animate-pulse" />
            <span className="font-semibold text-cyan-900 dark:text-cyan-200 tracking-wide text-[11px]">
              TACTICAL RF LINK BUDGET
            </span>
          </div>
          <div className="flex items-center space-x-2">
            {budget && (
              <span
                className="px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wider"
                style={{
                  backgroundColor: `${budget.status_color}20`,
                  color: budget.status_color,
                  border: `1px solid ${budget.status_color}50`,
                }}
              >
                {budget.status}
              </span>
            )}
            {isOpen ? (
              <ChevronUp className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
            )}
          </div>
        </div>

        {/* Collapsible Content */}
        {isOpen && (
          <div className="p-3 space-y-3">
            {/* Active Path Info */}
            <div className="bg-slate-50 dark:bg-slate-950/60 p-2 rounded border border-slate-200 dark:border-slate-800 text-[10px]">
              <div className="text-slate-500 dark:text-slate-400 font-bold">ACTIVE RF HORIZON:</div>
              <div className="text-cyan-700 dark:text-cyan-300 truncate font-semibold mt-0.5">{activeHopName}</div>
              <div className="flex justify-between mt-1 text-slate-600 dark:text-slate-400">
                <span>Distance:</span>
                <span className="text-slate-900 dark:text-slate-200 font-bold">{currentDistanceKm.toFixed(1)} km</span>
              </div>
            </div>

            {/* Tactical Presets */}
            <div>
              <div className="text-[10px] text-slate-400 mb-1">TACTICAL BAND PRESET:</div>
              <div className="grid grid-cols-2 gap-1.5">
                {[
                  { key: 'VHF_TACTICAL', label: 'VHF 144M', power: '50W' },
                  { key: 'UHF_MOTOTRBO', label: 'UHF 433M', power: '5W' },
                  { key: 'ISM_TACTICAL_MESH', label: 'ISM 915M', power: '1W' },
                  { key: 'AIRBORNE_DOWNLINK', label: 'L-Band 1.4G', power: '2W' },
                ].map((p) => (
                  <button
                    key={p.key}
                    onClick={() => setSelectedPreset(p.key)}
                    className={`px-2 py-1.5 rounded text-[10px] border text-left transition-colors ${
                      selectedPreset === p.key
                        ? 'border-cyan-500 bg-cyan-950/40 text-cyan-200 font-bold'
                        : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div>{p.label}</div>
                    <div className="text-[8px] text-slate-500">{p.power}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Calculations Display */}
            {budget && (
              <div className="space-y-1.5 bg-slate-950/80 p-2.5 rounded border border-slate-800 text-[10px]">
                <div className="flex justify-between">
                  <span className="text-slate-400">Free Space Loss (FSPL):</span>
                  <span className="text-slate-200">{budget.fspl_db} dB</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Tx Power (EIRP):</span>
                  <span className="text-slate-200">{budget.eirp_dbm} dBm</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Rx Signal (Prx):</span>
                  <span className="text-slate-200">{budget.rx_power_dbm} dBm</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Rx Sensitivity:</span>
                  <span className="text-slate-400">{budget.rx_sensitivity_dbm} dBm</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Thermal Noise:</span>
                  <span className="text-slate-500">{budget.thermal_noise_dbm} dBm</span>
                </div>
                <div className="h-px bg-slate-800 my-1" />
                <div className="flex justify-between items-center text-[11px] font-bold">
                  <span className="text-slate-300">Link Margin:</span>
                  <span style={{ color: budget.status_color }}>
                    {budget.link_margin_db > 0 ? `+${budget.link_margin_db}` : budget.link_margin_db} dB
                  </span>
                </div>
                <div className="text-[9px] text-slate-400 italic mt-1">{budget.status_desc}</div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
