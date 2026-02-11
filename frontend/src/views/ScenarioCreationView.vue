<template>
  <section class="space-y-6">
    <div class="story-panel p-5 md:p-7">
      <div class="flex mb-1 gap-4 items-center justify-between flex-wrap">
        <div class="flex items-center gap-3">
          <UButton color="neutral" variant="ghost" icon="i-lucide-arrow-left" @click="navigateBack" />
          <div>
            <h2 class="text-3xl story-headline">Create Scenario</h2>
            <p class="text-sm story-subtext mt-1">Compose by tag groups: cast tags + world lore tags.</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <div v-if="autoSaveStatus !== 'idle'" class="flex items-center gap-2 text-sm story-subtext">
            <UIcon
              :name="autoSaveStatus === 'saving' ? 'i-lucide-loader-circle' : 'i-lucide-check-circle'"
              :class="['w-4 h-4', autoSaveStatus === 'saving' && 'animate-spin']"
            />
            <span>{{ autoSaveStatus === 'saving' ? 'Saving...' : 'Saved' }}</span>
          </div>
          <UButton color="neutral" variant="ghost" icon="i-lucide-refresh-cw" @click="resetScenarioCreation" :disabled="isThinking || saving">
            Reset
          </UButton>
        </div>
      </div>
    </div>

    <UMain>
      <div class="grid lg:grid-cols-2 grid-cols-1 gap-6 flex-1 pb-8">
        <div class="flex flex-col story-panel overflow-hidden max-h-[88vh] lg:sticky top-24">
          <div class="p-4 border-b border-gray-200/70 dark:border-gray-800 bg-cyan-50/70 dark:bg-gray-900">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-sparkles" class="w-5 h-5 text-primary" />
              <h3 class="text-lg font-semibold">AI Scenario Architect</h3>
            </div>
            <p class="text-sm story-subtext mt-1">Describe your scenario and refine it through conversation.</p>
          </div>

          <div class="flex-1 overflow-y-auto p-4 space-y-4">
            <div v-if="messages.length === 0" class="space-y-3">
              <div class="p-3 rounded-lg bg-primary/10 border border-primary/20">
                <p class="text-sm">
                  Start by describing the scene idea, conflict, or tone you want.
                  Selected cast: <strong>{{ selectedCharacterNames || 'none yet' }}</strong>.
                </p>
              </div>
            </div>

            <div v-for="(message, index) in messages" :key="index" class="space-y-3">
              <div :class="['p-3 rounded-lg max-w-[85%]', message.isUser ? 'ml-auto bg-primary text-white' : 'bg-gray-100 dark:bg-gray-800']">
                <div class="flex items-start gap-2">
                  <UIcon :name="message.isUser ? 'i-lucide-user' : 'i-lucide-sparkles'" class="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <div class="text-sm flex-1">
                    <template v-for="(segment, idx) in parseMessageSegments(message.content)" :key="idx">
                      <span v-if="segment.type === 'text'" class="whitespace-pre-wrap">{{ segment.content }}</span>
                      <div
                        v-else-if="segment.type === 'update'"
                        class="inline-flex items-center gap-2 px-3 py-1.5 my-1 rounded-md bg-primary/10 border border-primary/20 text-primary"
                      >
                        <UIcon :name="segment.complete ? 'i-lucide-check-circle' : 'i-lucide-loader-circle'" :class="['w-3.5 h-3.5', !segment.complete && 'animate-spin']" />
                        <span class="text-xs font-medium">{{ segment.complete ? 'Scenario updated' : 'Updating scenario...' }}</span>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="isThinking" class="flex items-center gap-2 text-sm story-subtext">
              <div class="flex gap-1">
                <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0s"></span>
                <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0.2s"></span>
                <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0.4s"></span>
              </div>
              <span>AI is thinking...</span>
            </div>

            <div v-if="error" class="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
              <div class="flex items-start gap-2">
                <UIcon name="i-lucide-alert-circle" class="w-4 h-4 text-red-600 dark:text-red-400 mt-0.5" />
                <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
              </div>
            </div>
          </div>

          <div class="p-4 border-t border-gray-200 dark:border-gray-800">
            <form @submit.prevent="sendMessage" class="flex gap-2">
              <UInput
                v-model="userInput"
                placeholder="Describe your scenario idea..."
                :disabled="isThinking || selectedCharacterIds.length === 0"
                class="w-full"
                size="lg"
              />
              <UButton type="submit" color="primary" icon="i-lucide-send" :disabled="isThinking || !userInput.trim() || selectedCharacterIds.length === 0" :loading="isThinking" />
            </form>
          </div>
        </div>

        <div class="overflow-y-auto story-panel p-5 md:p-6">
          <h2 class="text-xl story-headline mb-4">Scenario Setup</h2>

          <div class="mb-6 p-4 story-panel-muted space-y-4">
            <div>
              <h3 class="text-md font-semibold mb-2 font-serif">Cast Tags</h3>
              <p class="text-xs story-subtext mb-2">Select one or more character tags. Matching characters become the cast.</p>
              <div class="grid sm:grid-cols-2 gap-2">
                <label v-for="tag in characterTagOptions" :key="`char-${tag.id}`" class="flex items-center gap-2 text-sm">
                  <UCheckbox :model-value="selectedCharacterTags.includes(tag.id)" @update:model-value="(v: boolean | 'indeterminate') => toggleCharacterTag(tag.id, v === true)" />
                  <span>{{ tag.label }} <span class="story-subtext">({{ tag.count }})</span></span>
                </label>
              </div>
            </div>

            <div>
              <h3 class="text-md font-semibold mb-2 font-serif">Ruleset</h3>
              <USelect
                class="w-full"
                value-key="id"
                v-model="scenarioData.ruleset_id"
                :items="rulesets.map(item => ({ id: item.id, label: item.name }))"
              />
              <p class="text-xs story-subtext mt-2">
                Controls mechanics, checks, and scene-state schema for this scenario.
              </p>
            </div>

            <div v-if="sceneSeedFields.length > 0">
              <h3 class="text-md font-semibold mb-2 font-serif">Ruleset Scene State</h3>
              <div class="grid sm:grid-cols-2 gap-3">
                <UFormField
                  v-for="field in sceneSeedFields"
                  :key="`scene-${field.key}`"
                  :label="field.label"
                >
                  <UInput
                    v-if="field.type === 'integer' || field.type === 'number'"
                    v-model.number="scenarioData.scene_seed[field.key]"
                    type="number"
                    class="w-full"
                    :min="field.minimum"
                    :max="field.maximum"
                  />
                  <UInput
                    v-else-if="field.type === 'string'"
                    v-model="scenarioData.scene_seed[field.key]"
                    class="w-full"
                  />
                  <UCheckbox
                    v-else
                    :model-value="Boolean(scenarioData.scene_seed[field.key])"
                    @update:model-value="(value: boolean | 'indeterminate') => { scenarioData.scene_seed[field.key] = value === true }"
                    :label="field.key"
                  />
                </UFormField>
              </div>
            </div>

            <div>
              <h3 class="text-md font-semibold mb-2 font-serif">World Lore Tags</h3>
              <p class="text-xs story-subtext mb-2">Select tags to resolve the best matching world lore entry.</p>
              <div class="grid sm:grid-cols-2 gap-2">
                <label v-for="tag in worldLoreTagOptions" :key="`world-${tag.id}`" class="flex items-center gap-2 text-sm">
                  <UCheckbox :model-value="selectedWorldLoreTags.includes(tag.id)" @update:model-value="(v: boolean | 'indeterminate') => toggleWorldLoreTag(tag.id, v === true)" />
                  <span>{{ tag.label }} <span class="story-subtext">({{ tag.count }})</span></span>
                </label>
              </div>
              <p class="text-xs story-subtext mt-2">Resolved lore: <strong>{{ resolvedWorldLoreName }}</strong></p>
            </div>

            <div>
              <h3 class="text-md font-semibold mb-2 font-serif">Your Persona</h3>
              <USelect class="w-full" value-key="id" v-model="selectedPersonaId" :items="personaOptions" :loading="personasLoading" />
              <p v-if="scenarioData.suggested_persona_reason" class="text-xs story-subtext mt-2">{{ scenarioData.suggested_persona_reason }}</p>
            </div>
          </div>

          <div class="space-y-5">
            <UFormField label="Title">
              <UInput v-model="scenarioData.summary" class="w-full" placeholder="Scenario title..." size="lg" variant="ghost" />
            </UFormField>
            <UFormField label="Opening Scene">
              <UTextarea v-model="scenarioData.intro_message" class="w-full" :rows="6" autoresize variant="ghost" placeholder="The scene that sets everything in motion..." />
            </UFormField>
            <UFormField label="Genre / Tone">
              <UInput v-model="scenarioData.narrative_category" class="w-full" placeholder="e.g., mystery/thriller, romantic tension" variant="ghost" />
            </UFormField>
            <UFormField label="Location">
              <UInput v-model="scenarioData.location" class="w-full" placeholder="Where the scene takes place..." variant="ghost" />
            </UFormField>
            <UFormField label="Atmosphere">
              <UTextarea v-model="scenarioData.atmosphere" class="w-full" :rows="2" autoresize variant="ghost" placeholder="The mood and sensory details..." />
            </UFormField>
            <UFormField label="Stakes">
              <UTextarea v-model="scenarioData.stakes" class="w-full" :rows="2" autoresize variant="ghost" placeholder="What's at risk..." />
            </UFormField>
          </div>

          <div class="flex gap-3 justify-end mt-6 pt-6 border-t border-gray-200/70 dark:border-gray-800">
            <UButton color="neutral" variant="outline" @click="navigateBack">Cancel</UButton>
            <UButton color="neutral" variant="outline" :disabled="!isScenarioValid || saving" :loading="saving" @click="saveScenarioToLibrary">Save to Library</UButton>
            <UButton color="primary" :disabled="!isScenarioValid || saving" :loading="saving" @click="startSessionWithCurrentScenario">Start Chat</UButton>
          </div>
        </div>
      </div>
    </UMain>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { usePersonas } from '@/composables/usePersonas'
