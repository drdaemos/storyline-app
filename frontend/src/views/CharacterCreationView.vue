<template>
  <section class="space-y-6">
    <div class="story-panel p-5 md:p-7">
      <div class="flex gap-4 items-center justify-between flex-wrap">
        <div>
          <span class="story-chip px-3 py-1 text-xs font-medium inline-flex mb-3">
            Assisted Authoring
          </span>
          <h2 class="text-3xl story-headline">{{ isEditMode ? 'Edit Character' : 'Create New Character' }}</h2>
        </div>
        <div class="flex items-center gap-3">
          <!-- Auto-save indicator (only in create mode) -->
          <div v-if="!isEditMode && autoSaveStatus !== 'idle'" class="flex items-center gap-2 text-sm story-subtext">
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
            @click="resetCharacterCreation"
            :disabled="isThinking || saving"
          >
            Reset
          </UButton>
        </div>
      </div>
    </div>

  <!-- 2 Column Layout -->
  <UMain>
    <div class="grid lg:grid-cols-2 grid-cols-1 gap-6 flex-1 pb-8">
      <!-- Left Column: AI Chat Assistant -->
      <div class="flex flex-col story-panel overflow-hidden max-h-[88vh] lg:sticky top-24">
        <div class="p-4 border-b border-gray-200/70 dark:border-gray-800 bg-cyan-50/70 dark:bg-gray-900">
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-sparkles" class="w-5 h-5 text-primary" />
            <h3 class="text-lg font-semibold">AI Assistant</h3>
          </div>
          <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Describe your character naturally, and I'll help build their profile.
          </p>
        </div>

        <!-- Chat Messages -->
        <div class="flex-1 overflow-y-auto p-4 space-y-4">
          <!-- Welcome message -->
          <div v-if="messages.length === 0" class="space-y-3">
            <div class="p-3 rounded-lg bg-primary/10 border border-primary/20">
              <p class="text-sm">
                Welcome! Describe the character you want to create. You can talk about their personality,
                backstory, appearance, or any other details.
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

                    <!-- Character update block -->
                    <div
                      v-else-if="segment.type === 'update'"
                      class="inline-flex items-center gap-2 px-3 py-1.5 my-1 rounded-md bg-primary/10 border border-primary/20 text-primary"
                    >
                      <UIcon
                        :name="segment.complete ? 'i-lucide-check-circle' : 'i-lucide-loader-circle'"
                        :class="['w-3.5 h-3.5', !segment.complete && 'animate-spin']"
                      />
                      <span class="text-xs font-medium">
                        {{ segment.complete ? 'Character updated' : 'Updating character...' }}
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

        </div>

        <!-- Chat Input -->
        <div class="p-4 border-t border-gray-200 dark:border-gray-800">
          <form @submit.prevent="sendMessage" class="flex gap-2">
            <UInput
              v-model="userInput"
              placeholder="Describe your character..."
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

      <!-- Right Column: Character Sheet -->
      <div class="overflow-y-auto story-panel p-5 md:p-6">
        <h2 class="text-xl story-headline mb-3">Character card</h2>
          <div class="flex items-center gap-3 mb-6">
            <div class="flex-1 space-y-2">
              <UFormField>
                <UInput
                  v-model="characterData.name"
                  placeholder="Jane Doe..."
                  size="lg"
                  variant="ghost"
                  class="w-full"
                  :disabled="isEditMode"
                />
              </UFormField>
              <UFormField>
                <UInput
                  v-model="characterData.tagline"
                  placeholder="e.g., 'A whisper in the wind, a shadow in the night.'"
                  variant="ghost"
                  class="w-full"
                />
              </UFormField>
            </div>
            <div class="w-20 h-20 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center overflow-hidden">
              <UIcon v-if="!characterData.appearance" name="i-lucide-user" class="w-10 h-10 text-gray-400" />
              <img v-else :src="characterData.appearance" alt="Character" class="w-full h-full object-cover" />
            </div>
          </div>

          <div class="space-y-6">
            <!-- Backstory Section -->
            <div>
              <h3 class="text-md font-semibold mb-2 font-serif">Backstory</h3>
              <UFormField>
                <UTextarea
                  v-model="characterData.backstory"
                  :rows="4"
                  autoresize 
                  variant="ghost"
                  class="w-full"
                  placeholder="Character's history and background..."
                />
              </UFormField>
            </div>

            <!-- Personality Section -->
            <div>
              <h3 class="text-md font-semibold mb-2 font-serif">Personality</h3>
              <UFormField>
                <UTextarea
                  v-model="characterData.personality"
                  :rows="4"
                  autoresize 
                  variant="ghost"
                  class="w-full"
                  placeholder="Personality traits and characteristics..."
                />
              </UFormField>
            </div>

            <div>
              <h3 class="text-md font-semibold mb-2 font-serif">Tags</h3>
              <UFormField>
                <UInput
                  v-model="tagsInput"
                  class="w-full"
                  placeholder="Comma-separated tags, e.g. detective, noir, city"
                  @blur="syncTagsFromInput"
                />
              </UFormField>
            </div>

            <!-- Appearance Section -->
            <div>
              <h3 class="text-md font-semibold mb-2 font-serif">Appearance</h3>
              <UFormField>
                <UTextarea
                  v-model="characterData.appearance"
                  :rows="4"
                  autoresize
                  variant="ghost"
                  class="w-full"
                  placeholder="Physical description..."
                />
              </UFormField>
            </div>

            <!-- Interests Section -->
            <div>
              <h3 class="text-md font-semibold mb-3 font-serif">Interests</h3>
              <UFormField>
                <div class="space-y-4">
                  <div
                    v-for="(_, index) in characterData.interests"
                    :key="index"
                    class="flex gap-2"
                  >
                    <UInput
                      v-model="characterData.interests[index]"
                      :placeholder="`Interest ${index + 1}`"
                      class="flex-1"
                    />
                    <UButton
                      color="neutral"
                      variant="ghost"
                      icon="i-lucide-x"
                      size="sm"
                      @click="removeInterest(index)"
                    />
                  </div>
                </div>
              </UFormField>
              <UButton
                v-if="(characterData.interests?.length || 0) < 10"
                color="neutral"
                variant="outline"
                icon="i-lucide-plus"
                size="sm"
                class="mt-3"
                @click="addInterest"
              >
                Add Interest
              </UButton>
            </div>

            <!-- Dislikes Section -->
            <div>
              <h3 class="text-md font-semibold mb-3 font-serif">Dislikes</h3>
              <UFormField>
                <div class="space-y-4">
                  <div
                    v-for="(_, index) in characterData.dislikes"
                    :key="index"
                    class="flex gap-2"
                  >
                    <UInput
                      v-model="characterData.dislikes[index]"
                      :placeholder="`Dislike ${index + 1}`"
                      class="flex-1"
                    />
                    <UButton
                      color="neutral"
                      variant="ghost"
                      icon="i-lucide-x"
                      size="sm"
                      @click="removeDislike(index)"
                    />
                  </div>
                </div>
              </UFormField>
              <UButton
                v-if="(characterData.dislikes?.length || 0) < 10"
                color="neutral"
                variant="outline"
                icon="i-lucide-plus"
                size="sm"
                class="mt-3"
                @click="addDislike"
              >
                Add Dislike
              </UButton>
            </div>

            <!-- Desires Section -->
            <div>
              <h3 class="text-md font-semibold mb-3 font-serif">Desires</h3>
              <UFormField>
                <div class="space-y-4">
                  <div
                    v-for="(_, index) in characterData.desires"
                    :key="index"
                    class="flex gap-2"
                  >
                    <UInput
                      v-model="characterData.desires[index]"
                      :placeholder="`Desire ${index + 1}`"
                      class="flex-1"
                    />
                    <UButton
                      color="neutral"
                      variant="ghost"
                      icon="i-lucide-x"
                      size="sm"
                      @click="removeDesire(index)"
                    />
                  </div>
                </div>
              </UFormField>
              <UButton
                v-if="(characterData.desires?.length || 0) < 10"
                color="neutral"
                variant="outline"
                icon="i-lucide-plus"
                size="sm"
                class="mt-3"
                @click="addDesire"
              >
                Add Desire
              </UButton>
            </div>

            <!-- Kinks Section -->
            <div>
              <h3 class="text-md font-semibold mb-3 font-serif">Kinks</h3>
              <UFormField>
                <div class="space-y-4">
                  <div
                    v-for="(_, index) in characterData.kinks"
                    :key="index"
                    class="flex gap-2"
                  >
                    <UInput
                      v-model="characterData.kinks[index]"
                      :placeholder="`Kink ${index + 1}`"
                      class="flex-1"
                    />
                    <UButton
                      color="neutral"
                      variant="ghost"
                      icon="i-lucide-x"
                      size="sm"
                      @click="removeKink(index)"
                    />
                  </div>
                </div>
              </UFormField>
              <UButton
                v-if="(characterData.kinks?.length || 0) < 10"
                color="neutral"
                variant="outline"
                icon="i-lucide-plus"
                size="sm"
                class="mt-3"
                @click="addKink"
              >
                Add Kink
              </UButton>
            </div>

            <!-- Relationships Section -->
            <div>
              <h3 class="text-md font-semibold mb-2 font-serif">Relationships</h3>
              <div class="space-y-3">
                <div
                  v-for="(rel, index) in relationshipsList"
                  :key="index"
                  class="p-3 border border-gray-200 dark:border-gray-800 rounded-lg space-y-2"
                >
                  <div class="flex gap-2 items-start">
                    <UFormField label="Name" class="flex-1">
                      <UInput
                        v-model="rel.name"
                        placeholder="Character name"
                      />
                    </UFormField>
                    <UButton
                      color="neutral"
                      variant="ghost"
                      icon="i-lucide-x"
                      size="sm"
                      class="mt-6"
                      @click="removeRelationship(index)"
                    />
                  </div>
                  <UFormField label="Description">
                    <UTextarea
                      v-model="rel.description"
                      :rows="2"
                      autoresize
                      variant="ghost"
                      class="w-full"
                      placeholder="Describe the relationship..."
                    />
                  </UFormField>
                </div>
              </div>
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-plus"
                size="sm"
                class="mt-2"
                @click="addRelationship"
              >
                Add Relationship
              </UButton>
            </div>

            <div class="space-y-4">
              <h3 class="text-md font-semibold mb-2 font-serif">Ruleset</h3>
              <UFormField label="Ruleset">
                <USelect
                  class="w-full"
                  value-key="id"
                  v-model="characterData.ruleset_id"
                  :items="rulesets.map(r => ({ id: r.id, label: r.name }))"
                  :loading="rulesetsLoading"
                />
              </UFormField>
              <p class="text-xs story-subtext">
                Ruleset controls stat schema used by simulation for this character.
              </p>
            </div>

            <div v-if="rulesetStatFields.length > 0" class="space-y-3">
              <h3 class="text-md font-semibold mb-2 font-serif">Ruleset Stats</h3>
              <div class="grid sm:grid-cols-2 gap-3">
                <UFormField
                  v-for="field in rulesetStatFields"
                  :key="field.key"
                  :label="field.label"
                >
                  <UInput
                    v-if="field.type === 'integer' || field.type === 'number'"
                    v-model.number="characterData.ruleset_stats[field.key]"
                    type="number"
                    class="w-full"
                    :min="field.minimum"
                    :max="field.maximum"
                  />
                  <UInput
                    v-else-if="field.type === 'string'"
                    v-model="characterData.ruleset_stats[field.key]"
                    class="w-full"
                  />
                  <UCheckbox
                    v-else
                    :model-value="Boolean(characterData.ruleset_stats[field.key])"
                    @update:model-value="(value: boolean | 'indeterminate') => { characterData.ruleset_stats[field.key] = value === true }"
                    :label="field.key"
                  />
                </UFormField>
              </div>
            </div>
          </div>

          <div class="flex gap-3 justify-end mt-6">
            <UButton
              color="neutral"
              variant="outline"
              @click="navigateBack"
            >
              Cancel
            </UButton>
            <UButton
              v-if="!isEditMode"
              color="neutral"
              variant="outline"
              :disabled="!isCharacterValid || saving"
              :loading="saving"
              @click="() => saveCharacter(true)"
            >
              Save as Persona
            </UButton>
            <UButton
              color="primary"
              :disabled="!isCharacterValid || saving"
              :loading="saving"
              @click="() => saveCharacter(false)"
            >
              {{ isEditMode ? 'Update Character' : 'Create Character' }}
            </UButton>
          </div>
      </div>
    </div>
  </UMain>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, reactive, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { useCharacterCreationAutoSave } from '@/composables/useCharacterCreationAutoSave'
