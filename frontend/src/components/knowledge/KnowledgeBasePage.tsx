import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Database, Search, FileText, Loader2, Sparkles, ShieldAlert } from 'lucide-react'
import { api } from '../../api/client'
import type { KnowledgeShowcaseSummary, KnowledgeChunkResult } from '../../types/knowledge'

const SAMPLE_QUERIES = [
  'maximum reverse voltage rating',
  'operating temperature range',
  'flash memory capacity',
  'switching regulator efficiency',
  'connector pin current rating',
  'motor driver protection features',
]

const PROJECT_COLOR: Record<string, string> = {
  AcornRobotElectronics: '#4fd8ff',
  'CF-Chef': '#35e6c3',
  HadesFCS: '#ff8a3d',
  Meshinger: '#ffd23d',
  'OPNhydro-r2': '#7cd6ff',
  PortalHardware: '#ffb27a',
}

export default function KnowledgeBasePage() {
  const [summary, setSummary] = useState<KnowledgeShowcaseSummary | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<KnowledgeChunkResult[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

  useEffect(() => {
    api
      .getKnowledgeShowcaseSummary()
      .then(setSummary)
      .catch(() => setSummary(null))
      .finally(() => setSummaryLoading(false))
  }, [])

  const runSearch = useCallback(async (q: string) => {
    if (!q.trim()) return
    setSearching(true)
    setSearchError(null)
    try {
      const res = await api.searchKnowledgeShowcase(q, 6)
      setResults(res.results)
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : String(err))
      setResults(null)
    } finally {
      setSearching(false)
    }
  }, [])

  const totalPages = summary?.documents.reduce((sum, d) => sum + (d.page_count ?? 0), 0) ?? 0

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-6 pb-4">
      <div className="glass-panel rounded-xl p-5">
        <div className="flex items-center gap-2">
          <Database className="h-5 w-5 text-teal-glow" />
          <h3 className="text-lg font-semibold text-slate-100">Engineering Knowledge Base (RAG)</h3>
        </div>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-400">
          Hybrid retrieval (deterministic metadata filtering + BM25 keyword search + TF-IDF cosine similarity) over{' '}
          <span className="text-slate-200">real component datasheets</span> sourced from the reference{' '}
          <code className="rounded bg-board-800 px-1 py-0.5 text-copper-400">pcb_qa-4FEE</code> benchmark repository —
          spanning regulators, switches, diodes, connectors, and motor drivers across 6 real hardware projects. Chunked
          with page/section provenance preserved per chunk (Phase 6/7).
        </p>
        <div className="mt-2 rounded-lg border border-cyan-glow/25 bg-cyan-glow/5 p-2.5 text-[11px] text-cyan-glow/90">
          Kept intentionally separate from the live diagnosis pipeline's own knowledge base: these real datasheets
          belong to different real hardware projects (e.g. a genuine "U3") than the synthetic demo board's components,
          so mixing them would risk citing the wrong part's specs as evidence for the demo board's violations.
        </div>

        {summaryLoading ? (
          <div className="mt-4 grid grid-cols-3 gap-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-lg bg-board-800/60" />
            ))}
          </div>
        ) : summary ? (
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <StatBlock label="Documents indexed" value={summary.document_count} />
            <StatBlock label="Total chunks" value={summary.total_chunks} />
            <StatBlock label="Total pages" value={totalPages} />
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-500">Knowledge base unavailable.</p>
        )}
      </div>

      <div className="glass-panel rounded-xl p-5">
        <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
          <Search className="h-4 w-4 text-teal-glow" /> Live Hybrid Search
        </h4>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            runSearch(query)
          }}
          className="flex gap-2"
        >
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. maximum reverse voltage rating"
            className="flex-1 rounded-lg border border-board-600 bg-board-900/60 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:border-teal-glow/60 focus:outline-none"
          />
          <button
            type="submit"
            disabled={searching || !query.trim()}
            className="flex items-center gap-1.5 rounded-lg border border-teal-glow/50 bg-teal-glow/15 px-4 py-2 text-sm font-medium text-teal-glow hover:bg-teal-glow/25 disabled:opacity-40"
          >
            {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            Search
          </button>
        </form>

        <div className="mt-3 flex flex-wrap gap-1.5">
          {SAMPLE_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => {
                setQuery(q)
                runSearch(q)
              }}
              className="rounded-full border border-board-600 bg-board-800/50 px-2.5 py-1 text-[11px] text-slate-400 hover:border-teal-glow/40 hover:text-teal-glow"
            >
              {q}
            </button>
          ))}
        </div>

        {searchError && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-severity-critical/40 bg-severity-critical/10 px-3 py-2 text-sm text-severity-critical">
            <ShieldAlert className="h-4 w-4 shrink-0" /> {searchError}
          </div>
        )}

        <AnimatePresence mode="wait">
          {results && (
            <motion.div
              key={results.length + query}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-4 flex flex-col gap-2.5"
            >
              {results.length === 0 ? (
                <p className="text-sm text-slate-500">No chunks matched that query above the similarity threshold.</p>
              ) : (
                results.map((r, i) => (
                  <div key={r.chunk_id} className="rounded-lg border border-board-600 bg-board-850/60 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <FileText className="h-3.5 w-3.5 text-copper-400" />
                        <span className="text-xs font-semibold text-slate-200">{r.document_name}</span>
                        {r.page != null && <span className="text-[10px] text-slate-500">p.{r.page}</span>}
                      </div>
                      <SimilarityBar value={r.similarity ?? 0} rank={i} />
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-slate-400">{truncate(r.text, 380)}</p>
                  </div>
                ))
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="glass-panel rounded-xl p-5">
        <h4 className="mb-3 text-sm font-semibold text-slate-200">Indexed Documents</h4>
        {summaryLoading ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded-lg bg-board-800/60" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {summary?.documents.map((doc, i) => (
              <motion.div
                key={doc.document_id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                className="rounded-lg border border-board-600 bg-board-800/50 p-3.5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-slate-100">{doc.label}</span>
                  <span
                    className="rounded px-1.5 py-0.5 text-[10px] font-medium"
                    style={{
                      color: PROJECT_COLOR[doc.project] ?? '#9aa8c7',
                      backgroundColor: `${PROJECT_COLOR[doc.project] ?? '#9aa8c7'}22`,
                    }}
                  >
                    {doc.project}
                  </span>
                </div>
                <div className="mt-2 flex gap-2 text-[11px] text-slate-500">
                  <span>{doc.chunk_count} chunks</span>
                  {doc.page_count != null && <span>· {doc.page_count} pages</span>}
                  <span>· real datasheet</span>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  )
}

function StatBlock({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-board-600 bg-board-800/50 p-3 text-center">
      <div className="text-2xl font-bold text-teal-glow">{value.toLocaleString()}</div>
      <div className="mt-0.5 text-[11px] text-slate-500">{label}</div>
    </div>
  )
}

function SimilarityBar({ value, rank }: { value: number; rank: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100)
  const color = rank === 0 ? '#35e6c3' : rank < 3 ? '#4fd8ff' : '#9aa8c7'
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-board-700">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-[10px] font-mono text-slate-500">{pct}%</span>
    </div>
  )
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text
  return text.slice(0, max).trim() + '…'
}
