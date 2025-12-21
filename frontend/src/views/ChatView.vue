<template>
  <!-- Header -->
  <div class="flex flex-col sm:flex-row mb-6 sm:mb-8 gap-3 sm:gap-4 sm:items-center">
    <!-- Top row on mobile: Back button and character name -->
    <div class="flex items-center gap-3 sm:gap-4">
      <UButton
        color="neutral"
        variant="ghost"
        icon="i-lucide-arrow-left"
        @click="navigateBack"
      >
        <span class="hidden sm:inline">Back</span>
      </UButton>
      <h2 class="text-xl sm:text-2xl font-bold font-serif truncate">{{ characterId }}</h2>
    </div>

    <!-- Second row on mobile: Session info and persona -->
    <div class="flex items-center gap-2 sm:gap-3 flex-wrap">
      <span class="text-xs sm:text-sm text-gray-500 font-mono hidden sm:inline">Session: {{ displaySessionId }}</span>
      <UBadge v-if="personaName" color="primary" variant="subtle">
        <UIcon name="i-lucide-user" class="mr-1" />
        {{ personaName }}
      </UBadge>
    </div>

    <!-- Action buttons - aligned right on desktop, full width on mobile -->
    <div class="flex items-center gap-2 sm:gap-3 sm:ml-auto">
      <UButton
        color="neutral"
        variant="outline"
        icon="i-lucide-file-text"
        size="sm"
        @click="showSummaryModal = true"
        class="flex-1 sm:flex-none"
      >
        <span class="hidden sm:inline">View Summary</span>
        <span class="sm:hidden">Summary</span>
      </UButton>
      <UBadge v-if="isConnected" color="success" variant="subtle" class="hidden sm:flex">
        Connected
      </UBadge>
      <UBadge v-else-if="error" color="error" variant="subtle" class="hidden sm:flex">
        Error
      </UBadge>
    </div>
  </div>

  <!-- Chat Container -->
  <div class="pb-12 flex-1 justify-items-center">
    <!-- Empty state -->
    <div v-if="messages.length === 0 && !isThinking" class="flex-1 flex items-center justify-center text-center p-8">
      <div class="space-y-4">
        <div class="w-16 h-16 mx-auto rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
          <UIcon name="i-lucide-message-square" class="w-8 h-8 text-gray-400" />
        </div>
        <h3 class="text-xl font-semibold">Start a conversation with {{ characterId }}</h3>
        <p class="text-gray-500">Type a message below to begin chatting.</p>
      </div>
    </div>

    <!-- Messages -->
    <UChatMessages
      v-else
      :status="chatStatus"
      should-auto-scroll
      class="max-w-2xl"
    >
      <template #indicator>
        <div class="flex items-center gap-3 py-3">
          <div class="flex gap-1">
            <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse " style="animation-delay: 0s"></span>
            <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0.2s"></span>
            <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0.4s"></span>
          </div>
          <span class="text-sm italic text-gray-600 dark:text-gray-400">{{ thinkingMessage }}</span>
        </div>
      </template>
      <UChatMessage
        v-for="(message, index) in messages"
        :id="index.toString()"
        :role="message.isUser ? 'user' : 'assistant'"
        :parts="[]"
        :side="message.isUser ? 'right' : 'left'"
        :variant="message.isUser ? 'outline' : 'soft'"
      >
        <template #content>
          <div v-html="message.content"></div>
        </template>
      </UChatMessage>
    </UChatMessages>

    <!-- Error message -->
    <div v-if="error && !isThinking" class="fixed top-20 left-0 right-0 z-50 flex justify-center px-6">
      <div class="w-full max-w-2xl">
        <UAlert
          color="error"
          variant="soft"
          icon="i-lucide-alert-triangle"
          title="Error"
          :description="error"
        >
          <template #actions>
            <UButton
              color="error"
              variant="solid"
              size="xs"
              icon="i-lucide-refresh-cw"
              label="Regenerate"
              @click="regenerateAfterError"
            />
          </template>
        </UAlert>
      </div>
    </div>

    <!-- Chat Input -->
    <ChatInput
      :chat-status="chatStatus"
      :disabled="isThinking"
      :character-name="characterId"
      @send="handleChatInput"
      @stop="handleStop"
      @regenerate="regenerateAfterError"
    />
  </div>

  <!-- Summary Modal -->
  <SummaryModal
    :show="showSummaryModal"
    :session-id="sessionId"
    @close="showSummaryModal = false"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useEventStream } from '@/composables/useEventStream'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { getThinkingDescriptor } from '@/utils/formatters'