import { usePersonas } from '@/composables/usePersonas'
import type { Character, ChatMessage, CharacterCreationRequest, RulesetDefinition } from '@/types'

const props = defineProps<{
  characterId?: string
}>()

const router = useRouter()
const { streamCharacterCreation, createCharacter, updateCharacter, getCharacterInfo, listRulesets } = useApi()
const { settings } = useLocalSettings()
const { fetchPersonas } = usePersonas()

const isEditMode = computed(() => !!props.characterId)

const userInput = ref('')
const messages = ref<ChatMessage[]>([])
const isThinking = ref(false)
const error = ref('')
const saving = ref(false)

type CharacterFormData = {
  name: string
  tagline: string
  backstory: string
  personality: string
  appearance: string
  relationships: Record<string, string>
  ruleset_id: string
  ruleset_stats: Record<string, number | string | boolean>
  interests: string[]
  dislikes: string[]
  desires: string[]
  kinks: string[]
  tags: string[]
}

interface RelationshipItem {
  name: string
  description: string
}

const characterData = reactive<CharacterFormData>({
  name: '',
  tagline: '',
  backstory: '',
  personality: '',
  appearance: '',
  relationships: {},
  ruleset_id: 'everyday-tension',
  ruleset_stats: {},
  interests: [],
  dislikes: [],
  desires: [],
  kinks: [],
  tags: [],
})

