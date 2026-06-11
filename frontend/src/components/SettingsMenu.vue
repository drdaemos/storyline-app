<template>
  <UButton
    color="neutral"
    variant="ghost"
    icon="i-lucide-settings"
    class="cursor-pointer"
    @click="open = true"
  />

  <UModal v-model:open="open" title="Settings">
    <template #body>
      <UForm class="space-y-6">
        <UFormField label="AI Processor" description="Choose which AI model to use for new conversations. Changes apply to new sessions only.">
          <USelect
            class="w-full"
            value-key="id"
            v-model="settings.aiProcessor"
            :items="processorOptions"
          />
        </UFormField>

        <UFormField label="Backup AI Processor" description="Choose which AI model to use as a fallback if the primary processor fails.">
          <USelect
            class="w-full"
            value-key="id"
            v-model="settings.backupProcessor"
            :items="processorOptions"
          />
        </UFormField>

        <UFormField label="Last Selected Character">
          <div>{{ settings.lastSelectedCharacter || 'None' }}</div>
        </UFormField>

        <UButton
          color="neutral"
          variant="outline"
          block
          icon="i-lucide-trash-2"
          @click="clearSettings"
        >
          Clear All Settings
        </UButton>
        <p class="text-sm text-gray-500 -mt-4">
          Reset all settings to default values. This will not affect your conversations.
        </p>
      </UForm>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { SelectItem } from '@nuxt/ui'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { usePromptProcessorOptions } from '@/composables/usePromptProcessorOptions'

const open = ref(false)

const { settings, clearSettings } = useLocalSettings()
const { refresh: refreshProcessorOptions, getOptionsWithCurrentValues } = usePromptProcessorOptions()

const processorOptions = computed<SelectItem[]>(() =>
  getOptionsWithCurrentValues([settings.value.aiProcessor, settings.value.backupProcessor]).map(
    (model) => ({
      id: model.id,
      label: model.displayName,
    })
  )
)

watch(open, async (isOpen) => {
  if (!isOpen) {
    return
  }
  await refreshProcessorOptions()
})
</script>
