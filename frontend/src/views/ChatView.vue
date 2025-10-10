<template>
  <div class="chat-view">
    <header class="chat-header">
      <div class="header-content">
        <div class="character-info">
          <router-link to="/" class="btn btn-secondary">
            <ArrowLeft :size="20" />
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

          <button
            class="settings-button"
            @click="showSettings = !showSettings"
            title="Settings"
          >
            <Settings :size="20" />
          </button>
        </div>
      </div>
    </header>

    <!-- Settings Modal -->
    <SettingsMenu
      :show="showSettings"
      @update:show="showSettings = $event"
      @setting-changed="onSettingChanged"
    />

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
          :message="message"
          :show-actions="isLastCharacterMessage(message)"
          :show-rewind="isLastUserMessage(message)"
          @regenerate="regenerateLastMessage"
          @rewind="rewindLastExchange"
        />

        <!-- Error message -->
        <div v-if="error && !isThinking" class="error-message">
          <div class="error-content">
            <AlertTriangle :size="20" class="error-icon" />
            <div class="error-text">
              <strong>Error:</strong> {{ error }}
            </div>
            <button
              class="error-regenerate"
              @click="regenerateAfterError"
              title="Regenerate response"
            >
              <RefreshCw :size="16" class="inline mr-1" /> Regenerate
            </button>
          </div>
        </div>

        <!-- Thinking indicator -->
        <div v-if="isThinking && !streamingContent" class="thinking-indicator">
          <div class="thinking-content">
            <div class="thinking-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <span class="thinking-text">{{ thinkingMessage }}</span>
          </div>
        </div>

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
        @send="handleChatInput"
      />
    </div>

    <div v-if="showScrollButton" class="scroll-to-bottom">
      <button class="btn btn-secondary" @click="scrollToBottom">
        <ChevronDown :size="16" class="inline mr-1" /> New messages
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
// biome-ignore lint/style/useNamingConvention: Vue template functions need specific names
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useEventStream } from '@/composables/useEventStream'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { getThinkingDescriptor } from '@/utils/formatters'
import ChatMessage from '@/components/ChatMessage.vue'
import ChatInput from '@/components/ChatInput.vue'
import SettingsMenu from '@/components/SettingsMenu.vue'
import type { ChatMessage as ChatMessageType, InteractRequest, SessionDetails } from '@/types'
import { ArrowLeft, AlertTriangle, RefreshCw, ChevronDown, Settings } from 'lucide-vue-next'

interface Props {
  characterName: string
  sessionId: string
}

const props = defineProps<Props>()

const router = useRouter()
const { settings, loadSettings } = useLocalSettings()
const {
  isConnected,
  error,
  streamingContent,
  sessionId,
  thinkingStage,
  connect,
  disconnect,
  clearStreamContent,
  clearError
} = useEventStream()

const messages = ref<ChatMessageType[]>([])
const messagesContainer = ref<HTMLElement>()
const isThinking = ref(false)
const currentSessionId = ref<string | null>(null)
const showScrollButton = ref(false)
const autoScroll = ref(true)
const lastInteractPayload = ref<InteractRequest | null>(null)
const showSettings = ref(false)

const displaySessionId = computed(() => {
  if (props.sessionId === 'new') {
    return 'New Session'
  }
  return props.sessionId.substring(0, 8)
})

const currentStreamingMessage = computed((): ChatMessageType => {
  return {
    author: props.characterName,
    content: streamingContent.value,
    isUser: false,
    timestamp: new Date()
  }
})

const thinkingMessage = computed((): string => {
  if (!thinkingStage.value) {
    return `${props.characterName} is thinking...`
  }
  return getThinkingDescriptor(thinkingStage.value, props.characterName)
})

const isLastCharacterMessage = (message: ChatMessageType): boolean => {
  const lastMessage = messages.value[messages.value.length - 1]
  return message === lastMessage && !message.isUser
}

const isLastUserMessage = (message: ChatMessageType): boolean => {
  // Show rewind button on the last user message only if there's a subsequent AI response
  if (!message.isUser) return false

  const messageIndex = messages.value.indexOf(message)
  const nextMessage = messages.value[messageIndex + 1]

  // Show if this user message has an AI response after it
  return nextMessage && !nextMessage.isUser
}

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

  await scrollToBottom()

  try {
    const payload: InteractRequest = {
      character_name: props.characterName,
      user_message: userMessage,
      session_id: props.sessionId === 'new' ? null : props.sessionId,
      processor_type: settings.value.aiProcessor,
      backup_processor_type: settings.value.backupProcessor
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
          author: props.characterName,
          content: streamingContent.value,
          isUser: false,
          timestamp: new Date()
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
              characterName: props.characterName,
              sessionId: sessionId?.value
            }
          })
        }

        scrollToBottom()
      } else if (!isConnected.value && !streamingContent.value && !error.value) {
        // Command completed without content (like /rewind)
        isThinking.value = false
        scrollToBottom()
      } else if (!isConnected.value && error.value) {
        // Stream failed - unblock send button and keep error visible
        isThinking.value = false
        // Auto-scroll to show error message
        scrollToBottom()
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
    timestamp: new Date()
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

const scrollToBottom = async () => {
  await nextTick()
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: 'smooth'
  })
}

