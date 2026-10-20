import React, { useState, useEffect } from 'react'
import {
  HelpCircle,
  Search,
  BookOpen,
  Layers,
  Shield,
  Radio,
  Cpu,
  Activity,
  AlertTriangle,
  X,
  ExternalLink,
  ChevronRight,
  Info,
} from 'lucide-react'
import { api } from '../../services/api'
import { GlossaryItem, HelpDocumentation } from '../../types'

interface HelpCenterModalProps {
  isOpen: boolean
  onClose: () => void
  onStartTour: (mode: 'beginner' | 'experiment') => void
}

export const HelpCenterModal: React.FC<HelpCenterModalProps> = ({
  isOpen,
  onClose,
  onStartTour,
}) => {
  const [activeTab, setActiveTab] = useState<'glossary' | 'guides' | 'faq'>('glossary')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [glossary, setGlossary] = useState<Record<string, GlossaryItem>>({})
  const [helpDocs, setHelpDocs] = useState<HelpDocumentation | null>(null)
  const [loading, setLoading] = useState<boolean>(true)

  useEffect(() => {
    if (!isOpen) return
    Promise.all([
      api.getGlossary().catch(() => ({})),
      api.getHelpDocumentation().catch(() => null),
    ]).then(([glossRes, docsRes]) => {
      setGlossary(glossRes)
      if (docsRes) setHelpDocs(docsRes)
      setLoading(false)
    })
  }, [isOpen])

  if (!isOpen) return null

  // Filter glossary
  const filteredGlossary = Object.values(glossary).filter((item) => {
    const q = searchQuery.toLowerCase()
    return (
      item.term.toLowerCase().includes(q) ||
      item.category.toLowerCase().includes(q) ||
      item.definition.toLowerCase().includes(q)
    )
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-4xl max-h-[85vh] bg-zinc-950 border border-zinc-800 rounded-2xl shadow-2xl flex flex-col overflow-hidden text-zinc-100 font-sans animate-in fade-in zoom-in-95 duration-200">
        {/* Top Header */}
        <div className="p-4 sm:p-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/80">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-bold font-mono tracking-wide text-zinc-100">
                  ASTRA Help Centre &amp; Technical Documentation
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-700/60 text-emerald-400">
                  v4.2 Reference
                </span>
              </div>
              <p className="text-xs text-zinc-400 font-sans">
                Searchable communications engineering glossary, signal analysis guides, and hardware safety standards
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Tabs & Search Bar */}
        <div className="border-b border-zinc-800 px-5 py-3 bg-zinc-900/40 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center space-x-2 text-xs font-mono">
            <button
              onClick={() => setActiveTab('glossary')}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === 'glossary'
                  ? 'bg-zinc-800 text-emerald-400 font-bold border border-zinc-700'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Searchable Glossary
            </button>
            <button
              onClick={() => setActiveTab('guides')}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === 'guides'
                  ? 'bg-zinc-800 text-emerald-400 font-bold border border-zinc-700'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Signal Guides &amp; Pipeline
            </button>
            <button
              onClick={() => setActiveTab('faq')}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === 'faq'
                  ? 'bg-zinc-800 text-emerald-400 font-bold border border-zinc-700'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Hardware Safety &amp; FAQ
            </button>
          </div>

          {activeTab === 'glossary' && (
            <div className="relative w-full sm:w-64 text-xs font-mono">
              <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Search AES, SNR, FFT, BER..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg pl-8 pr-3 py-1.5 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-500"
              />
            </div>
          )}
        </div>

        {/* Content Viewport */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* TAB 1: Searchable Glossary */}
          {activeTab === 'glossary' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs font-mono text-zinc-400 pb-2 border-b border-zinc-850">
                <span>Displaying {filteredGlossary.length} technical terminology entries</span>
                <span className="text-[10px] text-emerald-400">IEEE &amp; NIST Aligned</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {filteredGlossary.map((item, idx) => (
                  <div
                    key={idx}
                    className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2 hover:border-zinc-700 transition-colors font-mono text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <h4 className="font-bold text-zinc-100 text-sm text-emerald-300">
                        {item.term}
                      </h4>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                        {item.category}
                      </span>
                    </div>
                    <p className="text-zinc-300 font-sans text-xs leading-relaxed">
                      {item.definition}
                    </p>
                    <div className="pt-2 border-t border-zinc-850 text-[11px] text-zinc-400">
                      <strong className="text-zinc-400">Project Role:</strong> {item.relevance}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 2: Guides & Pipeline Documentation */}
          {activeTab === 'guides' && (
            <div className="space-y-6">
              {/* Getting Started Guide */}
              <div className="bg-zinc-900/60 border border-zinc-800 p-5 rounded-xl space-y-3">
                <h3 className="text-sm font-bold font-mono text-emerald-400 uppercase tracking-wider flex items-center space-x-2">
                  <Shield className="w-4 h-4" />
                  <span>{helpDocs?.getting_started?.title || 'Getting Started with ASTRA'}</span>
                </h3>
                <div className="space-y-3 text-xs leading-relaxed text-zinc-300 font-sans">
                  {(helpDocs?.getting_started?.sections || []).map((sec, idx) => (
                    <div key={idx} className="space-y-1">
                      <h4 className="font-bold font-mono text-zinc-100">{sec.heading}</h4>
                      <p className="text-zinc-300">{sec.content}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* 14-Stage Pipeline Breakdown */}
              <div className="bg-zinc-900/60 border border-zinc-800 p-5 rounded-xl space-y-3">
                <h3 className="text-sm font-bold font-mono text-cyan-400 uppercase tracking-wider flex items-center space-x-2">
                  <Layers className="w-4 h-4" />
                  <span>{helpDocs?.communication_pipeline?.title || '14-Stage Communication & DSP Pipeline'}</span>
                </h3>
                <div className="space-y-3 text-xs leading-relaxed text-zinc-300 font-sans">
                  {(helpDocs?.communication_pipeline?.sections || []).map((sec, idx) => (
                    <div key={idx} className="space-y-1">
                      <h4 className="font-bold font-mono text-zinc-100">{sec.heading}</h4>
                      <p className="text-zinc-300 font-mono text-[11px] bg-zinc-950 p-2 rounded border border-zinc-850">
                        {sec.content}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Signal Visualisation Reading Guide */}
              <div className="bg-zinc-900/60 border border-zinc-800 p-5 rounded-xl space-y-3">
                <h3 className="text-sm font-bold font-mono text-purple-400 uppercase tracking-wider flex items-center space-x-2">
                  <Activity className="w-4 h-4" />
                  <span>{helpDocs?.signal_visualisations?.title || 'Interpreting Signal Visualisations'}</span>
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs leading-relaxed text-zinc-300 font-sans">
                  {(helpDocs?.signal_visualisations?.sections || []).map((sec, idx) => (
                    <div key={idx} className="bg-zinc-950 p-3 rounded-lg border border-zinc-850 space-y-1">
                      <h4 className="font-bold font-mono text-purple-300">{sec.heading}</h4>
                      <p className="text-zinc-400 text-[11px]">{sec.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: FAQ & Hardware Safety */}
          {activeTab === 'faq' && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-800/60 text-amber-200 text-xs font-mono space-y-1">
                <div className="font-bold flex items-center space-x-2 text-amber-400">
                  <AlertTriangle className="w-4 h-4" />
                  <span>Hardware Safety &amp; RF Transmission Governance</span>
                </div>
                <p className="font-sans text-zinc-300 text-[11px]">
                  Physical RF transmission on ISM Channel 14 (2.484 GHz) requires explicit confirmation to protect co-channel devices.
                  If no USRP B205mini is connected, physical RF transmission is locked out and the workstation operates in verified simulation loopback.
                </p>
              </div>

              <div className="space-y-3">
                {(helpDocs?.diagnostics_faq?.faqs || []).map((faq, idx) => (
                  <div key={idx} className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-1.5 font-mono text-xs">
                    <h4 className="font-bold text-zinc-100 flex items-center space-x-2">
                      <span className="text-emerald-400">Q:</span>
                      <span>{faq.q}</span>
                    </h4>
                    <p className="text-zinc-300 font-sans text-xs pl-5 leading-relaxed">
                      {faq.a}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer Quick Launch Tour Actions */}
        <div className="p-4 border-t border-zinc-800 bg-zinc-900/80 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs font-mono">
          <div className="text-zinc-400 flex items-center space-x-2">
            <Info className="w-3.5 h-3.5 text-zinc-400" />
            <span>Need hands-on orientation? Launch an interactive walkthrough:</span>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => {
                onClose()
                onStartTour('beginner')
              }}
              className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition-colors"
            >
              Beginner Tour
            </button>
            <button
              onClick={() => {
                onClose()
                onStartTour('experiment')
              }}
              className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition-colors shadow-sm"
            >
              Guided Experiment
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
