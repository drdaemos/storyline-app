<template>
  <section class="space-y-6">
  <!-- Header -->
  <div class="story-panel p-4 md:p-6 flex flex-col sm:flex-row gap-3 sm:gap-4 sm:items-center">
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
      <h2 class="text-xl sm:text-2xl story-headline truncate">{{ characterId }}</h2>
    </div>

    <!-- Second row on mobile: Session info and persona -->
    <div class="flex items-center gap-2 sm:gap-3 flex-wrap">
      <span class="text-xs sm:text-sm story-subtext font-mono hidden sm:inline">Session: {{ displaySessionId }}</span>
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
  <div class="pb-12 flex-1 justify-items-center story-panel p-4 md:p-6">
    <!-- Empty state -->
    <div v-if="messages.length === 0 && !isThinking" class="flex-1 flex items-center justify-center text-center p-8">
      <div class="space-y-4">
        <div class="w-16 h-16 mx-auto rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
          <UIcon name="i-lucide-message-square" class="w-8 h-8 text-gray-400" />
        </div>
        <h3 class="text-xl font-semibold">Start a conversation with {{ characterId }}</h3>
        <p class="story-subtext">Type a message below to begin chatting.</p>
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
          <div
            v-if="!message.isUser && message.metaText"
            class="mt-3 border border-gray-200 dark:border-gray-700 rounded-md p-3 text-xs leading-5 whitespace-pre-wrap font-mono text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900/40"
          >
            {{ message.metaText }}
          </div>
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
      :suggested-actions="suggestedActions"
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
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useEventStream } from '@/composables/useEventStream'
import { useApi } from '@/composables/useApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { getThinkingDescriptor } from '@/utils/formatters'
import ChatInput from '@/components/ChatInput.vue'
import SummaryModal from '@/components/SummaryModal.vue'
import type { ChatMessage as ChatMessageType, InteractRequest, SessionDetails, SessionPersonaResponse } from '@/types'

interface Props {
  characterId: string
  sessionId: string
}

const props = defineProps<Props>()

const router = useRouter()
const { startSessionWithScenario } = useApi()
const { settings } = useLocalSettings()
const {
  isConnected,
  error,
  streamingContent,
  sessionId,
  thinkingStage,
  suggestedActions,
  metaText,
  connect,
  disconnect,
  clearStreamContent,
  clearError,
} = useEventStream()

const messages = ref<ChatMessageType[]>([])
const isThinking = ref(false)
const currentSessionId = ref<string | null>(null)
const lastInteractPayload = ref<InteractRequest | null>(null)
const lastUserMessageForRetry = ref<string | null>(null)
const showSummaryModal = ref(false)
const personaName = ref<string | null>(null)

const bootstrapSuggestedActionsFromIntro = () => {
  if (messages.value.length === 0) return
  const hasUserTurn = messages.value.some(msg => msg.isUser)
  if (hasUserTurn) return
  suggestedActions.value = [
    'I pause and read the room before acting.',
    'I speak directly to the closest character.',
    'I make a cautious move to test the tension.',
  ]
}

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
  await sendMessage(text)
}

const ensureSessionForMessage = async (): Promise<string> => {
  if (props.sessionId !== 'new') {
    return props.sessionId
  }
  if (!settings.value.selectedPersonaId) {
    throw new Error('Select a persona before starting a new chat session.')
  }
  const response = await startSessionWithScenario({
    character_name: props.characterId,
    persona_id: settings.value.selectedPersonaId,
    intro_message: 'The scene begins. Continue naturally from here.',
    small_model_key: settings.value.smallModelKey,
    large_model_key: settings.value.largeModelKey,
  })
  currentSessionId.value = response.session_id
  router.replace({
    name: 'chat',
    params: {
      characterId: props.characterId,
      sessionId: response.session_id,
    },
  })
  return response.session_id
}

const sendInteractRequest = async (userMessage: string) => {
  // Start thinking
  isThinking.value = true
  clearStreamContent()

  try {
    const activeSessionId = await ensureSessionForMessage()
    const payload: InteractRequest = {
      character_name: props.characterId,
      user_message: userMessage,
      session_id: activeSessionId,
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
          metaText: metaText.value,
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
              characterId: props.characterId,
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
  lastUserMessageForRetry.value = text.trim()

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

const regenerateAfterError = async () => {
  if (isThinking.value) return

  // Clear the error and reattempt the last interact request
  clearError()

  const retryMessage = lastUserMessageForRetry.value ?? lastInteractPayload.value?.user_message
  if (!retryMessage) return
  await sendInteractRequest(retryMessage)
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
      metaText: msg.meta_text || null,
      isUser: msg.role === 'user',
      timestamp: new Date(msg.created_at),
    }))
    suggestedActions.value = sessionDetails.suggested_actions || []
    if (suggestedActions.value.length === 0) {
      bootstrapSuggestedActionsFromIntro()
    }
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