const relationshipsList = ref<RelationshipItem[]>([])
const tagsInput = ref('')
const rulesets = ref<RulesetDefinition[]>([])
const rulesetsLoading = ref(false)

type RulesetStatField = {
  key: string
  type: 'integer' | 'number' | 'string' | 'boolean'
  minimum?: number
  maximum?: number
  label: string
}

const selectedRuleset = computed(() => {
  if (rulesets.value.length === 0) return null
  return rulesets.value.find(ruleset => ruleset.id === characterData.ruleset_id) || rulesets.value[0]
})

const rulesetStatFields = computed<RulesetStatField[]>(() => {
  const schema = selectedRuleset.value?.character_stat_schema
  if (!schema || typeof schema !== 'object') return []
  const properties = (schema as Record<string, unknown>).properties
  if (!properties || typeof properties !== 'object') return []
  return Object.entries(properties as Record<string, Record<string, unknown>>).map(([key, prop]) => {
    const rawType = String(prop.type || 'string')
    const normalizedType = (['integer', 'number', 'string', 'boolean'].includes(rawType) ? rawType : 'string') as RulesetStatField['type']
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

const coerceStatValue = (field: RulesetStatField, value: unknown): number | string | boolean => {
  if (field.type === 'integer') {
    const numeric = Number(value)
    const fallback = typeof field.minimum === 'number' ? field.minimum : 0
    let result = Number.isFinite(numeric) ? Math.round(numeric) : fallback
    if (typeof field.minimum === 'number') result = Math.max(field.minimum, result)
    if (typeof field.maximum === 'number') result = Math.min(field.maximum, result)
    return result
  }
  if (field.type === 'number') {
    const numeric = Number(value)
    const fallback = typeof field.minimum === 'number' ? field.minimum : 0
    let result = Number.isFinite(numeric) ? numeric : fallback
    if (typeof field.minimum === 'number') result = Math.max(field.minimum, result)
    if (typeof field.maximum === 'number') result = Math.min(field.maximum, result)
    return result
  }
  if (field.type === 'boolean') {
    return Boolean(value)
  }
  return String(value ?? '')
}

const ensureRulesetStatsDefaults = () => {
  const next: Record<string, number | string | boolean> = {}
  for (const field of rulesetStatFields.value) {
    const existing = characterData.ruleset_stats[field.key]
    if (existing === undefined || existing === null || existing === '') {
      if (field.type === 'boolean') {
        next[field.key] = false
      } else if (field.type === 'string') {
        next[field.key] = ''
      } else {
        next[field.key] = coerceStatValue(field, field.minimum ?? 0)
      }
      continue
    }
    next[field.key] = coerceStatValue(field, existing)
  }
  characterData.ruleset_stats = next
}

const loadRulesets = async () => {
  rulesetsLoading.value = true
  try {
    rulesets.value = await listRulesets()
    if (rulesets.value.length > 0 && !characterData.ruleset_id) {
      characterData.ruleset_id = rulesets.value[0].id
    }
  } finally {
    rulesetsLoading.value = false
    ensureRulesetStatsDefaults()
  }
}
const getErrorMessage = (err: unknown, fallback: string): string => {
  if (err instanceof Error && err.message) return err.message
  return fallback
}

// Auto-save functionality (only for create mode, not edit mode)
const autoSaveEnabled = !isEditMode.value
const autoSaveFunctions = autoSaveEnabled
  ? useCharacterCreationAutoSave(characterData, messages)
  : {
      autoSaveStatus: ref<'saving' | 'saved' | 'idle'>('idle'),
      saveToLocalStorage: () => {},
      loadFromLocalStorage: () => false,
      clearLocalStorage: () => {}
    }

const { autoSaveStatus, saveToLocalStorage, loadFromLocalStorage, clearLocalStorage } = autoSaveFunctions

// Load saved state or character data on mount
onMounted(async () => {
  await loadRulesets()
  if (isEditMode.value && props.characterId) {
    // Load existing character data for editing
    try {
      const characterInfo = await getCharacterInfo(props.characterId)

      // Populate characterData with all loaded fields
      Object.assign(characterData, {
        name: characterInfo.name || '',
        tagline: characterInfo.tagline || '',
        backstory: characterInfo.backstory || '',
        personality: characterInfo.personality || '',
        appearance: characterInfo.appearance || '',
        ruleset_id: characterInfo.ruleset_id || characterData.ruleset_id || 'everyday-tension',
        ruleset_stats: characterInfo.ruleset_stats || {},
        relationships: characterInfo.relationships || {},
        interests: characterInfo.interests || [],
        dislikes: characterInfo.dislikes || [],
        desires: characterInfo.desires || [],
        kinks: characterInfo.kinks || [],
        tags: characterInfo.tags || [],
      })

      // Populate relationshipsList from relationships object
      if (characterInfo.relationships) {
        relationshipsList.value = Object.entries(characterInfo.relationships).map(([name, description]) => ({
          name,
          description: description as string,
        }))
      }
    } catch (err) {
      error.value = getErrorMessage(err, 'Failed to load character data')
    }
    ensureRulesetStatsDefaults()
  } else {
    // Load from localStorage for new character creation
    loadFromLocalStorage()
    ensureRulesetStatsDefaults()
  }
})

// Reset functionality
const resetCharacterCreation = async () => {
  // Different behavior for edit mode vs create mode
  if (isEditMode.value && props.characterId) {
    // In edit mode: reload from server
    if (!confirm('Are you sure you want to discard your changes? This will reload the character from the server.')) {
      return
    }

    try {
      const characterInfo = await getCharacterInfo(props.characterId)

      // Reload character data
      Object.assign(characterData, {
        name: characterInfo.name || '',
        tagline: characterInfo.tagline || '',
        backstory: characterInfo.backstory || '',
        personality: characterInfo.personality || '',
        appearance: characterInfo.appearance || '',
        ruleset_id: characterInfo.ruleset_id || characterData.ruleset_id || 'everyday-tension',
        ruleset_stats: characterInfo.ruleset_stats || {},
        relationships: characterInfo.relationships || {},
        interests: characterInfo.interests || [],
        dislikes: characterInfo.dislikes || [],
        desires: characterInfo.desires || [],
        kinks: characterInfo.kinks || [],
        tags: characterInfo.tags || [],
      })

      // Reload relationshipsList
      if (characterInfo.relationships) {
        relationshipsList.value = Object.entries(characterInfo.relationships).map(([name, description]) => ({
          name,
          description: description as string,
        }))
      } else {
        relationshipsList.value = []
      }

      // Clear messages and other state
      messages.value = []
      error.value = ''
      userInput.value = ''
      ensureRulesetStatsDefaults()
    } catch (err) {
      error.value = getErrorMessage(err, 'Failed to reload character data')
    }
  } else {
    // In create mode: clear everything
    if (!confirm('Are you sure you want to reset? All progress will be lost.')) {
      return
    }

    // Clear character data
    Object.assign(characterData, {
      name: '',
      tagline: '',
      backstory: '',
      personality: '',
      appearance: '',
      relationships: {},
      ruleset_id: rulesets.value[0]?.id || 'everyday-tension',
      ruleset_stats: {},
      interests: [],
      dislikes: [],
      desires: [],
      kinks: [],
      tags: [],
    })

    // Clear relationshipsList
    relationshipsList.value = []

    // Clear messages
    messages.value = []

    // Clear localStorage
    clearLocalStorage()

    // Reset other state
    error.value = ''
    userInput.value = ''
    ensureRulesetStatsDefaults()
  }
}

// Watch for relationships changes and sync with characterData
watch(relationshipsList, (newList) => {
  const relationshipsObj: Record<string, string> = {}
  newList.forEach((rel) => {
    if (rel.name.trim() && rel.description.trim()) {
      relationshipsObj[rel.name.trim()] = rel.description.trim()
    }
  })
  characterData.relationships = relationshipsObj
}, { deep: true })

// Watch for characterData.relationships changes from AI and sync with list
watch(() => characterData.relationships, (newRelationships) => {
  if (newRelationships) {
    const newList = Object.entries(newRelationships).map(([name, description]) => ({
      name,
      description,
    }))

    // Only update if different to avoid infinite loop
    if (JSON.stringify(newList) !== JSON.stringify(relationshipsList.value)) {
      relationshipsList.value = newList
    }
  }
}, { deep: true })

const syncTagsFromInput = () => {
  const tags = tagsInput.value
    .split(',')
    .map(tag => tag.trim())
    .filter(Boolean)
  characterData.tags = tags.filter((tag, index) => tags.indexOf(tag) === index)
}

watch(() => characterData.tags, (tags) => {
  tagsInput.value = (tags || []).join(', ')
}, { deep: true, immediate: true })

watch(() => characterData.ruleset_id, () => {
  ensureRulesetStatsDefaults()
})

const isCharacterValid = computed(() => {
  return true
})

const navigateBack = () => {
  router.push('/')
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
  // scrollToBottom()

  try {
    const payload: CharacterCreationRequest = {
      user_message: message,
      current_character: characterData,
      conversation_history: messages.value.map(msg => ({
        author: msg.author,
        content: msg.content,
        is_user: msg.isUser
      })),
      processor_type: settings.value.largeModelKey,
      backup_processor_type: settings.value.smallModelKey,
    }

    // Create a temporary AI message that will be updated in real-time
    const aiMessageIndex = messages.value.length

    await streamCharacterCreation(
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
      (updates: Partial<Character>) => {
        // Merge updates into characterData
        Object.assign(characterData, updates)
      },
      // onComplete callback
      () => {
        // Remove empty message if no content was received
        if (!messages.value[aiMessageIndex].content) {
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
        messages.value.splice(aiMessageIndex, 1)
        isThinking.value = false
      }
    )
  } catch (_err) {
    error.value = 'Failed to send message. Please try again.'
    isThinking.value = false
  }
}

const saveCharacter = async (isPersona: boolean = false) => {
  if (!isCharacterValid.value) return

  syncTagsFromInput()
  ensureRulesetStatsDefaults()
  saving.value = true
  try {
    if (isEditMode.value && props.characterId) {
      // Update existing character
      await updateCharacter(props.characterId, {
        data: characterData as Character,
        is_yaml_text: false,
        is_persona: isPersona,
      })
    } else {
      // Create new character
      await createCharacter({
        data: characterData as Character,
        is_yaml_text: false,
        is_persona: isPersona,
      })
    }

    // If saved as persona, refetch personas to update the list
    if (isPersona) {
      await fetchPersonas()
    }

    // Clear localStorage after successful save
    clearLocalStorage()

    // Navigate back
    if (isEditMode.value && props.characterId) {
      router.push(`/character/${props.characterId}`)
    } else {
      router.push('/')
    }
  } catch (err) {
    error.value = getErrorMessage(err, `Failed to ${isEditMode.value ? 'update' : 'create'} character`)
  } finally {
    saving.value = false
  }
}

const addRelationship = () => {
  relationshipsList.value.push({ name: '', description: ''})
}

const removeRelationship = (index: number) => {
  relationshipsList.value.splice(index, 1)
}

const addInterest = () => {
  if (!characterData.interests) {
    characterData.interests = []
  }
  if (characterData.interests.length < 10) {
    characterData.interests.push('')
  }
}

const removeInterest = (index: number) => {
  characterData.interests?.splice(index, 1)
}

const addDislike = () => {
  if (!characterData.dislikes) {
    characterData.dislikes = []
  }
  if (characterData.dislikes.length < 10) {
    characterData.dislikes.push('')
  }
}

const removeDislike = (index: number) => {
  characterData.dislikes?.splice(index, 1)
}

const addDesire = () => {
  if (!characterData.desires) {
    characterData.desires = []
  }
  if (characterData.desires.length < 10) {
    characterData.desires.push('')
  }
}

const removeDesire = (index: number) => {
  characterData.desires?.splice(index, 1)
}

const addKink = () => {
  if (!characterData.kinks) {
    characterData.kinks = []
  }
  if (characterData.kinks.length < 10) {
    characterData.kinks.push('')
  }
}

const removeKink = (index: number) => {
  characterData.kinks?.splice(index, 1)
}

interface MessageSegment {
  type: 'text' | 'update'
  content: string
  complete: boolean
}

const parseMessageSegments = (content: string): MessageSegment[] => {
  if (!content) return []

  const segments: MessageSegment[] = []

  // Split by <character_update> tags and track positions
  const parts = content.split(/(<character_update>[\s\S]*?(?:<\/character_update>|$))/g)

  for (const part of parts) {
    if (!part) continue

    // Check if this part is a character update block
    if (part.startsWith('<character_update>')) {
      const hasClosingTag = part.includes('</character_update>')
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
