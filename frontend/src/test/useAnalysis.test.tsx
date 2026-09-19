import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useAnalysis, useViolationDetail } from '../hooks/useAnalysis'
import type { PCBDesign } from '../types/pcb'
import type { DRCViolation, ViolationDetailResponse } from '../types/diagnosis'

// Mock the whole API client module so these tests never touch the network
// -- useAnalysis's job (loading states, error handling, sample switching) is
// what's under test here, not the real backend.
vi.mock('../api/client', () => ({
  api: {
    analyzeDemo: vi.fn(),
    listSamples: vi.fn(),
    analyzeSample: vi.fn(),
    analyzeUpload: vi.fn(),
    getAnalysis: vi.fn(),
    getBoard: vi.fn(),
    listViolations: vi.fn(),
    listDiagnosesSummary: vi.fn(),
    getViolationDetail: vi.fn(),
  },
}))

import { api } from '../api/client'

const mockBoard = { board: { board_id: 'b1', width_mm: 60, height_mm: 40 }, components: [], pads: [] } as unknown as PCBDesign
const mockViolations: DRCViolation[] = []

function mockHappyPath(analysisId: string) {
  vi.mocked(api.analyzeDemo).mockResolvedValue({
    analysis_id: analysisId,
    violation_count: 0,
    kicad_executed: false,
    kicad_available: false,
  })
  vi.mocked(api.getBoard).mockResolvedValue(mockBoard)
  vi.mocked(api.listViolations).mockResolvedValue(mockViolations)
  vi.mocked(api.listDiagnosesSummary).mockResolvedValue([])
  vi.mocked(api.getAnalysis).mockResolvedValue({
    analysis_id: analysisId,
    board: mockBoard.board,
    violation_count: 0,
    kicad_executed: false,
    fixture_used: true,
    diagnosis_count: 0,
  })
  vi.mocked(api.listSamples).mockResolvedValue({ samples: [] })
}

describe('useAnalysis', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads the demo board automatically on mount', async () => {
    mockHappyPath('demo')

    const { result } = renderHook(() => useAnalysis())

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(api.analyzeDemo).toHaveBeenCalledTimes(1)
    expect(result.current.analysisId).toBe('demo')
    expect(result.current.board).toEqual(mockBoard)
    expect(result.current.activeSampleId).toBe('small')
    expect(result.current.error).toBeNull()
  })

  it('surfaces a network error without leaving loading stuck true', async () => {
    vi.mocked(api.analyzeDemo).mockRejectedValue(new Error('network down'))
    vi.mocked(api.listSamples).mockResolvedValue({ samples: [] })

    const { result } = renderHook(() => useAnalysis())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe('network down')
  })

  it('loadSample switches the active sample and re-fetches the board', async () => {
    mockHappyPath('demo')
    vi.mocked(api.analyzeSample).mockResolvedValue({
      analysis_id: 'sample-medium',
      violation_count: 9,
      kicad_executed: false,
      kicad_available: false,
    })

    const { result } = renderHook(() => useAnalysis())
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.loadSample('medium')
    })

    expect(api.analyzeSample).toHaveBeenCalledWith('medium')
    expect(result.current.activeSampleId).toBe('medium')
    expect(result.current.analysisId).toBe('sample-medium')
  })

  it('rejects an invalid upload client-side without calling the API', async () => {
    mockHappyPath('demo')
    const { result } = renderHook(() => useAnalysis())
    await waitFor(() => expect(result.current.loading).toBe(false))

    const badFile = new File([new Uint8Array(10)], 'notes.txt')
    await act(async () => {
      await result.current.uploadAndAnalyze(badFile)
    })

    expect(api.analyzeUpload).not.toHaveBeenCalled()
    expect(result.current.error).toMatch(/doesn't look like a KiCad PCB file/)
  })

  it('uploads and analyzes a valid file', async () => {
    mockHappyPath('demo')
    vi.mocked(api.analyzeUpload).mockResolvedValue({
      analysis_id: 'upload-1',
      violation_count: 0,
      kicad_executed: false,
      kicad_available: false,
    })

    const { result } = renderHook(() => useAnalysis())
    await waitFor(() => expect(result.current.loading).toBe(false))

    const goodFile = new File([new Uint8Array(10)], 'board.kicad_pcb')
    await act(async () => {
      await result.current.uploadAndAnalyze(goodFile)
    })

    expect(api.analyzeUpload).toHaveBeenCalledWith(goodFile)
    expect(result.current.analysisId).toBe('upload-1')
    expect(result.current.activeSampleId).toBeNull()
  })
})

describe('useViolationDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns null detail when analysisId or violationId is missing', () => {
    const { result } = renderHook(() => useViolationDetail(null, null))
    expect(result.current.detail).toBeNull()
    expect(result.current.loading).toBe(false)
  })

  it('fetches and returns violation detail once both ids are present', async () => {
    const detail: ViolationDetailResponse = {
      violation: { violation_id: 'drc-0' } as DRCViolation,
      diagnosis: null,
      trace: null,
    }
    vi.mocked(api.getViolationDetail).mockResolvedValue(detail)

    const { result } = renderHook(() => useViolationDetail('demo', 'drc-0'))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.detail).toEqual(detail)
    expect(api.getViolationDetail).toHaveBeenCalledWith('demo', 'drc-0')
  })

  it('clears detail to null if the fetch fails', async () => {
    vi.mocked(api.getViolationDetail).mockRejectedValue(new Error('not found'))

    const { result } = renderHook(() => useViolationDetail('demo', 'missing-id'))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.detail).toBeNull()
  })
})
