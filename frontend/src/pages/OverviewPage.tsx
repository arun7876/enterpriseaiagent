import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity,
  ArrowRight,
  BarChart3,
  BookOpen,
  Bot,
  Database,
  FileCheck,
  FileText,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  UploadCloud,
} from 'lucide-react'
import { apiClient, ApiError, type AuthUser } from '../services/api'
import type { DocumentSummary, HealthStatus, RAGStatus, ReadinessStatus } from '../types'
import { PageHeader } from '../components/PageHeader'
import { StatusBadge } from '../components/StatusBadge'

interface OverviewPageProps {
  user: AuthUser
}

export function OverviewPage({ user }: OverviewPageProps) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [ragStatus, setRAGStatus] = useState<RAGStatus | null>(null)
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [readiness, setReadiness] = useState<ReadinessStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadData = async (isRefresh = false) => {
    try {
      if (isRefresh) setRefreshing(true)
      else setLoading(true)
      setError(null)

      const [healthResult, ragResult, docResult, readyResult] = await Promise.all([
        apiClient.getHealth().catch(() => null),
        apiClient.getRAGStatus().catch(() => null),
        apiClient.getDocuments().catch(() => []),
        apiClient.getReadiness().catch(() => null),
      ])

      setHealth(healthResult)
      setRAGStatus(ragResult)
      setDocuments(docResult)
      setReadiness(readyResult)
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to fetch dashboard metrics.'
      setError(msg)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  // Derive honest health status from real endpoints
  const isAiOnline = ragStatus ? ragStatus.llm_reachable && ragStatus.llm_model_available : false
  const aiStatusValue = ragStatus ? (isAiOnline ? 'healthy' : 'unavailable') : 'unknown'

  // Readiness status check
  const systemStatusValue = health?.status === 'ok'
    ? readiness?.status === 'ready'
      ? 'operational'
      : 'degraded'
    : 'unavailable'

  const userDisplayName = user.email.split('@')[0] || 'Researcher'
  const isViewer = user.role === 'viewer'

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Grounded enterprise research, private document retrieval, and deterministic analytics."
        tag="WORKSPACE"
        actions={
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => void loadData(true)}
              disabled={loading || refreshing}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition disabled:opacity-60"
              title="Refresh dashboard metrics"
            >
              <RefreshCw className={`h-3.5 w-3.5 text-slate-500 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <Link
              to="/assistant"
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-indigo-700 transition"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Ask AI
            </Link>
            {!isViewer && (
              <Link
                to="/documents"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 hover:text-slate-900 transition"
              >
                <UploadCloud className="h-3.5 w-3.5 text-indigo-600" />
                Upload Document
              </Link>
            )}
          </div>
        }
      />

      {error && (
        <div className="mb-6 flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 shadow-xs">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => void loadData(true)}
            className="text-xs font-semibold underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Greeting card */}
      <div className="mb-6 rounded-2xl border border-indigo-100 bg-linear-to-r from-indigo-50/70 via-white to-slate-50 p-6 shadow-card">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-md bg-indigo-100/80 px-2 py-0.5 text-[11px] font-semibold text-indigo-700 font-mono">
              ROLE: {user.role.toUpperCase()}
            </span>
            <h3 className="mt-2 text-xl font-bold text-slate-900 font-display">
              Welcome back, {userDisplayName}
            </h3>
            <p className="mt-1 text-sm text-slate-600 max-w-2xl leading-relaxed">
              Your research workspace is connected to a local-first retrieval index and verified business analytics. All queries respect strict document permission boundaries.
            </p>
          </div>
          <Link
            to="/about"
            className="inline-flex items-center gap-2 text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition"
          >
            <BookOpen className="h-4 w-4" />
            Read architecture guide &rarr;
          </Link>
        </div>
      </div>

      {/* Metrics Row */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">

            {/* Card 1: Documents */}
            <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card transition-all hover:shadow-soft">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 font-mono">
                  Documents
                </span>
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                  <FileText className="h-4 w-4" />
                </div>
              </div>
              <div className="mt-3 text-3xl font-bold tracking-tight text-slate-900 font-display">
                {documents.length}
              </div>
              <div className="mt-2 text-xs text-slate-500">
                Authorized in your catalog
              </div>
            </div>

            {/* Card 2: Indexed Chunks */}
            <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card transition-all hover:shadow-soft">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 font-mono">
                  Indexed chunks
                </span>
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                  <Database className="h-4 w-4" />
                </div>
              </div>
              <div className="mt-3 text-3xl font-bold tracking-tight text-slate-900 font-display">
                {ragStatus ? ragStatus.indexed_chunk_count : '—'}
              </div>
              <div className="mt-2 text-xs text-slate-500">
                {ragStatus ? 'Global vector database chunks' : 'Index checking pending'}
              </div>
            </div>

            {/* Card 3: AI Service */}
            <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card transition-all hover:shadow-soft">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 font-mono">
                  AI service
                </span>
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
                  <Bot className="h-4 w-4" />
                </div>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <span className="text-2xl font-bold tracking-tight text-slate-900 font-display">
                  {ragStatus ? (isAiOnline ? 'Online' : 'Offline') : 'Unknown'}
                </span>
                <StatusBadge value={aiStatusValue} size="sm" />
              </div>
              <div className="mt-2 text-xs text-slate-500 truncate" title={ragStatus?.model_identifier}>
                {ragStatus ? `Model: ${ragStatus.model_identifier}` : 'Ollama host query pending'}
              </div>
            </div>

            {/* Card 4: System Health */}
            <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card transition-all hover:shadow-soft">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 font-mono">
                  System health
                </span>
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
                  <ShieldCheck className="h-4 w-4" />
                </div>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <span className="text-2xl font-bold tracking-tight text-slate-900 font-display">
                  {health?.status === 'ok' ? 'Healthy' : 'Unknown'}
                </span>
                <StatusBadge value={systemStatusValue} size="sm" />
              </div>
              <div className="mt-2 text-xs text-slate-500">
                {readiness?.status === 'ready' ? 'All dependencies ready' : 'FastAPI core active'}
              </div>
            </div>
      </section>

      {/* Main Content Layout: 2 Columns */}
      <section className="mt-8 grid gap-6 lg:grid-cols-12">
        {/* Left: Recent Documents (7 cols) */}
        <div className="lg:col-span-7 flex flex-col rounded-2xl border border-slate-200/80 bg-white shadow-card">
          <div className="flex items-center justify-between border-b border-slate-200/80 px-6 py-4">
            <div>
              <h3 className="text-base font-bold text-slate-900 font-display">
                Recent documents
              </h3>
              <p className="text-xs text-slate-500">
                Authorized files indexed for semantic search
              </p>
            </div>
            <Link
              to="/documents"
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition"
            >
              View all ({documents.length}) &rarr;
            </Link>
          </div>

          <div className="p-6 flex-1">
            {documents.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/60 p-10 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-indigo-50 text-indigo-600 mb-3">
                  <UploadCloud className="h-6 w-6" />
                </div>
                <h4 className="text-sm font-semibold text-slate-800">
                  No documents in your catalog
                </h4>
                <p className="mt-1 text-xs text-slate-500 max-w-sm">
                  {isViewer
                    ? 'As a viewer, you have read-only access. Ask an analyst or admin to share documents with your account.'
                    : 'Upload PDF, DOCX, or CSV files to enable semantic document search and cited RAG answers.'}
                </p>
                {!isViewer && (
                  <Link
                    to="/documents"
                    className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-indigo-700 transition"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Upload first document
                  </Link>
                )}
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {documents.slice(0, 5).map((doc) => (
                  <div key={doc.document_id} className="flex items-center justify-between py-3 hover:bg-slate-50/80 rounded-xl px-2.5 transition">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
                        <FileText className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-slate-800" title={doc.original_filename}>
                          {doc.original_filename}
                        </p>
                        <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-500">
                          <span className="font-mono uppercase font-semibold text-[10px] bg-slate-100 px-1.5 py-0.2 rounded text-slate-600">
                            {doc.file_type}
                          </span>
                          <span>&bull;</span>
                          <span>{doc.chunk_count} chunk{doc.chunk_count !== 1 ? 's' : ''}</span>
                          <span>&bull;</span>
                          <span>{new Date(doc.uploaded_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                    </div>
                    <StatusBadge value={doc.indexing_status} size="sm" />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Quick Actions & How It Works (5 cols) */}
        <div className="lg:col-span-5 flex flex-col gap-6">
          {/* Quick Actions Card */}
          <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
            <h3 className="text-base font-bold text-slate-900 font-display mb-1">
              Quick actions
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Navigate directly to platform capabilities
            </p>

            <div className="grid gap-2.5 sm:grid-cols-2">
              <Link
                to="/assistant"
                className="group flex flex-col justify-between rounded-xl border border-slate-200/80 bg-slate-50/50 p-3.5 hover:border-indigo-200 hover:bg-indigo-50/40 transition"
              >
                <div className="flex items-center justify-between">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700">
                    <Bot className="h-4 w-4" />
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-indigo-600 transition-transform group-hover:translate-x-0.5" />
                </div>
                <div className="mt-3">
                  <span className="block text-xs font-bold text-slate-800 group-hover:text-indigo-900">
                    Open AI assistant
                  </span>
                  <span className="block text-[11px] text-slate-500">
                    Grounded RAG & tools
                  </span>
                </div>
              </Link>

              <Link
                to="/documents"
                className="group flex flex-col justify-between rounded-xl border border-slate-200/80 bg-slate-50/50 p-3.5 hover:border-indigo-200 hover:bg-indigo-50/40 transition"
              >
                <div className="flex items-center justify-between">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-blue-700">
                    <FileCheck className="h-4 w-4" />
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-indigo-600 transition-transform group-hover:translate-x-0.5" />
                </div>
                <div className="mt-3">
                  <span className="block text-xs font-bold text-slate-800 group-hover:text-indigo-900">
                    Upload documents
                  </span>
                  <span className="block text-[11px] text-slate-500">
                    Index & manage files
                  </span>
                </div>
              </Link>

              <Link
                to="/analytics"
                className="group flex flex-col justify-between rounded-xl border border-slate-200/80 bg-slate-50/50 p-3.5 hover:border-indigo-200 hover:bg-indigo-50/40 transition"
              >
                <div className="flex items-center justify-between">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700">
                    <BarChart3 className="h-4 w-4" />
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-indigo-600 transition-transform group-hover:translate-x-0.5" />
                </div>
                <div className="mt-3">
                  <span className="block text-xs font-bold text-slate-800 group-hover:text-indigo-900">
                    Explore analytics
                  </span>
                  <span className="block text-[11px] text-slate-500">
                    Safe SQL tool queries
                  </span>
                </div>
              </Link>

              <Link
                to="/status"
                className="group flex flex-col justify-between rounded-xl border border-slate-200/80 bg-slate-50/50 p-3.5 hover:border-indigo-200 hover:bg-indigo-50/40 transition"
              >
                <div className="flex items-center justify-between">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-100 text-purple-700">
                    <Activity className="h-4 w-4" />
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-indigo-600 transition-transform group-hover:translate-x-0.5" />
                </div>
                <div className="mt-3">
                  <span className="block text-xs font-bold text-slate-800 group-hover:text-indigo-900">
                    View system status
                  </span>
                  <span className="block text-[11px] text-slate-500">
                    Check services & models
                  </span>
                </div>
              </Link>
            </div>
          </div>

          {/* Stepper: How it Works */}
          <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-900 font-display">
                How it works
              </h3>
              <span className="text-[11px] font-semibold text-indigo-600 font-mono">
                RAG PIPELINE
              </span>
            </div>

            <div className="space-y-3">
              {[
                { step: '1', title: 'Upload', desc: 'Securely upload PDF, DOCX, or CSV business files.' },
                { step: '2', title: 'Index', desc: 'Text extracted, chunked, and embedded into SQLite vector store.' },
                { step: '3', title: 'Ask', desc: 'Query in plain language; RAG retrieves relevant passages.' },
                { step: '4', title: 'Cited Answer', desc: 'Local Ollama LLM synthesizes answers with source citations.' },
              ].map((item, idx) => (
                <div key={idx} className="flex items-start gap-3">
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-[11px] font-bold text-indigo-700">
                    {item.step}
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-800">
                      {item.title}
                    </h4>
                    <p className="text-[11px] text-slate-500 leading-normal">
                      {item.desc}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-5 border-t border-slate-100 pt-4">
              <Link
                to="/about"
                className="flex items-center justify-between text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition"
              >
                <span>Learn about LangGraph & SQL tools</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
