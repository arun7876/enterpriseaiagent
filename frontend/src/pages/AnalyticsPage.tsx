import { useState } from 'react'
import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  Code2,
  Database,
  LoaderCircle,
  Play,
  Table,
} from 'lucide-react'
import { apiClient, ApiError } from '../services/api'
import type { AgentAskResponse } from '../types'
import { PageHeader } from '../components/PageHeader'

const QUERY_TEMPLATES = [
  {
    category: 'Sales Analytics',
    title: 'September 2026 Total Sales',
    prompt: 'What were total sales from 2026-09-01 to 2026-09-30?',
    tool: 'total_sales',
  },
  {
    category: 'Department Breakdown',
    title: 'Sales by Department (Aug - Oct)',
    prompt: 'Show sales by department from 2026-08-01 to 2026-10-31',
    tool: 'sales_by_department',
  },
  {
    category: 'Human Resources',
    title: 'Employee Headcounts by Department',
    prompt: 'What are employee counts by department?',
    tool: 'employee_counts_by_department',
  },
  {
    category: 'Transaction Ledger',
    title: 'Recent Sales Transactions',
    prompt: 'List recent sales transactions between 2026-09-01 and 2026-09-30',
    tool: 'list_sales_transactions',
  },
]

export function AnalyticsPage() {
  const [question, setQuestion] = useState('What were total sales from 2026-09-01 to 2026-09-30?')
  const [result, setResult] = useState<AgentAskResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showRawJson, setShowRawJson] = useState(false)

  const runQuestion = async (customQuestion?: string) => {
    const q = (customQuestion ?? question).trim()
    if (!q) {
      setError('Enter a business analytics question.')
      return
    }

    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.askAgent(q, true)
      setResult(response)
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'The analytics workflow failed.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const formatCellValue = (key: string, val: unknown) => {
    if (typeof val === 'number') {
      if (key.toLowerCase().includes('usd') || key.toLowerCase().includes('amount') || key.toLowerCase().includes('cents')) {
        return `$${val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
      }
      return val.toLocaleString()
    }
    return String(val ?? '—')
  }

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <PageHeader
        title="Data Analytics"
        subtitle="Deterministic business insights executed over read-only SQLite database tables with strict schema guards."
        tag="SQL TOOLS"
      />

      {/* Query Templates Carousel/Grid */}
      <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-indigo-600" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 font-mono">
              Allowlisted Query Templates
            </h3>
          </div>
          <span className="text-[11px] text-slate-400 font-mono">
            departments &bull; employees &bull; sales
          </span>
        </div>

        <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
          {QUERY_TEMPLATES.map((tmpl, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                setQuestion(tmpl.prompt)
                void runQuestion(tmpl.prompt)
              }}
              className="flex flex-col text-left rounded-xl border border-slate-200/80 bg-slate-50/50 p-3 hover:border-indigo-300 hover:bg-indigo-50/30 transition group shadow-2xs"
            >
              <div className="flex items-center justify-between w-full">
                <span className="text-[10px] font-mono font-bold uppercase text-indigo-600 bg-indigo-50 px-1.5 py-0.2 rounded">
                  {tmpl.tool}
                </span>
                <Play className="h-3 w-3 text-slate-400 group-hover:text-indigo-600 transition-transform group-hover:translate-x-0.5" />
              </div>
              <h4 className="mt-2 text-xs font-bold text-slate-900 group-hover:text-indigo-900">
                {tmpl.title}
              </h4>
              <p className="mt-1 text-[11px] text-slate-500 line-clamp-2">
                {tmpl.prompt}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Query Input Box */}
      <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
        <label className="block text-xs font-bold text-slate-800 font-display mb-2">
          Analytics Question (Natural Language Query)
        </label>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          placeholder="e.g. What were total sales from 2026-09-01 to 2026-09-30?"
          className="w-full resize-none rounded-xl border border-slate-200 bg-slate-50/60 p-3 text-xs md:text-sm text-slate-800 placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-100 transition"
        />

        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-500 font-mono">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
            <span>Strict read-only isolation (PRAGMA query_only = ON)</span>
          </div>

          <button
            type="button"
            onClick={() => void runQuestion()}
            disabled={loading || !question.trim()}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-indigo-700 transition disabled:opacity-50"
          >
            {loading ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <BarChart3 className="h-3.5 w-3.5" />}
            <span>{loading ? 'Evaluating Query...' : 'Run Analytics'}</span>
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}

      {/* Query Execution Result */}
      {result && (
        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-slate-900 font-display">
                Execution Output
              </span>
              <span className="rounded-md bg-indigo-50 border border-indigo-100 px-2 py-0.5 text-[10px] font-mono font-bold text-indigo-700 uppercase">
                {result.workflow}
              </span>
            </div>

            {result.selected_tools && result.selected_tools.length > 0 && (
              <div className="flex items-center gap-1">
                <span className="text-[10px] text-slate-400 font-mono uppercase">Tool:</span>
                {result.selected_tools.map((t) => (
                  <span key={t} className="rounded bg-slate-100 px-1.5 py-0.2 text-[10px] font-mono font-semibold text-slate-700">
                    {t}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Natural language summary */}
          <div className="rounded-xl border border-indigo-50 bg-indigo-50/30 p-4 text-xs md:text-sm text-slate-800 leading-relaxed font-sans">
            <p className="font-bold text-xs uppercase text-indigo-700 font-mono mb-1">Synthesis:</p>
            <p>{result.answer}</p>
          </div>

          {/* Structured SQL Data Table */}
          {result.structured_data && result.structured_data.length > 0 ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-700 font-mono uppercase flex items-center gap-1.5">
                  <Table className="h-3.5 w-3.5 text-indigo-600" />
                  <span>Structured Query Rows ({result.structured_data.length})</span>
                </span>
                <button
                  type="button"
                  onClick={() => setShowRawJson(!showRawJson)}
                  className="flex items-center gap-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 transition"
                >
                  <Code2 className="h-3.5 w-3.5" />
                  <span>{showRawJson ? 'Render Table' : 'Raw JSON'}</span>
                </button>
              </div>

              {showRawJson ? (
                <pre className="overflow-x-auto rounded-xl bg-slate-950 p-4 text-[11px] font-mono text-emerald-400">
                  {JSON.stringify(result.structured_data, null, 2)}
                </pre>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-slate-200">
                  <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                    <thead className="bg-slate-50 font-mono font-bold text-slate-700 uppercase tracking-wider text-[11px]">
                      <tr>
                        {Object.keys(result.structured_data[0]).map((col) => (
                          <th key={col} className="px-4 py-3">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                      {result.structured_data.map((row, rIdx) => (
                        <tr key={rIdx} className="hover:bg-slate-50/60 transition">
                          {Object.entries(row).map(([k, v], cIdx) => (
                            <td key={cIdx} className="px-4 py-2.5 font-mono text-slate-800 text-[11px]">
                              {formatCellValue(k, v)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-6 text-center text-xs text-slate-500">
              No tabular SQL rows were returned for this question. The response was answered via semantic retrieval or general synthesis.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
