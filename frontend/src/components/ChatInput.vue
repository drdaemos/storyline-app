<template>
  <div class="chat-input-container">
    <div class="chat-input">
      <div class="input-wrapper">
        <textarea
          ref="textareaRef"
          v-model="message"
          class="message-input"
          placeholder="Type your message..."
          rows="1"
          :disabled="disabled"
          @keydown="handleKeydown"
          @input="adjustHeight"
        />

        <button
          class="send-button"
          :disabled="disabled || !message.trim()"
          @click="sendMessage"
          title="Send message (Enter)"
        >
          <Send v-if="!disabled" :size="16" />
          <div v-else class="loading-spinner"></div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { Send } from 'lucide-vue-next'

interface Props {
  disabled?: boolean
  characterName?: string
}

defineProps<Props>()

const emit = defineEmits<{
  send: [message: string]
}>()

const message = ref('')
const textareaRef = ref<HTMLTextAreaElement>()

const sendMessage = () => {
  const text = message.value.trim()
  if (!text) return

  emit('send', text)
  message.value = ''
  adjustHeight()
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter') {
    if (event.ctrlKey || event.metaKey) {
      event.preventDefault()
      sendMessage()
    } else if (!event.shiftKey) {
      event.preventDefault()
      sendMessage()
    }
  }
}

const adjustHeight = async () => {
  await nextTick()
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
    textareaRef.value.style.height = `${textareaRef.value.scrollHeight}px`
  }
}

onMounted(() => {
  adjustHeight()
})
</script>

<style scoped>
.chat-input-container {
  position: sticky;
  bottom: 0;
  background: transparent;
  padding: 1rem;
  margin: 0 1rem 1rem 1rem;
}

.chat-input {
  max-width: 800px;
  margin: 0 auto;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(8px);
}

.input-wrapper {
  display: flex;
  gap: 0.75rem;
  flex-direction: row;
  align-items: center;
  background: transparent;
  border: none;
  padding: 0.75rem 1rem;
}

.chat-input:focus-within {
  border-color: var(--primary-color);
  box-shadow: 0 4px 0 rgba(37, 99, 235, 0.3), 0 8px 0 rgba(37, 99, 235, 0.1), 0 0 0 3px rgb(37 99 235 / 0.1);
}

.message-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 1rem;
  line-height: 1.5;
  resize: none;
  max-height: 120px;
  overflow-y: auto;
  background: transparent;
  font-family: inherit;
  color: var(--text-primary);
  min-height: 24px;
}

.message-input::placeholder {
  color: var(--text-secondary);
}

.send-button {
  background: var(--primary-color);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  padding: 0.75rem;
  font-size: 1.25rem;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
  min-width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  align-self: flex-end;
}

.send-button:hover:not(:disabled) {
  background: var(--primary-hover);
}

.send-button:disabled {
  background: var(--secondary-color);
  cursor: not-allowed;
}

.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.75rem;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.thinking-dots {
  display: flex;
  gap: 4px;
}

.thinking-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-secondary);
  animation: thinking-pulse 1.4s infinite ease-in-out;
}

.thinking-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.thinking-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes thinking-pulse {
  0%, 80%, 100% {
    opacity: 0.3;
    transform: scale(1);
  }
  40% {
    opacity: 1;
    transform: scale(1.2);
  }
}

.input-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.75rem;
  justify-content: flex-end;
}

.btn-sm {
  padding: 0.5rem 0.875rem;
  font-size: 0.875rem;
  min-height: 36px;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top: 2px solid currentColor;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@media (max-width: 768px) {
  .chat-input-container {
    padding: 1rem 0.5rem;
    margin: 0 0.5rem 0.5rem 0.5rem;
  }

  .input-wrapper {
    padding: 0.625rem 0.875rem;
  }

  .send-button {
    padding: 0.625rem;
    min-width: 36px;
    height: 36px;
    font-size: 1.1rem;
  }

  .input-actions {
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .btn-sm {
    padding: 0.5rem 0.75rem;
    font-size: 0.8rem;
  }
}

@media (max-width: 480px) {
  .chat-input-container {
    margin: 0 0.25rem 0.5rem 0.25rem;
  }

  .input-wrapper {
    flex-direction: row;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
  }

  .send-button {
    width: auto;
    min-width: 36px;
    height: 36px;
    padding: 0.5rem;
    font-size: 1.1rem;
  }
}
</style>