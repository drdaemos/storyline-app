<template>
  <div
    class="chat-message"
    :class="{
      'user-message': message.isUser,
      'character-message': !message.isUser,
      'streaming': isStreaming
    }"
  >
    <div class="message-avatar">
      <div v-if="message.isUser" class="user-avatar">
        You
      </div>
      <div v-else class="character-avatar">
        {{ message.author.charAt(0).toUpperCase() }}
      </div>

      <div v-if="showRewind && message.isUser && !isStreaming" class="avatar-actions">
        <button
          class="btn-icon rewind-btn"
          @click="emit('rewind')"
          title="Remove this exchange"
        >
          <Undo2 :size="16" />
        </button>
      </div>
    </div>

    <div class="message-content">
      <div class="message-header">
        <span class="message-author">{{ message.isUser ? 'You' : message.author }}</span>
        <time class="message-time">{{ formatMessageTime(message.timestamp) }}</time>
      </div>

      <div class="message-body">
        <div
          v-if="isStreaming"
          class="streaming-content"
          v-html="parseMarkdown(parsedContent.visible)"
        ></div>
        <div
          v-else
          class="message-text"
          v-html="parseMarkdown(parsedContent.visible)"
        ></div>

        <!-- Hidden Context Section / Actions Footer -->
        <div v-if="(parsedContent.hiddenContext && !message.isUser) || (showActions && !message.isUser && !isStreaming)" class="message-footer">
          <button
            v-if="parsedContent.hiddenContext"
            class="btn-icon context-btn"
            :class="{ active: hiddenContextRevealed }"
            @click="toggleHiddenContext"
            :title="hiddenContextRevealed ? 'Hide context' : 'Show context'"
          >
            <ReceiptText :size="16" />
          </button>
          <button
            v-if="showActions && !isStreaming"
            class="btn-icon regenerate-btn"
            @click="emit('regenerate')"
            title="Regenerate response"
          >
            <RefreshCw :size="16" />
          </button>
        </div>

        <div
          v-if="hiddenContextRevealed && parsedContent.hiddenContext"
          class="hidden-context-content"
        >
          {{ parsedContent.hiddenContext }}
        </div>

        <div v-if="isStreaming" class="typing-indicator">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ChatMessage } from '@/types'
import { formatMessageTime, parseMarkdown } from '@/utils/formatters'
import { Undo2, RefreshCw, ReceiptText } from 'lucide-vue-next'

interface Props {
  message: ChatMessage
  isStreaming?: boolean
  showActions?: boolean
  showRewind?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  regenerate: []
  rewind: []
}>()

const hiddenContextRevealed = ref(false)

const parsedContent = computed(() => {
  const content = props.message.content
  const hiddenContextRegex = /<hidden_context>(.*?)<\/hidden_context>/is

  const match = content.match(hiddenContextRegex)

  if (match) {
    return {
      visible: content.replace(hiddenContextRegex, '').trim(),
      hiddenContext: match[1].trim()
    }
  }

  return {
    visible: content,
    hiddenContext: null
  }
})

const toggleHiddenContext = () => {
  hiddenContextRevealed.value = !hiddenContextRevealed.value
}
</script>

<style scoped>
.chat-message {
  display: flex;
  gap: 0.75rem;
  padding: 1rem 0;
  max-width: 100%;
}

.user-message {
  flex-direction: row-reverse;
}

.user-message .message-content {
  background: var(--primary-color);
  color: white;
  margin-left: 2rem;
}

.user-message .message-header {
  color: rgba(255, 255, 255, 0.9);
}

.character-message .message-content {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  margin-right: 2rem;
}

.message-avatar {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.user-avatar,
.character-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  font-weight: 600;
}

.user-avatar {
  background: var(--primary-color);
  color: white;
}

.character-avatar {
  background: var(--secondary-color);
  color: white;
}

.message-content {
  flex: 1;
  border-radius: var(--radius-lg);
  padding: 1rem 1.25rem;
  min-width: 0;
  position: relative;
}

.message-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
}

.message-author {
  font-weight: 600;
}

.message-time {
  opacity: 0.7;
  font-size: 0.75rem;
}

.message-body {
  position: relative;
}

.message-text,
.streaming-content {
  line-height: 1.6;
  word-wrap: break-word;
}

.streaming-content {
  position: relative;
}

.streaming-content::after {
  content: '|';
  animation: blink 1s infinite;
  margin-left: 2px;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.typing-indicator {
  display: flex;
  gap: 4px;
  margin-top: 0.5rem;
  align-items: center;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.4;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 80%, 100% {
    opacity: 0.4;
    transform: scale(1);
  }
  40% {
    opacity: 1;
    transform: scale(1.2);
  }
}

.message-footer {
  margin-top: 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.btn-icon {
  background: none;
  border: none;
  padding: 0.375rem;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background-color 0.2s;
  font-size: 0.875rem;
  opacity: 0.7;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-icon:hover {
  background: rgba(0, 0, 0, 0.05);
  opacity: 1;
}

.btn-icon.active {
  opacity: 1;
  background: rgba(0, 0, 0, 0.08);
}

.user-message .btn-icon:hover {
  background: rgba(255, 255, 255, 0.1);
}

.user-message .btn-icon.active {
  background: rgba(255, 255, 255, 0.15);
}

.avatar-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.avatar-actions .btn-icon {
  padding: 0.375rem;
  font-size: 0.875rem;
  min-width: 32px;
  min-height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-actions .btn-icon:hover {
  background: rgba(0, 0, 0, 0.1);
  opacity: 1;
}

/* Markdown styling */
.message-text :deep(strong),
.streaming-content :deep(strong) {
  font-weight: 600;
}

.message-text :deep(em),
.streaming-content :deep(em) {
  font-style: italic;
}

.message-text :deep(br),
.streaming-content :deep(br) {
  line-height: 1.6;
}

/* Hidden Context Styling */
.hidden-context-content {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.05);
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  opacity: 0.7;
  font-style: italic;
  white-space: pre-wrap;
}

.user-message .hidden-context-content {
  background: rgba(255, 255, 255, 0.1);
}

@media (max-width: 768px) {
  .chat-message {
    gap: 0.5rem;
  }

  .user-message .message-content {
    margin-left: 1rem;
  }

  .character-message .message-content {
    margin-right: 1rem;
  }

  .message-content {
    padding: 0.875rem 1rem;
  }

  .user-avatar,
  .character-avatar {
    width: 32px;
    height: 32px;
    font-size: 0.75rem;
  }

  .message-header {
    font-size: 0.8rem;
  }

  .message-time {
    font-size: 0.7rem;
  }
}
</style>