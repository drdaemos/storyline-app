import { ref, type Ref } from 'vue'
import type {
  CharacterSummary,
  SessionInfo,
  InteractRequest,
  CreateCharacterRequest,
  CreateCharacterResponse,
  GenerateCharacterRequest,
  GenerateCharacterResponse,
  GenerateScenariosRequest,
  GenerateScenariosResponse,
  StartSessionRequest,
  StartSessionResponse
} from '@/types'
import { useAuth } from './useAuth'

interface ApiError {
  message: string
  status?: number
}

export function useApi() {
  const loading = ref(false)
  const error: Ref<ApiError | null> = ref(null)
  const { getAuthToken } = useAuth()

  const handleResponse = async (response: Response) => {
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      const errorMessage = errorData.message || `HTTP ${response.status}: ${response.statusText}`
      const error = new Error(errorMessage) as any
      error.status = response.status
      throw error
    }
    return response.json()
  }

  const makeRequest = async <T>(url: string, options: RequestInit = {}, retryAttempt = 0): Promise<T> => {
    loading.value = true
    error.value = null

    try {
      // Get auth token if available
      const token = await getAuthToken()

      // Build headers with optional Authorization header
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string> || {})
      }

      if (token) {
        headers.Authorization = `Bearer ${token}`
      }

      const response = await fetch(url, {
        ...options,
        headers
      })

      const data = await handleResponse(response)
      return data
    } catch (err) {
      // Handle 502 Bad Gateway errors with silent retry
      const is502Error = err instanceof Error && (
        err.message.includes('502') ||
        ('status' in err && (err as any).status === 502)
      )

      if (is502Error && retryAttempt === 0) {
        // Wait 5 seconds then retry silently
        await new Promise(resolve => setTimeout(resolve, 5000))
        return makeRequest<T>(url, options, 1)
      }

      error.value = {
        message: err instanceof Error ? err.message : 'An unknown error occurred',
        status: err instanceof Error && 'status' in err ? (err as any).status : undefined
      }
      throw err
    } finally {
      loading.value = false
    }
  }

  const getCharacters = async (): Promise<CharacterSummary[]> => {
    return makeRequest<CharacterSummary[]>('/api/characters')
  }

  const getCharacterInfo = async (name: string): Promise<Record<string, string>> => {
    return makeRequest<Record<string, string>>(`/api/characters/${encodeURIComponent(name)}`)
  }

  const getSessions = async (): Promise<SessionInfo[]> => {
    return makeRequest<SessionInfo[]>('/api/sessions')
  }

  const createCharacter = async (payload: CreateCharacterRequest): Promise<CreateCharacterResponse> => {
    return makeRequest<CreateCharacterResponse>('/api/characters', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  const generateCharacter = async (payload: GenerateCharacterRequest): Promise<GenerateCharacterResponse> => {
    return makeRequest<GenerateCharacterResponse>('/api/characters/generate', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  const deleteSession = async (sessionId: string): Promise<{ message: string }> => {
    return makeRequest<{ message: string }>(`/api/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE'
    })
  }

  const handleInteraction = async (payload: InteractRequest, retryAttempt = 0): Promise<EventSource> => {
    const eventSource = new EventSource('/api/interact', {

    })

    // Get auth token if available
    const token = await getAuthToken()

    // Build headers with optional Authorization header
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    }

    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    // Since EventSource doesn't support POST directly, we need to use a different approach
    // We'll create the EventSource after making a POST request
    fetch('/api/interact', {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    }).then(response => {
      if (!response.ok) {
        const errorMessage = `HTTP ${response.status}: ${response.statusText}`
        const error = new Error(errorMessage) as any
        error.status = response.status
        throw error
      }
      // The actual EventSource will be handled in the component
    }).catch(err => {
      // Handle 502 Bad Gateway errors with silent retry
      const is502Error = err instanceof Error && (
        err.message.includes('502') ||
        ('status' in err && (err as any).status === 502)
      )

      if (is502Error && retryAttempt === 0) {
        // Wait 5 seconds then retry silently
        setTimeout(() => {
          handleInteraction(payload, 1)
        }, 5000)
        return
      }

      error.value = {
        message: err instanceof Error ? err.message : 'Failed to start interaction',
        status: err instanceof Error && 'status' in err ? (err as any).status : undefined
      }
    })

    return eventSource
  }

  const generateScenarios = async (payload: GenerateScenariosRequest): Promise<GenerateScenariosResponse> => {
    return makeRequest<GenerateScenariosResponse>('/api/scenarios/generate', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  const startSessionWithScenario = async (payload: StartSessionRequest): Promise<StartSessionResponse> => {
    return makeRequest<StartSessionResponse>('/api/sessions/start', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  return {
    loading,
    error,
    getCharacters,
    getCharacterInfo,
    getSessions,
    createCharacter,
    generateCharacter,
    deleteSession,
    handleInteraction,
    generateScenarios,
    startSessionWithScenario
  }
}