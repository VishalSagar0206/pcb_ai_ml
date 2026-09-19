import { useMemo, useRef, useState, type ChangeEvent } from 'react'
import { motion } from 'framer-motion'
import { Upload, RefreshCw, AlertCircle, Loader2, ShieldAlert, Gauge, Cpu, Ruler, UserCheck } from 'lucide-react'
import PCBCanvas from '../board/PCBCanvas'
import LayerToggle, { type ViewMode } from '../board/LayerToggle'
import ViolationList from '../violations/ViolationList'
import DiagnosisPanel from '../violations/DiagnosisPanel'
import StatCard from './StatCard'
import SampleSwitcher from './SampleSwitcher'
import { SkeletonBoardExplorer } from './Skeleton'
import { useAnalysis, useViolationDetail } from '../../hooks/useAnalysis'
import { SEVERITY_ORDER, severityColor, formatPercent } from '../../lib/format'

export default function BoardExplorer() {
  const {
    analysisId,
    board,
    violations,
    diagnosesSummary,
    loading,
    error,
    kicadExecuted,
    fixtureUsed,
    activeSampleId,
    samples,
    loadSample,
    uploadAndAnalyze,
  } = useAnalysis()
  const [selectedViolationId, setSelectedViolationId] = useState<string | null>(null)
  const [activeLayer, setActiveLayer] = useState<ViewMode>('all')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { detail, loading: detailLoading } = useViolationDetail(analysisId, selectedViolationId)

  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const v of violations) counts[v.severity] = (counts[v.severity] ?? 0) + 1
    return counts
  }, [violations])

  const diagnosedIds = useMemo(() => new Set(violations.map((v) => v.violation_id)), [violations])

  const stats = useMemo(() => {
    const n = diagnosesSummary.length
    const avgConfidence = n
      ? diagnosesSummary.reduce((sum, d) => sum + (d.classification?.confidence ?? 0), 0) / n
      : null
    const humanReviewCount = diagnosesSummary.filter((d) => d.requires_human_review).length
    const criticalOrHigh = (severityCounts.critical ?? 0) + (severityCounts.high ?? 0)
    return { avgConfidence, humanReviewCount, criticalOrHigh }
  }, [diagnosesSummary, severityCounts])

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) uploadAndAnalyze(file)
    e.target.value = ''
  }

  return (
    <div className="flex flex-col gap-4 pb-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-semibold text-slate-100">Board Explorer</h2>
          {board && (
            <span className="rounded-full border border-board-600 bg-board-800/60 px-3 py-1 text-xs text-slate-400">
              {board.board.title ?? board.board.board_id} · rev {board.board.revision ?? 'n/a'}
            </span>
          )}
          {analysisId && (
            <span
              className={`rounded-full px-3 py-1 text-xs ${
                kicadExecuted
                  ? 'bg-teal-glow/15 text-teal-glow'
                  : fixtureUsed
                    ? 'bg-severity-medium/15 text-severity-medium'
                    : 'bg-severity-high/15 text-severity-high'
              }`}
            >
              {kicadExecuted ? 'Live KiCad DRC' : fixtureUsed ? 'Recorded DRC fixture (offline demo)' : 'DRC unavailable'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <SampleSwitcher
            samples={samples}
            activeSampleId={activeSampleId}
            loading={loading}
            onSelect={loadSample}
          />
          <button
            onClick={() => loadSample(activeSampleId ?? 'small')}
            className="flex items-center gap-1.5 rounded-md border border-board-600 bg-board-800/60 px-3 py-1.5 text-xs text-slate-300 hover:border-teal-glow/50 hover:text-teal-glow"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Reload
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-1.5 rounded-md border border-copper-500/60 bg-copper-500/15 px-3 py-1.5 text-xs font-medium text-copper-400 hover:bg-copper-500/25"
          >
            <Upload className="h-3.5 w-3.5" /> Analyze your own .kicad_pcb
          </button>
          <input ref={fileInputRef} type="file" accept=".kicad_pcb" className="hidden" onChange={handleFileChange} />
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-severity-critical/40 bg-severity-critical/10 px-3 py-2 text-sm text-severity-critical">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {loading && !board && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <Loader2 className="h-4 w-4 animate-spin text-teal-glow" /> Running pipeline: parse → DRC → context → RAG →
            LLM diagnosis…
          </div>
          <SkeletonBoardExplorer />
        </div>
      )}

      {board && (
        <>
          {/* Dashboard stat row */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard
              label="Total Violations"
              value={violations.length}
              icon={<ShieldAlert className="h-4 w-4" />}
              accent="#ff8a3d"
              delay={0}
            />
            <StatCard
              label="Critical / High"
              value={stats.criticalOrHigh}
              icon={<ShieldAlert className="h-4 w-4" />}
              accent="#ff3b5c"
              delay={0.04}
            />
            <StatCard
              label="Human Review"
              value={stats.humanReviewCount}
              icon={<UserCheck className="h-4 w-4" />}
              accent="#ffd23d"
              delay={0.08}
              sub={`of ${diagnosesSummary.length} diagnosed`}
            />
            <StatCard
              label="Avg. Confidence"
              value={formatPercent(stats.avgConfidence)}
              icon={<Gauge className="h-4 w-4" />}
              accent="#35e6c3"
              delay={0.12}
            />
            <StatCard
              label="Board Size"
              value={`${board.board.width_mm?.toFixed(0) ?? '?'}×${board.board.height_mm?.toFixed(0) ?? '?'}mm`}
              icon={<Ruler className="h-4 w-4" />}
              accent="#4fd8ff"
              delay={0.16}
              sub={`${board.components.length} components`}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.9fr)_290px_370px]">
            {/* Canvas */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="glass-panel relative flex h-[560px] flex-col overflow-hidden rounded-xl"
            >
              <div className="flex items-center justify-between gap-2 border-b border-board-700 p-3">
                <LayerToggle active={activeLayer} onChange={setActiveLayer} />
                <div className="flex gap-2 text-[10px] text-slate-500">
                  {SEVERITY_ORDER.filter((s) => severityCounts[s]).map((s) => (
                    <span key={s} className="flex items-center gap-1">
                      <span
                        className="inline-block h-2 w-2 rounded-full"
                        style={{ backgroundColor: severityColor(s) }}
                      />
                      {severityCounts[s]}
                    </span>
                  ))}
                </div>
              </div>
              <div className="relative flex-1 pcb-grid-bg">
                <PCBCanvas
                  board={board}
                  violations={violations}
                  selectedViolationId={selectedViolationId}
                  onSelectViolation={setSelectedViolationId}
                  activeLayer={activeLayer}
                />
              </div>
              {loading && (
                <div className="absolute inset-0 flex items-center justify-center bg-board-950/70 backdrop-blur-sm">
                  <Loader2 className="h-6 w-6 animate-spin text-teal-glow" />
                </div>
              )}
            </motion.div>

            {/* Violation list */}
            <div className="glass-panel flex h-[560px] flex-col overflow-hidden rounded-xl">
              <div className="flex items-center gap-2 border-b border-board-700 px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
                <Cpu className="h-3.5 w-3.5" /> DRC Violations ({violations.length})
              </div>
              <ViolationList
                violations={violations}
                selectedId={selectedViolationId}
                onSelect={setSelectedViolationId}
                diagnosedIds={diagnosedIds}
              />
            </div>

            {/* Diagnosis panel */}
            <div className="glass-panel flex h-[560px] flex-col overflow-hidden rounded-xl">
              <div className="border-b border-board-700 px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Evidence-Grounded Diagnosis
              </div>
              <DiagnosisPanel detail={detail} loading={detailLoading} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
