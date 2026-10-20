import React, { useState, useEffect } from 'react'
import {
  Compass,
  Play,
  RotateCcw,
  BookOpen,
  HelpCircle,
  Activity,
  CheckCircle2,
  Sparkles,
  ArrowRight,
  Shield,
  Radio,
} from 'lucide-react'
import { TourMode } from './GuidedTourModal'

interface GuidedDemoControlPanelProps {
  onStartTour: (mode: TourMode) => void
  onOpenHelp: () => void
  onViewDiagnostics: () => void
  onExploreManually: () => void
}

export const GuidedDemoControlPanel: React.FC<GuidedDemoControlPanelProps> = ({
  onStartTour,
  onOpenHelp,
  onViewDiagnostics,
  onExploreManually,
}) => {
  const [hasCompletedBeginner, setHasCompletedBeginner] = useState<boolean>(false)
  const [hasCompletedExperiment, setHasCompletedExperiment] = useState<boolean>(false)
  const [inProgressStep, setInProgressStep] = useState<number | null>(null)

  useEffect(() => {
    try {
      setHasCompletedBeginner(localStorage.getItem('astra_tour_beginner_completed') === 'true')
      setHasCompletedExperiment(localStorage.getItem('astra_tour_experiment_completed') === 'true')
      const step = localStorage.getItem('astra_tour_experiment_step')
      if (step && parseInt(step, 10) > 0) {
        setInProgressStep(parseInt(step, 10) + 1)
      }
    } catch {
      // ignore localStorage errors
    }
  }, [])

  const handleResetDemoState = () => {
    try {
      localStorage.removeItem('astra_tour_beginner_completed')
      localStorage.removeItem('astra_tour_experiment_completed')
      localStorage.removeItem('astra_tour_beginner_step')
      localStorage.removeItem('astra_tour_experiment_step')
      setHasCompletedBeginner(false)
      setHasCompletedExperiment(false)
      setInProgressStep(null)
    } catch {}
  }

  return (
    <div className="bg-gradient-to-r from-zinc-900/90 via-zinc-900/70 to-zinc-900/90 border border-emerald-500/40 rounded-2xl p-5 shadow-xl space-y-4 font-mono text-xs">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 border-b border-zinc-800/80 pb-3">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
            <Compass className="w-5 h-5 animate-spin-slow" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-bold font-mono tracking-wide text-zinc-100">
                Interactive Guided Orientation &amp; Communication Demo
              </h3>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800 font-bold">
                Operator Walkthrough
              </span>
            </div>
            <p className="text-xs text-zinc-400 font-sans mt-0.5">
              First-time researcher? Launch a step-by-step interactive experiment walkthrough with plain-language explanations.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={handleResetDemoState}
            className="px-2.5 py-1 rounded bg-zinc-950 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-zinc-800 transition-colors flex items-center space-x-1"
            title="Reset guided tour progress"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Reset Tour</span>
          </button>
        </div>
      </div>

      {/* Main Action Buttons Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Action 1: Guided Experiment */}
        <button
          onClick={() => onStartTour('experiment')}
          className="p-3.5 rounded-xl bg-gradient-to-br from-emerald-950/60 to-zinc-900 border border-emerald-500/40 hover:border-emerald-500/70 hover:from-emerald-900/40 text-left transition-all group flex flex-col justify-between space-y-2 shadow-sm"
        >
          <div className="flex items-center justify-between">
            <span className="w-7 h-7 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 group-hover:scale-105 transition-transform">
              <Play className="w-3.5 h-3.5 fill-emerald-400" />
            </span>
            {hasCompletedExperiment ? (
              <span className="text-[10px] text-emerald-400 flex items-center space-x-1">
                <CheckCircle2 className="w-3 h-3" />
                <span>Done</span>
              </span>
            ) : inProgressStep ? (
              <span className="text-[10px] text-cyan-400 font-bold">Step {inProgressStep} / 9</span>
            ) : null}
          </div>
          <div>
            <div className="font-bold text-zinc-100 flex items-center space-x-1">
              <span>{inProgressStep ? 'Continue Guided Demo' : 'Start Guided Demo'}</span>
              <ArrowRight className="w-3.5 h-3.5 text-emerald-400 group-hover:translate-x-1 transition-transform" />
            </div>
            <p className="text-[11px] text-zinc-400 font-sans mt-0.5">
              9-step end-to-end experiment: compose, synthesize, inject channel noise, and decode.
            </p>
          </div>
        </button>

        {/* Action 2: Beginner Tour */}
        <button
          onClick={() => onStartTour('beginner')}
          className="p-3.5 rounded-xl bg-zinc-900/70 border border-zinc-800 hover:border-zinc-700 hover:bg-zinc-850/80 text-left transition-all group flex flex-col justify-between space-y-2"
        >
          <div className="flex items-center justify-between">
            <span className="w-7 h-7 rounded-lg bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-400 group-hover:scale-105 transition-transform">
              <Sparkles className="w-3.5 h-3.5" />
            </span>
            {hasCompletedBeginner && (
              <span className="text-[10px] text-emerald-400 flex items-center space-x-1">
                <CheckCircle2 className="w-3 h-3" />
                <span>Done</span>
              </span>
            )}
          </div>
          <div>
            <div className="font-bold text-zinc-100 flex items-center space-x-1">
              <span>Beginner Tour</span>
              <ArrowRight className="w-3.5 h-3.5 text-cyan-400 group-hover:translate-x-1 transition-transform" />
            </div>
            <p className="text-[11px] text-zinc-400 font-sans mt-0.5">
              6-step orientation to workstation navigation, instruments, and operating modes.
            </p>
          </div>
        </button>

        {/* Action 3: Open Help Centre */}
        <button
          onClick={onOpenHelp}
          className="p-3.5 rounded-xl bg-zinc-900/70 border border-zinc-800 hover:border-zinc-700 hover:bg-zinc-850/80 text-left transition-all group flex flex-col justify-between space-y-2"
        >
          <div className="flex items-center justify-between">
            <span className="w-7 h-7 rounded-lg bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 group-hover:scale-105 transition-transform">
              <BookOpen className="w-3.5 h-3.5" />
            </span>
            <span className="text-[10px] text-purple-400">Glossary</span>
          </div>
          <div>
            <div className="font-bold text-zinc-100 flex items-center space-x-1">
              <span>Open Help Centre</span>
              <ArrowRight className="w-3.5 h-3.5 text-purple-400 group-hover:translate-x-1 transition-transform" />
            </div>
            <p className="text-[11px] text-zinc-400 font-sans mt-0.5">
              Searchable terminology (AES, CGAN, FFT, SNR, BER) and pipeline docs.
            </p>
          </div>
        </button>

        {/* Action 4: Explore Manually / View Diagnostics */}
        <button
          onClick={onExploreManually}
          className="p-3.5 rounded-xl bg-zinc-900/70 border border-zinc-800 hover:border-zinc-700 hover:bg-zinc-850/80 text-left transition-all group flex flex-col justify-between space-y-2"
        >
          <div className="flex items-center justify-between">
            <span className="w-7 h-7 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-300 group-hover:scale-105 transition-transform">
              <Activity className="w-3.5 h-3.5 text-zinc-300" />
            </span>
            <span className="text-[10px] text-zinc-400">Advanced</span>
          </div>
          <div>
            <div className="font-bold text-zinc-100 flex items-center space-x-1">
              <span>Explore Manually</span>
              <ArrowRight className="w-3.5 h-3.5 text-zinc-400 group-hover:translate-x-1 transition-transform" />
            </div>
            <p className="text-[11px] text-zinc-400 font-sans mt-0.5">
              Operate the engineering workstation directly without walkthrough overlays.
            </p>
          </div>
        </button>
      </div>
    </div>
  )
}