const handleScroll = () => {
  if (!messagesContainer.value) return

  const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
  const isNearBottom = scrollHeight - scrollTop - clientHeight < 100

  autoScroll.value = isNearBottom
  showScrollButton.value = !isNearBottom && messages.value.length > 0
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
    const chatMessages: ChatMessageType[] = sessionDetails.last_messages.map(msg => ({
      author: msg.role === 'user' ? 'User' : props.characterName,
      content: msg.content,
      isUser: msg.role === 'user',
      timestamp: new Date(msg.created_at)
    }))

    // Set the messages
    messages.value = chatMessages

    // Auto-scroll to bottom after loading
    await nextTick()
    scrollToBottom()

  } catch (err) {
    console.error('Failed to load session history:', err)
    // Don't show error to user for session loading failures, just start fresh
  }
}

// Watch for streaming content changes and auto-scroll
watch(streamingContent, () => {
  if (autoScroll.value) {
    scrollToBottom()
  }
}, { flush: 'post' })

// Watch for messages array changes and auto-scroll to new messages
watch(messages, (newMessages, oldMessages) => {
  // Only auto-scroll if messages were added and user is near bottom
  if (newMessages.length > (oldMessages?.length || 0) && autoScroll.value) {
    nextTick(() => {
      scrollToBottom()
    })
  }
}, { flush: 'post' })

// Watch for error changes and auto-scroll to show error messages
watch(error, (newError) => {
  if (newError && autoScroll.value) {
    nextTick(() => {
      scrollToBottom()
    })
  }
}, { flush: 'post' })

const onSettingChanged = (payload: { key: string; value: any }) => {
  // Settings are automatically persisted by useLocalSettings
  // Just close the modal for non-theme changes that don't need immediate feedback
  if (payload.key !== 'theme') {
    // Could show a toast notification here if desired
    console.log(`Setting ${payload.key} changed to:`, payload.value)
  }
}

// Initialize session
onMounted(async () => {
  // Reload settings to pick up any changes made in SettingsMenu
  loadSettings()

  if (props.sessionId !== 'new') {
    currentSessionId.value = props.sessionId
    await loadSessionHistory(props.sessionId)
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
  gap: 1rem;
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

.error-message {
  margin: 1rem 0;
  padding: 1rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: var(--radius-md);
  animation: slideIn 0.3s ease-out;
}

.error-content {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

.error-icon {
  font-size: 1.25rem;
  flex-shrink: 0;
}

.error-text {
  flex: 1;
  color: #dc2626;
  line-height: 1.5;
}

.error-text strong {
  color: #991b1b;
}

.error-regenerate {
  background: #dc2626;
  border: none;
  color: white;
  font-size: 0.875rem;
  cursor: pointer;
  padding: 0.5rem 1rem;
  border-radius: var(--radius-sm);
  transition: all 0.2s;
  flex-shrink: 0;
  font-weight: 500;
}

.error-regenerate:hover {
  background: #b91c1c;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.thinking-indicator {
  margin: 1rem 0;
  padding: 1rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: var(--radius-md);
  animation: fadeIn 0.3s ease-in;
}

.thinking-content {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--text-secondary);
  font-style: italic;
}

.thinking-dots {
  display: flex;
  gap: 4px;
}

.thinking-dots span {
  width: 8px;
  height: 8px;
  background: var(--primary-color);
  border-radius: 50%;
  animation: pulse 1.4s ease-in-out infinite both;
}

.thinking-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.thinking-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

.thinking-dots span:nth-child(3) {
  animation-delay: 0s;
}

.thinking-text {
  font-size: 0.95rem;
}

@keyframes pulse {
  0%, 80%, 100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Icon utility classes */
.inline {
  display: inline-block;
  vertical-align: middle;
}

.mr-1 {
  margin-right: 0.25rem;
}

/* Settings button styles */
.settings-button {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.5rem;
  border-radius: var(--radius-sm);
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.settings-button:hover {
  color: var(--primary-color);
  background: #eff6ff;
}
</style>