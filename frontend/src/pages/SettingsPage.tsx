import {
  Info,
  Server,
  User,
} from 'lucide-react'
import type { AuthUser } from '../services/api'
import { PageHeader } from '../components/PageHeader'

interface SettingsPageProps {
  user: AuthUser
}

export function SettingsPage({ user }: SettingsPageProps) {
  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <PageHeader
        title="Settings"
        subtitle="Active session parameters, environment variables, and deployment configuration."
        tag="CONFIGURATION"
      />

      {/* Notice card */}
      <div className="rounded-2xl border border-indigo-100 bg-indigo-50/50 p-4 text-xs text-indigo-900 flex items-start gap-3">
        <Info className="h-5 w-5 text-indigo-600 shrink-0 mt-0.5" />
        <div>
          <p className="font-bold">Environment-Driven Configuration</p>
          <p className="text-indigo-700 mt-0.5 leading-relaxed">
            In this local-first architecture, platform parameters are managed securely via root <code>.env</code> files and deployment overrides. Interactive runtime parameter modification is intentionally restricted to maintain configuration integrity across processes.
          </p>
        </div>
      </div>

      {/* Section 1: Active User Session */}
      <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-600 font-mono mb-4">
          <User className="h-4 w-4" />
          <span>Active Authenticated Session</span>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 text-xs">
          <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3.5">
            <span className="text-slate-400 font-mono block text-[10px] uppercase">User Email</span>
            <span className="font-bold text-slate-800 text-sm mt-0.5 block truncate">{user.email}</span>
          </div>

          <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3.5">
            <span className="text-slate-400 font-mono block text-[10px] uppercase">Assigned Role</span>
            <div className="mt-0.5 flex items-center gap-2">
              <span className="font-bold text-slate-800 text-sm uppercase">{user.role}</span>
              <span className="rounded bg-indigo-100 px-1.5 py-0.2 text-[10px] font-mono font-semibold text-indigo-700">
                {user.role === 'admin' ? 'Full Access' : user.role === 'analyst' ? 'Upload & Query' : 'Read-Only'}
              </span>
            </div>
          </div>

          <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3.5">
            <span className="text-slate-400 font-mono block text-[10px] uppercase">Token Storage</span>
            <span className="font-semibold text-slate-700 mt-0.5 block">SessionStorage (JWT Bearer)</span>
          </div>

          <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3.5">
            <span className="text-slate-400 font-mono block text-[10px] uppercase">Account Created</span>
            <span className="font-semibold text-slate-700 mt-0.5 block">
              {new Date(user.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
      </div>

      {/* Section 2: Environment Settings Overview */}
      <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-600 font-mono mb-4">
          <Server className="h-4 w-4" />
          <span>Application Environment Defaults</span>
        </div>

        <div className="space-y-3">
          {[
            { key: 'VITE_API_BASE_URL', value: 'http://127.0.0.1:8000', note: 'FastAPI gateway address' },
            { key: 'OLLAMA_MODEL', value: 'qwen2.5:0.5b', note: 'Local Ollama model tag' },
            { key: 'EMBEDDING_MODEL', value: 'sentence-transformers/all-MiniLM-L6-v2', note: 'Embedding vector model' },
            { key: 'MAX_UPLOAD_SIZE_BYTES', value: '10,485,760 (10 MB)', note: 'Maximum accepted upload size' },
            { key: 'RAG_MIN_RELEVANCE_SCORE', value: '0.30', note: 'Retrieval cosine similarity threshold' },
            { key: 'ACCESS_TOKEN_TTL_MINUTES', value: '60 minutes', note: 'JWT signing validity lifetime' },
          ].map((item, idx) => (
            <div key={idx} className="flex flex-col sm:flex-row sm:items-center sm:justify-between rounded-xl border border-slate-100 bg-slate-50/50 p-3 text-xs gap-1">
              <div>
                <span className="font-mono font-bold text-slate-800">{item.key}</span>
                <span className="block text-[11px] text-slate-400">{item.note}</span>
              </div>
              <span className="font-mono text-xs font-semibold text-indigo-700 bg-indigo-50/80 border border-indigo-100 px-2 py-0.5 rounded w-fit">
                {item.value}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
