import { computed, ref } from 'vue'
import { usePipelineApi } from '@/composables/usePipelineApi'
import type { ProcessorOptionsResponseV2 } from '@/types/pipeline'

const CACHE_TTL_MS = 2 * 60 * 1000

interface PromptProcessorOptionItem {
  id: string
  displayName: string
}

const cachedProcessorOptions = ref<PromptProcessorOptionItem[]>([])
const cacheExpiresAt = ref(0)
const loading = ref(false)
const error = ref<string | null>(null)
let inflightRequest: Promise<void> | null = null

const normalizeProcessorOptions = (
  options: PromptProcessorOptionItem[]
): PromptProcessorOptionItem[] => {
  const deduped = new Map<string, PromptProcessorOptionItem>()
  for (const option of options) {
    const normalizedId = option.id.trim()
    if (!normalizedId) {
      continue
    }
    if (!deduped.has(normalizedId)) {
      const normalizedDisplayName = option.displayName.trim()
      deduped.set(normalizedId, {
        id: normalizedId,
        displayName: normalizedDisplayName || normalizedId,
      })
    }
  }
  return [...deduped.values()]
}

const normalizeFromResponse = (
  response: ProcessorOptionsResponseV2
): PromptProcessorOptionItem[] => {
  const optionsFromPayload = response.processor_options?.map((option) => ({
    id: option.id,
    displayName: option.display_name,
  }))
  if (optionsFromPayload?.length) {
    return normalizeProcessorOptions(optionsFromPayload)
  }
  return normalizeProcessorOptions(
    response.processor_types.map((id) => ({
      id,
      displayName: id,
    }))
  )
}

export function usePromptProcessorOptions() {
  const { listPromptProcessors } = usePipelineApi()

  const refresh = async (force = false): Promise<void> => {
    const now = Date.now()
    if (!force && now < cacheExpiresAt.value && cachedProcessorOptions.value.length > 0) {
      return
    }

    if (inflightRequest) {
      return inflightRequest
    }

    loading.value = true
    error.value = null

    inflightRequest = (async () => {
      try {
        const response = await listPromptProcessors()
        cachedProcessorOptions.value = normalizeFromResponse(response)
        cacheExpiresAt.value = Date.now() + CACHE_TTL_MS
      } catch (err) {
        error.value = err instanceof Error ? err.message : 'Failed to load prompt processor options.'
      } finally {
        loading.value = false
        inflightRequest = null
      }
    })()

    return inflightRequest
  }

  const getOptionsWithCurrentValues = (currentValues: string[] = []): PromptProcessorOptionItem[] => {
    const currentOptions = currentValues.map((value) => ({
      id: value,
      displayName: value,
    }))
    return normalizeProcessorOptions([...cachedProcessorOptions.value, ...currentOptions])
  }

  return {
    processorOptions: computed(() => cachedProcessorOptions.value),
    processorIds: computed(() => cachedProcessorOptions.value.map((option) => option.id)),
    loading: computed(() => loading.value),
    error: computed(() => error.value),
    refresh,
    getOptionsWithCurrentValues,
  }
}
