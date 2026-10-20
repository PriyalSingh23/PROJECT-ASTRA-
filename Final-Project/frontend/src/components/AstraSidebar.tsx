import React from 'react'
import {
  Activity,
  Layers,
  Radio,
  MessageSquare,
  Cpu,
  Settings,
  Shield,
  Wifi,
} from 'lucide-react'

export type AstraTab =
  | 'overview'
  | 'spectrum'
  | 'waveform'
  | 'topology'
  | 'messages'
  | 'research'
  | 'hardware'
  | 'settings'

interface AstraSidebarProps {
  activeTab: AstraTab
  setActiveTab: (tab: AstraTab) => void
  isNightMode: boolean
  setIsNightMode: (val: boolean) => void
  isBackendHealthy: boolean
}

export function AstraSidebar({
  activeTab,
  setActiveTab,
  isNightMode,
  setIsNightMode,
  isBackendHealthy,
}: AstraSidebarProps) {
  const navItems = [
    {
      id: 'overview' as AstraTab,
      label: 'Overview',
      icon: Layers,
      badge: null,
    },
    {
      id: 'topology' as AstraTab,
      label: '3D Tactical Mesh',
      icon: Wifi,
      badge: '3D',
    },
    {
      id: 'messages' as AstraTab,
      label: 'Secure Messaging',
      icon: MessageSquare,
      badge: 'PQC',
    },
    {
      id: 'waveform' as AstraTab,
      label: 'Waveform & LPI',
      icon: Activity,
      badge: 'LPI',
    },
    {
      id: 'spectrum' as AstraTab,
      label: 'Spectrum & Waterfall',
      icon: Radio,
      badge: 'LIVE',
    },
    {
      id: 'research' as AstraTab,
      label: 'Research & CGAN',
      icon: Cpu,
      badge: 'MPS',
    },
    {
      id: 'hardware' as AstraTab,
      label: 'RF Hardware & SDR',
      icon: Shield,
      badge: null,
    },
    {
      id: 'settings' as AstraTab,
      label: 'Settings & Export',
      icon: Settings,
      badge: null,
    },
  ]

  return (
    <aside className="w-[245px] h-screen sticky top-0 flex flex-col justify-between p-4 border-r border-[var(--line)] bg-[var(--bg)] select-none">
      {/* Top: Logo & Brand */}
      <div className="space-y-4">
        {/* Institute Brand Header — Natural Shield Insignia (No circular frame) */}
        <div className="flex items-center gap-3 px-2 py-1">
          <img
            src="/astra_logo.jpg"
            alt="ASTRA Institute Insignia"
            className="h-12 w-auto object-contain filter drop-shadow-md select-none transition-transform duration-200 hover:scale-105"
          />
          <div>
            <div className="text-xl font-black tracking-widest leading-none text-[var(--ink)]">
              ASTRA
            </div>
            <div className="text-[9px] font-extrabold tracking-widest text-[var(--muted)] uppercase mt-1">
              Signal Intelligence
            </div>
          </div>
        </div>

        {/* Operational Workspace Status Chip */}
        <div className="neo-inset p-3 rounded-2xl flex items-center gap-2.5">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              isBackendHealthy
                ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]'
                : 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]'
            }`}
          />
          <div className="min-w-0">
            <div className="text-xs font-bold leading-tight truncate">
              Station Alpha (Local)
            </div>
            <div className="text-[10px] text-[var(--muted)] truncate">
              {isBackendHealthy ? 'Online · Port 5051' : 'Daemon Offline'}
            </div>
          </div>
        </div>

        {/* Navigation Item List */}
        <div className="space-y-1 pt-1">
          <div className="text-[10px] font-extrabold uppercase tracking-widest text-[var(--subtle)] px-3 mb-2">
            Workspaces
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = activeTab === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`neo-tab ${isActive ? 'active' : ''}`}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span className="flex-1 truncate">{item.label}</span>
                  {item.badge && (
                    <span className="text-[9px] font-extrabold px-1.5 py-0.5 rounded-md bg-[var(--line)] text-[var(--muted)]">
                      {item.badge}
                    </span>
                  )}
                </button>
              )
            })}
          </nav>
        </div>
      </div>

      {/* Bottom: Operator Profile & Security Tier */}
      <div className="space-y-3 pt-3 border-t border-[var(--line)]">
        <div className="flex items-center gap-3 px-2 py-2 rounded-xl neo-inset">
          <div className="w-8 h-8 rounded-lg bg-[var(--surface-raised)] flex items-center justify-center font-black text-xs text-[var(--accent)] shadow-sm">
            OP
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-bold truncate text-[var(--ink)]">ASTRA Operator</div>
            <div className="text-[10px] text-[var(--muted)] truncate flex items-center gap-1 font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
              <span>PQC Tier 1 Field</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}
