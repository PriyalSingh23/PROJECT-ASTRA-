import React from 'react'
import { TopologyModel } from './model'
import { DrawerStation } from '../MessageDrawer'

/**
 * Dependency-free 2D schematic used when WebGL is unavailable or the 3D scene
 * fails. Same information, no GPU requirement.
 */
export const TopologyFallback: React.FC<{
  model: TopologyModel
  onSelectStation?: (station: DrawerStation) => void
}> = ({ model, onSelectStation }) => {
  const { alpha, bravo, relays, link } = model
  const aX = 110
  const bX = 690
  const y = 150
  const relayXs = [300, 400, 500]

  return (
    <div className="w-full rounded-lg border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-2 text-[11px] font-mono uppercase tracking-widest text-amber-400">
        2D Fallback Schematic — WebGL unavailable
      </div>
      <svg viewBox="0 0 800 300" className="w-full h-[300px]">
        <defs>
          <pattern id="topoGrid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1f2937" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="800" height="300" fill="url(#topoGrid)" />

        {/* Link line */}
        <line
          x1={aX}
          y1={y}
          x2={bX}
          y2={y}
          stroke={link.color}
          strokeWidth={link.queued > 0 ? 4 : 2}
          strokeDasharray={link.online ? undefined : '8 8'}
          opacity={0.9}
        />

        {/* Relays */}
        {relays.map((r, i) => {
          const cx = relayXs[i] ?? 400
          return (
            <g key={r.id}>
              <polygon
                points={`${cx},${y - 16} ${cx + 16},${y} ${cx},${y + 16} ${cx - 16},${y}`}
                fill={r.online ? '#065f46' : '#3f3f46'}
                stroke={r.online ? '#34d399' : '#71717a'}
                strokeWidth="1.5"
              />
              <text x={cx} y={y + 36} textAnchor="middle" className="fill-zinc-400" fontSize="10" fontFamily="monospace">
                {r.label.slice(0, 14)}
              </text>
              <text x={cx} y={y + 48} textAnchor="middle" className="fill-zinc-500" fontSize="9" fontFamily="monospace">
                {r.battery}%
              </text>
            </g>
          )
        })}

        {/* Stations */}
        {[
          { x: aX, s: alpha },
          { x: bX, s: bravo },
        ].map(({ x, s }) => (
          <g
            key={s.id}
            onClick={onSelectStation ? () => onSelectStation({ id: s.id, label: s.label }) : undefined}
            style={onSelectStation ? { cursor: 'pointer' } : undefined}
          >
            <circle cx={x} cy={y} r="30" fill="#0f172a" stroke={link.color} strokeWidth="2" />
            <circle cx={x} cy={y} r="10" fill={link.color} />
            <text x={x} y={y - 44} textAnchor="middle" className="fill-zinc-200" fontSize="12" fontFamily="monospace">
              {s.label.slice(0, 18)}
            </text>
            <text x={x} y={y + 52} textAnchor="middle" className="fill-zinc-500" fontSize="10" fontFamily="monospace">
              {s.kind === 'alpha' ? `OUTBOX ${s.queued}` : `DELIVERED ${s.queued}`}
            </text>
          </g>
        ))}

        <text x="400" y="40" textAnchor="middle" className="fill-zinc-300" fontSize="12" fontFamily="monospace">
          {link.label} · {link.pending} in flight
        </text>
      </svg>
    </div>
  )
}
