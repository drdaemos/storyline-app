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
        <UFormField label="Large Model" description="Used for narrator continuation. Changes apply to new sessions only.">
          <USelect
            class="w-full"
            value-key="id"
            v-model="settings.largeModelKey"
            :items="processorOptions"
          />
        </UFormField>

        <UFormField label="Small Model" description="Used for ruleset resolution and character reflection. Changes apply to new sessions only.">
          <USelect
            class="w-full"
            value-key="id"
            v-model="settings.smallModelKey"
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
import { ref } from 'vue'
import type { SelectItem } from '@nuxt/ui'
import { useLocalSettings } from '@/composables/useLocalSettings'

const open = ref(false)

const { settings, clearSettings } = useLocalSettings()

const processorOptions = ref<SelectItem[]>([
  { label: 'Claude Haiku 4.5 ($5/M)', id: 'claude-haiku' },
  { label: 'Claude Sonnet 4.5 ($15/M)', id: 'claude-sonnet' },
  { label: 'Claude Opus 4.6 ($25/M)', id: 'claude-opus' },
  { label: 'GPT-5.2 Chat ($14/M)', id: 'gpt-5.2' },
  { label: 'Gemini 3 Flash ($3/M)', id: 'google-flash' },
  { label: 'Gemini 3 Pro ($12/M)', id: 'google-pro' },
  { label: 'DeepSeek V3.2 ($1.68/M)', id: 'deepseek-v32' },
  { label: 'Kimi K2.5 ($2.80/M)', id: 'kimi-k2.5' },
  { label: 'Minimax M2 HER ($1.20/M)', id: 'minimax-m2-her' },
  { label: 'Grok 4.1 Fast ($0.50/M)', id: 'grok' },
  { label: 'GLM-4.7 ($2.20/M)', id: 'glm' },
  { label: 'Cohere Command A ($10/M)', id: 'cohere' },
])
</script>
