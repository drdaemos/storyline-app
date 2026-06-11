import { ref, type Ref } from 'vue'
import { useAuth } from './useAuth'
import type {
  VNAction,
  VNGenerationEvent,
  VNGenerationInput,
  VNGenerationJob,
  VNImportResponse,
  VNScriptDetail,
  VNScriptSummary,
  VNSessionSummary,
  VNSessionView,
  VNValidationReport,
} from '@/types/vn'

interface VnApiError {
  message: string
  status?: number
}

export function useVnApi() {
  const loading = ref(false)
  const error: Ref<VnApiError | null> = ref(null)
  const { getAuthToken } = useAuth()

  const authHeaders = async (): Promise<Record<string, string>> => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    const token = await getAuthToken()
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
    return headers
  }

  const request = async <T>(url: string, options: RequestInit = {}): Promise<T> => {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(url, {
        ...options,
        headers: { ...(await authHeaders()), ...((options.headers as Record<string, string>) || {}) },
      })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        const message = body.detail || body.message || `HTTP ${response.status}: ${response.statusText}`
        error.value = { message, status: response.status }
        throw new Error(message)
      }
      return (await response.json()) as T
    } finally {
      loading.value = false
    }
  }

  // --- scripts ---

  const listScripts = () => request<VNScriptSummary[]>('/api/vn/scripts')

  const getScript = (scriptId: string) => request<VNScriptDetail>(`/api/vn/scripts/${scriptId}`)

  const importScript = (script: unknown) =>
    request<VNImportResponse>('/api/vn/scripts', { method: 'POST', body: JSON.stringify({ script }) })

  const validateScript = (script: unknown) =>
    request<VNValidationReport>('/api/vn/scripts/validate', { method: 'POST', body: JSON.stringify({ script }) })

  const deleteScript = (scriptId: string) =>
    request<{ message: string }>(`/api/vn/scripts/${scriptId}`, { method: 'DELETE' })

  // --- sessions ---

  const createSession = (scriptId: string, seed?: number) =>
    request<VNSessionView>('/api/vn/sessions', { method: 'POST', body: JSON.stringify({ script_id: scriptId, seed: seed ?? null }) })

  const listSessions = () => request<VNSessionSummary[]>('/api/vn/sessions')

  const getSession = (sessionId: string) => request<VNSessionView>(`/api/vn/sessions/${sessionId}`)

  const advanceSession = (sessionId: string, action: VNAction) =>
    request<VNSessionView>(`/api/vn/sessions/${sessionId}/advance`, { method: 'POST', body: JSON.stringify({ action }) })

  const deleteSession = (sessionId: string) =>
    request<{ message: string }>(`/api/vn/sessions/${sessionId}`, { method: 'DELETE' })

  // --- streaming ---

  const narrateSession = async (sessionId: string, processorType: string, onChunk: (text: string) => void): Promise<void> => {
    const response = await fetch(`/api/vn/sessions/${sessionId}/narrate`, {
      method: 'POST',
      headers: await authHeaders(),
      body: JSON.stringify({ processor_type: processorType }),
    })
    if (!response.ok || !response.body) {
      const body = await response.json().catch(() => ({}))
      throw new Error(body.detail || `HTTP ${response.status}`)
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      onChunk(decoder.decode(value, { stream: true }))
    }
  }

  const streamGenerationEvents = async (url: string, body: string | undefined, onEvent: (event: VNGenerationEvent) => void): Promise<void> => {
    const response = await fetch(url, {
      method: 'POST',
      headers: await authHeaders(),
      body,
    })
    if (!response.ok || !response.body) {
      const errorBody = await response.json().catch(() => ({}))
      throw new Error(errorBody.detail || `HTTP ${response.status}`)
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            onEvent(JSON.parse(line.slice(6)) as VNGenerationEvent)
          } catch {
            // ignore malformed SSE lines
          }
        }
      }
    }
  }

  const generateScript = (input: VNGenerationInput, processorType: string, onEvent: (event: VNGenerationEvent) => void) =>
    streamGenerationEvents('/api/vn/scripts/generate', JSON.stringify({ input, processor_type: processorType }), onEvent)

  // --- generation jobs ---

  const listGenerationJobs = () => request<VNGenerationJob[]>('/api/vn/generation-jobs')

  const resumeGeneration = (jobId: string, onEvent: (event: VNGenerationEvent) => void) =>
    streamGenerationEvents(`/api/vn/generation-jobs/${jobId}/resume`, undefined, onEvent)

  const deleteGenerationJob = (jobId: string) =>
    request<{ message: string }>(`/api/vn/generation-jobs/${jobId}`, { method: 'DELETE' })

  return {
    loading,
    error,
    listScripts,
    getScript,
    importScript,
    validateScript,
    deleteScript,
    createSession,
    listSessions,
    getSession,
    advanceSession,
    deleteSession,
    narrateSession,
    generateScript,
    listGenerationJobs,
    resumeGeneration,
    deleteGenerationJob,
  }
}
