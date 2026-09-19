import { Loader2, Zap } from 'lucide-react'
import type { SampleBoardInfo } from '../../types/samples'

interface Props {
  samples: SampleBoardInfo[]
  activeSampleId: string | null
  loading: boolean
  onSelect: (sampleId: string) => void
}

const FALLBACK_ORDER = ['small', 'medium', 'large']
const SHORT_LABEL: Record<string, string> = { small: 'Small', medium: 'Medium', large: 'Large' }

/** Compact segmented control for switching between the bundled sample
 * boards (small/medium/large), used to stress-test the canvas, violation
 * list, and diagnosis taxonomy coverage at different board scales. Samples
 * that haven't been analyzed yet in this server process show a bolt icon as
 * a hint that selecting them triggers a fresh (slower) live LLM diagnosis
 * run rather than an instant cached one. */
export default function SampleSwitcher({ samples, activeSampleId, loading, onSelect }: Props) {
  const ordered = [...samples].sort((a, b) => FALLBACK_ORDER.indexOf(a.id) - FALLBACK_ORDER.indexOf(b.id))
  if (ordered.length === 0) return null

  return (
    <div
      className="inline-flex items-center gap-0.5 rounded-lg border border-board-600 bg-board-900/60 p-0.5"
      role="group"
      aria-label="Sample board switcher"
    >
      {ordered.map((sample) => {
        const isActive = activeSampleId === sample.id
        const isPending = isActive && loading
        return (
          <button
            key={sample.id}
            onClick={() => onSelect(sample.id)}
            disabled={loading}
            title={`${sample.name} — ${sample.description}${sample.cached ? '' : ' (first run analyzes live, ~1-4 min)'}`}
            aria-pressed={isActive}
            aria-label={`${sample.name}${sample.cached ? '' : ' (not yet analyzed)'}`}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors disabled:cursor-wait ${
              isActive ? 'bg-copper-500/20 text-copper-400' : 'text-slate-400 hover:bg-board-800 hover:text-slate-200'
            }`}
          >
            {isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              !sample.cached && <Zap className="h-3 w-3 opacity-60" aria-hidden="true" />
            )}
            {SHORT_LABEL[sample.id] ?? sample.name}
          </button>
        )
      })}
    </div>
  )
}
