import { motion } from 'framer-motion'
import PipelineDiagram from '../pipeline/PipelineDiagram'
import { Layers, ShieldCheck } from 'lucide-react'

export default function PipelinePage() {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-6">
      <div className="glass-panel rounded-xl p-5">
        <div className="flex items-center gap-2">
          <Layers className="h-5 w-5 text-teal-glow" />
          <h3 className="text-lg font-semibold text-slate-100">Evidence Hierarchy</h3>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-5">
          {[
            { level: 'L1', label: 'Deterministic truth', detail: 'KiCad DRC', color: '#4fd8ff' },
            { level: 'L2', label: 'Structured facts', detail: 'PCB JSON / graph', color: '#35e6c3' },
            { level: 'L3', label: 'External knowledge', detail: 'Datasheets / guidelines', color: '#ffd23d' },
            { level: 'L4', label: 'LLM reasoning', detail: 'Interpretation / diagnosis', color: '#ff8a3d' },
            { level: 'L5', label: 'Human approval', detail: 'Final engineering decision', color: '#9aa8c7' },
          ].map((l, i) => (
            <motion.div
              key={l.level}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              className="rounded-lg border border-board-600 bg-board-800/50 p-3 text-center"
            >
              <div className="mx-auto mb-1.5 flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-bold" style={{ backgroundColor: `${l.color}22`, color: l.color }}>
                {l.level}
              </div>
              <p className="text-xs font-semibold text-slate-200">{l.label}</p>
              <p className="mt-0.5 text-[10px] text-slate-500">{l.detail}</p>
            </motion.div>
          ))}
        </div>
        <p className="mt-3 text-xs text-slate-500">
          The LLM sits at Level 4: an evidence-grounded reasoning layer, never the source of truth. It cannot detect
          violations, invent PCB facts, or apply any change to the design.
        </p>
      </div>

      <div className="glass-panel rounded-xl p-5">
        <div className="mb-4 flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-cyan-glow" />
          <h3 className="text-lg font-semibold text-slate-100">Pipeline Stages</h3>
        </div>
        <PipelineDiagram />
      </div>
    </motion.div>
  )
}
