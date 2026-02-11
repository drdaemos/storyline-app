<template>
  <UModal v-model:open="isOpen" class="max-w-2xl" :title="headerTitle">
    <template #body>
      <!-- Step 1: Choice -->
      <div v-if="currentStep === 'choice'" class="text-center space-y-6 py-4">
        <p class="text-lg">How would you like to start your conversation?</p>
        <div class="flex flex-col gap-4 justify-center items-center">
          <div class="flex flex-col sm:flex-row gap-4">
            <UButton
              color="primary"
              size="xl"
              icon="i-lucide-wand-sparkles"
              @click="selectAIAssistant"
            >
              Create with AI
            </UButton>
            <UButton
              color="neutral"
              variant="soft"
              size="xl"
              icon="i-lucide-sparkles"
              @click="selectGenerateScenario"
            >
              Quick Generate
            </UButton>
          </div>
          <UButton
            color="neutral"
            variant="ghost"
            size="lg"
            icon="i-lucide-message-square"
            @click="selectSkipToChat"
          >
            Skip to Chat
          </UButton>
        </div>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          <strong>Create with AI</strong> lets you craft a custom scenario through conversation.
          <strong>Quick Generate</strong> creates scenarios based on mood selection.
        </p>
      </div>

      <!-- Step 2: Persona Selection -->
      <div v-if="currentStep === 'personaSelection'" class="space-y-6">
        <p class="text-center">Select your persona</p>

        <UFormField label="Persona" description="Choose which character represents you in this conversation">
          <USelect
            class="w-full"
            value-key="id"
            v-model="selectedPersonaId"
            :items="personaOptions"
            :loading="personasLoading"
          />
        </UFormField>

        <div class="flex gap-3">
          <UButton
            color="neutral"
            variant="outline"
            block
            icon="i-lucide-arrow-left"
            @click="currentStep = 'choice'"
          >
            Back
          </UButton>
          <UButton
            color="primary"
            block
            icon="i-lucide-arrow-right"
            @click="currentStep = 'mood'"
          >
            Continue
          </UButton>
        </div>
      </div>

      <!-- Step 3: Mood Selection -->
      <div v-if="currentStep === 'mood'" class="space-y-6">
        <div class="space-y-2">
          <p class="text-center text-lg">Select the mood(s) for your scenarios</p>
          <p class="text-center text-sm text-gray-600 dark:text-gray-400">Choose one or more tones to mix and match</p>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          <UCheckbox
            v-for="mood in moodOptions"
            :key="mood.value"
            v-model="moodSelections[mood.value]"
            :label="mood.label"
            variant="card"
          />
        </div>
        <div class="flex gap-3">
          <UButton
            color="neutral"
            variant="outline"
            block
            icon="i-lucide-arrow-left"
            @click="currentStep = 'personaSelection'"
          >
            Back
          </UButton>
          <UButton
            color="primary"
            block
            icon="i-lucide-sparkles"
            :disabled="selectedMoodsArray.length === 0"
            @click="generateScenariosForMood"
          >
            Generate Scenarios
          </UButton>
        </div>
      </div>

      <!-- Step 3: Loading -->
      <div v-if="currentStep === 'loading'" class="flex flex-col items-center justify-center py-12 space-y-4">
        <UIcon name="i-lucide-loader-2" class="w-16 h-16 animate-spin text-primary" />
        <p class="text-lg">Generating scenarios...</p>
        <UAlert v-if="error" color="error" variant="soft" icon="i-lucide-alert-circle" :description="error" />
      </div>

      <!-- Step 4: Scenario Selection -->
      <div v-if="currentStep === 'scenario'" class="space-y-4">
        <div v-if="isGeneratingScenarios" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 mb-2">
          <UIcon name="i-lucide-loader-2" class="w-4 h-4 animate-spin" />
          <span>Generating more scenarios...</span>
        </div>
        <UCard
          v-for="(scenario, index) in scenarios"
          :key="index"
          class="cursor-pointer hover:ring-2 hover:ring-primary transition-all"
          @click="selectScenario(scenario)"
        >
          <div class="space-y-3">
            <h3 class="text-lg font-semibold">{{ scenario.summary }}</h3>
            <UBadge color="primary" variant="subtle">
              {{ scenario.narrative_category }}
            </UBadge>
            <p
              class="text-sm"
              :class="expandedScenario === index ? '' : 'line-clamp-2'"
              v-html="highlight(scenario.intro_message)"
            >
            </p>
            <UButton
              color="neutral"
              variant="ghost"
              size="xs"
              @click.stop="toggleExpanded(index)"
            >
              {{ expandedScenario === index ? 'Show less' : 'Show more' }}
            </UButton>
          </div>
        </UCard>

        <div class="flex gap-3">
          <UButton
            color="neutral"
            variant="outline"
            block
            icon="i-lucide-arrow-left"
            @click="currentStep = 'personaSelection'"
          >
            Back to Persona
          </UButton>
          <UButton
            color="neutral"
            variant="outline"
            block
            icon="i-lucide-refresh-cw"
            @click="goBackToMood"
          >
            Regenerate
          </UButton>
        </div>
      </div>

    </template>
  </UModal>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { usePersonas } from '@/composables/usePersonas'
