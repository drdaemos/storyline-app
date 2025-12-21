<template>
  <!-- Header -->
  <div class="flex mb-8 gap-4 items-center justify-between">
    <div class="flex items-center gap-3">
      <UButton
        color="neutral"
        variant="ghost"
        icon="i-lucide-arrow-left"
        @click="navigateBack"
      />
      <h2 class="text-3xl font-bold font-serif">Create Scenario</h2>
      <UBadge v-if="characterInfo" color="primary" variant="subtle">
        {{ characterInfo.name }}
      </UBadge>
    </div>
    <div class="flex items-center gap-3">
      <!-- Auto-save indicator -->
      <div v-if="autoSaveStatus !== 'idle'" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
        <UIcon
          :name="autoSaveStatus === 'saving' ? 'i-lucide-loader-circle' : 'i-lucide-check-circle'"
          :class="['w-4 h-4', autoSaveStatus === 'saving' && 'animate-spin']"
        />
        <span>{{ autoSaveStatus === 'saving' ? 'Saving...' : 'Saved' }}</span>
      </div>
      <!-- Reset button -->
      <UButton
        color="neutral"
        variant="ghost"
        icon="i-lucide-refresh-cw"
        @click="resetScenarioCreation"
        :disabled="isThinking || saving"
      >
        Reset
      </UButton>
    </div>
  </div>

  <!-- 2 Column Layout -->
  <UMain>
    <div class="grid lg:grid-cols-2 grid-cols-1 gap-6 flex-1 pb-8">
      <!-- Left Column: AI Chat Assistant -->
      <div class="flex flex-col border border-gray-200 dark:border-gray-800 rounded-lg overflow-hidden max-h-[88vh] lg:sticky top-24">
        <div class="p-4 border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900">
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-sparkles" class="w-5 h-5 text-primary" />
            <h3 class="text-lg font-semibold">AI Scenario Architect</h3>
          </div>
          <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Describe the scenario you want, and I'll help craft a compelling starting point.
          </p>
        </div>

        <!-- Chat Messages -->
        <div class="flex-1 overflow-y-auto p-4 space-y-4">
          <!-- Welcome message -->
          <div v-if="messages.length === 0" class="space-y-3">
            <div class="p-3 rounded-lg bg-primary/10 border border-primary/20">
              <p class="text-sm">
                Let's create a scenario for <strong>{{ characterInfo?.name || characterId }}</strong>.
                Tell me what kind of scene you'd like - maybe a dramatic confrontation,
                a mysterious encounter, or something unexpected?
              </p>
            </div>
          </div>

          <!-- Chat messages -->
          <div v-for="(message, index) in messages" :key="index" class="space-y-3">
            <div
              :class="[
                'p-3 rounded-lg max-w-[85%]',
                message.isUser
                  ? 'ml-auto bg-primary text-white'
                  : 'bg-gray-100 dark:bg-gray-800'
              ]"
            >
              <div class="flex items-start gap-2">
                <UIcon
                  :name="message.isUser ? 'i-lucide-user' : 'i-lucide-sparkles'"
                  class="w-4 h-4 mt-0.5 flex-shrink-0"
                />
                <div class="text-sm flex-1">
                  <template v-for="(segment, idx) in parseMessageSegments(message.content)" :key="idx">
                    <!-- Regular text segment -->
                    <span v-if="segment.type === 'text'" class="whitespace-pre-wrap">{{ segment.content }}</span>

                    <!-- Scenario update block -->
                    <div
                      v-else-if="segment.type === 'update'"
                      class="inline-flex items-center gap-2 px-3 py-1.5 my-1 rounded-md bg-primary/10 border border-primary/20 text-primary"
                    >
                      <UIcon
                        :name="segment.complete ? 'i-lucide-check-circle' : 'i-lucide-loader-circle'"
                        :class="['w-3.5 h-3.5', !segment.complete && 'animate-spin']"
                      />
                      <span class="text-xs font-medium">
                        {{ segment.complete ? 'Scenario updated' : 'Updating scenario...' }}
                      </span>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </div>

          <!-- Thinking indicator -->
          <div v-if="isThinking" class="flex items-center gap-2 text-sm text-gray-500">
            <div class="flex gap-1">
              <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0s"></span>
              <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0.2s"></span>
              <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0.4s"></span>
            </div>
            <span>AI is thinking...</span>
          </div>

          <!-- Error message -->
          <div v-if="error" class="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
            <div class="flex items-start gap-2">
              <UIcon name="i-lucide-alert-circle" class="w-4 h-4 text-red-600 dark:text-red-400 mt-0.5" />
              <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
            </div>
          </div>

          <div ref="chatEndRef"></div>
        </div>

        <!-- Chat Input -->
        <div class="p-4 border-t border-gray-200 dark:border-gray-800">
          <form @submit.prevent="sendMessage" class="flex gap-2">
            <UInput
              v-model="userInput"
              placeholder="Describe your scenario idea..."
              :disabled="isThinking"
              class="flex-1"
              size="lg"
            />
            <UButton
              type="submit"
              color="primary"
              icon="i-lucide-send"
              :disabled="isThinking || !userInput.trim()"
              :loading="isThinking"
            />
          </form>
        </div>
      </div>

      <!-- Right Column: Scenario Preview -->
      <div class="overflow-y-auto">
        <h2 class="text-lg font-semibold mb-4 font-serif">Scenario Preview</h2>

        <!-- Persona Selection -->
        <div class="mb-6 p-4 border border-gray-200 dark:border-gray-800 rounded-lg">
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-md font-semibold font-serif">Your Persona</h3>
            <UBadge v-if="scenarioData.suggested_persona_id" color="primary" variant="subtle" class="text-xs">
              AI Suggestion
            </UBadge>
          </div>
          <UFormField description="Select which character represents you">
            <USelect
              class="w-full"
              value-key="id"
              v-model="selectedPersonaId"
              :items="personaOptions"
              :loading="personasLoading"
            />
          </UFormField>
          <p v-if="scenarioData.suggested_persona_reason" class="text-xs text-gray-600 dark:text-gray-400 mt-2">
            {{ scenarioData.suggested_persona_reason }}
          </p>
        </div>

        <div class="space-y-6">
          <!-- Summary -->
          <div>
            <h3 class="text-md font-semibold mb-2 font-serif">Title</h3>
            <UFormField>
              <UInput
                v-model="scenarioData.summary"
                placeholder="Scenario title..."
                size="lg"
                variant="ghost"
                class="w-full"
              />
            </UFormField>
          </div>

          <!-- Intro Message -->
          <div>
            <h3 class="text-md font-semibold mb-2 font-serif">Opening Scene</h3>
            <UFormField>
              <UTextarea
                v-model="scenarioData.intro_message"
                :rows="6"
                autoresize
                variant="ghost"
                class="w-full"
                placeholder="The scene that sets everything in motion..."
              />
            </UFormField>
          </div>

          <!-- Category -->
          <div>
            <h3 class="text-md font-semibold mb-2 font-serif">Genre / Tone</h3>
            <UFormField>
              <UInput
                v-model="scenarioData.narrative_category"
                placeholder="e.g., mystery/thriller, romantic tension"
                variant="ghost"
                class="w-full"
              />
            </UFormField>
          </div>

          <!-- Location -->
          <div>
            <h3 class="text-md font-semibold mb-2 font-serif">Location</h3>
            <UFormField>
              <UInput
                v-model="scenarioData.location"
                placeholder="Where the scene takes place..."
                variant="ghost"
                class="w-full"
              />
            </UFormField>
          </div>

          <!-- Atmosphere -->
          <div>
            <h3 class="text-md font-semibold mb-2 font-serif">Atmosphere</h3>
            <UFormField>
              <UTextarea
                v-model="scenarioData.atmosphere"
                :rows="2"
                autoresize
                variant="ghost"
                class="w-full"
                placeholder="The mood and sensory details..."
              />
            </UFormField>
          </div>

          <!-- Stakes -->
          <div>
            <h3 class="text-md font-semibold mb-2 font-serif">Stakes</h3>
            <UFormField>
              <UTextarea
                v-model="scenarioData.stakes"
                :rows="2"
                autoresize
                variant="ghost"
                class="w-full"
                placeholder="What's at risk..."
              />
            </UFormField>
          </div>

          <!-- Plot Hooks -->
          <div>
            <h3 class="text-md font-semibold mb-3 font-serif">Plot Hooks</h3>
            <div class="space-y-2">
              <div
                v-for="(hook, index) in scenarioData.plot_hooks"
                :key="index"
                class="flex gap-2"
              >
                <UInput
                  v-model="scenarioData.plot_hooks[index]"
                  :placeholder="`Tension ${index + 1}`"
                  class="flex-1"
                />
                <UButton
                  color="neutral"
                  variant="ghost"
                  icon="i-lucide-x"
                  size="sm"
                  @click="removePlotHook(index)"
                />
              </div>
            </div>
            <UButton
              v-if="(scenarioData.plot_hooks?.length || 0) < 6"
              color="neutral"
              variant="outline"
              icon="i-lucide-plus"
              size="sm"
              class="mt-3"
              @click="addPlotHook"
            >
              Add Plot Hook
            </UButton>
          </div>

          <!-- Potential Directions -->
          <div>
            <h3 class="text-md font-semibold mb-3 font-serif">Potential Directions</h3>
            <div class="space-y-2">
              <div
                v-for="(direction, index) in scenarioData.potential_directions"
                :key="index"
                class="flex gap-2"
              >
                <UInput
                  v-model="scenarioData.potential_directions[index]"
                  :placeholder="`Direction ${index + 1}`"
                  class="flex-1"
                />
                <UButton
                  color="neutral"
                  variant="ghost"
                  icon="i-lucide-x"
                  size="sm"
                  @click="removePotentialDirection(index)"
                />
              </div>
            </div>
            <UButton
              v-if="(scenarioData.potential_directions?.length || 0) < 4"
              color="neutral"
              variant="outline"
              icon="i-lucide-plus"
              size="sm"
              class="mt-3"
              @click="addPotentialDirection"
            >
              Add Direction
            </UButton>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex gap-3 justify-end mt-6 pt-6 border-t border-gray-200 dark:border-gray-800">
          <UButton
            color="neutral"
            variant="outline"
            @click="navigateBack"
          >
            Cancel
          </UButton>
          <UButton
            color="neutral"
            variant="outline"
            :disabled="!isScenarioValid || saving"
            :loading="saving"
            @click="saveAndReturnToCharacter"
          >
            Save to Library
          </UButton>
          <UButton
            color="primary"
            :disabled="!isScenarioValid || saving"
            :loading="saving"
            @click="startSessionWithCurrentScenario"
          >
            Start Chat
          </UButton>
        </div>
      </div>
    </div>
  </UMain>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { usePersonas } from '@/composables/usePersonas'
