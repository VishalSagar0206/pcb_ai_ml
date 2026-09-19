import { type ComponentType } from 'react'
import { CircuitBoard, LayoutDashboard, FlaskConical, BookOpen, Database } from 'lucide-react'

export type TabId = 'board' | 'pipeline' | 'knowledge' | 'evaluation' | 'research'

interface Props {
  active: TabId
  onChange: (tab: TabId) => void
}

const TABS: { id: TabId; label: string; icon: ComponentType<{ className?: string }> }[] = [
  { id: 'board', label: 'Board Explorer', icon: CircuitBoard },
  { id: 'pipeline', label: 'Pipeline Architecture', icon: LayoutDashboard },
  { id: 'knowledge', label: 'Knowledge Base', icon: Database },
  { id: 'evaluation', label: 'Evaluation', icon: FlaskConical },
  { id: 'research', label: 'Research Lineage', icon: BookOpen },
]

export default function AppHeader({ active, onChange }: Props) {
  return (
    <header className="mb-4 flex flex-col gap-3 border-b border-board-700 pb-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-teal-glow/20 to-cyan-glow/10 text-teal-glow">
            <CircuitBoard className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold leading-tight text-slate-50">
              PCB DRC <span className="text-gradient-copper">Intelligence</span>
            </h1>
            <p className="text-[11px] text-slate-500">
              Evidence-grounded LLM diagnosis of deterministic PCB design-rule violations
            </p>
          </div>
        </div>
        <span className="hidden rounded-full border border-teal-glow/30 bg-teal-glow/10 px-3 py-1 text-[11px] text-teal-glow sm:block">
          Deterministic DRC · Structured PCB context · Engineering RAG · Evidence-validated LLM
        </span>
      </div>

      <nav className="flex gap-1.5 overflow-x-auto" role="tablist" aria-label="Main sections">
        {TABS.map((tab) => {
          const Icon = tab.icon
          const isActive = active === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => onChange(tab.id)}
              role="tab"
              aria-selected={isActive}
              aria-label={tab.label}
              className={`flex shrink-0 items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-teal-glow/15 text-teal-glow'
                  : 'text-slate-400 hover:bg-board-800 hover:text-slate-200'
              }`}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {tab.label}
            </button>
          )
        })}
      </nav>
    </header>
  )
}
