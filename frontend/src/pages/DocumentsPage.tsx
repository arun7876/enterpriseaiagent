import { useState, useRef, useEffect, useMemo, type ChangeEvent, type DragEvent } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  FileCheck,
  FileSpreadsheet,
  FileText,
  LoaderCircle,
  RefreshCw,
  Search,
  ShieldAlert,
  UploadCloud,
  X,
} from 'lucide-react'
import { apiClient, ApiError, type AuthUser } from '../services/api'
import type { DocumentSummary } from '../types'
import { PageHeader } from '../components/PageHeader'
import { StatusBadge } from '../components/StatusBadge'
import { TableRowSkeleton } from '../components/SkeletonLoader'

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024 // 10 MB

interface DocumentsPageProps {
  user: AuthUser
}

export function DocumentsPage({ user }: DocumentsPageProps) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Search & Filter state
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<'all' | 'pdf' | 'docx' | 'csv'>('all')

  const inputRef = useRef<HTMLInputElement | null>(null)
  const isViewer = user.role === 'viewer'

  const loadDocuments = async () => {
    try {
      setLoading(true)
      const result = await apiClient.getDocuments()
      setDocuments(result)
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Unable to load document catalog.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadDocuments()
  }, [])

  const validateFile = (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!ext || !['pdf', 'docx', 'csv'].includes(ext)) {
      throw new Error('Only PDF, DOCX, and CSV files are supported.')
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      throw new Error('The file exceeds the 10 MB upload ceiling.')
    }
  }

  const uploadFiles = async (fileList: FileList | File[]) => {
    if (isViewer) {
      setError('Viewers cannot upload documents. Contact an analyst or admin.')
      return
    }

    const files = Array.from(fileList)
    if (files.length === 0) return

    const file = files[0]
    try {
      validateFile(file)
      setUploading(true)
      setError(null)
      setSuccess(null)

      const formData = new FormData()
      formData.append('file', file)
      const result = await apiClient.uploadDocument(formData)

      setSuccess(`"${result.original_filename}" successfully uploaded and processed. Chunks: ${result.chunk_count}. Indexing: ${result.indexing_status}.`)
      await loadDocuments()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed.'
      setError(msg)
    } finally {
      setUploading(false)
      if (inputRef.current) {
        inputRef.current.value = ''
      }
    }
  }

  const onDragOver = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault()
    if (!isViewer) setIsDragging(true)
  }

  const onDragLeave = () => {
    setIsDragging(false)
  }

  const onDrop = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault()
    setIsDragging(false)
    if (isViewer) return
    void uploadFiles(e.dataTransfer.files)
  }

  const onSelect = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      void uploadFiles(e.target.files)
    }
  }

  // Filtered documents
  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      const matchesSearch = doc.original_filename.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesType = typeFilter === 'all' || doc.file_type.toLowerCase() === typeFilter
      return matchesSearch && matchesType
    })
  }, [documents, searchQuery, typeFilter])

  const getFileIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'pdf':
        return <FileText className="h-4 w-4 text-rose-600" />
      case 'docx':
        return <FileCheck className="h-4 w-4 text-blue-600" />
      case 'csv':
        return <FileSpreadsheet className="h-4 w-4 text-emerald-600" />
      default:
        return <FileText className="h-4 w-4 text-slate-500" />
    }
  }

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      <PageHeader
        title="Documents"
        subtitle="Manage and index enterprise business files for semantic retrieval."
        tag="DATA INGESTION"
        actions={
          <button
            type="button"
            onClick={() => void loadDocuments()}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 text-slate-500 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        }
      />

      {/* Viewer restriction alert */}
      {isViewer && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4 text-xs text-amber-900 flex items-center gap-3">
          <ShieldAlert className="h-5 w-5 text-amber-600 shrink-0" />
          <div>
            <p className="font-bold">Viewer Account Access Notice</p>
            <p className="text-amber-700 mt-0.5">
              Your account is assigned the Viewer role. You have read-only access to query shared documents. Document uploads and administrative edits are restricted.
            </p>
          </div>
        </div>
      )}

      {/* Upload Drop Zone Card */}
      {!isViewer && (
        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
          <label
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-10 text-center transition-all ${
              isDragging
                ? 'border-indigo-500 bg-indigo-50/60 ring-4 ring-indigo-50'
                : 'border-slate-300/80 bg-slate-50/50 hover:border-indigo-300 hover:bg-indigo-50/20'
            }`}
          >
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 mb-3 shadow-xs">
              <UploadCloud className="h-7 w-7" />
            </div>

            <div className="text-base font-bold text-slate-900 font-display">
              Drop files here or click to browse
            </div>

            <p className="mt-1.5 text-xs text-slate-500 max-w-sm">
              Supports PDF, DOCX, and CSV spreadsheets up to 10 MB per file.
            </p>

            <div className="mt-4 flex items-center gap-2">
              <span className="rounded-md bg-white border border-slate-200 px-2 py-0.5 text-[10px] font-mono font-bold text-rose-600 uppercase">
                PDF
              </span>
              <span className="rounded-md bg-white border border-slate-200 px-2 py-0.5 text-[10px] font-mono font-bold text-blue-600 uppercase">
                DOCX
              </span>
              <span className="rounded-md bg-white border border-slate-200 px-2 py-0.5 text-[10px] font-mono font-bold text-emerald-600 uppercase">
                CSV
              </span>
            </div>

            <input
              ref={inputRef}
              type="file"
              className="hidden"
              accept=".pdf,.docx,.csv"
              onChange={onSelect}
              disabled={uploading}
            />
          </label>

          {/* Feedback messages */}
          {error && (
            <div className="mt-4 flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs text-rose-800">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
                <span>{error}</span>
              </div>
              <button type="button" onClick={() => setError(null)} className="text-rose-500 hover:text-rose-800">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          {success && (
            <div className="mt-4 flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs text-emerald-800">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                <span>{success}</span>
              </div>
              <button type="button" onClick={() => setSuccess(null)} className="text-emerald-500 hover:text-emerald-800">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          {uploading && (
            <div className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-indigo-50 border border-indigo-100 p-3 text-xs font-semibold text-indigo-700">
              <LoaderCircle className="h-4 w-4 animate-spin text-indigo-600" />
              <span>Extracting text, computing embeddings & indexing into SQLite vector index...</span>
            </div>
          )}
        </div>
      )}

      {/* Document Library List Card */}
      <div className="rounded-2xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
        {/* Header & Controls */}
        <div className="flex flex-col gap-3 border-b border-slate-200/80 p-5 sm:flex-row sm:items-center sm:justify-between bg-slate-50/30">
          <div>
            <h3 className="text-base font-bold text-slate-900 font-display">
              Authorized Document Catalog
            </h3>
            <p className="text-xs text-slate-500">
              {filteredDocuments.length} of {documents.length} document{documents.length !== 1 ? 's' : ''} shown
            </p>
          </div>

          {/* Search & Type filter */}
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search documents..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="rounded-xl border border-slate-200 bg-white pl-8 pr-3 py-1.5 text-xs text-slate-800 shadow-2xs focus:border-indigo-500 focus:outline-none"
              />
            </div>

            <div className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white p-0.5 shadow-2xs">
              {(['all', 'pdf', 'docx', 'csv'] as const).map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setTypeFilter(type)}
                  className={`rounded-lg px-2.5 py-1 text-[11px] font-bold uppercase transition ${
                    typeFilter === type
                      ? 'bg-indigo-600 text-white shadow-2xs'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-100 text-left text-xs">
            <thead className="bg-slate-50/80 font-mono text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="px-5 py-3.5">Filename</th>
                <th className="px-5 py-3.5">Type</th>
                <th className="px-5 py-3.5">Chunks</th>
                <th className="px-5 py-3.5">Indexing</th>
                <th className="px-5 py-3.5">Uploaded</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <>
                  <TableRowSkeleton />
                  <TableRowSkeleton />
                  <TableRowSkeleton />
                </>
              ) : filteredDocuments.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-12 text-center text-xs text-slate-500">
                    {documents.length === 0
                      ? 'No documents uploaded yet. Upload a PDF, DOCX, or CSV file above.'
                      : 'No documents match your filter criteria.'}
                  </td>
                </tr>
              ) : (
                filteredDocuments.map((doc) => (
                  <tr key={doc.document_id} className="hover:bg-slate-50/70 transition">
                    <td className="px-5 py-3.5 font-semibold text-slate-800">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100">
                          {getFileIcon(doc.file_type)}
                        </div>
                        <span className="truncate max-w-sm" title={doc.original_filename}>
                          {doc.original_filename}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="font-mono text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                        {doc.file_type}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 font-mono text-slate-600">
                      {doc.chunk_count} chunk{doc.chunk_count !== 1 ? 's' : ''}
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge value={doc.indexing_status} size="sm" />
                    </td>
                    <td className="px-5 py-3.5 text-slate-500 font-mono text-[11px]">
                      {new Date(doc.uploaded_at).toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