import { useCharacterCreationAutoSave } from '@/composables/useCharacterCreationAutoSave'
import type { PartialScenario, ChatMessage, ScenarioCreationRequest, PersonaSummary, Scenario } from '@/types'

const router = useRouter()
const route = useRoute()
const { streamScenarioCreation, saveScenario, startSessionWithScenario, getCharacterInfo } = useApi()
const { settings } = useLocalSettings()
const { personaOptions, personasLoading, fetchPersonas, personas } = usePersonas()

// Get characterId from route params
const characterId = computed(() => route.params.characterId as string)

const userInput = ref('')
const messages = ref<ChatMessage[]>([])
const isThinking = ref(false)
const error = ref('')
const saving = ref(false)
const chatEndRef = ref<HTMLElement | null>(null)
const selectedPersonaId = ref<string>('')
const characterInfo = ref<{ name: string; tagline: string } | null>(null)

const scenarioData = reactive<PartialScenario>({
  summary: '',
  intro_message: '',
  narrative_category: '',
  character_id: '',
  persona_id: '',
  location: '',
  time_context: '',
  atmosphere: '',
  plot_hooks: [],
  stakes: '',
  character_goals: {},
  potential_directions: [],
  suggested_persona_id: '',
  suggested_persona_reason: '',
})

// Auto-save functionality (using separate localStorage keys for scenarios)
const { autoSaveStatus, saveToLocalStorage, loadFromLocalStorage, clearLocalStorage } =
  useCharacterCreationAutoSave(scenarioData as any, messages, 'scenario-creation')

