// Mirrors src/pcb_ai/schemas/drc.py and diagnosis.py

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'

export interface ViolationLocation {
  x?: number | null
  y?: number | null
}

export interface ViolationItem {
  type: string
  reference?: string | null
  pad?: string | null
  net?: string | null
  description?: string | null
}

export interface DRCViolation {
  schema_version: string
  violation_id: string
  rule_type: string
  raw_rule_id?: string | null
  severity: Severity
  message: string
  layer?: string | null
  location?: ViolationLocation | null
  items: ViolationItem[]
  actual_value?: number | null
  required_value?: number | null
  unit?: string | null
  raw_drc_message: string
  source: string
}

export interface Classification {
  type: string
  severity: Severity
  confidence: number
}

export interface AffectedObject {
  type: string
  reference?: string | null
  pad?: string | null
  net?: string | null
}

export interface DrivingRule {
  rule_name: string
  required_value?: string | number | null
  actual_value?: string | number | null
  unit?: string | null
}

export interface RootCause {
  explanation: string
  confidence: number
}

export interface EngineeringImpact {
  description: string
  potential_effects: string[]
}

export interface RecommendedFix {
  description: string
  actions: string[]
}

export interface EvidenceItem {
  source_type: 'drc' | 'pcb' | 'datasheet' | 'engineering_document' | string
  source_id: string
  location?: string | null
  claim: string
}

export interface ViolationDiagnosis {
  schema_version: string
  violation_id: string
  classification: Classification
  summary: string
  affected_objects: AffectedObject[]
  driving_rule?: DrivingRule | null
  root_cause: RootCause
  engineering_impact: EngineeringImpact
  recommended_fix: RecommendedFix
  evidence: EvidenceItem[]
  uncertainty: string[]
  requires_human_review: boolean
  deterministic_severity?: Severity | null
  llm_assessed_severity?: Severity | null
  severity_policy_version?: string | null
  insufficient_evidence: boolean
  validation_passed?: boolean | null
  validation_errors: string[]
}

export interface AnalysisTrace {
  schema_version: string
  analysis_id: string
  violation_id: string
  tools_called: string[]
  retrieved_pcb_objects: string[]
  retrieved_documents: string[]
  llm_model?: string | null
  prompt_version?: string | null
  response_schema_version?: string | null
  latency_ms?: number | null
  token_usage: Record<string, number>
  stages_completed: string[]
  errors: string[]
}

export interface AnalyzeResponse {
  analysis_id: string
  violation_count: number
  kicad_executed: boolean
  kicad_available: boolean
}

export interface ViolationDetailResponse {
  violation: DRCViolation
  diagnosis: ViolationDiagnosis | null
  trace: AnalysisTrace | null
}

export interface DiagnosisSummaryEntry {
  violation_id: string
  classification: Classification
  deterministic_severity?: Severity | null
  llm_assessed_severity?: Severity | null
  requires_human_review: boolean
  insufficient_evidence: boolean
  validation_passed?: boolean | null
}
