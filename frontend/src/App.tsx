import { useEffect, useState, type FormEvent } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import {
  LoaderCircle,
  Menu,
  ShieldCheck,
} from 'lucide-react'
import { apiClient, type AuthUser } from './services/api'
import { Sidebar } from './components/Sidebar'
import { OverviewPage } from './pages/OverviewPage'
import { AssistantPage } from './pages/AssistantPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { SystemStatusPage } from './pages/SystemStatusPage'
import { AboutProjectPage } from './pages/AboutProjectPage'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  const [authUser, setAuthUser] = useState<AuthUser | null>(null)
  const [checkingSession, setCheckingSession] = useState(apiClient.hasSession())
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  useEffect(() => {
    if (!apiClient.hasSession()) {
      setCheckingSession(false)
      return
    }
    void apiClient
      .getCurrentUser()
      .then(setAuthUser)
      .catch(() => apiClient.signOut())
      .finally(() => setCheckingSession(false))
  }, [])

  if (checkingSession) {
    return (
      <div className="grid min-h-screen place-items-center bg-slate-50">
        <div className="flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-soft">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <LoaderCircle className="h-6 w-6 animate-spin text-indigo-600" />
          <span className="text-xs font-semibold text-slate-500 font-mono">
            Verifying secure session...
          </span>
        </div>
      </div>
    )
  }

  if (!authUser) {
    return <SignInPage onAuthenticated={setAuthUser} />
  }

  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-slate-50 text-slate-900 font-sans">
        {/* Sidebar Component (Desktop persistent + Mobile drawer) */}
        <Sidebar
          user={authUser}
          onSignOut={() => {
            apiClient.signOut()
            setAuthUser(null)
          }}
          mobileOpen={mobileNavOpen}
          onCloseMobile={() => setMobileNavOpen(false)}
        />

        {/* Content Shell */}
        <div className="flex flex-1 flex-col min-w-0">
          {/* Mobile top bar */}
          <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur-sm lg:hidden">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white">
                <ShieldCheck className="h-4 w-4" />
              </div>
              <span className="text-sm font-bold text-slate-900 font-display">
                Enterprise AI Research
              </span>
            </div>

            <button
              type="button"
              onClick={() => setMobileNavOpen(true)}
              className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 transition"
              aria-label="Open navigation menu"
            >
              <Menu className="h-5 w-5" />
            </button>
          </header>

          {/* Main Router Content */}
          <main className="flex-1 p-4 md:p-8 max-w-7xl w-full mx-auto">
            <Routes>
              <Route path="/" element={<OverviewPage user={authUser} />} />
              <Route path="/assistant" element={<AssistantPage />} />
              <Route path="/documents" element={<DocumentsPage user={authUser} />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/status" element={<SystemStatusPage />} />
              <Route path="/about" element={<AboutProjectPage />} />
              <Route path="/settings" element={<SettingsPage user={authUser} />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  )
}

function SignInPage({ onAuthenticated }: { onAuthenticated: (user: AuthUser) => void }) {
  const canRegister = import.meta.env.DEV
  const [registering, setRegistering] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const user = registering
        ? await apiClient.register(email, password)
        : await apiClient.signIn(email, password)
      onAuthenticated(user)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Authentication failed.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-md">
        {/* Brand header */}
        <div className="text-center mb-8">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-soft ring-4 ring-indigo-50 mb-3">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <p className="text-[11px] font-bold tracking-[0.2em] uppercase text-indigo-600 font-mono">
            Enterprise AI Research Agent
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 font-display">
            {registering ? 'Create analyst account' : 'Sign in'}
          </h1>
          <p className="mt-1.5 text-xs text-slate-500">
            {registering
              ? 'Register a local analyst workspace account'
              : 'Sign in to access your authorized documents and RAG agent'}
          </p>
        </div>

        {/* Form Card */}
        <form
          onSubmit={submit}
          className="rounded-2xl border border-slate-200/80 bg-white p-7 shadow-card"
        >
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Email address
              </label>
              <input
                autoComplete="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2.5 text-xs md:text-sm text-slate-800 focus:border-indigo-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-100 transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Password
              </label>
              <input
                autoComplete={registering ? 'new-password' : 'current-password'}
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2.5 text-xs md:text-sm text-slate-800 focus:border-indigo-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-100 transition"
              />
            </div>
          </div>

          {error && (
            <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800" role="alert">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-indigo-700 transition disabled:opacity-60"
          >
            {submitting && <LoaderCircle className="h-4 w-4 animate-spin" />}
            <span>{registering ? 'Create account' : 'Sign in'}</span>
          </button>

          {canRegister && (
            <div className="mt-5 border-t border-slate-100 pt-4 text-center">
              <button
                type="button"
                onClick={() => {
                  setRegistering(!registering)
                  setError(null)
                }}
                className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition"
              >
                {registering ? 'Already registered? Sign in' : 'Create an analyst account'}
              </button>
            </div>
          )}
        </form>
      </div>
    </main>
  )
}
