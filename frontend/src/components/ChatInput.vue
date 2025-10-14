<template>
  <div class="fixed bottom-0 left-0 right-0 px-4 pb-4 bg-gradient-to-t from-white dark:from-gray-950 via-white/80 dark:via-gray-950/80 to-transparent pt-4">
    <div class="max-w-2xl mx-auto">
      <UChatPrompt
        v-model="message"
        placeholder="Type your message..."
        :autofocus="true"
        :disabled="disabled"
        variant="outline"
        @submit="sendMessage"
      >
        <UButton
          type="submit"
          :disabled="disabled || !message.trim()"
          :icon="disabled ? 'i-lucide-loader-2' : 'i-lucide-send'"
          :loading="disabled"
          color="primary"
          size="sm"
          class="rounded-full"
        />
      </UChatPrompt>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  disabled?: boolean
  characterName?: string
}

defineProps<Props>()

const emit = defineEmits<{
  send: [message: string]
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
