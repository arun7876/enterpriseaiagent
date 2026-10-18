import { Link } from 'react-router-dom'
import {
  Activity,
  BookOpen,
  Bot,
  CheckCircle2,
  Cpu,
  Database,
  FileSearch,
  FileText,
  Lock,
  Network,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Terminal,
  UploadCloud,
  Workflow,
} from 'lucide-react'
import { PageHeader } from '../components/PageHeader'

export function AboutProjectPage() {
  const scrollToArchitecture = () => {
    const el = document.getElementById('architecture')
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' })
    }
  }

  return (
    <div className="space-y-12 pb-16">
      <PageHeader
        title="About This Project"
        subtitle="Architecture, capabilities, and practical workflows for the Enterprise AI Research Agent."
        tag="DOCUMENTATION & GUIDE"
      />

      {/* A. Hero Section */}
      <section className="relative overflow-hidden rounded-3xl border border-indigo-100 bg-linear-to-br from-indigo-50/80 via-white to-slate-50 p-8 md:p-12 shadow-soft">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200/80 bg-white px-3 py-1 text-xs font-semibold text-indigo-700 shadow-2xs">
            <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
            <span>Local-First Enterprise Intelligence</span>
          </div>

          <h1 className="mt-4 text-3xl font-extrabold tracking-tight text-slate-900 md:text-5xl font-display leading-[1.15]">
            Enterprise AI Research Agent
          </h1>

          <p className="mt-4 text-base md:text-lg text-slate-600 leading-relaxed font-sans">
            An AI-powered research workspace that searches your documents, generates evidence-based answers, and supports secure business-data analysis.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3.5">
            <Link
              to="/assistant"
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 transition"
            >
              <Bot className="h-4 w-4" />
              Try AI Assistant
            </Link>
            <Link
              to="/documents"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 shadow-xs hover:bg-slate-50 hover:text-slate-900 transition"
            >
              <UploadCloud className="h-4 w-4 text-indigo-600" />
              Upload a Document
            </Link>
            <button
              type="button"
              onClick={scrollToArchitecture}
              className="inline-flex items-center gap-2 rounded-xl border border-indigo-100 bg-indigo-50/60 px-5 py-3 text-sm font-semibold text-indigo-700 hover:bg-indigo-100/70 transition"
            >
              <Network className="h-4 w-4" />
              Explore Architecture
            </button>
          </div>
        </div>
      </section>

      {/* B. Project Overview */}
      <section className="rounded-2xl border border-slate-200/80 bg-white p-6 md:p-8 shadow-card">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-600 font-mono mb-2">
          <BookOpen className="h-4 w-4" />
          <span>PROJECT OVERVIEW</span>
        </div>
        <h2 className="text-xl md:text-2xl font-bold text-slate-900 font-display">
          Private Document Research Meets Constrained Business Analytics
        </h2>
        <div className="mt-4 grid gap-6 md:grid-cols-2 text-sm text-slate-600 leading-relaxed">
          <p>
            The Enterprise AI Research Agent is engineered for knowledge workers who need dependable, grounded insights from enterprise files without sending sensitive company data to third-party public clouds. Users can upload business documents (PDF, DOCX, and CSV) into an isolated catalog.
          </p>
          <p>
            When a question is asked, the system retrieves only relevant text passages authorized for the authenticated user, assembling exact citations so every assertion can be verified. In addition, an integrated LangGraph agent routes between document search and safe, allowlisted SQL queries to compute deterministic metrics.
          </p>
        </div>
      </section>

      {/* C. Key Features */}
      <section>
        <div className="mb-6">
          <p className="text-xs font-bold uppercase tracking-wider text-indigo-600 font-mono">
            CORE CAPABILITIES
          </p>
          <h2 className="text-xl md:text-2xl font-bold text-slate-900 font-display mt-1">
            Engineered for Grounded Accuracy & Control
          </h2>
          <p className="text-xs md:text-sm text-slate-500 mt-1">
            Every feature below is implemented in the repository code and tested.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            {
              icon: UploadCloud,
              title: 'Document Ingestion',
              desc: 'Supports PDF, DOCX, and CSV formats with a configurable 10 MB limit. Extracts text, normalizes content, and manages private uploads.',
              tag: 'INGESTION',
            },
            {
              icon: FileSearch,
              title: 'Semantic Vector Search',
              desc: 'Sentence-transformers (all-MiniLM-L6-v2) embedding model combined with a persistent SQLite vector index and cosine similarity.',
              tag: 'RETRIEVAL',
            },
            {
              icon: Bot,
              title: 'RAG Question Answering',
              desc: 'Grounded generation constructing model prompts exclusively from passages the current user is authorized to read.',
              tag: 'SYNTHESIS',
            },
            {
              icon: FileText,
              title: 'Granular Source Citations',
              desc: 'Every generated answer includes citations containing source filename, chunk index, page number, and verifiable excerpt.',
              tag: 'AUDITABILITY',
            },
            {
              icon: Workflow,
              title: 'LangGraph AI Agent',
              desc: 'A stateful workflow graph that decides whether a query requires semantic document retrieval, business SQL tools, or both.',
              tag: 'ORCHESTRATION',
            },
            {
              icon: Database,
              title: 'Safe Business Analytics',
              desc: 'Strictly allowlisted, parameterized SQL tools over departments, employees, and sales tables with query timeouts and read-only mode.',
              tag: 'SQL LAYER',
            },
            {
              icon: Lock,
              title: 'Authentication & RBAC',
              desc: 'Role-based access control (Admin, Analyst, Viewer) using secure bcrypt password hashing and signed JWT bearer tokens.',
              tag: 'SECURITY',
            },
            {
              icon: ShieldCheck,
              title: 'Document Privacy & Isolation',
              desc: 'Document catalog records ownership and share lists. Vector searches filter strictly on allowed document IDs.',
              tag: 'ISOLATION',
            },
            {
              icon: Cpu,
              title: 'Local Model Inference',
              desc: 'Direct HTTP integration with local Ollama runtime (qwen2.5:0.5b). Zero model payloads leave the local host.',
              tag: 'PRIVACY',
            },
            {
              icon: Activity,
              title: 'Observability & Monitoring',
              desc: 'Structured JSON logging, correlation IDs (X-Request-ID) for tracing, ready/liveness probes, and full Pytest verification.',
              tag: 'OPS',
            },
          ].map((feature, i) => (
            <div
              key={i}
              className="flex flex-col justify-between rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card transition-all hover:border-indigo-200 hover:shadow-soft"
            >
              <div>
                <div className="flex items-center justify-between">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                    <feature.icon className="h-4 w-4" />
                  </div>
                  <span className="font-mono text-[10px] font-bold text-slate-400 bg-slate-50 px-2 py-0.5 rounded border border-slate-100">
                    {feature.tag}
                  </span>
                </div>
                <h3 className="mt-3 text-sm font-bold text-slate-900 font-display">
                  {feature.title}
                </h3>
                <p className="mt-1.5 text-xs text-slate-500 leading-relaxed">
                  {feature.desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* D. How to Use the Application (Step-by-Step Guide) */}
      <section className="rounded-2xl border border-slate-200/80 bg-white p-6 md:p-8 shadow-card">
        <div className="mb-8">
          <p className="text-xs font-bold uppercase tracking-wider text-indigo-600 font-mono">
            USER GUIDE
          </p>
          <h2 className="text-xl md:text-2xl font-bold text-slate-900 font-display mt-1">
            How to Use the Enterprise AI Research Agent
          </h2>
          <p className="text-xs md:text-sm text-slate-500 mt-1">
            Follow this 7-step guide to conduct verified research and run business analytics.
          </p>
        </div>

        <div className="space-y-6">
          {[
            {
              step: 'Step 1',
              title: 'Sign In and Check Role Permissions',
              desc: 'Log in or register an account. In development mode, registration automatically provisions an Analyst account. Analysts can upload files and query; Admins can view all documents; Viewers have read-only access to shared content.',
              action: 'Visit Overview or Settings to view your active role and permissions.',
            },
            {
              step: 'Step 2',
              title: 'Upload Business Documents',
              desc: 'Navigate to Documents. Select or drag-and-drop a supported PDF, DOCX, or CSV file. Files must be within the 10 MB upload ceiling. Viewers will see a read-only message.',
              action: 'Try uploading a policy document, financial statement, or project briefing.',
            },
            {
              step: 'Step 3',
              title: 'Wait for Ingestion & Vector Indexing',
              desc: 'The backend extracts plain text, partitions it into semantic chunks, computes sentence-transformer embeddings, and updates the SQLite vector index. The indexing status badge shows "indexed" once ready.',
              action: 'Confirm the document status badge turns green in the Documents table.',
            },
            {
              step: 'Step 4',
              title: 'Ask a Question in AI Assistant',
              desc: 'Open AI Assistant. Select RAG Assistant (document-grounded) or Enterprise Agent (documents + SQL tools). Type your question in plain English.',
              action: 'Example: "What are the key compliance requirements outlined in the policy?"',
            },
            {
              step: 'Step 5',
              title: 'Verify the Answer and Citations',
              desc: 'Review the generated answer and examine each citation card. Expand citations to inspect the source filename, page number, and verbatim excerpt to verify critical facts against the original text.',
              action: 'Always cross-reference critical business decisions against the source excerpts.',
            },
            {
              step: 'Step 6',
              title: 'Execute Safe Business Data Analytics',
              desc: 'Use the Data Analytics tab or the Enterprise Agent to query deterministic business data. The agent executes allowlisted SQL queries without arbitrary database execution risk.',
              action: 'Example: "What were total sales from 2026-09-01 to 2026-09-30?" or "Show employee counts by department."',
            },
            {
              step: 'Step 7',
              title: 'Manage Documents and Permissions',
              desc: 'Inspect your authorized catalog in the Documents page. Document permissions ensure that retrieval never leaks unshared documents across users.',
              action: 'Track chunk counts and upload timestamps across your catalog.',
            },
          ].map((item, idx) => (
            <div key={idx} className="flex flex-col md:flex-row md:items-start gap-4 rounded-xl border border-slate-100 bg-slate-50/50 p-4 transition hover:bg-slate-50">
              <div className="flex h-8 w-16 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-xs font-bold text-white font-mono shadow-2xs">
                {item.step}
              </div>
              <div className="flex-1">
                <h3 className="text-sm font-bold text-slate-900 font-display">
                  {item.title}
                </h3>
                <p className="mt-1 text-xs text-slate-600 leading-relaxed">
                  {item.desc}
                </p>
                <div className="mt-2.5 flex items-center gap-2 text-[11px] font-semibold text-indigo-700 bg-indigo-50/70 px-2.5 py-1 rounded-md border border-indigo-100 w-fit">
                  <CheckCircle2 className="h-3 w-3 shrink-0" />
                  <span>{item.action}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Tips Box */}
        <div className="mt-8 rounded-xl border border-amber-200 bg-amber-50/50 p-4">
          <div className="flex items-center gap-2 text-xs font-bold text-amber-900 mb-1 font-mono">
            <ShieldAlert className="h-4 w-4 text-amber-600" />
            <span>PRO-TIPS FOR GROUNDED RESEARCH</span>
          </div>
          <ul className="mt-2 space-y-1.5 text-xs text-amber-800 list-disc list-inside">
            <li><strong>Be specific:</strong> Ask targeted questions mentioning entities, dates, or sections for higher retrieval precision.</li>
            <li><strong>Insufficient Evidence:</strong> When documents do not contain enough facts, the model will honestly report insufficient evidence rather than hallucinating answers.</li>
            <li><strong>Analytics Date Format:</strong> Use ISO 8601 dates (e.g. <code>YYYY-MM-DD</code>) for analytics queries.</li>
          </ul>
        </div>
      </section>

      {/* E. Architecture Overview */}
      <section id="architecture" className="rounded-2xl border border-slate-200/80 bg-white p-6 md:p-8 shadow-card scroll-mt-6">
        <div className="mb-6">
          <p className="text-xs font-bold uppercase tracking-wider text-indigo-600 font-mono">
            SYSTEM ARCHITECTURE
          </p>
          <h2 className="text-xl md:text-2xl font-bold text-slate-900 font-display mt-1">
            End-to-End Information Flow
          </h2>
          <p className="text-xs md:text-sm text-slate-500 mt-1">
            Data flow diagram showing the isolated document processing and LangGraph agent pipelines.
          </p>
        </div>

        {/* Visual Architecture Flow Diagram */}
        <div className="rounded-2xl border border-slate-200 bg-slate-950 p-6 text-white shadow-soft">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
            <span className="text-xs font-bold uppercase tracking-widest text-indigo-400 font-mono">
              ARCHITECTURE SCHEMATIC
            </span>
            <span className="text-[11px] text-slate-400 font-mono">
              FastAPI &bull; LangGraph &bull; SQLite &bull; Ollama
            </span>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            {/* Column 1: Client & Ingestion */}
            <div className="space-y-4">
              <div className="text-xs font-bold uppercase tracking-wider text-indigo-300 font-mono">
                1. Client & Ingestion
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5">
                <div className="text-xs font-bold text-white">React 19 & Vite UI</div>
                <div className="text-[11px] text-slate-400 mt-1">JWT Bearer auth header &bull; Lucide icons</div>
              </div>

              <div className="text-center text-slate-500 text-xs">&darr; HTTP POST /upload</div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5">
                <div className="text-xs font-bold text-white">FastAPI Auth & RBAC</div>
                <div className="text-[11px] text-slate-400 mt-1">Role checks (Admin, Analyst, Viewer) &bull; Token validation</div>
              </div>

              <div className="text-center text-slate-500 text-xs">&darr; Extracted Text</div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5">
                <div className="text-xs font-bold text-white">Private Storage & Catalog</div>
                <div className="text-[11px] text-slate-400 mt-1">Upload directory &bull; SQLite document catalog</div>
              </div>
            </div>

            {/* Column 2: Vector & RAG */}
            <div className="space-y-4">
              <div className="text-xs font-bold uppercase tracking-wider text-blue-300 font-mono">
                2. Semantic Vector Pipeline
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5">
                <div className="text-xs font-bold text-white">Sentence-Transformers</div>
                <div className="text-[11px] text-slate-400 mt-1">all-MiniLM-L6-v2 embeddings &bull; Local CPU inference</div>
              </div>

              <div className="text-center text-slate-500 text-xs">&darr; Cosine Similarity Search</div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5">
                <div className="text-xs font-bold text-white">SQLite Vector Store</div>
                <div className="text-[11px] text-slate-400 mt-1">Filtered by user's authorized document IDs</div>
              </div>

              <div className="text-center text-slate-500 text-xs">&darr; Evidence Passages</div>

              <div className="rounded-xl border border-indigo-950/80 border-indigo-800/50 bg-indigo-950/40 p-3.5">
                <div className="text-xs font-bold text-indigo-200">Local Ollama LLM</div>
                <div className="text-[11px] text-indigo-300/80 mt-1">qwen2.5:0.5b &bull; Strict citation-grounded synthesis</div>
              </div>
            </div>

            {/* Column 3: LangGraph & SQL Tools */}
            <div className="space-y-4">
              <div className="text-xs font-bold uppercase tracking-wider text-emerald-300 font-mono">
                3. LangGraph & SQL Tools
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5">
                <div className="text-xs font-bold text-white">LangGraph Orchestrator</div>
                <div className="text-[11px] text-slate-400 mt-1">StateGraph router &bull; Document search vs SQL selection</div>
              </div>

              <div className="text-center text-slate-500 text-xs">&darr; Tool Execution</div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5">
                <div className="text-xs font-bold text-white">Safe SQL Tools Allowlist</div>
                <div className="text-[11px] text-slate-400 mt-1">total_sales &bull; sales_by_dept &bull; employee_counts</div>
              </div>

              <div className="text-center text-slate-500 text-xs">&darr; Read-Only Execution</div>

              <div className="rounded-xl border border-emerald-950/80 border-emerald-800/50 bg-emerald-950/40 p-3.5">
                <div className="text-xs font-bold text-emerald-200">Business SQLite DB</div>
                <div className="text-[11px] text-emerald-300/80 mt-1">PRAGMA query_only=ON &bull; Execution timeout progress handler</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* F. Technology Stack */}
      <section className="rounded-2xl border border-slate-200/80 bg-white p-6 md:p-8 shadow-card">
        <div className="mb-6">
          <p className="text-xs font-bold uppercase tracking-wider text-indigo-600 font-mono">
            VERIFIED STACK
          </p>
          <h2 className="text-xl md:text-2xl font-bold text-slate-900 font-display mt-1">
            Technology Specifications
          </h2>
          <p className="text-xs md:text-sm text-slate-500 mt-1">
            Directly verified against repository configuration and package manifests.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { name: 'Python 3.13', role: 'Backend Runtime', badge: 'v3.13.3' },
            { name: 'FastAPI', role: 'REST API & Middleware', badge: 'v0.115+' },
            { name: 'LangGraph', role: 'Agent Workflow Graph', badge: 'LangChain' },
            { name: 'SQLite', role: 'Auth, Docs, Vectors & SQL', badge: 'Native DB' },
            { name: 'Sentence-Transformers', role: 'all-MiniLM-L6-v2', badge: 'HuggingFace' },
            { name: 'Ollama', role: 'qwen2.5:0.5b', badge: 'Local Host' },
            { name: 'React 19 & Vite', role: 'Dashboard UI', badge: 'React 19.2' },
            { name: 'TailwindCSS', role: 'Styling & Design System', badge: 'v3.4' },
          ].map((tech, i) => (
            <div key={i} className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 p-3">
              <div>
                <span className="block text-xs font-bold text-slate-800">{tech.name}</span>
                <span className="block text-[11px] text-slate-500">{tech.role}</span>
              </div>
              <span className="font-mono text-[10px] font-semibold text-indigo-700 bg-indigo-50 border border-indigo-100 px-1.5 py-0.5 rounded">
                {tech.badge}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* G. Security and Limitations */}
      <section className="rounded-2xl border border-slate-200/80 bg-white p-6 md:p-8 shadow-card">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-600 font-mono mb-2">
          <ShieldAlert className="h-4 w-4" />
          <span>SECURITY & SYSTEM LIMITATIONS</span>
        </div>
        <h2 className="text-xl md:text-2xl font-bold text-slate-900 font-display">
          Security Boundary & Operational Guardrails
        </h2>

        <div className="mt-4 grid gap-4 md:grid-cols-2 text-xs md:text-sm text-slate-600 leading-relaxed">
          <div className="rounded-xl border border-slate-200/80 p-4 bg-slate-50/50">
            <h3 className="font-bold text-slate-900 flex items-center gap-2 mb-1.5">
              <Lock className="h-4 w-4 text-indigo-600" />
              Access Control & User Isolation
            </h3>
            <p className="text-xs text-slate-600">
              Authentication is required for all data and AI endpoints. Users can only retrieve documents they own or have been explicitly granted permission to read. Viewers cannot upload or mutate files.
            </p>
          </div>

          <div className="rounded-xl border border-slate-200/80 p-4 bg-slate-50/50">
            <h3 className="font-bold text-slate-900 flex items-center gap-2 mb-1.5">
              <Scale className="h-4 w-4 text-amber-600" />
              Probabilistic Model Limitations
            </h3>
            <p className="text-xs text-slate-600">
              AI outputs are probabilistic syntheses. While citations ground claims in retrieved excerpts, users must verify high-stakes business or legal decisions against the original source documents.
            </p>
          </div>

          <div className="rounded-xl border border-slate-200/80 p-4 bg-slate-50/50">
            <h3 className="font-bold text-slate-900 flex items-center gap-2 mb-1.5">
              <Cpu className="h-4 w-4 text-blue-600" />
              Local Hardware Dependency
            </h3>
            <p className="text-xs text-slate-600">
              Embedding and generation run on the local host. Inference latency depends directly on available CPU threads, RAM, and Ollama background load. Cold embedding models require a warmup query.
            </p>
          </div>

          <div className="rounded-xl border border-slate-200/80 p-4 bg-slate-50/50">
            <h3 className="font-bold text-slate-900 flex items-center gap-2 mb-1.5">
              <Database className="h-4 w-4 text-emerald-600" />
              Constrained SQL Boundary
            </h3>
            <p className="text-xs text-slate-600">
              The agent does not have arbitrary SQL execution privileges. Queries are restricted to predefined parameter schemas executed over a separate read-only connection with strict execution timeouts.
            </p>
          </div>
        </div>
      </section>

      {/* H. Developer Information & Technical Reference */}
      <section className="rounded-2xl border border-slate-200/80 bg-white p-6 md:p-8 shadow-card">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-600 font-mono mb-2">
          <Terminal className="h-4 w-4" />
          <span>TECHNICAL REFERENCE</span>
        </div>
        <h2 className="text-xl md:text-2xl font-bold text-slate-900 font-display">
          Local Development Commands & API Endpoints
        </h2>

        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {/* CLI Commands */}
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 text-white">
            <span className="text-[11px] font-bold text-slate-400 font-mono uppercase tracking-wider block mb-2">
              PowerShell Commands
            </span>
            <div className="space-y-3 font-mono text-xs">
              <div>
                <p className="text-slate-400 text-[11px]"># Backend server</p>
                <p className="text-emerald-400">.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000</p>
              </div>
              <div>
                <p className="text-slate-400 text-[11px]"># Frontend dev server</p>
                <p className="text-emerald-400">npm run dev</p>
              </div>
              <div>
                <p className="text-slate-400 text-[11px]"># Model preparation</p>
                <p className="text-emerald-400">ollama pull qwen2.5:0.5b</p>
              </div>
            </div>
          </div>

          {/* Endpoints Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 font-mono font-semibold text-slate-700">
                <tr>
                  <th className="px-3.5 py-2.5">Method</th>
                  <th className="px-3.5 py-2.5">Endpoint</th>
                  <th className="px-3.5 py-2.5">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-600">
                <tr>
                  <td className="px-3.5 py-2 font-mono font-bold text-emerald-600">GET</td>
                  <td className="px-3.5 py-2 font-mono">/api/v1/health</td>
                  <td className="px-3.5 py-2">API liveness probe</td>
                </tr>
                <tr>
                  <td className="px-3.5 py-2 font-mono font-bold text-emerald-600">GET</td>
                  <td className="px-3.5 py-2 font-mono">/api/v1/ready</td>
                  <td className="px-3.5 py-2">Deep dependency readiness</td>
                </tr>
                <tr>
                  <td className="px-3.5 py-2 font-mono font-bold text-blue-600">POST</td>
                  <td className="px-3.5 py-2 font-mono">/api/v1/documents/upload</td>
                  <td className="px-3.5 py-2">Upload & index document</td>
                </tr>
                <tr>
                  <td className="px-3.5 py-2 font-mono font-bold text-blue-600">POST</td>
                  <td className="px-3.5 py-2 font-mono">/api/v1/chat/ask</td>
                  <td className="px-3.5 py-2">Grounded RAG synthesis</td>
                </tr>
                <tr>
                  <td className="px-3.5 py-2 font-mono font-bold text-blue-600">POST</td>
                  <td className="px-3.5 py-2 font-mono">/api/v1/agent/ask</td>
                  <td className="px-3.5 py-2">LangGraph agent query</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  )
}
