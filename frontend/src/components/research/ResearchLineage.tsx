import { useEffect, useState, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { Loader2, GitBranch, HelpCircle, Cpu, Waypoints } from 'lucide-react'
import { api } from '../../api/client'
import type { PCBQAReferenceResponse } from '../../types/evaluation'

function PositionCard({ icon, title, body }: { icon: ReactNode; title: string; body: string }) {
  return (
    <div className="rounded-lg border border-board-600 bg-board-800/40 p-3">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-cyan-glow">
        {icon}
        {title}
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-slate-400">{body}</p>
    </div>
  )
}

function Stat({ label, value }: { label: string; value?: number }) {
  if (value == null) return null
  return (
    <span className="rounded bg-board-700 px-2 py-1 text-slate-300">
      <span className="font-mono font-semibold text-slate-100">{value}</span> {label}
    </span>
  )
}

export default function ResearchLineage() {
  const [data, setData] = useState<PCBQAReferenceResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getPcbQaReference()
      .then(setData)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="flex flex-col gap-6">
      <div className="glass-panel rounded-xl p-5">
        <div className="flex items-center gap-2">
          <GitBranch className="h-5 w-5 text-copper-400" />
          <h3 className="text-lg font-semibold text-slate-100">Research Positioning</h3>
        </div>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-400">
          <span className="font-semibold text-copper-400">PCB-QA</span> demonstrated that structured, information-dense
          JSON representations of KiCad designs substantially improve LLM interpretation compared with raw netlist/file
          representations, evaluated via passive question-answering over static circuit facts. This project extends that
          paradigm from <span className="text-slate-200">passive PCB question answering</span> to{' '}
          <span className="text-slate-200">active interpretation of deterministic design-rule violations</span> — the
          deterministic KiCad DRC engine remains the sole source of truth for what is wrong with a board; the LLM performs
          only evidence-grounded interpretation, root-cause reasoning, and remediation recommendation on top of it.
        </p>
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <PositionCard
            icon={<HelpCircle className="h-4 w-4" />}
            title="PCB-QA paradigm"
            body="Structured circuit JSON → LLM answers static factual questions about the design (component specs, connectivity, SPICE behaviour)."
          />
          <PositionCard
            icon={<Waypoints className="h-4 w-4" />}
            title="This system's extension"
            body="Deterministic DRC violation → structured PCB context + engineering RAG → LLM diagnoses root cause, impact & fix — never detects violations itself."
          />
          <PositionCard
            icon={<Cpu className="h-4 w-4" />}
            title="Shared foundation"
            body="Both rely on converting KiCad designs into hierarchical, information-dense JSON instead of flooding the LLM with raw file text."
          />
        </div>
      </div>

      <div className="glass-panel rounded-xl p-5">
        <h3 className="mb-3 text-lg font-semibold text-slate-100">Reference Benchmark: pcb_qa-4FEE</h3>
        {loading ? (
          <div className="flex items-center gap-2 py-8 text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading reference dataset stats…
          </div>
        ) : !data?.available ? (
          <p className="text-sm text-slate-500">Reference repository not found in this environment.</p>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.projects.map((project, i) => (
              <motion.div
                key={project.project}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                className="rounded-lg border border-board-600 bg-board-800/50 p-3.5"
              >
                <h4 className="font-semibold text-slate-100">{project.project}</h4>
                <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                  <Stat label="components" value={project.component_count} />
                  <Stat label="nets" value={project.net_count} />
                  <Stat label="subcircuits" value={project.subcircuit_count} />
                  <Stat label="QA pairs" value={project.question_count} />
                </div>
                {project.sample_questions && project.sample_questions.length > 0 && (
                  <div className="mt-3 space-y-1.5 border-t border-board-700 pt-2.5">
                    {project.sample_questions.map((q, qi) => (
                      <div key={qi} className="text-xs text-slate-400">
                        <span className="rounded bg-board-700 px-1 py-0.5 text-[9px] text-slate-500">{q.category}</span>{' '}
                        <span className="italic">"{q.question}"</span>{' '}
                        <span className="font-semibold text-teal-glow">{q.answer}</span>
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        )}
        <p className="mt-4 text-[11px] text-slate-600">
          Read-only reference data from the bundled <code className="text-slate-500">pcb_qa-4FEE</code> benchmark
          repository (hierarchical schematic/netlist circuit JSON + 60 QA pairs per board). This data is display-only —
          it contains no physical layout/component-position information, so it is not fed into the DRC diagnosis
          pipeline itself.
        </p>
      </div>
    </div>
  )
}
