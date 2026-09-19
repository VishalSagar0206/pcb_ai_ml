import type {
  AnalyzeResponse,
  ViolationDetailResponse,
  AnalysisTrace,
  DiagnosisSummaryEntry,
} from '../types/diagnosis'
import type { PCBDesign } from '../types/pcb'
import type { DRCViolation } from '../types/diagnosis'
import type { EvalSummaryResponse, PCBQAReferenceResponse } from '../types/evaluation'
import type { KnowledgeSearchResponse, KnowledgeShowcaseSummary } from '../types/knowledge'
import type { SampleBoardInfo } from '../types/samples'

const BASE = '/api'

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      /* ignore parse failure */
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; kicad_available: boolean }>('/health'),

  analyzeDemo: () => request<AnalyzeResponse>('/pcb/demo', { method: 'POST' }),

  listSamples: () => request<{ samples: SampleBoardInfo[] }>('/pcb/samples'),

  analyzeSample: (sampleId: string) =>
    request<AnalyzeResponse>(`/pcb/samples/${sampleId}/analyze`, { method: 'POST' }),

  analyzeUpload: async (file: File): Promise<AnalyzeResponse> => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${BASE}/pcb/analyze`, { method: 'POST', body: form })
    if (!res.ok) {
      let detail = res.statusText
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail)
    }
    return res.json()
  },

  getAnalysis: (analysisId: string) =>
    request<{
      analysis_id: string
      board: PCBDesign['board']
      violation_count: number
      kicad_executed: boolean
      fixture_used: boolean
      diagnosis_count: number
    }>(`/pcb/analyze/${analysisId}`),

  getBoard: (analysisId: string) => request<PCBDesign>(`/pcb/board/${analysisId}`),

  listViolations: (analysisId: string) => request<DRCViolation[]>(`/pcb/violations/${analysisId}`),

  listDiagnosesSummary: (analysisId: string) => request<DiagnosisSummaryEntry[]>(`/pcb/diagnoses/${analysisId}`),

  getViolationDetail: (analysisId: string, violationId: string) =>
    request<ViolationDetailResponse>(`/pcb/violations/${analysisId}/${violationId}`),

  getReport: async (analysisId: string): Promise<string> => {
    const res = await fetch(`${BASE}/pcb/report/${analysisId}`)
    if (!res.ok) throw new ApiError(res.status, res.statusText)
    return res.text()
  },

  query: (analysisId: string, question: string) =>
    request<{ answer: string; tool_calls: string[]; iterations: number }>('/pcb/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_id: analysisId, question }),
    }),

  getEvalSummary: () => request<EvalSummaryResponse>('/eval/summary'),

  getPcbQaReference: () => request<PCBQAReferenceResponse>('/research/pcb-qa-reference'),

  getKnowledgeShowcaseSummary: () => request<KnowledgeShowcaseSummary>('/knowledge/showcase/summary'),

  searchKnowledgeShowcase: (query: string, topK = 8) =>
    request<KnowledgeSearchResponse>('/knowledge/showcase/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, top_k: topK }),
    }),
}

export { ApiError }
export type { AnalysisTrace }
