<template>
  <div class="relative">
    <!-- Rewind button for user messages -->
    <div v-if="showRewind && message.isUser && !isStreaming" class="absolute -left-12 top-2">
      <UButton
        color="neutral"
        variant="ghost"
        icon="i-lucide-undo-2"
        size="xs"
        @click="emit('rewind')"
        title="Remove this exchange"
      />
    </div>

    <UChatMessage
      :id="message.timestamp.toString()"
      :role="message.isUser ? 'user' : 'assistant'"
      :parts="messageParts"
      :avatar="avatarProps"
      :variant="message.isUser ? 'soft' : 'naked'"
      :side="message.isUser ? 'right' : 'left'"
      :actions="messageActions"
    >
      <template #content>
        <div class="space-y-2">
          <!-- Message header -->
          <div class="flex items-center justify-between gap-4 text-sm mb-2">
            <span class="font-semibold">{{ message.isUser ? 'You' : message.author }}</span>
            <time class="text-xs opacity-70">{{ formatMessageTime(message.timestamp) }}</time>
          </div>

          <!-- Message content with markdown -->
          <div
            class="prose prose-sm dark:prose-invert max-w-none"
            v-html="parseMarkdown(parsedContent.visible)"
          ></div>

          <!-- Streaming indicator -->
          <div v-if="isStreaming" class="flex gap-1 mt-2">
            <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0s"></span>
            <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0.2s"></span>
            <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0.4s"></span>
          </div>

          <!-- Hidden context reveal -->
          <div v-if="hiddenContextRevealed && parsedContent.hiddenContext" class="mt-3">
            <UAlert
              color="neutral"
              variant="soft"
              icon="i-lucide-receipt-text"
              :description="parsedContent.hiddenContext"
            />
          </div>
        </div>
      </template>
    </UChatMessage>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ChatMessage } from '@/types'
import { formatMessageTime, parseMarkdown } from '@/utils/formatters'

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
      hiddenContext: match[1].trim(),
    }
  }

  return {
    visible: content,
    hiddenContext: null,
  }
})

// Convert message to AI SDK v5 parts format
const messageParts = computed(() => {
  return [
    {
      type: 'text' as const,
      text: parsedContent.value.visible,
    },
  ]
})

// Avatar configuration
const avatarProps = computed(() => {
  if (props.message.isUser) {
    return {
      icon: 'i-lucide-user',
    }
  }
  return {
    text: props.message.author.charAt(0).toUpperCase(),
  }
})

// Message actions (regenerate, hidden context toggle)
const messageActions = computed(() => {
  if (props.message.isUser || props.isStreaming) return []

  const actions = []

  // Hidden context toggle
  if (parsedContent.value.hiddenContext) {
    actions.push({
      icon: 'i-lucide-receipt-text',
      label: hiddenContextRevealed.value ? 'Hide context' : 'Show context',
      onClick: () => {
        hiddenContextRevealed.value = !hiddenContextRevealed.value
      },
    })
  }

  // Regenerate action
  if (props.showActions) {
    actions.push({
      icon: 'i-lucide-refresh-cw',
      label: 'Regenerate response',
      onClick: () => emit('regenerate'),
    })
  }

  return actions
})
</script>