import ChatInput from '@/components/ChatInput.vue'
import SummaryModal from '@/components/SummaryModal.vue'
import type { ChatMessage as ChatMessageType, InteractRequest, SessionDetails, SessionPersonaResponse } from '@/types'
import { useChatHighlight } from '@/composables/useChatHighlight.ts'

interface Props {
  characterId: string
  sessionId: string
}

const props = defineProps<Props>()

const router = useRouter()
const { highlight } = useChatHighlight()
const { settings } = useLocalSettings()
const {
  isConnected,
  error,
  streamingContent,
  sessionId,
  thinkingStage,
  connect,
  disconnect,
  clearStreamContent,
  clearError,
} = useEventStream()

const messages = ref<ChatMessageType[]>([])
const isThinking = ref(false)
const currentSessionId = ref<string | null>(null)
const lastInteractPayload = ref<InteractRequest | null>(null)
const showSummaryModal = ref(false)
const personaName = ref<string | null>(null)

const navigateBack = () => {
  router.back()
}

const displaySessionId = computed(() => {
  if (props.sessionId === 'new') {
    return 'New Session'
  }
  return props.sessionId.substring(0, 8)
})

const thinkingMessage = computed((): string => {
  if (!thinkingStage.value) {
    return `${props.characterId} is thinking...`
  }
  return getThinkingDescriptor(thinkingStage.value, props.characterId)
})

// Convert isThinking to AI SDK chat status
const chatStatus = computed(() => {
  if (isThinking.value && !streamingContent.value) {
    return 'submitted'
  }
  if (isThinking.value && streamingContent.value) {
    return 'streaming'
  }
  if (error.value) {
    return 'error'
  }
  return 'ready'
})

const handleChatInput = async (text: string) => {
  const trimmedText = text.trim()

  // Handle commands
  switch (trimmedText) {
    case '/regenerate':
      await regenerateLastMessage()
      break
    case '/rewind':
      await rewindLastExchange()
      break
    default:
      await sendMessage(text)
      break
  }
}

const sendInteractRequest = async (userMessage: string) => {
  // Start thinking
  isThinking.value = true
  clearStreamContent()

  try {
    const payload: InteractRequest = {
      character_name: props.characterId,
      user_message: userMessage,
      session_id: props.sessionId === 'new' ? null : props.sessionId,
      processor_type: settings.value.aiProcessor,
      backup_processor_type: settings.value.backupProcessor,
    }

    // Store payload for potential regeneration
    lastInteractPayload.value = payload

    // Start streaming response
    await connect(payload)

    // Monitor streaming completion
    const checkCompletion = () => {
      if (!isConnected.value && streamingContent.value) {
        // Stream completed successfully
        const characterMessage: ChatMessageType = {
          author: props.characterId,
          content: streamingContent.value,
          isUser: false,
          timestamp: new Date(),
        }

        messages.value.push(characterMessage)
        clearStreamContent()
        isThinking.value = false

        // Update session ID if this was a new session
        if (sessionId?.value !== '') {
          // Update URL without navigation
          router.replace({
            name: 'chat',
            params: {
              characterName: props.characterId,
              sessionId: sessionId?.value,
            },
          })
        }
      } else if (!isConnected.value && !streamingContent.value && !error.value) {
        // Command completed without content (like /rewind)
        isThinking.value = false
      } else if (!isConnected.value && error.value) {
        // Stream failed - unblock send button and keep error visible
        isThinking.value = false
      }
    }

    // Check completion periodically
    const completionInterval = setInterval(() => {
      checkCompletion()
      if (!isThinking.value) {
        clearInterval(completionInterval)
      }
    }, 100)
  } catch (err) {
    console.error('Failed to send message:', err)
    isThinking.value = false
  }
}

