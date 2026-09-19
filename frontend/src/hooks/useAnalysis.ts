import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { PCBDesign } from '../types/pcb'
import type { DRCViolation, ViolationDetailResponse, DiagnosisSummaryEntry } from '../types/diagnosis'
import type { SampleBoardInfo } from '../types/samples'

const MAX_UPLOAD_BYTES = 20 * 1024 * 1024 // 20MB -- generous for a text-based .kicad_pcb file

/** Client-side pre-flight checks for user-uploaded board files, so obviously
 * invalid uploads (wrong extension, empty/oversized file) get an immediate,
 * specific error message instead of a round-trip to the server. The backend
 * still re-validates independently -- this is just a fast, friendly first
 * line of feedback. */
export function validateBoardFile(file: File): string | null {
  if (!file.name.toLowerCase().endsWith('.kicad_pcb')) {
    return `"${file.name}" doesn't look like a KiCad PCB file -- expected a .kicad_pcb extension.`
  }
  if (file.size === 0) {
    return `"${file.name}" is empty.`
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return `"${file.name}" is ${(file.size / (1024 * 1024)).toFixed(1)}MB, which exceeds the ${MAX_UPLOAD_BYTES / (1024 * 1024)}MB limit for this demo.`
  }
  return null
}

interface AnalysisState {
  analysisId: string | null
  board: PCBDesign | null
  violations: DRCViolation[]
  diagnosesSummary: DiagnosisSummaryEntry[]
  loading: boolean
  error: string | null
  kicadExecuted: boolean
  fixtureUsed: boolean
  activeSampleId: string | null
  samples: SampleBoardInfo[]
  samplesLoading: boolean
}

export function useAnalysis() {
  const [state, setState] = useState<AnalysisState>({
    analysisId: null,
    board: null,
    violations: [],
    diagnosesSummary: [],
    loading: false,
    error: null,
    kicadExecuted: false,
    fixtureUsed: false,
    activeSampleId: null,
    samples: [],
    samplesLoading: false,
  })

  const loadAnalysis = useCallback(async (analysisId: string) => {
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const [board, violations, analysisMeta, diagnosesSummary] = await Promise.all([
        api.getBoard(analysisId),
        api.listViolations(analysisId),
        api.getAnalysis(analysisId),
        api.listDiagnosesSummary(analysisId).catch(() => []),
      ])
      setState((s) => ({
        ...s,
        analysisId,
        board,
        violations,
        diagnosesSummary,
        loading: false,
        kicadExecuted: analysisMeta.kicad_executed,
        fixtureUsed: analysisMeta.fixture_used,
      }))
    } catch (err) {
      setState((s) => ({ ...s, loading: false, error: err instanceof Error ? err.message : String(err) }))
    }
  }, [])

  const loadDemo = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null, activeSampleId: 'small' }))
    try {
      const res = await api.analyzeDemo()
      await loadAnalysis(res.analysis_id)
    } catch (err) {
      setState((s) => ({ ...s, loading: false, error: err instanceof Error ? err.message : String(err) }))
    }
  }, [loadAnalysis])

  const refreshSamples = useCallback(async () => {
    setState((s) => ({ ...s, samplesLoading: true }))
    try {
      const res = await api.listSamples()
      setState((s) => ({ ...s, samples: res.samples, samplesLoading: false }))
    } catch {
      setState((s) => ({ ...s, samplesLoading: false }))
    }
  }, [])

  const loadSample = useCallback(
    async (sampleId: string) => {
      setState((s) => ({ ...s, loading: true, error: null, activeSampleId: sampleId }))
      try {
        const res = await api.analyzeSample(sampleId)
        await loadAnalysis(res.analysis_id)
        refreshSamples()
      } catch (err) {
        setState((s) => ({ ...s, loading: false, error: err instanceof Error ? err.message : String(err) }))
      }
    },
    [loadAnalysis, refreshSamples],
  )

  const uploadAndAnalyze = useCallback(
    async (file: File) => {
      const validationError = validateBoardFile(file)
      if (validationError) {
        setState((s) => ({ ...s, error: validationError }))
        return
      }
      setState((s) => ({ ...s, loading: true, error: null, activeSampleId: null }))
      try {
        const res = await api.analyzeUpload(file)
        await loadAnalysis(res.analysis_id)
      } catch (err) {
        setState((s) => ({ ...s, loading: false, error: err instanceof Error ? err.message : String(err) }))
      }
    },
    [loadAnalysis],
  )

  useEffect(() => {
    loadDemo()
    refreshSamples()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { ...state, loadDemo, uploadAndAnalyze, loadAnalysis, loadSample, refreshSamples }
}


export function useViolationDetail(analysisId: string | null, violationId: string | null) {
  const [detail, setDetail] = useState<ViolationDetailResponse | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!analysisId || !violationId) {
      setDetail(null)
      return
    }
    let cancelled = false
    setLoading(true)
    api
      .getViolationDetail(analysisId, violationId)
      .then((res) => {
        if (!cancelled) setDetail(res)
      })
      .catch(() => {
        if (!cancelled) setDetail(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [analysisId, violationId])

  return { detail, loading }
}
