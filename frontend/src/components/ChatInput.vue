<template>
  <div class="sticky bottom-4 left-4 right-4 pt-4 max-w-2xl w-full">
    <div class="mx-auto">
      <UChatPrompt
        v-model="message"
        placeholder="Type your message..."
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
}

defineProps<Props>()

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
</script>