// Build available personas list for API
const availablePersonas = computed<PersonaSummary[]>(() => {
  return personas.value.map(p => ({
    id: p.id,
    name: p.name,
    tagline: p.tagline || '',
    personality: '', // We don't have full character data here
  }))
})

// Load character info and personas on mount
onMounted(async () => {
  // Load from localStorage first
  loadFromLocalStorage()

  if (characterId.value) {
    scenarioData.character_id = characterId.value
    try {
      const info = await getCharacterInfo(characterId.value)
      characterInfo.value = { name: info.name, tagline: info.tagline }
    } catch (err) {
      console.error('Failed to load character info:', err)
    }
  }
  await fetchPersonas()
  selectedPersonaId.value = settings.value.selectedPersonaId || 'none'
})

// Watch for AI persona suggestions
watch(() => scenarioData.suggested_persona_id, (newId) => {
  if (newId && (!selectedPersonaId.value || selectedPersonaId.value === 'none')) {
    selectedPersonaId.value = newId
  }
})

// Update persona_id when selection changes
watch(selectedPersonaId, (newId) => {
  if (newId && newId !== 'none') {
    scenarioData.persona_id = newId
  } else {
    scenarioData.persona_id = ''
  }
})

const isScenarioValid = computed(() => {
  return scenarioData.summary?.trim() && scenarioData.intro_message?.trim()
})

