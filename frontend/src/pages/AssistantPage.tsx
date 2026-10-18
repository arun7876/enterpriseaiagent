import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import {
  AlertTriangle,
  Bot,
  ChevronDown,
  ChevronUp,
  Code2,
  FileText,
  LoaderCircle,
  Plus,
  Send,
  Sparkles,
  Table,
  User,
  Workflow,
} from 'lucide-react'
import { apiClient, ApiError } from '../services/api'
import type { AgentAskResponse, AssistantMode, Citation } from '../types'
import { PageHeader } from '../components/PageHeader'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  structuredData?: Array<Record<string, unknown>>
  workflow?: string
  sufficientEvidence?: boolean
  error?: string
  processingTimeMs?: number
}

const EXAMPLE_PROMPTS = [
  { label: 'Document Risks', text: 'What are the main risks mentioned in this report?', mode: 'rag' as AssistantMode },
  { label: 'Leave Policy', text: 'What is the company annual leave policy?', mode: 'rag' as AssistantMode },
  { label: 'Q3 Sales Total', text: 'What were total sales from 2026-09-01 to 2026-09-30?', mode: 'agent' as AssistantMode },
  { label: 'Department Headcount', text: 'What are employee counts by department?', mode: 'agent' as AssistantMode },
]

export function AssistantPage() {
  const [mode, setMode] = useState<AssistantMode>('rag')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedCitations, setExpandedCitations] = useState<Record<string, boolean>>({})
  const [showRawJson, setShowRawJson] = useState<Record<string, boolean>>({})

  const chatBottomRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = async (customPrompt?: string) => {
    const promptToSend = (customPrompt ?? draft).trim()
    if (!promptToSend) {
      setError('Please enter a question.')
      return
    }

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: promptToSend,
    }

    setMessages((prev) => [...prev, userMessage])
    setDraft('')
    setLoading(true)
    setError(null)

    try {
      if (mode === 'rag') {
        const response = await apiClient.askRAG(promptToSend)
        const assistantMessage: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: response.answer,
          citations: response.citations ?? [],
          processingTimeMs: response.processing_time_ms,
        }
        setMessages((prev) => [...prev, assistantMessage])
      } else {
        const response: AgentAskResponse = await apiClient.askAgent(promptToSend, true)
        const assistantMessage: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: response.answer,
          citations: response.citations ?? [],
          structuredData: response.structured_data ?? [],
          workflow: response.workflow,
          sufficientEvidence: response.sufficient_evidence,
          error: response.errors?.length ? response.errors.join('; ') : undefined,
          processingTimeMs: response.processing_time_ms,
        }
        setMessages((prev) => [...prev, assistantMessage])
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'The request could not be completed.'
      setError(msg)
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: 'The assistant could not complete this request. Please check system status or verify that the local Ollama model is ready.',
          error: msg,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSend()
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setError(null)
    setDraft('')
    textareaRef.current?.focus()
  }

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)] max-w-5xl mx-auto">
      <PageHeader
        title="AI Assistant"
        subtitle="Ask grounded questions about your authorized documents or run deterministic analytics queries."
        tag="REASONING & RETRIEVAL"
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleNewChat}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition"
              title="Start a new chat session"
            >
              <Plus className="h-3.5 w-3.5 text-slate-500" />
              New Chat
            </button>
          </div>
        }
      />

      {/* Mode Selector Tabs */}
      <div className="mb-4 flex items-center justify-between border-b border-slate-200/80 pb-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setMode('rag')}
            className={`flex items-center gap-2 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition ${
              mode === 'rag'
                ? 'bg-indigo-600 text-white shadow-2xs'
                : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            <Bot className="h-3.5 w-3.5" />
            <span>RAG Assistant</span>
            <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${mode === 'rag' ? 'bg-indigo-700 text-indigo-100' : 'bg-slate-100 text-slate-500'}`}>
              Documents
            </span>
          </button>

          <button
            type="button"
            onClick={() => setMode('agent')}
            className={`flex items-center gap-2 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition ${
              mode === 'agent'
                ? 'bg-indigo-600 text-white shadow-2xs'
                : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            <Workflow className="h-3.5 w-3.5" />
            <span>Enterprise Agent</span>
            <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${mode === 'agent' ? 'bg-indigo-700 text-indigo-100' : 'bg-slate-100 text-slate-500'}`}>
              Docs + SQL
            </span>
          </button>
        </div>

        <span className="hidden sm:inline-block text-[11px] text-slate-500 font-mono">
          {mode === 'rag' ? 'Semantic vector retrieval only' : 'LangGraph agent router'}
        </span>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1 pb-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center shadow-card">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 mb-3 shadow-xs">
              <Sparkles className="h-6 w-6" />
            </div>
            <h3 className="text-base font-bold text-slate-900 font-display">
              {mode === 'rag' ? 'Document Research Assistant' : 'Enterprise Multi-Tool Agent'}
            </h3>
            <p className="mt-1 text-xs text-slate-500 max-w-md leading-relaxed">
              {mode === 'rag'
                ? 'Ask questions about your uploaded PDFs, Word documents, or CSV spreadsheets. Answers include verifiable source citations.'
                : 'Ask questions that span private documents or business data metrics (sales, departments, headcounts). The LangGraph router selects the appropriate tool.'}
            </p>

            {/* Example Prompt Chips */}
            <div className="mt-6 w-full max-w-lg">
              <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 font-mono mb-2">
                Suggested Prompts
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {EXAMPLE_PROMPTS.filter((p) => p.mode === mode || p.mode === 'rag').map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setDraft(item.text)
                      textareaRef.current?.focus()
                    }}
                    className="flex flex-col text-left rounded-xl border border-slate-200/80 bg-slate-50/60 p-2.5 hover:border-indigo-200 hover:bg-indigo-50/40 transition group"
                  >
                    <span className="text-[11px] font-bold text-slate-800 group-hover:text-indigo-900">
                      {item.label}
                    </span>
                    <span className="text-[10px] text-slate-500 truncate mt-0.5">
                      {item.text}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`flex gap-3 rounded-2xl p-4 transition-all shadow-card ${
                message.role === 'user'
                  ? 'border border-indigo-100 bg-indigo-50/40 ml-8 sm:ml-16'
                  : 'border border-slate-200/80 bg-white mr-8 sm:mr-16'
              }`}
            >
              <div
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl shadow-2xs ${
                  message.role === 'user'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-900 text-indigo-300'
                }`}
              >
                {message.role === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-900 font-display">
                      {message.role === 'user' ? 'You' : mode === 'agent' ? 'Enterprise Agent' : 'RAG Assistant'}
                    </span>
                    {message.workflow && (
                      <span className="text-[10px] font-mono font-semibold uppercase px-1.5 py-0.2 rounded bg-slate-100 text-slate-600">
                        {message.workflow}
                      </span>
                    )}
                  </div>
                  {message.processingTimeMs !== undefined && (
                    <span className="text-[10px] font-mono text-slate-400">
                      {message.processingTimeMs.toFixed(0)} ms
                    </span>
                  )}
                </div>

                <div className="text-xs md:text-sm text-slate-800 whitespace-pre-wrap leading-relaxed">
                  {message.content}
                </div>

                {/* Insufficient Evidence Warning Banner */}
                {message.sufficientEvidence === false && (
                  <div className="mt-3 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-800">
                    <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
                    <div>
                      <p className="font-semibold">Insufficient Evidence Found</p>
                      <p className="text-[11px] text-amber-700 mt-0.5">
                        The retrieved documents did not contain sufficient verifiable context to conclusively answer this query without speculation.
                      </p>
                    </div>
                  </div>
                )}

                {/* Error Banner */}
                {message.error && (
                  <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-800">
                    {message.error}
                  </div>
                )}

                {/* Structured Data Table for Agent queries */}
                {message.structuredData && message.structuredData.length > 0 && (
                  <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/60 p-3">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 font-mono">
                        <Table className="h-3.5 w-3.5 text-indigo-600" />
                        <span>Structured SQL Results ({message.structuredData.length} row{message.structuredData.length !== 1 ? 's' : ''})</span>
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          setShowRawJson((prev) => ({
                            ...prev,
                            [message.id]: !prev[message.id],
                          }))
                        }
                        className="flex items-center gap-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-800"
                      >
                        <Code2 className="h-3 w-3" />
                        <span>{showRawJson[message.id] ? 'Table View' : 'Raw JSON'}</span>
                      </button>
                    </div>

                    {showRawJson[message.id] ? (
                      <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-[11px] text-emerald-400">
                        {JSON.stringify(message.structuredData, null, 2)}
                      </pre>
                    ) : (
                      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                        <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                          <thead className="bg-slate-50 font-semibold text-slate-700">
                            <tr>
                              {Object.keys(message.structuredData[0]).map((key) => (
                                <th key={key} className="px-3 py-2 font-mono text-[11px]">
                                  {key}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {message.structuredData.map((row, rIdx) => (
                              <tr key={rIdx} className="hover:bg-slate-50/50">
                                {Object.entries(row).map(([k, v], cIdx) => (
                                  <td key={cIdx} className="px-3 py-2 font-mono text-slate-700 text-[11px]">
                                    {typeof v === 'number' && k.includes('usd')
                                      ? `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                                      : String(v)}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {/* Granular Source Citations */}
                {message.citations && message.citations.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400 font-mono">
                      <FileText className="h-3 w-3" />
                      <span>Verified Citations ({message.citations.length})</span>
                    </div>

                    <div className="space-y-1.5">
                      {message.citations.map((citation) => {
                        const citKey = `${message.id}-${citation.source_id}-${citation.chunk_id}`
                        const isExpanded = expandedCitations[citKey]

                        return (
                          <div
                            key={citKey}
                            className="rounded-xl border border-slate-200 bg-slate-50/70 p-2.5 transition hover:bg-slate-50"
                          >
                            <button
                              type="button"
                              onClick={() =>
                                setExpandedCitations((prev) => ({
                                  ...prev,
                                  [citKey]: !isExpanded,
                                }))
                              }
                              className="flex w-full items-center justify-between gap-3 text-left"
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                <FileText className="h-3.5 w-3.5 text-indigo-600 shrink-0" />
                                <span className="font-semibold text-xs text-slate-800 truncate" title={citation.filename}>
                                  {citation.filename}
                                </span>
                                {citation.page_number !== null && (
                                  <span className="text-[10px] font-mono bg-white border border-slate-200 text-slate-600 px-1.5 py-0.2 rounded">
                                    Page {citation.page_number}
                                  </span>
                                )}
                              </div>

                              <div className="flex items-center gap-2 shrink-0">
                                <span className="text-[10px] font-mono font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.2 rounded">
                                  Score: {(citation.relevance_score * 100).toFixed(0)}%
                                </span>
                                {isExpanded ? (
                                  <ChevronUp className="h-3.5 w-3.5 text-slate-400" />
                                ) : (
                                  <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
                                )}
                              </div>
                            </button>

                            {isExpanded && (
                              <div className="mt-2 rounded-lg bg-white border border-slate-200/80 p-2.5 text-xs text-slate-700 leading-relaxed font-sans">
                                <div className="text-[10px] font-bold text-slate-400 font-mono uppercase mb-1">
                                  Retrieved Passage Excerpt (Chunk #{citation.chunk_index}):
                                </div>
                                <blockquote className="italic border-l-2 border-indigo-400 pl-2 text-slate-600">
                                  "{citation.excerpt}"
                                </blockquote>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {/* Loading Indicator */}
        {loading && (
          <div className="flex items-center gap-3 rounded-2xl border border-indigo-100 bg-white p-4 shadow-card mr-8 sm:mr-16">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-900 text-indigo-300">
              <Bot className="h-4 w-4" />
            </div>
            <div className="flex items-center gap-2 text-xs font-medium text-slate-600">
              <LoaderCircle className="h-4 w-4 animate-spin text-indigo-600" />
              <span>
                {mode === 'rag'
                  ? 'Searching authorized document vectors & synthesizing answer...'
                  : 'LangGraph agent evaluating question & invoking tools...'}
              </span>
            </div>
          </div>
        )}

        <div ref={chatBottomRef} />
      </div>

      {/* Input Box Footer */}
      <div className="mt-auto pt-2">
        {error && (
          <div className="mb-2 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-3 py-1.5">
            {error}
          </div>
        )}

        <div className="rounded-2xl border border-slate-200/80 bg-white p-2 shadow-soft focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-100 transition">
          <textarea
            ref={textareaRef}
            rows={2}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            placeholder={
              mode === 'rag'
                ? 'Ask a question about your uploaded documents (Enter to send, Shift+Enter for new line)...'
                : 'Ask a question about documents or business metrics (e.g. sales, employee counts)...'
            }
            className="w-full resize-none border-0 bg-transparent px-3 py-2 text-xs md:text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none"
          />

          <div className="flex items-center justify-between border-t border-slate-100 pt-2 px-2">
            <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
              <span>Shift+Enter: newline</span>
              <span>&bull;</span>
              <span>Enter: send</span>
            </div>

            <button
              type="button"
              onClick={() => void handleSend()}
              disabled={loading || !draft.trim()}
              className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-1.5 text-xs font-semibold text-white shadow-2xs hover:bg-indigo-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              <span>Send</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
