import type {
  AgentAskResponse,
  DocumentSummary,
  DocumentUploadResponse,
  HealthStatus,
  RAGAskResponse,
  RAGStatus,
  ReadinessStatus,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
const TOKEN_KEY = 'enterprise-ai-agent-token'
let accessToken = typeof sessionStorage === 'undefined' ? null : sessionStorage.getItem(TOKEN_KEY)

export type AuthUser = {
  id: string
  email: string
  role: 'admin' | 'analyst' | 'viewer'
  created_at: string
}

type AuthResponse = {
  user: AuthUser
  token: string
}

function saveToken(token: string | null) {
  accessToken = token
  if (typeof sessionStorage !== 'undefined') {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  }
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function normalizeErrorDetail(detail: unknown): string {
  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item: unknown) => {
        if (typeof item === 'string') {
          return item
        }

        if (item && typeof item === 'object' && 'msg' in item && typeof item.msg === 'string') {
          return item.msg
        }

        return String(item)
      })
      .join(', ')
  }

  if (detail && typeof detail === 'object' && 'msg' in detail && typeof detail.msg === 'string') {
    return detail.msg
  }

  return String(detail)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(init.headers ?? {}),
    },
  })

  if (!response.ok) {
    let detail = 'Request failed.'
    try {
      const payload = await response.json()
      if (payload?.detail) {
        detail = normalizeErrorDetail(payload.detail)
      }
    } catch {
      detail = response.statusText || detail
    }
    throw new ApiError(detail, response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

interface CacheEntry<T> {
  promise: Promise<T>
  timestamp: number
}

const statusCache = new Map<string, CacheEntry<unknown>>()

async function cachedRequest<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttlMs = 5000,
  force = false,
): Promise<T> {
  const now = Date.now()
  const existing = statusCache.get(key)
  if (!force && existing && now - existing.timestamp < ttlMs) {
    return existing.promise as Promise<T>
  }
  const promise = fetcher().catch((err) => {
    statusCache.delete(key)
    throw err
  })
  statusCache.set(key, { promise, timestamp: now })
  return promise
}

export const apiClient = {
  hasSession: () => Boolean(accessToken),
  getCurrentUser: () => request<AuthUser>('/api/v1/auth/me'),
  signIn: async (email: string, password: string) => {
    const result = await request<AuthResponse>('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    statusCache.clear()
    saveToken(result.token)
    return result.user
  },
  register: async (email: string, password: string) => {
    const result = await request<AuthResponse>('/api/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, role: 'analyst' }),
    })
    statusCache.clear()
    saveToken(result.token)
    return result.user
  },
  signOut: () => {
    statusCache.clear()
    saveToken(null)
  },
  getHealth: (forceRefresh = false) =>
    cachedRequest('health', () => request<HealthStatus>('/api/v1/health'), 10000, forceRefresh),
  getReadiness: async (forceRefresh = false): Promise<ReadinessStatus> => {
    return cachedRequest(
      'readiness',
      async () => {
        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/ready`, {
            headers: {
              Accept: 'application/json',
              ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
            },
          })
          const payload = await response.json()
          return payload as ReadinessStatus
        } catch {
          return {
            status: 'not_ready',
            dependencies: {},
          }
        }
      },
      5000,
      forceRefresh,
    )
  },
  getRAGStatus: (forceRefresh = false) =>
    cachedRequest('ragStatus', () => request<RAGStatus>('/api/v1/rag/status'), 5000, forceRefresh),
  getDocuments: () => request<DocumentSummary[]>('/api/v1/documents'),
  uploadDocument: (formData: FormData) =>
    fetch(`${API_BASE_URL}/api/v1/documents/upload`, {
      method: 'POST',
      body: formData,
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    }).then(async (response) => {
      if (!response.ok) {
        let detail = 'Upload failed.'
        try {
          const payload = await response.json()
          if (payload?.detail) {
            detail = String(payload.detail)
          }
        } catch {
          detail = response.statusText || detail
        }
        throw new ApiError(detail, response.status)
      }
      return (await response.json()) as DocumentUploadResponse
    }),
  askRAG: (question: string, topK = 5) =>
    request<RAGAskResponse>('/api/v1/chat/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, top_k: topK }),
    }),
  askAgent: (question: string, includeSources = true) =>
    request<AgentAskResponse>('/api/v1/agent/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, include_sources: includeSources }),
    }),
}
