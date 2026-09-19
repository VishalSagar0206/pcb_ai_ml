export interface AggregateMetrics {
  condition: string
  n: number
  classification_accuracy: number
  severity_agreement_rate: number
  human_review_agreement_rate: number
  mean_root_cause_overlap: number
  mean_recommendation_overlap: number
  evidence_grounding_rate: number
  hallucination_rate: number
  mean_unsupported_claims: number
  mean_evidence_word_count: number
  mean_total_tokens: number
  mean_latency_ms?: number | null
  retrieval_precision: string
  retrieval_recall: string
  cost: string
}

export interface EvalSummaryResponse {
  available: boolean
  conditions: Record<string, AggregateMetrics>
}

export interface PCBQASampleQuestion {
  category: string
  question: string
  answer: string
}

export interface PCBQAProject {
  project: string
  circuit_name?: string
  component_count?: number
  net_count?: number
  subcircuit_count?: number
  question_count?: number
  sample_questions?: PCBQASampleQuestion[]
}

export interface PCBQAReferenceResponse {
  available: boolean
  projects: PCBQAProject[]
}
