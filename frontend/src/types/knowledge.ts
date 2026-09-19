export interface KnowledgeShowcaseDocument {
  document_id: string
  document_name: string
  label: string
  project: string
  source: string
  chunk_count: number
  page_count: number | null
}

export interface KnowledgeShowcaseSummary {
  document_count: number
  total_chunks: number
  documents: KnowledgeShowcaseDocument[]
}

export interface KnowledgeChunkResult {
  schema_version: string
  document_id: string
  document_name: string
  source: string
  page: number | null
  section: string | null
  chunk_id: string
  text: string
  component_references: string[]
  keywords: string[]
  similarity: number | null
}

export interface KnowledgeSearchResponse {
  query: string
  results: KnowledgeChunkResult[]
}
