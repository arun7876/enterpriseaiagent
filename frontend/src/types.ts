export type HealthStatus = {
  status: 'ok'
}

export type RAGStatus = {
  embedding_model_identifier: string
  embedding_model_loaded: boolean
  vector_index_exists: boolean
  indexed_chunk_count: number
  model_identifier: string
  llm_reachable: boolean
  llm_model_available: boolean
}

export type Citation = {
  source_id: string
  document_id: string
  chunk_id: string
  filename: string
  chunk_index: number
  page_number: number | null
  excerpt: string
  relevance_score: number
  metadata: Record<string, unknown>
}

export type RAGAskResponse = {
  answer: string
  citations: Citation[]
  source_filenames: string[]
  retrieval_count: number
  model_identifier: string
  processing_time_ms: number
}

export type AgentAskResponse = {
  answer: string
  workflow: 'document_search' | 'sql_analytics' | 'combined'
  selected_tools: string[]
  structured_data: Array<Record<string, unknown>>
  citations: Citation[]
  sufficient_evidence: boolean
  processing_time_ms: number
  errors: string[]
}

export type DocumentSummary = {
  document_id: string
  original_filename: string
  file_type: 'pdf' | 'docx' | 'csv'
  extraction_status: 'success' | 'empty'
  uploaded_at: string
  chunk_count: number
  indexing_status: 'indexed' | 'already_indexed' | 'empty' | 'failed'
  metadata: Record<string, unknown>
}

export type DocumentUploadResponse = DocumentSummary & {
  indexing_error?: string | null
  extracted_text?: string
  pages?: Array<Record<string, unknown>>
  rows?: Array<Record<string, unknown>>
}

export type AssistantMode = 'rag' | 'agent'

export type ReadinessStatus = {
  status: 'ready' | 'not_ready'
  dependencies: Record<string, string>
}
