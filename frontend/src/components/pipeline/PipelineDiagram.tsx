import { useState, type ComponentType } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ShieldCheck,
  Network,
  BookMarked,
  BrainCircuit,
  ShieldAlert,
  FileText,
  CircuitBoard,
} from 'lucide-react'

interface Stage {
  id: string
  icon: ComponentType<{ className?: string }>
  title: string
  subtitle: string
  detail: string
  phase: string
  deterministic: boolean
}

const STAGES: Stage[] = [
  {
    id: 'parser',
    icon: CircuitBoard,
    title: 'PCB Parser',
    subtitle: '.kicad_pcb → structured JSON',
    detail:
      'Parses the KiCad S-expression file into a versioned, hierarchical PCB JSON schema (components, pads, nets, tracks, vias, zones, rules) preserving KiCad object uuids and absolute board coordinates.',
    phase: 'Phase 1',
    deterministic: true,
  },
  {
    id: 'drc',
    icon: ShieldCheck,
    title: 'Deterministic DRC',
    subtitle: 'kicad-cli pcb drc',
    detail:
      'The ONLY source of truth for violations. Runs (or loads a recorded fixture of) KiCad\'s own DRC engine, preserving raw evidence verbatim. The LLM never detects violations here — it only interprets what this stage found.',
    phase: 'Phase 2/3',
    deterministic: true,
  },
  {
    id: 'context',
    icon: Network,
    title: 'Context Retriever',
    subtitle: 'minimal per-violation PCB context',
    detail:
      'Deterministically resolves each violation to the exact components/pads/nets/tracks/vias/zones/rules involved — never the whole board — via a KiCad-uuid-indexed relationship graph.',
    phase: 'Phase 4/5',
    deterministic: true,
  },
  {
    id: 'rag',
    icon: BookMarked,
    title: 'Engineering RAG',
    subtitle: 'datasheets + design guidelines',
    detail:
      'Hybrid retrieval (metadata filtering + BM25 + TF-IDF) over ingested datasheets and design-guideline documents, chunked with page/section provenance preserved per chunk.',
    phase: 'Phase 6/7',
    deterministic: true,
  },
  {
    id: 'llm',
    icon: BrainCircuit,
    title: 'LLM Reasoning Agent',
    subtitle: 'evidence-constrained diagnosis',
    detail:
      'One constrained, JSON-mode call synthesizes root cause, engineering impact, and remediation — reasoning ONLY over the evidence assembled above. Must say "insufficient_evidence" rather than invent facts.',
    phase: 'Phase 8/9/11',
    deterministic: false,
  },
  {
    id: 'validation',
    icon: ShieldAlert,
    title: 'Evidence Validator',
    subtitle: 'catches hallucinated citations',
    detail:
      'Checks every referenced component/pad/net actually exists, every numeric claim matches DRC evidence, and every citation resolves to a real supplied source. Failures reduce confidence and force human review.',
    phase: 'Phase 12/13',
    deterministic: true,
  },
  {
    id: 'report',
    icon: FileText,
    title: 'Engineering Report',
    subtitle: 'human-readable + API/UI',
    detail:
      'Generates a structured engineering report (board summary, violation-by-violation analysis, recurring root causes, uncertain findings, recommended actions) from the validated diagnoses.',
    phase: 'Phase 14/15',
    deterministic: true,
  },
]

export default function PipelineDiagram() {
  const [activeId, setActiveId] = useState<string | null>(null)
  const active = STAGES.find((s) => s.id === activeId)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-stretch gap-1">
        {STAGES.map((stage, i) => {
          const Icon = stage.icon
          const isActive = activeId === stage.id
          return (
            <div key={stage.id} className="flex items-center">
              <motion.button
                onMouseEnter={() => setActiveId(stage.id)}
                onFocus={() => setActiveId(stage.id)}
                whileHover={{ scale: 1.04 }}
                className={`flex w-36 flex-col items-center gap-2 rounded-xl border px-3 py-4 text-center transition-colors ${
                  isActive
                    ? 'border-teal-glow/70 bg-teal-glow/10 glow-teal'
                    : 'border-board-600 bg-board-800/50 hover:border-board-500'
                }`}
              >
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-full ${
                    stage.deterministic ? 'bg-cyan-glow/15 text-cyan-glow' : 'bg-copper-500/15 text-copper-400'
                  }`}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <span className="text-xs font-semibold text-slate-100">{stage.title}</span>
                <span className="text-[10px] text-slate-500">{stage.phase}</span>
              </motion.button>
              {i < STAGES.length - 1 && (
                <motion.div
                  className="mx-1 h-0.5 w-4 shrink-0 rounded bg-gradient-to-r from-board-500 to-teal-glow/40"
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  transition={{ delay: i * 0.08, duration: 0.4 }}
                  style={{ transformOrigin: 'left' }}
                />
              )}
            </div>
          )
        })}
      </div>

      <div className="flex gap-4 text-[10px] text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-cyan-glow" /> Deterministic (never fabricates)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-copper-400" /> LLM reasoning (evidence-constrained)
        </span>
      </div>

      <AnimatePresence mode="wait">
        {active && (
          <motion.div
            key={active.id}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            className="glass-panel rounded-xl p-4"
          >
            <div className="flex items-center gap-2">
              <h4 className="font-semibold text-slate-100">{active.title}</h4>
              <span className="rounded bg-board-700 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
                {active.subtitle}
              </span>
            </div>
            <p className="mt-1.5 text-sm text-slate-400">{active.detail}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
