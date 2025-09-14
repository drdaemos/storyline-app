import { ref, onUnmounted, type Ref } from 'vue'
import type { StreamEvent, InteractRequest } from '@/types'

export function useEventStream() {
  const isConnected = ref(false)
  const error: Ref<string | null> = ref(null)
  const streamingContent = ref('')

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
  }

  const connect = async (payload: InteractRequest): Promise<EventSource> => {
    cleanup()
    error.value = null
    streamingContent.value = ''
    retryCount = 0

    return new Promise((resolve, reject) => {
      // Use fetch with streaming response for POST request
      fetch('/interact', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          'Cache-Control': 'no-cache'
        },
        body: JSON.stringify(payload)
      }).then(async response => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
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

            if (done) {
              cleanup()
              return
            }

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')

            // Keep the last incomplete line in buffer
            buffer = lines.pop() || ''

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const jsonData = line.slice(6).trim()
                  if (jsonData === '[DONE]') {
                    cleanup()
                    return
                  }

                  const data = JSON.parse(jsonData) as StreamEvent

                  if (data.type === 'chunk' && data.content) {
                    streamingContent.value += data.content
                  } else if (data.type === 'complete') {
                    cleanup()
                    return
                  }
                } catch (parseError) {
                  console.warn('Failed to parse SSE data:', parseError, 'Line:', line)
                }
              }
            }

            // Continue reading
            readStream()
          } catch (readError) {
            console.error('Stream read error:', readError)
            error.value = readError instanceof Error ? readError.message : 'Stream read error'
            cleanup()
          }
        }

        readStream()

        // Create a mock EventSource object for compatibility
        const mockEventSource = {
          close: cleanup,
          readyState: 1,
          url: '/interact',
          withCredentials: false,
          addEventListener: () => {},
          removeEventListener: () => {},
          dispatchEvent: () => false,
          onopen: null,
          onmessage: null,
          onerror: null
        } as EventSource

        resolve(mockEventSource)
      }).catch(err => {
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

    return new Promise(resolve => {
      setTimeout(async () => {
        try {
          const eventSource = await connect(payload)
          resolve(eventSource)
        } catch (err) {
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

  // Cleanup on component unmount
  onUnmounted(() => {
    cleanup()
  })

  return {
    isConnected,
    error,
    streamingContent,
    connect,
    retry,
    disconnect,
    getStreamContent,
    clearStreamContent
  }
}