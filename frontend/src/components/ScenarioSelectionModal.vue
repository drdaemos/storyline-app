<template>
  <UModal v-model:open="isOpen" class="max-w-2xl" :title="headerTitle">
    <template #body>
      <!-- Step 1: Choice -->
      <div v-if="currentStep === 'choice'" class="text-center space-y-6 py-4">
        <p class="text-lg">How would you like to start your conversation?</p>
        <div class="flex flex-col sm:flex-row gap-4 justify-center">
          <UButton
            color="primary"
            size="xl"
            icon="i-lucide-sparkles"
            @click="selectGenerateScenario"
          >
            Generate Scenario
          </UButton>
          <UButton
            color="neutral"
            variant="outline"
            size="xl"
            icon="i-lucide-message-square"
            @click="selectSkipToChat"
          >
            Skip to Chat
          </UButton>
        </div>
      </div>

      <!-- Step 2: Mood Selection -->
      <div v-if="currentStep === 'mood'" class="space-y-6">
        <p class="text-center">Select the mood for your scenarios</p>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          <UButton
            v-for="mood in moodOptions"
            :key="mood"
            :color="selectedMood === mood ? 'primary' : 'neutral'"
            :variant="selectedMood === mood ? 'solid' : 'outline'"
            block
            @click="selectMood(mood)"
          >
            {{ mood }}
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
        <UCard
          v-for="(scenario, index) in scenarios"
          :key="index"
          class="cursor-pointer hover:ring-2 hover:ring-primary transition-all"
          @click="selectScenario(scenario)"
        >
          <div class="space-y-3">
            <div class="flex items-start justify-between gap-4">
              <h3 class="text-lg font-semibold flex-1">{{ scenario.summary }}</h3>
              <UBadge color="primary" variant="subtle">
                {{ scenario.narrative_category }}
              </UBadge>
            </div>
            <p
              class="text-sm"
              :class="expandedScenario === index ? '' : 'line-clamp-2'"
            >
              {{ scenario.intro_message }}
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

        <UButton
          color="neutral"
          variant="outline"
          block
          icon="i-lucide-arrow-left"
          @click="goBackToMood"
        >
          Back to Mood Selection
        </UButton>
      </div>

      <!-- Step 5: User Info -->
      <div v-if="currentStep === 'userInfo'" class="space-y-6">
        <p class="text-center">Tell us about yourself</p>

        <UFormField label="Your Name" required>
          <UInput
            v-model="userName"
            placeholder="Enter your name"
            size="lg"
            class="w-full"
          />
        </UFormField>

        <UFormField label="Your Description" description="Describe yourself in the roleplay (optional)">
          <UTextarea
            v-model="userDescription"
            placeholder="Describe yourself..."
            class="w-full"
            :rows="4"
          />
        </UFormField>

        <div class="flex gap-3">
          <UButton
            color="neutral"
            variant="outline"
            block
            icon="i-lucide-arrow-left"
            @click="goBack"
          >
            Back
          </UButton>
          <UButton
            color="primary"
            block
            icon="i-lucide-check"
            :disabled="!userName.trim()"
            @click="startSession"
          >
            Start Session
          </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import type { Scenario } from '@/types'

interface Props {
  show: boolean
  characterName: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
}>()

const router = useRouter()
const { generateScenarios, startSessionWithScenario } = useApi()
const { settings, loadSettings } = useLocalSettings()

type Step = 'choice' | 'mood' | 'loading' | 'scenario' | 'userInfo'

const currentStep = ref<Step>('choice')
const selectedMood = ref<string>('')
const scenarios = ref<Scenario[]>([])
const selectedScenario = ref<Scenario | null>(null)
const expandedScenario = ref<number | null>(null)
const userName = ref('')
const userDescription = ref('')
const error = ref<string | null>(null)

const moodOptions = [
  'Normal', 'Romantic', 'Spicy', 'Dark', 'Unhinged',
  'Mysterious', 'Comedic', 'Dramatic', 'Gritty',
  'Philosophical', 'Chaotic'
]

const headerTitle = computed(() => {
  switch (currentStep.value) {
    case 'choice': return 'Start New Session'
    case 'mood': return 'Select Mood'
    case 'loading': return 'Generating Scenarios'
    case 'scenario': return 'Choose Scenario'
    case 'userInfo': return 'Your Information'
    default: return 'New Session'
  }
})

const isOpen = computed({
  get: () => props.show,
  set: (value: boolean) => {
    if (!value) emit('close')
  }
})

const selectGenerateScenario = () => {
  currentStep.value = 'mood'
}

const selectSkipToChat = () => {
  emit('close')
  router.push({
    name: 'chat',
    params: {
      characterName: props.characterName,
      sessionId: 'new'
    }
  })
}

const selectMood = (mood: string) => {
  selectedMood.value = mood
  generateScenariosForMood()
}

const generateScenariosForMood = async () => {
  currentStep.value = 'loading'
  error.value = null

  try {
    const response = await generateScenarios({
      character_name: props.characterName,
      count: 3,
      mood: selectedMood.value.toLowerCase(),
      processor_type: settings.value.aiProcessor,
      backup_processor_type: settings.value.backupProcessor
    })

    scenarios.value = response.scenarios
    currentStep.value = 'scenario'
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to generate scenarios'
  }
}

const selectScenario = (scenario: Scenario) => {
  selectedScenario.value = scenario
  currentStep.value = 'userInfo'
}

const toggleExpanded = (index: number) => {
  expandedScenario.value = expandedScenario.value === index ? null : index
}

const goBack = () => {
  currentStep.value = 'scenario'
}

const goBackToMood = () => {
  currentStep.value = 'mood'
  scenarios.value = []
  selectedScenario.value = null
  expandedScenario.value = null
  error.value = null
}

const startSession = async () => {
  if (!selectedScenario.value || !userName.value.trim()) return

  try {
    const response = await startSessionWithScenario({
      character_name: props.characterName,
      intro_message: selectedScenario.value.intro_message,
      user_name: userName.value.trim(),
      user_description: userDescription.value.trim(),
      processor_type: settings.value.aiProcessor,
      backup_processor_type: settings.value.backupProcessor
    })

    emit('close')
    router.push({
      name: 'chat',
      params: {
        characterName: props.characterName,
        sessionId: response.session_id
      }
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to start session'
  }
}

const resetModal = () => {
  currentStep.value = 'choice'
  selectedMood.value = ''
  scenarios.value = []
  selectedScenario.value = null
  expandedScenario.value = null
  userName.value = ''
  userDescription.value = ''
  error.value = null
}

watch(() => props.show, (newShow) => {
  if (newShow) {
    loadSettings()
  } else {
    resetModal()
  }
})
</script>