import { useCharacterCreationAutoSave } from '@/composables/useCharacterCreationAutoSave'
import type { PartialScenario, ChatMessage, ScenarioCreationRequest, PersonaSummary, Scenario, CharacterSummary, WorldLoreAsset, RulesetDefinition } from '@/types'

const router = useRouter()
const route = useRoute()
const { streamScenarioCreation, saveScenario, startSessionWithScenario, getCharacters, listWorldLore, listRulesets } = useApi()
const { settings } = useLocalSettings()
const { personaOptions, personasLoading, fetchPersonas, personas } = usePersonas()

const userInput = ref('')
const messages = ref<ChatMessage[]>([])
const isThinking = ref(false)
const error = ref('')
const saving = ref(false)
const selectedPersonaId = ref<string>('none')
const selectedCharacterTags = ref<string[]>([])
const selectedWorldLoreTags = ref<string[]>([])

const characterCatalog = ref<CharacterSummary[]>([])
const worldLoreCatalog = ref<WorldLoreAsset[]>([])
const rulesets = ref<RulesetDefinition[]>([])

const characterTagOptions = ref<Array<{ id: string, label: string, count: number }>>([])
const worldLoreTagOptions = ref<Array<{ id: string, label: string, count: number }>>([])

type ScenarioFormData = {
  summary: string
  intro_message: string
  narrative_category: string
  character_id: string
  character_ids: string[]
  character_tags: string[]
  ruleset_id: string
  persona_id: string
  world_lore_id: string | null
  world_lore_tags: string[]
  scene_seed: Record<string, number | string | boolean>
  location: string
  time_context: string
  atmosphere: string
  plot_hooks: string[]
  stakes: string
  character_goals: Record<string, string>
  potential_directions: string[]
  suggested_persona_id: string
  suggested_persona_reason: string
}