const navigateBack = () => {
  router.push({ name: 'character', params: { characterId: characterId.value } })
}

const resetScenarioCreation = () => {
  if (!confirm('Are you sure you want to reset? All progress will be lost.')) {
    return
  }

  // Clear scenario data
  Object.assign(scenarioData, {
    summary: '',
    intro_message: '',
    narrative_category: '',
    character_id: characterId.value,
    persona_id: '',
    location: '',
    time_context: '',
    atmosphere: '',
    plot_hooks: [],
    stakes: '',
    character_goals: {},
    potential_directions: [],
    suggested_persona_id: '',
    suggested_persona_reason: '',
  })

  // Clear messages
  messages.value = []

  // Clear localStorage
  clearLocalStorage()

  // Reset other state
  error.value = ''
  userInput.value = ''
}

const sendMessage = async () => {
  if (!userInput.value.trim() || isThinking.value) return

  const message = userInput.value.trim()

  // Add user message to chat
  messages.value.push({
    author: 'User',
    content: message,
    isUser: true,
    timestamp: new Date(),
  })

  userInput.value = ''
  isThinking.value = true
  error.value = ''

  try {
    const payload: ScenarioCreationRequest = {
      user_message: message,
      current_scenario: { ...scenarioData },
      character_name: characterId.value,
      persona_id: selectedPersonaId.value && selectedPersonaId.value !== 'none' ? selectedPersonaId.value : null,
      available_personas: availablePersonas.value,
      conversation_history: messages.value.map(msg => ({
        author: msg.author,
        content: msg.content,
        is_user: msg.isUser,
      })),
      processor_type: settings.value.aiProcessor,
      backup_processor_type: settings.value.backupProcessor,
    }

    // Create a temporary AI message that will be updated in real-time
    const aiMessageIndex = messages.value.length

    await streamScenarioCreation(
      payload,
      // onMessage callback
      (messageChunk: string) => {
        if (!messages.value[aiMessageIndex]) {
          messages.value.push({
            author: 'AI Assistant',
            content: '',
            isUser: false,
            timestamp: new Date(),
          })
        }
        // Update the AI message content in real-time
        messages.value[aiMessageIndex].content += messageChunk
        isThinking.value = false
      },
      // onUpdate callback
      (updates: PartialScenario) => {
        // Merge updates into scenarioData
        Object.assign(scenarioData, updates)
      },
      // onComplete callback
      () => {
        // Remove empty message if no content was received
        if (messages.value[aiMessageIndex] && !messages.value[aiMessageIndex].content) {
          messages.value.splice(aiMessageIndex, 1)
        }
        isThinking.value = false
        // Auto-save after AI interaction completes
        saveToLocalStorage()
      },
      // onError callback
      (errorMessage: string) => {
        error.value = errorMessage
        // Remove the empty AI message on error
        if (messages.value[aiMessageIndex]) {
          messages.value.splice(aiMessageIndex, 1)
        }
        isThinking.value = false
      }
    )
  } catch (err) {
    console.error('Failed to send message:', err)
    error.value = 'Failed to send message. Please try again.'
    isThinking.value = false
  }
}