import type { Scenario } from '@/types'
import { useChatHighlight } from '@/composables/useChatHighlight.ts'

interface Props {
  show: boolean
  characterName: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
}>()

const { highlight } = useChatHighlight()
const router = useRouter()
const { streamGenerateScenarios, startSessionWithScenario } = useApi()
const { settings, loadSettings } = useLocalSettings()
const { personaOptions, personasLoading, fetchPersonas } = usePersonas()

type Step = 'choice' | 'personaSelection' | 'mood' | 'loading' | 'scenario'

const currentStep = ref<Step>('choice')
const moodSelections = ref<Record<string, boolean>>({
  normal: false,
  romantic: false,
  spicy: false,
  dark: false,
  unhinged: false,
  mysterious: false,
  comedic: false,
  dramatic: false,
  gritty: false,
  philosophical: false,
  chaotic: false,
})
const scenarios = ref<Scenario[]>([])
const selectedScenario = ref<Scenario | null>(null)
const expandedScenario = ref<number | null>(null)
const selectedPersonaId = ref<string>('')
const error = ref<string | null>(null)
const isGeneratingScenarios = ref<boolean>(false)

const selectedMoodsArray = computed(() => {
  return Object.keys(moodSelections.value).filter(key => moodSelections.value[key])
})

const moodOptions = [
  { label: 'Normal', value: 'normal' },
  { label: 'Romantic', value: 'romantic' },
  { label: 'Spicy', value: 'spicy' },
  { label: 'Dark', value: 'dark' },
  { label: 'Unhinged', value: 'unhinged' },
  { label: 'Mysterious', value: 'mysterious' },
  { label: 'Comedic', value: 'comedic' },
  { label: 'Dramatic', value: 'dramatic' },
  { label: 'Gritty', value: 'gritty' },
  { label: 'Philosophical', value: 'philosophical' },
  { label: 'Chaotic', value: 'chaotic' },
]

const headerTitle = computed(() => {
  switch (currentStep.value) {
    case 'choice':
      return 'Start New Session'
    case 'mood':
      return 'Select Mood'
    case 'loading':
      return 'Generating Scenarios'
    case 'scenario':
      return 'Choose Scenario'
    case 'personaSelection':
      return 'Select Persona'
    default:
      return 'New Session'
  }
})

const isOpen = computed({
  get: () => props.show,
  set: (value: boolean) => {
    if (!value) emit('close')
  },
})

const selectGenerateScenario = () => {
  if (selectedPersonaId.value && selectedPersonaId.value !== 'none') {
    settings.value.selectedPersonaId = selectedPersonaId.value
  }
  currentStep.value = 'personaSelection'
}

const selectAIAssistant = () => {
  emit('close')
  router.push({
    name: 'create-scenario',
    params: {
      characterId: props.characterName,
    },
  })
}

