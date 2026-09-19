import { motion } from 'framer-motion'
import type { DRCViolation } from '../../types/diagnosis'
import { ruleTypeLabel, severityColor } from '../../lib/format'

interface Props {
  violations: DRCViolation[]
  selectedId: string | null
  onSelect: (id: string) => void
  diagnosedIds: Set<string>
}

export default function ViolationList({ violations, selectedId, onSelect, diagnosedIds }: Props) {
  if (violations.length === 0) {
    return (
      <div className="p-4 text-sm text-slate-400">
        No DRC violations recorded for this board — clean board, or DRC hasn't been run.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1.5 overflow-y-auto p-2">
      {violations.map((v, idx) => {
        const color = severityColor(v.severity)
        const isSelected = v.violation_id === selectedId
        return (
          <motion.button
            key={v.violation_id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.04 }}
            onClick={() => onSelect(v.violation_id)}
            aria-pressed={isSelected}
            aria-label={`${v.severity} severity: ${ruleTypeLabel(v.rule_type)} -- ${v.message}`}
            className={`rounded-lg border px-3 py-2.5 text-left transition-all ${
              isSelected
                ? 'border-teal-glow/70 bg-teal-glow/10'
                : 'border-board-600 bg-board-800/50 hover:border-board-500 hover:bg-board-800'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span
                className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                style={{ color, backgroundColor: `${color}22` }}
              >
                {v.severity}
              </span>
              <span className="font-mono text-[11px] text-slate-500">{v.violation_id}</span>
            </div>
            <div className="mt-1.5 text-sm font-medium text-slate-100">{ruleTypeLabel(v.rule_type)}</div>
            <div className="mt-0.5 line-clamp-2 text-xs text-slate-400">{v.message}</div>
            <div className="mt-1.5 flex items-center gap-1.5">
              {v.items.slice(0, 3).map((item, i) => (
                <span key={i} className="rounded bg-board-700 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
                  {item.reference}
                  {item.pad ? `:${item.pad}` : ''}
                </span>
              ))}
              {diagnosedIds.has(v.violation_id) && (
                <span className="ml-auto rounded bg-teal-glow/15 px-1.5 py-0.5 text-[10px] text-teal-glow">
                  diagnosed
                </span>
              )}
            </div>
          </motion.button>
        )
      })}
    </div>
  )
}
