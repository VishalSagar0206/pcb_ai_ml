import { motion, AnimatePresence } from 'framer-motion'
import type { ReactNode } from 'react'
import type { ViolationDetailResponse } from '../../types/diagnosis'
import { formatMs, formatPercent, ruleTypeLabel, severityColor } from '../../lib/format'
import {
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  Wrench,
  BookOpen,
  Gauge,
  Loader2,
} from 'lucide-react'

interface Props {
  detail: ViolationDetailResponse | null
  loading: boolean
}

const SOURCE_BADGE: Record<string, string> = {
  drc: 'bg-cyan-glow/15 text-cyan-glow border-cyan-glow/40',
  pcb: 'bg-teal-glow/15 text-teal-glow border-teal-glow/40',
  datasheet: 'bg-copper-400/15 text-copper-400 border-copper-400/40',
  engineering_document: 'bg-severity-low/15 text-severity-low border-severity-low/40',
}

export default function DiagnosisPanel({ detail, loading }: Props) {
  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-slate-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading diagnosis…
      </div>
    )
  }

  if (!detail) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center text-slate-500">
        <AlertTriangle className="h-8 w-8 opacity-40" />
        <p className="text-sm">Select a violation marker on the board, or from the list, to see its full evidence-grounded diagnosis.</p>
      </div>
    )
  }

  const { violation, diagnosis, trace } = detail
  const color = severityColor(violation.severity)

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={violation.violation_id}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0 }}
        className="flex h-full flex-col gap-4 overflow-y-auto p-4"
      >
        {/* Header */}
        <div>
          <div className="flex items-center gap-2">
            <span
              className="rounded px-2 py-0.5 text-xs font-bold uppercase tracking-wide"
              style={{ color, backgroundColor: `${color}22` }}
            >
              {violation.severity}
            </span>
            <span className="font-mono text-xs text-slate-500">{violation.violation_id}</span>
          </div>
          <h3 className="mt-2 text-lg font-semibold text-slate-100">{ruleTypeLabel(violation.rule_type)}</h3>
          <p className="mt-1 text-sm text-slate-400">{violation.message}</p>
          {(violation.required_value != null || violation.actual_value != null) && (
            <div className="mt-2 flex gap-4 text-xs">
              <span className="text-slate-400">
                Required: <span className="font-mono text-slate-200">{violation.required_value ?? '—'} {violation.unit}</span>
              </span>
              <span className="text-slate-400">
                Actual: <span className="font-mono text-copper-400">{violation.actual_value ?? '—'} {violation.unit}</span>
              </span>
            </div>
          )}
        </div>

        {!diagnosis ? (
          <div className="rounded-lg border border-board-600 bg-board-800/60 p-4 text-sm text-slate-400">
            No LLM diagnosis has been generated yet for this violation.
          </div>
        ) : (
          <>
            {diagnosis.insufficient_evidence && (
              <div className="flex items-center gap-2 rounded-lg border border-severity-critical/40 bg-severity-critical/10 p-3 text-sm text-severity-critical">
                <ShieldAlert className="h-4 w-4 shrink-0" />
                Insufficient evidence — the LLM reasoning stage failed or returned an invalid response. This
                diagnosis was not fabricated; see uncertainty notes below.
              </div>
            )}

            {/* Summary */}
            <Section icon={<AlertTriangle className="h-4 w-4" />} title="What happened">
              <p className="text-sm text-slate-300">{diagnosis.summary}</p>
            </Section>

            {/* Root cause */}
            <Section icon={<Gauge className="h-4 w-4" />} title="Root cause" confidence={diagnosis.root_cause.confidence}>
              <p className="text-sm text-slate-300">{diagnosis.root_cause.explanation}</p>
            </Section>

            {/* Engineering impact */}
            <Section icon={<ShieldAlert className="h-4 w-4" />} title="Engineering impact">
              <p className="text-sm text-slate-300">{diagnosis.engineering_impact.description}</p>
              {diagnosis.engineering_impact.potential_effects.length > 0 && (
                <ul className="mt-1.5 space-y-1 text-xs text-slate-400">
                  {diagnosis.engineering_impact.potential_effects.map((effect, i) => (
                    <li key={i} className="flex gap-1.5">
                      <span className="text-severity-high">▸</span> {effect}
                    </li>
                  ))}
                </ul>
              )}
            </Section>

            {/* Recommended fix */}
            <Section icon={<Wrench className="h-4 w-4" />} title="Recommended fix">
              <p className="text-sm text-slate-300">{diagnosis.recommended_fix.description}</p>
              {diagnosis.recommended_fix.actions.length > 0 && (
                <ul className="mt-1.5 space-y-1 text-xs text-slate-400">
                  {diagnosis.recommended_fix.actions.map((action, i) => (
                    <li key={i} className="flex gap-1.5">
                      <span className="text-teal-glow">✓</span> {action}
                    </li>
                  ))}
                </ul>
              )}
            </Section>

            {/* Severity comparison */}
            <Section icon={<Gauge className="h-4 w-4" />} title="Severity (deterministic vs. LLM-assessed)">
              <div className="flex gap-4 text-xs">
                <SeverityPill label="Deterministic" value={diagnosis.deterministic_severity} />
                <SeverityPill label="LLM-assessed" value={diagnosis.llm_assessed_severity} />
              </div>
            </Section>

            {/* Evidence */}
            <Section icon={<BookOpen className="h-4 w-4" />} title={`Evidence (${diagnosis.evidence.length})`}>
              <div className="flex flex-col gap-2">
                {diagnosis.evidence.map((ev, i) => (
                  <div key={i} className="rounded-md border border-board-600 bg-board-850/60 p-2">
                    <span
                      className={`inline-block rounded border px-1.5 py-0.5 text-[10px] font-mono ${
                        SOURCE_BADGE[ev.source_type] ?? 'border-board-500 bg-board-700 text-slate-300'
                      }`}
                    >
                      {ev.source_type}
                    </span>
                    <span className="ml-2 font-mono text-[10px] text-slate-500">{ev.source_id}</span>
                    <p className="mt-1 text-xs text-slate-300">{ev.claim}</p>
                  </div>
                ))}
              </div>
            </Section>

            {/* Validation status */}
            <div
              className={`flex items-center gap-2 rounded-lg border p-3 text-xs ${
                diagnosis.validation_passed
                  ? 'border-teal-glow/40 bg-teal-glow/10 text-teal-glow'
                  : 'border-severity-high/40 bg-severity-high/10 text-severity-high'
              }`}
            >
              {diagnosis.validation_passed ? <ShieldCheck className="h-4 w-4" /> : <ShieldAlert className="h-4 w-4" />}
              <span>
                {diagnosis.validation_passed
                  ? 'Evidence validation passed — all claims are grounded in supplied evidence.'
                  : `Evidence validation flagged ${diagnosis.validation_errors.length} issue(s); confidence reduced and human review required.`}
              </span>
            </div>

            {diagnosis.uncertainty.length > 0 && (
              <div className="rounded-lg border border-severity-medium/30 bg-severity-medium/5 p-3 text-xs text-severity-medium">
                <p className="mb-1 font-semibold">Uncertainty notes</p>
                <ul className="space-y-1">
                  {diagnosis.uncertainty.map((u, i) => (
                    <li key={i}>• {u}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span
                className={`rounded px-2 py-0.5 ${
                  diagnosis.requires_human_review
                    ? 'bg-severity-high/15 text-severity-high'
                    : 'bg-teal-glow/15 text-teal-glow'
                }`}
              >
                {diagnosis.requires_human_review ? 'Human review required' : 'No human review flagged'}
              </span>
              <span>Confidence: {formatPercent(diagnosis.classification.confidence)}</span>
            </div>
          </>
        )}

        {trace && (
          <div className="mt-2 rounded-lg border border-board-700 bg-board-900/60 p-3 text-[11px] text-slate-500">
            <p className="mb-1 font-semibold text-slate-400">Observability trace</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <span>Model: <span className="font-mono text-slate-300">{trace.llm_model}</span></span>
              <span>Latency: <span className="font-mono text-slate-300">{formatMs(trace.latency_ms)}</span></span>
              <span>Tokens: <span className="font-mono text-slate-300">{trace.token_usage.total_tokens ?? '—'}</span></span>
              <span>Prompt: <span className="font-mono text-slate-300">{trace.prompt_version}</span></span>
            </div>
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  )
}

function Section({
  icon,
  title,
  confidence,
  children,
}: {
  icon: ReactNode
  title: string
  confidence?: number
  children: ReactNode
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
        {icon}
        {title}
        {confidence != null && <span className="ml-auto text-teal-glow">{formatPercent(confidence)}</span>}
      </div>
      <div className="mt-1.5">{children}</div>
    </div>
  )
}

function SeverityPill({ label, value }: { label: string; value?: string | null }) {
  const color = severityColor(value)
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-slate-500">{label}:</span>
      <span className="rounded px-1.5 py-0.5 font-semibold" style={{ color, backgroundColor: `${color}22` }}>
        {value ?? '—'}
      </span>
    </div>
  )
}