const selectSkipToChat = () => {
  emit('close')
  router.push({
    name: 'chat',
    params: {
      characterId: props.characterName,
      sessionId: 'new',
    },
  })
}

const generateScenariosForMood = async () => {
  if (selectedMoodsArray.value.length === 0) return

  currentStep.value = 'loading'
  error.value = null
  scenarios.value = []
  isGeneratingScenarios.value = true

  try {
    await streamGenerateScenarios(
      {
        character_name: props.characterName,
        count: 3,
        mood: selectedMoodsArray.value.join(', '),
        persona_id: selectedPersonaId.value && selectedPersonaId.value !== 'none' ? selectedPersonaId.value : null,
        processor_type: settings.value.largeModelKey,
        backup_processor_type: settings.value.smallModelKey,
      },
      // onChunk - for debugging or showing raw XML
      (chunk: string) => {
        // Optional: could show generation progress
        console.debug('Scenario chunk:', chunk)
      },
      // onScenario - add scenario as it's parsed
      (scenario: any) => {
        scenarios.value.push(scenario)
        // Switch to scenario view as soon as we have the first one
        if (scenarios.value.length === 1) {
          currentStep.value = 'scenario'
        }
      },
      // onComplete
      () => {
        isGeneratingScenarios.value = false
        if (scenarios.value.length > 0) {
          currentStep.value = 'scenario'
        } else {
          error.value = 'No scenarios were generated'
        }
      },
      // onError
      (errorMessage: string) => {
        isGeneratingScenarios.value = false
        error.value = errorMessage
      }
    )
  } catch (err) {
    isGeneratingScenarios.value = false
    error.value = err instanceof Error ? err.message : 'Failed to generate scenarios'
  }
}

const selectScenario = async (scenario: Scenario) => {
  selectedScenario.value = scenario
  await startSession()
}

const toggleExpanded = (index: number) => {
  expandedScenario.value = expandedScenario.value === index ? null : index
}

const goBackToMood = () => {
  currentStep.value = 'mood'
  scenarios.value = []
  selectedScenario.value = null
  expandedScenario.value = null
  // Reset all mood selections
  Object.keys(moodSelections.value).forEach(key => {
    moodSelections.value[key] = false
  })
  error.value = null
}

const startSession = async () => {
  if (!selectedScenario.value) return

  try {
    const response = await startSessionWithScenario({
      character_name: props.characterName,
      intro_message: selectedScenario.value.intro_message,
      persona_id: selectedPersonaId.value && selectedPersonaId.value !== 'none' ? selectedPersonaId.value : null,
      ruleset_id: selectedScenario.value.ruleset_id || 'everyday-tension',
      world_lore_id: selectedScenario.value.world_lore_id || 'default-world',
      scene_seed: selectedScenario.value.scene_seed || {},
      small_model_key: settings.value.smallModelKey,
      large_model_key: settings.value.largeModelKey,
    })

    emit('close')
    router.push({
      name: 'chat',
      params: {
        characterId: props.characterName,
        sessionId: response.session_id,
      },
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to start session'
  }
}

const resetModal = () => {
  currentStep.value = 'choice'
  // Reset all mood selections
  Object.keys(moodSelections.value).forEach(key => {
    moodSelections.value[key] = false
  })
  scenarios.value = []
  selectedScenario.value = null
  expandedScenario.value = null
  selectedPersonaId.value = 'none'
  error.value = null
}

watch(
  () => props.show,
  (newShow) => {
    if (newShow) {
      loadSettings()
      fetchPersonas()
      selectedPersonaId.value = settings.value.selectedPersonaId || 'none'
    } else {
      resetModal()
    }
  }
)

watch(selectedPersonaId, (newId) => {
  if (newId && newId !== 'none') {
    settings.value.selectedPersonaId = newId
  } else {
    settings.value.selectedPersonaId = undefined
  }
})

onMounted(() => {
  fetchPersonas()
  selectedPersonaId.value = settings.value.selectedPersonaId || 'none'
})
</script>
