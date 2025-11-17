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

        <UFormField label="Selected Persona" description="Choose which persona character represents you in conversations.">
          <USelect
            class="w-full"
            value-key="id"
            v-model="settings.selectedPersonaId"
            :items="personaOptions"
            :loading="personasLoading"
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
import { ref, onMounted } from 'vue'
import type { SelectItem } from '@nuxt/ui'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { usePersonas } from '@/composables/usePersonas'

const open = ref(false)

const { settings, clearSettings } = useLocalSettings()
const { personaOptions, personasLoading, fetchPersonas } = usePersonas()

const processorOptions = ref<SelectItem[]>([
  { label: 'Claude Sonnet 4.5 ($15/M)', id: 'claude-sonnet' },
  { label: 'Claude Haiku 4.5 ($5/M)', id: 'claude-haiku' },
  { label: 'o4-mini ($4.40/M)', id: 'gpt' },
  { label: 'GPT-5.1 ($10/M)', id: 'gpt-5.1' },
  { label: 'Gemini 2.5 Flash ($2.50/M)', id: 'google-flash' },
  { label: 'Gemini 2.5 Pro ($10/M)', id: 'google-pro' },
  { label: 'DeepSeek R1 ($1.75/M)', id: 'deepseek' },
  { label: 'DeepSeek Chat V3.1 ($1.00/M)', id: 'deepseek-chat-v3.1' },
  { label: 'Kimi K2 ($1.90/M)', id: 'kimi' },
  { label: 'Kimi K2 Thinking ($2.25/M)', id: 'kimi-thinking' },
  { label: 'Qwen3 Max ($6/M)', id: 'qwen3-max' },
  { label: 'Magistral Medium Thinking ($5/M)', id: 'magistral-thinking' },
  { label: 'Grok 4 Fast ($0.50/M)', id: 'grok' },
  { label: 'Hermes 4 405B ($1.20/M)', id: 'hermes' },
  { label: 'GLM-4.6 ($1.80/M)', id: 'glm' },
  { label: 'Sherlock Think Alpha (FREE)', id: 'sherlock-think' },
  { label: 'Cohere ($10/M)', id: 'cohere' },
])

onMounted(() => {
  fetchPersonas()
})
</script>
