import { ref, type Ref } from 'vue'
import type { SessionInfo, InteractRequest, CreateCharacterRequest, CreateCharacterResponse } from '@/types'

interface ApiError {
  message: string
  status?: number
}

export function useApi() {
  const loading = ref(false)
  const error: Ref<ApiError | null> = ref(null)

  const handleResponse = async (response: Response) => {
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`)
    }
    return response.json()
  }

  const makeRequest = async <T>(url: string, options: RequestInit = {}): Promise<T> => {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        },
        ...options
      })

      const data = await handleResponse(response)
      return data
    } catch (err) {
      error.value = {
        message: err instanceof Error ? err.message : 'An unknown error occurred',
        status: err instanceof Error && 'status' in err ? (err as any).status : undefined
      }
      throw err
    } finally {
      loading.value = false
    }
  }

  const getCharacters = async (): Promise<string[]> => {
    return makeRequest<string[]>('/api/characters')
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

  const deleteSession = async (sessionId: string): Promise<{ message: string }> => {
    return makeRequest<{ message: string }>(`/api/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE'
    })
  }

  const handleInteraction = (payload: InteractRequest): EventSource => {
    const eventSource = new EventSource('/api/interact', {

    })

    // Since EventSource doesn't support POST directly, we need to use a different approach
    // We'll create the EventSource after making a POST request
    fetch('/api/interact', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    }).then(response => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      // The actual EventSource will be handled in the component
    }).catch(err => {
      error.value = {
        message: err instanceof Error ? err.message : 'Failed to start interaction',
        status: err instanceof Error && 'status' in err ? (err as any).status : undefined
      }
    })

    return eventSource
  }

  return {
    loading,
    error,
    getCharacters,
    getCharacterInfo,
    getSessions,
    createCharacter,
    deleteSession,
    handleInteraction
  }
}