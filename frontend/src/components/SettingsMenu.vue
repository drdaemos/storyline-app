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
  { label: 'Claude Haiku 4.5 ($5/M)', id: 'claude-haiku' },
  { label: 'Claude Sonnet 4.5 ($15/M)', id: 'claude-sonnet' },
  { label: 'Claude Opus 4.5 ($25/M)', id: 'claude-opus' },
  { label: 'GPT-5.2 Chat ($14/M)', id: 'gpt-5.2' },
  { label: 'Gemini 3 Flash ($3/M)', id: 'google-flash' },
  { label: 'Gemini 3 Pro ($12/M)', id: 'google-pro' },
  { label: 'DeepSeek V3.2 ($0.41/M)', id: 'deepseek-v32' },
  { label: 'Kimi K2 ($1.90/M)', id: 'kimi' },
  { label: 'Kimi K2 Thinking ($2.35/M)', id: 'kimi-thinking' },
  { label: 'Mistral Small Creative ($0.30/M)', id: 'mistral' },
  { label: 'Drummer Cydonia ($0.50/M)', id: 'cydonia' },
  { label: 'Grok 4.1 Fast ($0.50/M)', id: 'grok' },
  { label: 'GLM-4.6 ($1.80/M)', id: 'glm' },
  { label: 'Cohere Command A ($10/M)', id: 'cohere' },
])

onMounted(() => {
  fetchPersonas()
})
</script>
