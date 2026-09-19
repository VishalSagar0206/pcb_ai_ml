import { useEffect, useState, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts'
import { Loader2, FlaskConical, AlertTriangle } from 'lucide-react'
import { api } from '../../api/client'
import type { EvalSummaryResponse } from '../../types/evaluation'

const CONDITION_LABEL: Record<string, string> = {
  drc_only: 'DRC only',
  raw_kicad: 'Raw KiCad file',
  pcb_json: 'Structured PCB JSON',
  full_pcb_json: 'Full PCB JSON',
  pcb_json_rag: 'PCB JSON + RAG',
}

const CONDITION_COLOR: Record<string, string> = {
  drc_only: '#9aa8c7',
  raw_kicad: '#ff8a3d',
  pcb_json: '#4fd8ff',
  full_pcb_json: '#f3924a',
  pcb_json_rag: '#35e6c3',
}

const CONDITION_ORDER = ['drc_only', 'raw_kicad', 'pcb_json', 'full_pcb_json', 'pcb_json_rag']

const METRIC_LABEL: Record<string, string> = {
  classification_accuracy: 'Accuracy',
  severity_agreement_rate: 'Severity agree.',
  evidence_grounding_rate: 'Grounding',
  human_review_agreement_rate: 'Review agree.',
}

const tooltipStyle = {
  background: '#0d1426',
  border: '1px solid #263454',
  borderRadius: 8,
  fontSize: 12,
  color: '#e7ecf7',
}

function round2(v: number): number {
  return Math.round(v * 100) / 100
}
function pct(v: number): string {
  return `${Math.round(v * 100)}%`
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="glass-panel rounded-xl p-4">
      <h4 className="mb-3 text-sm font-semibold text-slate-200">{title}</h4>
      {children}
    </div>
  )
}

export default function EvaluationDashboard() {
  const [data, setData] = useState<EvalSummaryResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getEvalSummary()
      .then(setData)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading evaluation results…
      </div>
    )
  }

  if (!data?.available) {
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center text-slate-500">
        <FlaskConical className="h-8 w-8 opacity-40" />
        <p className="max-w-md text-sm">
          No evaluation run found yet. Run{' '}
          <code className="rounded bg-board-800 px-1.5 py-0.5 text-copper-400">
            pcb-ai evaluate tests/fixtures/evaluation --out results
          </code>{' '}
          from the backend to populate this dashboard with real baseline/ablation metrics.
        </p>
      </div>
    )
  }

  const conditions = CONDITION_ORDER.filter((c) => data.conditions[c])
  const barData = conditions.map((c) => ({
    name: CONDITION_LABEL[c] ?? c,
    'Classification accuracy': round2(data.conditions[c].classification_accuracy),
    'Evidence grounding': round2(data.conditions[c].evidence_grounding_rate),
    'Hallucination rate': round2(data.conditions[c].hallucination_rate),
  }))

  const radarData = [
    'classification_accuracy',
    'severity_agreement_rate',
    'evidence_grounding_rate',
    'human_review_agreement_rate',
  ].map((metric) => {
    const entry: Record<string, string | number> = { metric: METRIC_LABEL[metric] ?? metric }
    for (const c of conditions) {
      entry[CONDITION_LABEL[c] ?? c] = round2((data.conditions[c] as unknown as Record<string, number>)[metric])
    }
    return entry
  })

  const tokenLatencyData = conditions.map((c) => ({
    name: CONDITION_LABEL[c] ?? c,
    Tokens: Math.round(data.conditions[c].mean_total_tokens),
  }))

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-6">
      <div className="rounded-lg border border-severity-medium/30 bg-severity-medium/5 p-3 text-xs text-severity-medium">
        <AlertTriangle className="mr-1.5 inline h-3.5 w-3.5" />
        Demonstration-scale evaluation (n={Object.values(data.conditions)[0]?.n ?? '?'} per condition, one synthetic
        board). Not a validated research-scale result — see EVALUATION.md for full scope and honest limitations.
      </div>

      <ChartCard title="Accuracy vs. evidence grounding vs. hallucination, by evidence condition">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={barData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1a2540" />
            <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} interval={0} angle={-12} textAnchor="end" height={60} />
            <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} domain={[0, 1]} />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
            <Bar dataKey="Classification accuracy" fill="#4fd8ff" radius={[3, 3, 0, 0]} />
            <Bar dataKey="Evidence grounding" fill="#35e6c3" radius={[3, 3, 0, 0]} />
            <Bar dataKey="Hallucination rate" fill="#ff3b5c" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ChartCard title="Multi-metric radar comparison">
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#1a2540" />
              <PolarAngleAxis dataKey="metric" tick={{ fill: '#94a3b8', fontSize: 10 }} />
              <PolarRadiusAxis domain={[0, 1]} tick={{ fill: '#4b5878', fontSize: 9 }} />
              {conditions.map((c) => (
                <Radar
                  key={c}
                  name={CONDITION_LABEL[c] ?? c}
                  dataKey={CONDITION_LABEL[c] ?? c}
                  stroke={CONDITION_COLOR[c]}
                  fill={CONDITION_COLOR[c]}
                  fillOpacity={0.12}
                />
              ))}
              <Legend wrapperStyle={{ fontSize: 10, color: '#94a3b8' }} />
              <Tooltip contentStyle={tooltipStyle} />
            </RadarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Token usage by condition">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={tokenLatencyData} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a2540" />
              <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis dataKey="name" type="category" tick={{ fill: '#94a3b8', fontSize: 11 }} width={110} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="Tokens" fill="#f3924a" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <ChartCard title="Per-condition summary">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-slate-500">
                <th className="px-2 py-1.5">Condition</th>
                <th className="px-2 py-1.5">n</th>
                <th className="px-2 py-1.5">Accuracy</th>
                <th className="px-2 py-1.5">Severity agree.</th>
                <th className="px-2 py-1.5">Grounding</th>
                <th className="px-2 py-1.5">Hallucination</th>
                <th className="px-2 py-1.5">Mean tokens</th>
                <th className="px-2 py-1.5">Mean latency</th>
              </tr>
            </thead>
            <tbody>
              {conditions.map((c) => {
                const m = data.conditions[c]
                return (
                  <tr key={c} className="border-t border-board-700 text-slate-300">
                    <td className="px-2 py-1.5 font-medium" style={{ color: CONDITION_COLOR[c] }}>
                      {CONDITION_LABEL[c] ?? c}
                    </td>
                    <td className="px-2 py-1.5">{m.n}</td>
                    <td className="px-2 py-1.5">{pct(m.classification_accuracy)}</td>
                    <td className="px-2 py-1.5">{pct(m.severity_agreement_rate)}</td>
                    <td className="px-2 py-1.5">{pct(m.evidence_grounding_rate)}</td>
                    <td className="px-2 py-1.5">{pct(m.hallucination_rate)}</td>
                    <td className="px-2 py-1.5">{Math.round(m.mean_total_tokens)}</td>
                    <td className="px-2 py-1.5">{m.mean_latency_ms ? `${(m.mean_latency_ms / 1000).toFixed(1)}s` : '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </ChartCard>
    </motion.div>
  )
}
