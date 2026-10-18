import { useState, useEffect } from 'react'
import {
  Activity,
  Bot,
  Clock,
  Cpu,
  Database,
  RefreshCw,
  Server,
  ShieldAlert,
} from 'lucide-react'
import { apiClient, ApiError } from '../services/api'
import type { HealthStatus, RAGStatus, ReadinessStatus } from '../types'
import { PageHeader } from '../components/PageHeader'
import { StatusBadge } from '../components/StatusBadge'

export function SystemStatusPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [ragStatus, setRAGStatus] = useState<RAGStatus | null>(null)
  const [readiness, setReadiness] = useState<ReadinessStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)

  const checkStatus = async () => {
    try {
      setLoading(true)
      setError(null)

      const [healthRes, ragRes, readyRes] = await Promise.all([
        apiClient.getHealth().catch(() => null),
        apiClient.getRAGStatus().catch(() => null),
        apiClient.getReadiness().catch(() => null),
      ])

      setHealth(healthRes)
      setRAGStatus(ragRes)
      setReadiness(readyRes)
      setLastChecked(new Date())
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Unable to query system health.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void checkStatus()
  }, [])

  // Honest service states
  const apiHealthy = health?.status === 'ok'
  const ragHealthy = ragStatus ? ragStatus.llm_reachable && ragStatus.llm_model_available : false
  const readyHealthy = readiness?.status === 'ready'

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <PageHeader
        title="System Status"
        subtitle="Real-time operational verification of backend services, SQLite datastores, and local AI model runtimes."
        tag="OBSERVABILITY"
        actions={
          <div className="flex items-center gap-3">
            {lastChecked && (
              <span className="text-[11px] text-slate-500 font-mono flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Checked: {lastChecked.toLocaleTimeString()}
              </span>
            )}
            <button
              type="button"
              onClick={() => void checkStatus()}
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition"
            >
              <RefreshCw className={`h-3.5 w-3.5 text-slate-500 ${loading ? 'animate-spin' : ''}`} />
              <span>Probe Health</span>
            </button>
          </div>
        }
      />

      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}

      {/* High-level Status Overview Banner */}
      <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className={`flex h-12 w-12 items-center justify-center rounded-2xl shadow-xs ${
              apiHealthy && readyHealthy
                ? 'bg-emerald-50 text-emerald-600 ring-4 ring-emerald-50/50'
                : 'bg-amber-50 text-amber-600 ring-4 ring-amber-50/50'
            }`}>
              <Activity className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900 font-display">
                {apiHealthy && readyHealthy ? 'All Core Services Operational' : 'Degraded or Initializing Services'}
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                {readyHealthy
                  ? 'FastAPI core, SQLite stores, local Ollama runtime, and embeddings are fully verified.'
                  : 'FastAPI responds to liveness probes, but some dependencies may be cold or initializing.'}
              </p>
            </div>
          </div>

          <StatusBadge
            value={apiHealthy ? (readyHealthy ? 'operational' : 'degraded') : 'unavailable'}
            label={apiHealthy ? (readyHealthy ? 'Fully Ready' : 'Degraded') : 'Offline'}
          />
        </div>
      </div>

      {/* Main Service Nodes Grid */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Node 1: FastAPI API Gateway */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                <Server className="h-4 w-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900 font-display">FastAPI API Gateway</h4>
                <p className="text-[10px] text-slate-400 font-mono">/api/v1/health</p>
              </div>
            </div>
            <StatusBadge value={apiHealthy ? 'operational' : 'unavailable'} />
          </div>

          <div className="mt-4 space-y-2 text-xs text-slate-600">
            <div className="flex justify-between">
              <span className="text-slate-400">Process status:</span>
              <span className="font-mono font-medium text-slate-800">{health?.status ?? 'Not responding'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">CORS origins:</span>
              <span className="font-mono text-[11px] text-slate-700">Configured</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Structured logging:</span>
              <span className="font-mono text-[11px] text-emerald-700 font-semibold">Active with X-Request-ID</span>
            </div>
          </div>
        </div>

        {/* Node 2: Ollama Local LLM */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
                <Bot className="h-4 w-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900 font-display">Ollama Local LLM</h4>
                <p className="text-[10px] text-slate-400 font-mono">http://127.0.0.1:11434</p>
              </div>
            </div>
            <StatusBadge value={ragHealthy ? 'operational' : 'unavailable'} />
          </div>

          <div className="mt-4 space-y-2 text-xs text-slate-600">
            <div className="flex justify-between">
              <span className="text-slate-400">Configured model:</span>
              <span className="font-mono text-[11px] font-bold text-slate-800">{ragStatus?.model_identifier ?? 'Unknown'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Host reachable:</span>
              <span className="font-mono text-[11px] text-slate-700">{ragStatus?.llm_reachable ? 'Yes (HTTP 200)' : 'Unreachable'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Model pulled & loaded:</span>
              <span className="font-mono text-[11px] text-slate-700">{ragStatus?.llm_model_available ? 'Available' : 'Missing'}</span>
            </div>
          </div>
        </div>

        {/* Node 3: Sentence-Transformers Embeddings */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                <Cpu className="h-4 w-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900 font-display">Embedding Model</h4>
                <p className="text-[10px] text-slate-400 font-mono">Hugging Face cache</p>
              </div>
            </div>
            <StatusBadge
              value={ragStatus?.embedding_model_loaded ? 'operational' : 'not_loaded'}
              label={ragStatus?.embedding_model_loaded ? 'Loaded' : 'Cold / On-Demand'}
            />
          </div>

          <div className="mt-4 space-y-2 text-xs text-slate-600">
            <div className="flex justify-between">
              <span className="text-slate-400">Identifier:</span>
              <span className="font-mono text-[11px] text-slate-800">{ragStatus?.embedding_model_identifier ?? 'all-MiniLM-L6-v2'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Memory cache state:</span>
              <span className="font-mono text-[11px] text-slate-700">
                {ragStatus?.embedding_model_loaded ? 'Warm in RAM' : 'Loads on first retrieval'}
              </span>
            </div>
          </div>
        </div>

        {/* Node 4: SQLite Vector Database */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                <Database className="h-4 w-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900 font-display">Vector Index Store</h4>
                <p className="text-[10px] text-slate-400 font-mono">data/index/vector_index.sqlite3</p>
              </div>
            </div>
            <StatusBadge value={ragStatus?.vector_index_exists ? 'operational' : 'unavailable'} />
          </div>

          <div className="mt-4 space-y-2 text-xs text-slate-600">
            <div className="flex justify-between">
              <span className="text-slate-400">Index database exists:</span>
              <span className="font-mono text-[11px] text-slate-800">{ragStatus?.vector_index_exists ? 'Verified' : 'Not found'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Total chunk vectors:</span>
              <span className="font-mono text-[11px] font-bold text-slate-900">{ragStatus?.indexed_chunk_count ?? 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Deep Readiness Dependencies Table (From /api/v1/ready) */}
      <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900 font-display">
              Readiness Dependency Probes
            </h3>
            <p className="text-xs text-slate-500">
              Active probes reported by the backend /api/v1/ready probe
            </p>
          </div>
          <span className="font-mono text-xs text-slate-400 uppercase">
            Overall: {readiness?.status ?? 'pending'}
          </span>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {readiness?.dependencies ? (
            Object.entries(readiness.dependencies).map(([depName, depStatus]) => (
              <div key={depName} className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50/60 p-3">
                <div className="min-w-0 pr-2">
                  <span className="block font-mono text-xs font-bold text-slate-800 capitalize">
                    {depName.replace(/_/g, ' ')}
                  </span>
                  <span className="block font-mono text-[10px] text-slate-400">
                    {depStatus}
                  </span>
                </div>
                <StatusBadge value={depStatus} size="sm" />
              </div>
            ))
          ) : (
            <div className="col-span-full py-4 text-center text-xs text-slate-400">
              Probing dependency matrix...
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
