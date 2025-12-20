<template>
  <UModal v-model:open="isOpen" :ui="{ width: 'max-w-3xl' }">
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-semibold">Current Session Summary</h3>
            <UButton
              color="neutral"
              variant="ghost"
              icon="i-lucide-x"
              size="sm"
              @click="handleClose"
            />
          </div>
        </template>

        <div class="max-h-[60vh] overflow-y-auto">
          <div v-if="loading" class="flex items-center justify-center py-8">
            <div class="flex flex-col items-center gap-3">
              <UIcon name="i-lucide-loader-2" class="w-8 h-8 animate-spin text-primary-500" />
              <p class="text-sm text-gray-500">Loading summary...</p>
            </div>
          </div>

          <div v-else-if="error" class="py-4">
            <UAlert
              color="error"
              variant="soft"
              icon="i-lucide-alert-triangle"
              title="Error"
              :description="error"
            />
          </div>

          <div v-else-if="!hasSummary" class="py-8 text-center">
            <div class="w-16 h-16 mx-auto rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center mb-4">
              <UIcon name="i-lucide-file-text" class="w-8 h-8 text-gray-400" />
            </div>
            <p class="text-gray-500">{{ summaryText }}</p>
          </div>

          <div v-else class="prose prose-sm dark:prose-invert max-w-none">
            <pre class="whitespace-pre-wrap font-mono text-sm bg-gray-50 dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-800">{{ summaryText }}</pre>
          </div>
        </div>

        <template #footer>
          <div class="flex gap-3 justify-end">
            <UButton
              color="neutral"
              variant="outline"
              @click="handleClose"
            >
              Close
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

interface Props {
  show: boolean
  sessionId: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
}>()

const isOpen = computed({
  get: () => props.show,
  set: (value: boolean) => {
    if (!value) {
      emit('close')
    }
  },
})

const loading = ref(false)
const error = ref<string | null>(null)
const summaryText = ref('')
const hasSummary = ref(false)

const handleClose = () => {
  emit('close')
}

const loadSummary = async () => {
  if (!props.sessionId || props.sessionId === 'new') {
    summaryText.value = 'No summary available for new sessions.'
    hasSummary.value = false
    return
  }

  loading.value = true
  error.value = null

  try {
    const response = await fetch(`/api/sessions/${props.sessionId}/summary`)

    if (!response.ok) {
      throw new Error(`Failed to load summary: ${response.status}`)
    }

    const data = await response.json()
    summaryText.value = data.summary_text
    hasSummary.value = data.has_summary
  } catch (err) {
    console.error('Failed to load summary:', err)
    error.value = err instanceof Error ? err.message : 'Failed to load summary'
  } finally {
    loading.value = false
  }
}

// Load summary when modal is opened
watch(() => props.show, (newValue) => {
  if (newValue) {
    loadSummary()
  }
}, { immediate: true })
</script>
