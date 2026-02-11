import { ref, onUnmounted, type Ref } from 'vue'
import type { StreamEvent, InteractRequest } from '@/types'

export function useEventStream() {
  const isConnected = ref(false)
  const error: Ref<string | null> = ref(null)
  const streamingContent = ref('')
  const sessionId = ref('')
  const thinkingStage: Ref<string | null> = ref(null)
  const suggestedActions = ref<string[]>([])
  const metaText: Ref<string | null> = ref(null)

  let eventSource: EventSource | null = null
  let retryCount = 0
  const maxRetries = 3
  const retryDelay = 1000

  const cleanup = () => {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    isConnected.value = false
    thinkingStage.value = null
  }

  const connect = async (payload: InteractRequest, retryAttempt = 0): Promise<EventSource> => {
    cleanup()
    error.value = null
    sessionId.value = ''
    streamingContent.value = ''
    suggestedActions.value = []
    metaText.value = null
    if (retryAttempt === 0) {
      retryCount = 0
    }

    return new Promise((resolve, reject) => {
      const processSseLine = (line: string): boolean => {
        if (!line.startsWith('data: ')) return false
        try {
          const jsonData = line.slice(6).trim()
          if (jsonData === '[DONE]') {
            cleanup()
            return true
          }

          const data = JSON.parse(jsonData) as StreamEvent

          if (data.type === 'chunk' && data.content) {
            streamingContent.value += data.content
          } else if (data.type === 'session' && data.session_id) {
            sessionId.value = data.session_id
          } else if (data.type === 'thinking' && data.stage) {
            thinkingStage.value = data.stage
          } else if (data.type === 'complete') {
            suggestedActions.value = data.suggested_actions || []
            metaText.value = data.meta_text || null
            thinkingStage.value = null
            cleanup()
            return true
          } else if (data.type === 'error') {
            thinkingStage.value = null
            error.value = data.error || 'An error occurred during streaming'
            cleanup()
            return true
          }
        } catch (parseError) {
          console.warn('Failed to parse SSE data:', parseError, 'Line:', line)
        }
        return false
      }

      // Use fetch with streaming response for POST request
      fetch('/api/interact', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
        body: JSON.stringify(payload),
      })
        .then(async (response) => {
          if (!response.ok) {
            const errorMessage = `HTTP ${response.status}: ${response.statusText}`
            const error = new Error(errorMessage) as Error & { status?: number }
            error.status = response.status
            throw error
          }

          if (!response.body) {
            throw new Error('Response body is null')
          }

          isConnected.value = true
          const reader = response.body.getReader()
          const decoder = new TextDecoder()
          let buffer = ''

          const readStream = async (): Promise<void> => {
            try {
              const { done, value } = await reader.read()
              if (!done && value) {
                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n')

                // Keep the last incomplete line in buffer
                buffer = lines.pop() || ''

                for (const line of lines) {
                  if (processSseLine(line)) {
                    return
                  }
                }
              }

              if (done) {
                const tail = buffer.trim()
                if (tail && processSseLine(tail)) {
                  return
                }
                cleanup()
                return
              }

              // Continue reading
              await readStream()
            } catch (readError) {
              error.value = readError instanceof Error ? readError.message : 'Stream read error'
              cleanup()
            }
          }

          readStream()

          // Create a mock EventSource object for compatibility
          const mockEventSource = {
            close: cleanup,
            readyState: 1,
            url: '/api/interact',
            withCredentials: false,
            CONNECTING: 0,
            OPEN: 1,
            CLOSED: 2,
            addEventListener: () => {},
            removeEventListener: () => {},
            dispatchEvent: () => false,
            onopen: null,
            onmessage: null,
            onerror: null,
          } as unknown as EventSource

          resolve(mockEventSource)
        })
        .catch(async (err) => {
          // Handle 502 Bad Gateway errors with silent retry
          const is502Error =
            err instanceof Error &&
            (err.message.includes('502') || ('status' in err && typeof err.status === 'number' && err.status === 502))

          if (is502Error && retryAttempt === 0) {
            // Wait 5 seconds then retry silently
            setTimeout(async () => {
              try {
                const eventSource = await connect(payload, 1)
                resolve(eventSource)
              } catch (retryErr) {
                error.value =
                  retryErr instanceof Error ? retryErr.message : 'Failed to connect to stream'
                cleanup()
                reject(retryErr)
              }
            }, 5000)
            return
          }

          error.value = err instanceof Error ? err.message : 'Failed to connect to stream'
          cleanup()
          reject(err)
        })
    })
  }

  const retry = async (payload: InteractRequest): Promise<EventSource | null> => {
    if (retryCount >= maxRetries) {
      error.value = `Failed to connect after ${maxRetries} attempts`
      return null
    }

    retryCount++

    return new Promise((resolve) => {
      setTimeout(async () => {
        try {
          const eventSource = await connect(payload)
          resolve(eventSource)
        } catch (err) {
          console.error('Failed to connect, retrying:', err)
          resolve(await retry(payload))
        }
      }, retryDelay * retryCount)
    })
  }

  const disconnect = () => {
    cleanup()
  }

  const getStreamContent = () => {
    return streamingContent.value
  }

  const clearStreamContent = () => {
    streamingContent.value = ''
  }

  const clearError = () => {
    error.value = null
  }

  // Cleanup on component unmount
  onUnmounted(() => {
    cleanup()
  })

  return {
    isConnected,
    error,
    streamingContent,
    sessionId,
    thinkingStage,
    suggestedActions,
    metaText,
    connect,
    retry,
    disconnect,
    getStreamContent,
    clearStreamContent,
    clearError,
  }
}
