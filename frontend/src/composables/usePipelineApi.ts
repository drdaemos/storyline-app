import { ref, type Ref } from 'vue'
import { useAuth } from './useAuth'
import type {
  CharacterDetailV2,
  CharacterSummaryV2,
  CreateRulesetInput,
  ListScenariosResponseV2,
  RulesetSummaryV2,
  ScenarioDetailV2,
  SessionCharacterSummaryV2,
  SessionDetailsV2,
  SessionInfoV2,
  SessionStateResponseV2,
  StartSessionRequestV2,
  StartSessionResponseV2,
  CreateWorldLoreInput,
  WorldLoreSummaryV2,
} from '@/types/pipeline'

interface ApiErrorV2 {
  message: string
  status?: number
}

interface RequestOptions extends RequestInit {
  headers?: Record<string, string>
}

export function usePipelineApi() {
  const loading = ref(false)
  const error: Ref<ApiErrorV2 | null> = ref(null)
  const { getAuthToken } = useAuth()

  const buildHeaders = (options: RequestOptions, token: string | null): Record<string, string> => {
    const headers: Record<string, string> = {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
    return headers
  }

  const parseErrorMessage = async (response: Response): Promise<string> => {
    const fallbackMessage = `HTTP ${response.status}: ${response.statusText}`
    try {
      const payload = await response.json()
      return typeof payload?.detail === 'string' ? payload.detail : fallbackMessage
    } catch {
      return fallbackMessage
    }
  }

  const toStatusError = (message: string, status: number): Error & { status: number } => {
    const responseError = new Error(message) as Error & { status: number }
    responseError.status = status
    return responseError
  }

  const parseSuccessResponse = async <T>(response: Response): Promise<T> => {
    if (response.status === 204) {
      return undefined as T
    }
    return (await response.json()) as T
  }

  const request = async <T>(url: string, options: RequestOptions = {}): Promise<T> => {
    loading.value = true
    error.value = null

    try {
      const token = await getAuthToken()
      const headers = buildHeaders(options, token)

      const response = await fetch(url, {
        ...options,
        headers,
      })

      if (!response.ok) {
        const message = await parseErrorMessage(response)
        throw toStatusError(message, response.status)
      }

      return parseSuccessResponse<T>(response)
    } catch (err) {
      const typedError = err as Error & { status?: number }
      error.value = {
        message: typedError.message || 'Unknown API error',
        status: typedError.status,
      }
      throw err
    } finally {
      loading.value = false
    }
  }

  const listCharacters = async (): Promise<CharacterSummaryV2[]> => {
    return request<CharacterSummaryV2[]>('/api/characters')
  }

  const getCharacterDetail = async (characterId: string): Promise<CharacterDetailV2> => {
    return request<CharacterDetailV2>(`/api/characters/${encodeURIComponent(characterId)}`)
  }

  const listPersonas = async (): Promise<CharacterSummaryV2[]> => {
    return request<CharacterSummaryV2[]>('/api/personas')
  }

  const listSessions = async (): Promise<SessionInfoV2[]> => {
    return request<SessionInfoV2[]>('/api/sessions')
  }

  const listCharacterSessions = async (
    characterId: string,
    options?: { status?: 'active' | 'paused' | 'completed'; limit?: number; offset?: number }
  ): Promise<SessionInfoV2[]> => {
    const params = new URLSearchParams()
    if (options?.status) {
      params.set('status', options.status)
    }
    if (typeof options?.limit === 'number') {
      params.set('limit', String(options.limit))
    }
    if (typeof options?.offset === 'number') {
      params.set('offset', String(options.offset))
    }

    const query = params.toString()
    const suffix = query ? `?${query}` : ''
    return request<SessionInfoV2[]>(
      `/api/characters/${encodeURIComponent(characterId)}/sessions${suffix}`
    )
  }

  const getSessionDetails = async (sessionId: string): Promise<SessionDetailsV2> => {
    return request<SessionDetailsV2>(`/api/sessions/${encodeURIComponent(sessionId)}`)
  }

  const getSessionState = async (sessionId: string): Promise<SessionStateResponseV2> => {
    return request<SessionStateResponseV2>(`/api/sessions/${encodeURIComponent(sessionId)}/state`)
  }

  const getSessionCharacters = async (sessionId: string): Promise<SessionCharacterSummaryV2[]> => {
    return request<SessionCharacterSummaryV2[]>(
      `/api/sessions/${encodeURIComponent(sessionId)}/characters`
    )
  }

  const deleteSession = async (sessionId: string): Promise<{ message: string }> => {
    return request<{ message: string }>(`/api/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
    })
  }

  const listRulesets = async (): Promise<RulesetSummaryV2[]> => {
    return request<RulesetSummaryV2[]>('/api/rulesets')
  }

  const createRuleset = async (
    input: CreateRulesetInput
  ): Promise<{ id: string; message: string }> => {
    const payload: Record<string, unknown> = {
      name: input.name,
      rules_text: input.rules_text ?? '',
    }

    if (input.state_schemas) {
      payload.state_schemas = input.state_schemas
    }
    if (input.config) {
      payload.config = input.config
    }

    return request<{ id: string; message: string }>('/api/rulesets', {
      method: 'POST',
      body: JSON.stringify({
        ruleset: payload,
      }),
    })
  }

  const deleteRuleset = async (rulesetId: string): Promise<{ message: string }> => {
    return request<{ message: string }>(`/api/rulesets/${encodeURIComponent(rulesetId)}`, {
      method: 'DELETE',
    })
  }

  const listWorldLore = async (): Promise<WorldLoreSummaryV2[]> => {
    return request<WorldLoreSummaryV2[]>('/api/world-lore')
  }

  const listWorldLoreTags = async (): Promise<string[]> => {
    return request<string[]>('/api/world-lore/tags')
  }

  const createWorldLore = async (
    input: CreateWorldLoreInput
  ): Promise<{ id: string; message: string }> => {
    return request<{ id: string; message: string }>('/api/world-lore', {
      method: 'POST',
      body: JSON.stringify({
        lore: {
          name: input.name,
          content: input.content,
          tags: input.tags,
        },
      }),
    })
  }

  const deleteWorldLore = async (loreId: string): Promise<{ message: string }> => {
    return request<{ message: string }>(`/api/world-lore/${encodeURIComponent(loreId)}`, {
      method: 'DELETE',
    })
  }

  const listScenarios = async (): Promise<ListScenariosResponseV2> => {
    return request<ListScenariosResponseV2>('/api/scenarios/list')
  }

  const getScenarioDetail = async (scenarioId: string): Promise<ScenarioDetailV2> => {
    return request<ScenarioDetailV2>(`/api/scenarios/detail/${encodeURIComponent(scenarioId)}`)
  }

  const deleteScenario = async (scenarioId: string): Promise<{ message: string }> => {
    return request<{ message: string }>(`/api/scenarios/${encodeURIComponent(scenarioId)}`, {
      method: 'DELETE',
    })
  }

  const startSession = async (payload: StartSessionRequestV2): Promise<StartSessionResponseV2> => {
    return request<StartSessionResponseV2>('/api/sessions/start', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  return {
    loading,
    error,
    listCharacters,
    getCharacterDetail,
    listPersonas,
    listSessions,
    listCharacterSessions,
    getSessionDetails,
    getSessionState,
    getSessionCharacters,
    deleteSession,
    listRulesets,
    createRuleset,
    deleteRuleset,
    listWorldLore,
    listWorldLoreTags,
    createWorldLore,
    deleteWorldLore,
    listScenarios,
    getScenarioDetail,
    deleteScenario,
    startSession,
  }
}
