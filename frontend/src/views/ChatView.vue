<template>
  <div class="chat-view">
    <header class="chat-header">
      <div class="header-content">
        <div class="character-info">
          <router-link to="/" class="back-button">
            ← Back
          </router-link>
          <div class="character-details">
            <h2>{{ characterName }}</h2>
            <span class="session-id">Session: {{ displaySessionId }}</span>
          </div>
        </div>

        <div class="chat-status">
          <div v-if="isConnected" class="status-indicator connected">
            Connected
          </div>
          <div v-else-if="error" class="status-indicator error">
            {{ error }}
          </div>
        </div>
      </div>
    </header>

    <div class="chat-container">
      <div
        ref="messagesContainer"
        class="messages-container"
        @scroll="handleScroll"
      >
        <div v-if="messages.length === 0 && !isThinking" class="welcome-message">
          <h3>Start a conversation with {{ characterName }}</h3>
          <p>Type a message below to begin chatting.</p>
        </div>

        <ChatMessage
          v-for="message in messages"
          :key="message.id"
          :message="message"
          :show-actions="isLastCharacterMessage(message)"
          @regenerate="regenerateLastMessage"
        />

        <!-- Streaming message -->
        <ChatMessage
          v-if="isThinking && streamingContent"
          :message="currentStreamingMessage"
          :is-streaming="true"
        />
      </div>

      <ChatInput
        :disabled="isThinking"
        :character-name="characterName"
        :can-rewind="messages.length >= 2"
        :can-regenerate="canRegenerate"
        @send="sendMessage"
        @rewind="rewindLastExchange"
        @regenerate="regenerateLastMessage"
      />
    </div>

    <div v-if="showScrollButton" class="scroll-to-bottom">
      <button class="btn btn-secondary" @click="scrollToBottom">
        ↓ New messages
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useEventStream } from '@/composables/useEventStream'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { generateSessionId } from '@/utils/formatters'
import ChatMessage from '@/components/ChatMessage.vue'
import ChatInput from '@/components/ChatInput.vue'
import type { ChatMessage as ChatMessageType, InteractRequest } from '@/types'

interface Props {
  characterName: string
  sessionId: string
}

const props = defineProps<Props>()

const route = useRoute()
const router = useRouter()
const { settings } = useLocalSettings()
const {
  isConnected,
  error,
  streamingContent,
  connect,
  disconnect,
  clearStreamContent
} = useEventStream()

const messages = ref<ChatMessageType[]>([])
const messagesContainer = ref<HTMLElement>()
const isThinking = ref(false)
const currentSessionId = ref<string | null>(null)
const showScrollButton = ref(false)
const autoScroll = ref(true)

const displaySessionId = computed(() => {
  if (props.sessionId === 'new') {
    return 'New Session'
  }
  return props.sessionId.substring(0, 8)
})

const canRegenerate = computed(() => {
  const lastMessage = messages.value[messages.value.length - 1]
  return lastMessage && !lastMessage.isUser && !isThinking.value
})

const currentStreamingMessage = computed((): ChatMessageType => {
  return {
    id: 'streaming',
    author: props.characterName,
    content: streamingContent.value,
    isUser: false,
    timestamp: new Date()
  }
})

const isLastCharacterMessage = (message: ChatMessageType): boolean => {
  const lastMessage = messages.value[messages.value.length - 1]
  return message === lastMessage && !message.isUser
}