const saveAndReturnToCharacter = async () => {
  if (!isScenarioValid.value) return

  saving.value = true
  try {
    // Convert PartialScenario to Scenario for saving
    const scenarioToSave: Scenario = {
      summary: scenarioData.summary || '',
      intro_message: scenarioData.intro_message || '',
      narrative_category: scenarioData.narrative_category || '',
      character_id: characterId.value,
      persona_id: selectedPersonaId.value && selectedPersonaId.value !== 'none' ? selectedPersonaId.value : undefined,
      location: scenarioData.location,
      time_context: scenarioData.time_context,
      atmosphere: scenarioData.atmosphere,
      plot_hooks: scenarioData.plot_hooks,
      stakes: scenarioData.stakes,
      character_goals: scenarioData.character_goals,
      potential_directions: scenarioData.potential_directions,
    }

    await saveScenario({ scenario: scenarioToSave })

    // Clear localStorage after successful save
    clearLocalStorage()

    // Navigate back to character page
    router.push({ name: 'character', params: { characterId: characterId.value } })
  } catch (err) {
    error.value = (err as any)?.message || 'Failed to save scenario'
  } finally {
    saving.value = false
  }
}

const startSessionWithCurrentScenario = async () => {
  if (!isScenarioValid.value) return

  saving.value = true
  try {
    // Save scenario to library first
    const scenarioToSave: Scenario = {
      summary: scenarioData.summary || '',
      intro_message: scenarioData.intro_message || '',
      narrative_category: scenarioData.narrative_category || '',
      character_id: characterId.value,
      persona_id: selectedPersonaId.value && selectedPersonaId.value !== 'none' ? selectedPersonaId.value : undefined,
      location: scenarioData.location,
      time_context: scenarioData.time_context,
      atmosphere: scenarioData.atmosphere,
      plot_hooks: scenarioData.plot_hooks,
      stakes: scenarioData.stakes,
      character_goals: scenarioData.character_goals,
      potential_directions: scenarioData.potential_directions,
    }

    const saveResponse = await saveScenario({ scenario: scenarioToSave })

    // Start session with the saved scenario ID
    const response = await startSessionWithScenario({
      character_name: characterId.value,
      scenario_id: saveResponse.scenario_id,
      processor_type: settings.value.aiProcessor,
      backup_processor_type: settings.value.backupProcessor,
    })

    // Clear localStorage after successful save
    clearLocalStorage()

    // Navigate to chat
    router.push({
      name: 'chat',
      params: {
        characterId: characterId.value,
        sessionId: response.session_id,
      },
    })
  } catch (err) {
    error.value = (err as any)?.message || 'Failed to start session'
  } finally {
    saving.value = false
  }
}

const addPlotHook = () => {
  if (!scenarioData.plot_hooks) {
    scenarioData.plot_hooks = []
  }
  if (scenarioData.plot_hooks.length < 6) {
    scenarioData.plot_hooks.push('')
  }
}

const removePlotHook = (index: number) => {
  scenarioData.plot_hooks?.splice(index, 1)
}

const addPotentialDirection = () => {
  if (!scenarioData.potential_directions) {
    scenarioData.potential_directions = []
  }
  if (scenarioData.potential_directions.length < 4) {
    scenarioData.potential_directions.push('')
  }
}

const removePotentialDirection = (index: number) => {
  scenarioData.potential_directions?.splice(index, 1)
}

interface MessageSegment {
  type: 'text' | 'update'
  content: string
  complete: boolean
}

const parseMessageSegments = (content: string): MessageSegment[] => {
  if (!content) return []

  const segments: MessageSegment[] = []

  // Split by <scenario_update> tags and track positions
  const parts = content.split(/(<scenario_update>[\s\S]*?(?:<\/scenario_update>|$))/g)

  for (const part of parts) {
    if (!part) continue

    // Check if this part is a scenario update block
    if (part.startsWith('<scenario_update>')) {
      const hasClosingTag = part.includes('</scenario_update>')
      segments.push({
        type: 'update',
        content: '', // We don't need the actual content for display
        complete: hasClosingTag,
      })
    } else {
      // Regular text
      segments.push({
        type: 'text',
        content: part,
        complete: true,
      })
    }
  }

  return segments
}
</script>