const scenarioData = reactive<ScenarioFormData>({
  summary: '',
  intro_message: '',
  narrative_category: '',
  character_id: '',
  character_ids: [],
  character_tags: [],
  ruleset_id: 'everyday-tension',
  persona_id: '',
  world_lore_id: null,
  world_lore_tags: [],
  scene_seed: {},
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

const { autoSaveStatus, saveToLocalStorage, loadFromLocalStorage, clearLocalStorage } =
  useCharacterCreationAutoSave(scenarioData as Record<string, unknown>, messages, 'scenario-creation')

const normalizeTag = (value: string) => value.trim().toLowerCase()

const selectedCharacterIds = computed(() => {
  const selected = new Set(selectedCharacterTags.value.map(normalizeTag))
  if (selected.size === 0) return []
  const ids: string[] = []
  for (const character of characterCatalog.value) {
    const tags = new Set((character.tags || []).map(normalizeTag))
    if ([...selected].some(tag => tags.has(tag))) {
      ids.push(character.id)
    }
  }
  return ids
})

const primaryCharacterId = computed(() => selectedCharacterIds.value[0] || '')

const selectedCharacterNames = computed(() => {
  const byId = new Map(characterCatalog.value.map(character => [character.id, character.name]))
  return selectedCharacterIds.value.map(id => byId.get(id) || id).join(', ')
})

const resolvedWorldLoreId = computed(() => {
  const selected = new Set(selectedWorldLoreTags.value.map(normalizeTag))
  if (selected.size === 0) return 'default-world'

  let bestId = 'default-world'
  let bestScore = 0
  for (const item of worldLoreCatalog.value) {
    const tags = new Set((item.tags || []).map(normalizeTag))
    const score = [...selected].filter(tag => tags.has(tag)).length
    if (score > bestScore) {
      bestScore = score
      bestId = item.id
    }
  }
  return bestId
})

const resolvedWorldLoreName = computed(() => {
  if (resolvedWorldLoreId.value === 'default-world') return 'Default World'
  return worldLoreCatalog.value.find(item => item.id === resolvedWorldLoreId.value)?.name || 'Default World'
})

const availablePersonas = computed<PersonaSummary[]>(() => {
  return personas.value.map(persona => ({
    id: persona.id,
    name: persona.name,
    tagline: persona.tagline || '',
    personality: '',
  }))
})

const isScenarioValid = computed(() => {
  return Boolean(
    scenarioData.summary.trim() &&
    scenarioData.intro_message.trim() &&
    scenarioData.character_tags.length > 0 &&
    scenarioData.character_ids.length > 0
  )
})

const getErrorMessage = (err: unknown, fallback: string): string => {
  if (err instanceof Error && err.message) return err.message
  return fallback
}

const buildTagOptions = (rows: Array<{ tags?: string[] }>) => {
  const counts = new Map<string, number>()
  for (const row of rows) {
    const tags = row.tags || []
    for (const tag of tags) {
      const key = normalizeTag(tag)
      if (!key) continue
      counts.set(key, (counts.get(key) || 0) + 1)
    }
  }
  return Array.from(counts.entries())
    .map(([id, count]) => ({ id, label: id, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
}

type SceneSeedField = {
  key: string
  type: 'integer' | 'number' | 'string' | 'boolean'
  minimum?: number
  maximum?: number
  label: string
}

const selectedRuleset = computed(() => {
  if (rulesets.value.length === 0) return null
  return rulesets.value.find(item => item.id === scenarioData.ruleset_id) || rulesets.value[0]
})

const sceneSeedFields = computed<SceneSeedField[]>(() => {
  const schema = selectedRuleset.value?.scene_state_schema
  if (!schema || typeof schema !== 'object') return []
  const properties = (schema as Record<string, unknown>).properties
  if (!properties || typeof properties !== 'object') return []
  return Object.entries(properties as Record<string, Record<string, unknown>>)
    .filter(([key]) => key !== 'present' && key !== 'relations')
    .map(([key, prop]) => {
      const rawType = String(prop.type || 'string')
      const normalizedType = (['integer', 'number', 'string', 'boolean'].includes(rawType) ? rawType : 'string') as SceneSeedField['type']
      const minimum = typeof prop.minimum === 'number' ? prop.minimum : (typeof prop.min === 'number' ? prop.min : undefined)
      const maximum = typeof prop.maximum === 'number' ? prop.maximum : (typeof prop.max === 'number' ? prop.max : undefined)
      return {
        key,
        type: normalizedType,
        minimum,
        maximum,
        label: key.replace(/_/g, ' '),
      }
    })
})

const coerceSceneValue = (field: SceneSeedField, value: unknown): number | string | boolean => {
  if (field.type === 'integer') {
    const numeric = Number(value)
    let result = Number.isFinite(numeric) ? Math.round(numeric) : (field.minimum ?? 0)
    if (typeof field.minimum === 'number') result = Math.max(field.minimum, result)
    if (typeof field.maximum === 'number') result = Math.min(field.maximum, result)
    return result
  }
  if (field.type === 'number') {
    const numeric = Number(value)
    let result = Number.isFinite(numeric) ? numeric : (field.minimum ?? 0)
    if (typeof field.minimum === 'number') result = Math.max(field.minimum, result)
    if (typeof field.maximum === 'number') result = Math.min(field.maximum, result)
    return result
  }
  if (field.type === 'boolean') return Boolean(value)
  return String(value ?? '')
}

const ensureSceneSeedDefaults = () => {
  const next: Record<string, number | string | boolean> = {}
  for (const field of sceneSeedFields.value) {
    const existing = scenarioData.scene_seed[field.key]
    if (existing === undefined || existing === null || existing === '') {
      if (field.type === 'boolean') {
        next[field.key] = false
      } else if (field.type === 'string') {
        next[field.key] = ''
      } else {
        next[field.key] = field.minimum ?? 0
      }
      continue
    }
    next[field.key] = coerceSceneValue(field, existing)
  }
  scenarioData.scene_seed = next
}

const initializeSelections = () => {
  const queryCharacterTags = typeof route.query.characterTags === 'string'
    ? route.query.characterTags.split(',').map(tag => normalizeTag(tag)).filter(Boolean)
    : []
  const queryWorldLoreTags = typeof route.query.worldLoreTags === 'string'
    ? route.query.worldLoreTags.split(',').map(tag => normalizeTag(tag)).filter(Boolean)
    : []

  if (queryCharacterTags.length > 0) {
    selectedCharacterTags.value = Array.from(new Set(queryCharacterTags))
  }
  if (queryWorldLoreTags.length > 0) {
    selectedWorldLoreTags.value = Array.from(new Set(queryWorldLoreTags))
  }
}

const loadInitialData = async () => {
  loadFromLocalStorage()
  initializeSelections()

  const [characters, worldLore, rulesetList] = await Promise.all([
    getCharacters().catch(() => []),
    listWorldLore().catch(() => []),
    listRulesets().catch(() => []),
    fetchPersonas(),
  ])

  characterCatalog.value = characters.filter(character => !character.is_persona)
  worldLoreCatalog.value = worldLore
  rulesets.value = rulesetList
  characterTagOptions.value = buildTagOptions(characters)
  worldLoreTagOptions.value = buildTagOptions(worldLore)
  if (rulesets.value.length > 0 && !scenarioData.ruleset_id) {
    scenarioData.ruleset_id = rulesets.value[0].id
  }

  if (scenarioData.character_tags.length > 0) {
    selectedCharacterTags.value = [...scenarioData.character_tags.map(normalizeTag)]
  }
  if (scenarioData.world_lore_tags.length > 0) {
    selectedWorldLoreTags.value = [...scenarioData.world_lore_tags.map(normalizeTag)]
  }

  selectedPersonaId.value = settings.value.selectedPersonaId || scenarioData.persona_id || 'none'
  ensureSceneSeedDefaults()
}

const toggleTag = (source: { value: string[] }, tagId: string, enabled: boolean) => {
  if (enabled) {
    if (!source.value.includes(tagId)) {
      source.value.push(tagId)
    }
    return
  }
  source.value = source.value.filter(tag => tag !== tagId)
}

const toggleCharacterTag = (tagId: string, enabled: boolean) => {
  toggleTag(selectedCharacterTags, tagId, enabled)
}

const toggleWorldLoreTag = (tagId: string, enabled: boolean) => {
  toggleTag(selectedWorldLoreTags, tagId, enabled)
}

watch(selectedCharacterTags, (tags) => {
  scenarioData.character_tags = [...tags]
  scenarioData.character_ids = [...selectedCharacterIds.value]
  scenarioData.character_id = primaryCharacterId.value
}, { deep: true })

watch(selectedWorldLoreTags, (tags) => {
  scenarioData.world_lore_tags = [...tags]
  scenarioData.world_lore_id = resolvedWorldLoreId.value
}, { deep: true })

watch(resolvedWorldLoreId, (id) => {
  scenarioData.world_lore_id = id
})

watch(selectedPersonaId, (value) => {
  if (value && value !== 'none') {
    scenarioData.persona_id = value
    settings.value.selectedPersonaId = value
  } else {
    scenarioData.persona_id = ''
    settings.value.selectedPersonaId = undefined
  }
})

watch(() => scenarioData.ruleset_id, () => {
  ensureSceneSeedDefaults()
})

watch(() => scenarioData.suggested_persona_id, (suggestedId) => {
  if (suggestedId && (!selectedPersonaId.value || selectedPersonaId.value === 'none')) {
    selectedPersonaId.value = suggestedId
  }
})

const navigateBack = () => {
  const routeCharacterId = route.params.characterId as string | undefined
  if (routeCharacterId) {
    router.push({ name: 'character', params: { characterId: routeCharacterId } })
  } else {
    router.push({ name: 'create' })
  }
}

const resetScenarioCreation = () => {
  if (!confirm('Are you sure you want to reset? All progress will be lost.')) {
    return
  }

  Object.assign(scenarioData, {
    summary: '',
    intro_message: '',
    narrative_category: '',
    character_id: '',
    character_ids: [],
    character_tags: [],
    ruleset_id: rulesets.value[0]?.id || 'everyday-tension',
    persona_id: '',
    world_lore_id: 'default-world',
    world_lore_tags: [],
    scene_seed: {},
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
  selectedCharacterTags.value = []
  selectedWorldLoreTags.value = []
  messages.value = []
  clearLocalStorage()
  error.value = ''
  userInput.value = ''
  ensureSceneSeedDefaults()
}

const sendMessage = async () => {
  if (!userInput.value.trim() || isThinking.value || selectedCharacterIds.value.length === 0) return

  const message = userInput.value.trim()
  messages.value.push({ author: 'User', content: message, isUser: true, timestamp: new Date() })
  userInput.value = ''
  isThinking.value = true
  error.value = ''

  try {
    const payload: ScenarioCreationRequest = {
      user_message: message,
      character_name: primaryCharacterId.value,
      character_names: [...selectedCharacterIds.value],
      current_scenario: { ...scenarioData, scene_seed: { ...scenarioData.scene_seed } },
      persona_id: selectedPersonaId.value && selectedPersonaId.value !== 'none' ? selectedPersonaId.value : null,
      available_personas: availablePersonas.value,
      conversation_history: messages.value.map(msg => ({ author: msg.author, content: msg.content, is_user: msg.isUser })),
      processor_type: settings.value.largeModelKey,
      backup_processor_type: settings.value.smallModelKey,
    }

    const aiMessageIndex = messages.value.length
    await streamScenarioCreation(
      payload,
      (messageChunk: string) => {
        if (!messages.value[aiMessageIndex]) {
          messages.value.push({ author: 'AI Assistant', content: '', isUser: false, timestamp: new Date() })
        }
        messages.value[aiMessageIndex].content += messageChunk
        isThinking.value = false
      },
      (updates: PartialScenario) => {
        Object.assign(scenarioData, updates)
        scenarioData.character_tags = [...selectedCharacterTags.value]
        scenarioData.character_ids = [...selectedCharacterIds.value]
        scenarioData.character_id = primaryCharacterId.value
        scenarioData.world_lore_tags = [...selectedWorldLoreTags.value]
        scenarioData.world_lore_id = resolvedWorldLoreId.value
      },
      () => {
        if (messages.value[aiMessageIndex] && !messages.value[aiMessageIndex].content) {
          messages.value.splice(aiMessageIndex, 1)
        }
        isThinking.value = false
        saveToLocalStorage()
      },
      (errorMessage: string) => {
        error.value = errorMessage
        if (messages.value[aiMessageIndex]) {
          messages.value.splice(aiMessageIndex, 1)
        }
        isThinking.value = false
      }
    )
  } catch (_err) {
    error.value = 'Failed to send message. Please try again.'
    isThinking.value = false
  }
}

const buildScenarioToSave = (): Scenario => ({
  summary: scenarioData.summary || '',
  intro_message: scenarioData.intro_message || '',
  narrative_category: scenarioData.narrative_category || '',
  character_id: primaryCharacterId.value,
  character_ids: [...selectedCharacterIds.value],
  character_tags: [...selectedCharacterTags.value],
  ruleset_id: scenarioData.ruleset_id,
  persona_id: selectedPersonaId.value && selectedPersonaId.value !== 'none' ? selectedPersonaId.value : undefined,
  world_lore_id: resolvedWorldLoreId.value,
  world_lore_tags: [...selectedWorldLoreTags.value],
  scene_seed: { ...scenarioData.scene_seed },
  location: scenarioData.location,
  time_context: scenarioData.time_context,
  atmosphere: scenarioData.atmosphere,
  plot_hooks: scenarioData.plot_hooks,
  stakes: scenarioData.stakes,
  character_goals: scenarioData.character_goals,
  potential_directions: scenarioData.potential_directions,
})

const saveScenarioToLibrary = async () => {
  if (!isScenarioValid.value) return
  saving.value = true
  try {
    await saveScenario({ scenario: buildScenarioToSave() })
    clearLocalStorage()
    router.push({ name: 'library-scenarios' })
  } catch (err) {
    error.value = getErrorMessage(err, 'Failed to save scenario')
  } finally {
    saving.value = false
  }
}

const startSessionWithCurrentScenario = async () => {
  if (!isScenarioValid.value) return
  saving.value = true
  try {
    const saveResponse = await saveScenario({ scenario: buildScenarioToSave() })
    const response = await startSessionWithScenario({
      scenario_id: saveResponse.scenario_id,
      small_model_key: settings.value.smallModelKey,
      large_model_key: settings.value.largeModelKey,
    })
    clearLocalStorage()
    router.push({ name: 'chat', params: { characterId: primaryCharacterId.value, sessionId: response.session_id } })
  } catch (err) {
    error.value = getErrorMessage(err, 'Failed to start session')
  } finally {
    saving.value = false
  }
}

interface MessageSegment {
  type: 'text' | 'update'
  content: string
  complete: boolean
}

const parseMessageSegments = (content: string): MessageSegment[] => {
  if (!content) return []
  const segments: MessageSegment[] = []
  const parts = content.split(/(<scenario_update>[\s\S]*?(?:<\/scenario_update>|$))/g)
  for (const part of parts) {
    if (!part) continue
    if (part.startsWith('<scenario_update>')) {
      segments.push({ type: 'update', content: '', complete: part.includes('</scenario_update>') })
    } else {
      segments.push({ type: 'text', content: part, complete: true })
    }
  }
  return segments
}

onMounted(() => {
  loadInitialData()
})
</script>
