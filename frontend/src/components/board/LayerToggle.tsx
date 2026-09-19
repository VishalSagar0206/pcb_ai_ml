import { Layers, ArrowUpToLine, ArrowDownToLine, Square } from 'lucide-react'

export type ViewMode = 'all' | 'F.Cu' | 'B.Cu' | 'Edge.Cuts'

interface Props {
  active: ViewMode
  onChange: (mode: ViewMode) => void
}

const MODES: { id: ViewMode; label: string; icon: typeof Layers }[] = [
  { id: 'all', label: 'All Layers', icon: Layers },
  { id: 'F.Cu', label: 'Top', icon: ArrowUpToLine },
  { id: 'B.Cu', label: 'Bottom', icon: ArrowDownToLine },
  { id: 'Edge.Cuts', label: 'Outline', icon: Square },
]

/** Compact, fixed 4-mode view selector matching what PCBCanvas actually
 * renders differently (copper/components split by side, or outline-only)
 * -- replaces a prior design that dumped every KiCad layer name (including
 * Paste/Mask/Adhesive layers with no distinct visual rendering) into a
 * wrapping row of a dozen buttons, which was cluttered and mostly
 * non-functional. */
export default function LayerToggle({ active, onChange }: Props) {
  return (
    <div
      className="inline-flex items-center gap-0.5 rounded-lg border border-board-600 bg-board-900/60 p-0.5"
      role="group"
      aria-label="Layer view mode"
    >
      {MODES.map((mode) => {
        const Icon = mode.icon
        const isActive = active === mode.id
        return (
          <button
            key={mode.id}
            onClick={() => onChange(mode.id)}
            aria-pressed={isActive}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
              isActive ? 'bg-teal-glow/15 text-teal-glow' : 'text-slate-400 hover:bg-board-800 hover:text-slate-200'
            }`}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            {mode.label}
          </button>
        )
      })}
    </div>
  )
}