const sendMessage = async (text: string) => {
  if (!text.trim() || isThinking.value) return

  // Add user message
  const userMessage: ChatMessageType = {
    author: 'User',
    content: text.trim(),
    isUser: true,
    timestamp: new Date(),
  }

  messages.value.push(userMessage)

  // Send the message to backend
  await sendInteractRequest(text.trim())
}

const regenerateLastMessage = async () => {
  if (isThinking.value || messages.value.length === 0) return

  const lastMessage = messages.value[messages.value.length - 1]
  if (lastMessage.isUser) return

  // Remove last character message visually
  messages.value.pop()

  // Send regenerate command to backend
  await sendInteractRequest('/regenerate')
}

const rewindLastExchange = async () => {
  if (messages.value.length === 0) return

  const lastMessage = messages.value[messages.value.length - 1]
  const secondLastMessage = messages.value[messages.value.length - 2]

  if (lastMessage.isUser) {
    // Last message is from user, remove only that
    messages.value.pop()
  } else if (secondLastMessage?.isUser) {
    // Remove both user and character messages
    messages.value.splice(-2, 2)
  } else {
    // Only remove character message
    messages.value.pop()
  }

  // Send rewind command to backend
  await sendInteractRequest('/rewind')
}

const regenerateAfterError = async () => {
  if (!lastInteractPayload.value || isThinking.value) return

  // Clear the error and reattempt the last interact request
  clearError()

  // Use the stored payload to retry the request
  await sendInteractRequest(lastInteractPayload.value.user_message)
}

const loadSessionHistory = async (sessionId: string, retryAttempt = 0) => {
  try {
    const response = await fetch(`/api/sessions/${sessionId}`)
    if (!response.ok) {
      if (response.status === 404) {
        console.warn(`Session ${sessionId} not found, starting fresh`)
        return
      }

      // Handle 502 Bad Gateway errors with silent retry
      if (response.status === 502 && retryAttempt === 0) {
        // Wait 5 seconds then retry silently
        setTimeout(() => {
          loadSessionHistory(sessionId, 1)
        }, 5000)
        return
      }

      throw new Error(`Failed to load session: ${response.status}`)
    }

    const sessionDetails: SessionDetails = await response.json()

    // Convert session messages to ChatMessage format
    // Set the messages
    messages.value = sessionDetails.last_messages.map((msg) => ({
      author: msg.role === 'user' ? 'User' : props.characterId,
      content: msg.content,
      isUser: msg.role === 'user',
      timestamp: new Date(msg.created_at),
    }))
  } catch (err) {
    console.error('Failed to load session history:', err)
    // Don't show error to user for session loading failures, just start fresh
  }
}

const handleStop = () => {}

// Fetch persona for the session
const fetchSessionPersona = async (sessionId: string) => {
  try {
    const response = await fetch(`/api/sessions/${sessionId}/persona`)
    if (response.ok) {
      const data: SessionPersonaResponse = await response.json()
      personaName.value = data.persona_name
    }
  } catch (err) {
    // Silently fail - persona is optional
    console.debug('Failed to fetch session persona:', err)
  }
}

// Initialize session
onMounted(async () => {
  if (props.sessionId !== 'new') {
    currentSessionId.value = props.sessionId
    await loadSessionHistory(props.sessionId)
    await fetchSessionPersona(props.sessionId)
  }
})

onUnmounted(() => {
  disconnect()
})
</script>