<template>
  <div class="sticky bottom-4 left-4 right-4 pt-4 max-w-2xl w-full">
    <div class="mx-auto">
      <div
        v-if="props.suggestedActions.length > 0"
        class="mb-3 rounded-lg border border-primary/30 bg-primary/8 px-3 py-3 shadow-md shadow-primary/10"
      >
        <p class="text-xs uppercase tracking-wide story-subtext mb-2">Suggested Actions</p>
        <div class="flex flex-wrap gap-2">
          <UButton
            v-for="(suggestion, index) in props.suggestedActions"
            :key="`${suggestion}-${index}`"
            color="primary"
            variant="soft"
            size="xs"
            :disabled="disabled"
            class="text-left"
            @click="sendSuggested(suggestion)"
          >
            {{ suggestion }}
          </UButton>
        </div>
      </div>
      <UChatPrompt
        v-model="message"
        placeholder="What do you do?"
        :autofocus="true"
        :disabled="disabled"
        variant="soft"
        :error="error"
        @submit="sendMessage"
        class="border-1 border-primary/40 shadow-md shadow-primary/20"
      >
        <UChatPromptSubmit
            :status="chatStatus"
            @stop="emit('stop')"
            @reload="emit('regenerate')"
            :variant="disabled ? 'ghost' : 'solid'"
            :class="disabled ? 'cursor-default' : 'cursor-pointer'"
            streaming-icon="i-lucide-square-stop"
        />
      </UChatPrompt>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

type ChatStatus = 'submitted' | 'streaming' | 'ready' | 'error'

interface Props {
  chatStatus: ChatStatus
  error?: Error
  disabled?: boolean
  suggestedActions?: string[]
}

const props = withDefaults(defineProps<Props>(), {
  suggestedActions: () => [],
})

const emit = defineEmits<{
  send: [message: string]
  regenerate: []
  stop: []
}>()

const message = ref('')

const sendMessage = (event: Event) => {
  event.preventDefault()

  const text = message.value.trim()
  if (!text) return

  emit('send', text)
  message.value = ''
}

const sendSuggested = (suggestion: string) => {
  if (!suggestion.trim()) return
  emit('send', suggestion.trim())
}
</script>