const sendMessage = async (text: string) => {
  if (!text.trim() || isThinking.value) return

  // Add user message
  const userMessage: ChatMessageType = {
    id: generateSessionId(),
    author: 'User',
    content: text.trim(),
    isUser: true,
    timestamp: new Date()
  }

  messages.value.push(userMessage)
  await scrollToBottom()

  // Start thinking
  isThinking.value = true
  clearStreamContent()

  try {
    // Determine session ID
    let sessionId = currentSessionId.value
    if (props.sessionId === 'new' && !sessionId) {
      sessionId = null // Backend will create new session
    } else if (props.sessionId !== 'new') {
      sessionId = props.sessionId
    }

    const payload: InteractRequest = {
      character_name: props.characterName,
      user_message: text.trim(),
      session_id: sessionId,
      processor_type: settings.value.aiProcessor
    }

    // Start streaming response
    const eventSource = await connect(payload)

    // Monitor streaming completion
    const checkCompletion = () => {
      if (!isConnected.value && streamingContent.value) {
        // Stream completed successfully
        const characterMessage: ChatMessageType = {
          id: generateSessionId(),
          author: props.characterName,
          content: streamingContent.value,
          isUser: false,
          timestamp: new Date()
        }

        messages.value.push(characterMessage)
        clearStreamContent()
        isThinking.value = false

        // Update session ID if this was a new session
        if (props.sessionId === 'new' && !currentSessionId.value) {
          currentSessionId.value = generateSessionId()
          // Update URL without navigation
          router.replace({
            name: 'chat',
            params: {
              characterName: props.characterName,
              sessionId: currentSessionId.value
            }
          })
        }

        scrollToBottom()
      } else if (!isConnected.value && error.value) {
        // Stream failed
        isThinking.value = false
        console.error('Stream error:', error.value)
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
    isThinking.value = false
    console.error('Failed to send message:', err)
  }
}

const rewindLastExchange = () => {
  if (messages.value.length < 2) return

  // Remove last two messages (user + character)
  const lastMessage = messages.value[messages.value.length - 1]
  const secondLastMessage = messages.value[messages.value.length - 2]

  if (lastMessage.isUser) {
    // Last message is from user, remove only that
    messages.value.pop()
  } else if (secondLastMessage && secondLastMessage.isUser) {
    // Remove both user and character messages
    messages.value.splice(-2, 2)
  } else {
    // Only remove character message
    messages.value.pop()
  }
}

const regenerateLastMessage = async () => {
  if (isThinking.value || messages.value.length === 0) return

  const lastMessage = messages.value[messages.value.length - 1]
  if (lastMessage.isUser) return

  // Find the user message that prompted this response
  let userMessage = null
  for (let i = messages.value.length - 2; i >= 0; i--) {
    if (messages.value[i].isUser) {
      userMessage = messages.value[i]
      break
    }
  }

  if (!userMessage) return

  // Remove last character message
  messages.value.pop()

  // Resend the user message
  await sendMessage(userMessage.content)
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const handleScroll = () => {
  if (!messagesContainer.value) return

  const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
  const isNearBottom = scrollHeight - scrollTop - clientHeight < 100

  autoScroll.value = isNearBottom
  showScrollButton.value = !isNearBottom && messages.value.length > 0
}

// Watch for streaming content changes and auto-scroll
watch(streamingContent, () => {
  if (autoScroll.value) {
    scrollToBottom()
  }
}, { flush: 'post' })

// Initialize session
onMounted(() => {
  if (props.sessionId !== 'new') {
    currentSessionId.value = props.sessionId
  }
})

onUnmounted(() => {
  disconnect()
})
</script>

<style scoped>
.chat-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.chat-header {
  background: var(--surface-color);
  border-bottom: 1px solid var(--border-color);
  padding: 1rem 1.5rem;
  flex-shrink: 0;
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.character-info {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.back-button {
  color: var(--text-secondary);
  text-decoration: none;
  font-weight: 500;
  padding: 0.5rem;
  border-radius: var(--radius-sm);
  transition: all 0.2s;
}

.back-button:hover {
  color: var(--primary-color);
  background: #eff6ff;
}

.character-details h2 {
  margin: 0;
  font-size: 1.5rem;
  color: var(--text-primary);
}

.session-id {
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-family: monospace;
}

.chat-status {
  display: flex;
  align-items: center;
}

.status-indicator {
  padding: 0.375rem 0.75rem;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  font-weight: 500;
}

.status-indicator.connected {
  background: #dcfce7;
  color: #166534;
}

.status-indicator.error {
  background: #fee2e2;
  color: #dc2626;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 1.5rem 0;
  scroll-behavior: smooth;
}

.welcome-message {
  text-align: center;
  padding: 3rem 2rem;
  color: var(--text-secondary);
}

.welcome-message h3 {
  margin: 0 0 1rem 0;
  color: var(--text-primary);
  font-size: 1.5rem;
}

.welcome-message p {
  margin: 0;
  font-size: 1.1rem;
}

.scroll-to-bottom {
  position: fixed;
  bottom: 120px;
  right: 2rem;
  z-index: 10;
}

.scroll-to-bottom .btn {
  box-shadow: var(--shadow-lg);
  animation: bounce 2s infinite;
}

@keyframes bounce {
  0%, 20%, 50%, 80%, 100% {
    transform: translateY(0);
  }
  40% {
    transform: translateY(-3px);
  }
  60% {
    transform: translateY(-2px);
  }
}

@media (max-width: 768px) {
  .chat-header {
    padding: 1rem;
  }

  .header-content {
    flex-direction: column;
    gap: 1rem;
    align-items: flex-start;
  }

  .character-info {
    align-self: stretch;
    justify-content: space-between;
  }

  .character-details {
    text-align: right;
  }

  .character-details h2 {
    font-size: 1.25rem;
  }

  .messages-container {
    padding: 1rem;
  }

  .welcome-message {
    padding: 2rem 1rem;
  }

  .welcome-message h3 {
    font-size: 1.25rem;
  }

  .scroll-to-bottom {
    bottom: 100px;
    right: 1rem;
  }
}

@media (max-width: 480px) {
  .character-info {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .character-details {
    text-align: left;
  }

  .character-details h2 {
    font-size: 1.125rem;
  }

  .messages-container {
    padding: 0.75rem;
  }
}

/* Custom scrollbar */
.messages-container::-webkit-scrollbar {
  width: 6px;
}

.messages-container::-webkit-scrollbar-track {
  background: var(--background-color);
}

.messages-container::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: var(--secondary-color);
}
</style>