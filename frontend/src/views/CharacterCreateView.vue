<script setup lang="ts">
import { Plus, SendHorizontal, Sparkles, Trash2, UserRound, Users } from 'lucide-vue-next'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import ModelSettingsDialog from '@/components/app/ModelSettingsDialog.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useApi } from '@/composables/useApi'
import { useCharacterCreationAutoSave } from '@/composables/useCharacterCreationAutoSave'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { usePipelineApi } from '@/composables/usePipelineApi'
import { usePersonas } from '@/composables/usePersonas'
import type { Character, CharacterCreationRequest, ChatMessage } from '@/types'
import type { CharacterDetailV2, RulesetDetailV2, RulesetSummaryV2 } from '@/types/pipeline'
import {
  hasPendingSpecialXmlTag,
  renderAssistantMessageHtml,
  renderPlainTextHtml,
} from '@/utils/assistantMessageFormatting'

interface Props {
  personaMode?: boolean
}

interface EmotionalStateDraft extends Record<string, unknown> {
  global_state: Record<string, number>
  per_relationship: Record<string, Record<string, number>>
}

interface CharacterDraft extends Partial<Character> {
  name: string
  tagline: string
  backstory: string
  personality: string
  appearance: string
  ruleset_id: string
  interests: string[]
  dislikes: string[]
  desires: string[]
  kinks: string[]
  starting_drives: Record<string, number>
  starting_skills: Record<string, number>
  starting_emotional_state: EmotionalStateDraft
}

type ListFieldKey = 'interests' | 'dislikes' | 'desires' | 'kinks'
const STRUCTURED_UPDATE_ANCHOR = '[[STRUCTURED_UPDATE_ANCHOR]]'

const props = withDefaults(defineProps<Props>(), {
  personaMode: false,
})

const route = useRoute()
const router = useRouter()

const editingCharacterId = computed(() => String(route.params.characterId || '').trim())
const isEditMode = computed(() => !!editingCharacterId.value)
const queryPersona = ['true', '1', 'yes'].includes(String(route.query.persona || '').toLowerCase())
const loadedPersonaMode = ref<boolean | null>(null)
const isPersonaMode = computed(() => loadedPersonaMode.value ?? (props.personaMode || queryPersona))

const { streamCharacterCreation, createCharacter, updateCharacter } = useApi()
const { getCharacterDetail, getRuleset, listRulesets } = usePipelineApi()
const { settings } = useLocalSettings()
const { fetchPersonas } = usePersonas()

const userInput = ref('')
const isThinking = ref(false)
const loadingEntity = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const rulesetError = ref<string | null>(null)
const loadingRulesets = ref(true)
const messages = ref<ChatMessage[]>([])
const chatEndRef = ref<HTMLElement | null>(null)
const originalSnapshot = ref<CharacterDraft | null>(null)
const specialUpdateState = ref<'idle' | 'processing' | 'done'>('idle')
const activeAssistantMessageIndex = ref<number | null>(null)

const rulesets = ref<RulesetSummaryV2[]>([])
const rulesetCache = ref<Record<string, RulesetDetailV2>>({})
const selectedRuleset = ref<RulesetDetailV2 | null>(null)
const selectedRulesetId = ref('none')

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const toNumber = (value: unknown, fallback: number): number => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

const clamp = (value: number, min: number, max: number): number => {
  if (value < min) {
    return min
  }
  if (value > max) {
    return max
  }
  return value
}

const toNumberRecord = (value: unknown): Record<string, number> => {
  if (!isRecord(value)) {
    return {}
  }

  return Object.entries(value).reduce<Record<string, number>>((acc, [key, rawValue]) => {
    const parsed = Number(rawValue)
    if (Number.isFinite(parsed)) {
      acc[key] = parsed
    }
    return acc
  }, {})
}

const toPerRelationshipState = (value: unknown): Record<string, Record<string, number>> => {
  if (!isRecord(value)) {
    return {}
  }

  return Object.entries(value).reduce<Record<string, Record<string, number>>>((acc, [name, dims]) => {
    acc[name] = toNumberRecord(dims)
    return acc
  }, {})
}

const normalizeEmotionalState = (value: unknown): EmotionalStateDraft => {
  if (!isRecord(value)) {
    return {
      global_state: {},
      per_relationship: {},
    }
  }

  return {
    global_state: toNumberRecord(value.global_state),
    per_relationship: toPerRelationshipState(value.per_relationship),
  }
}

const createEmptyCharacterData = (): CharacterDraft => ({
  name: '',
  tagline: '',
  backstory: '',
  personality: '',
  appearance: '',
  ruleset_id: '',
  interests: [],
  dislikes: [],
  desires: [],
  kinks: [],
  starting_drives: {},
  starting_skills: {},
  starting_emotional_state: {
    global_state: {},
    per_relationship: {},
  },
})

const characterData = reactive<CharacterDraft>(createEmptyCharacterData())

const draftKey = computed(() => {
  if (isEditMode.value) {
    return `character-edit-${editingCharacterId.value}`
  }
  return isPersonaMode.value ? 'persona-creation' : 'character-creation'
})

const { autoSaveStatus, loadFromLocalStorage, clearLocalStorage } = useCharacterCreationAutoSave(
  characterData,
  messages,
  draftKey.value
)

const listFields: Array<{ key: ListFieldKey; label: string; placeholder: string }> = [
  { key: 'interests', label: 'Interests', placeholder: 'Detective work' },
  { key: 'dislikes', label: 'Dislikes', placeholder: 'Being lied to' },
  { key: 'desires', label: 'Desires', placeholder: 'Clear the debt ledger' },
  { key: 'kinks', label: 'Kinks', placeholder: 'Optional' },
]

const panelTitle = computed(() => {
  if (isEditMode.value) {
    return isPersonaMode.value ? 'Persona Sheet' : 'Character Sheet'
  }
  return isPersonaMode.value ? 'Persona Sheet' : 'Character Sheet'
})

const pageTitle = computed(() => {
  if (isEditMode.value) {
    return isPersonaMode.value ? 'Edit Persona' : 'Edit Character'
  }
  return isPersonaMode.value ? 'Create Persona' : 'Create Character'
})

const pageSubtitle = computed(() =>
  isEditMode.value
    ? 'Adjust profile details and keep this entity aligned with the new scenario pipeline.'
    : isPersonaMode.value
      ? 'Build a reusable protagonist profile with AI-assisted drafting.'
      : 'Build a reusable NPC profile with AI-assisted drafting.'
)

const saveButtonText = computed(() => {
  if (isEditMode.value) {
    return 'Save Changes'
  }
  return isPersonaMode.value ? 'Create Persona' : 'Create Character'
})
const showCreatePersonaAction = computed(() => !isPersonaMode.value && !isEditMode.value)

const slugify = (value: string): string => value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
const normalizeSchemaKey = (value: string): string => value.toLowerCase().replace(/[^a-z0-9]+/g, '')

const driveSchemaByName = computed(() => {
  return new Map((selectedRuleset.value?.state_schemas.drives || []).map((item) => [item.name, item]))
})

const skillSchemaByName = computed(() => {
  return new Map((selectedRuleset.value?.state_schemas.skills || []).map((item) => [item.name, item]))
})

const emotionalGlobalSchemaByName = computed(() => {
  return new Map(
    (selectedRuleset.value?.state_schemas.emotional_state.global_dims || []).map((item) => [item.name, item])
  )
})

const selectedRulesetContext = computed<CharacterCreationRequest['ruleset_context']>(() => {
  if (!selectedRuleset.value) {
    return null
  }

  return {
    id: selectedRuleset.value.id,
    name: selectedRuleset.value.name,
    rules_text: selectedRuleset.value.rules_text,
    state_schemas: selectedRuleset.value.state_schemas as Record<string, unknown>,
  }
})

const updateListItem = (key: ListFieldKey, index: number, value: string) => {
  characterData[key][index] = value
}

const addListItem = (key: ListFieldKey) => {
  if (characterData[key].length < 10) {
    characterData[key].push('')
  }
}

const removeListItem = (key: ListFieldKey, index: number) => {
  characterData[key].splice(index, 1)
}

const setDriveValue = (name: string, rawValue: string | number) => {
  const schema = driveSchemaByName.value.get(name)
  if (!schema) {
    return
  }

  const next = clamp(toNumber(rawValue, schema.default), schema.range_min, schema.range_max)
  characterData.starting_drives = {
    ...characterData.starting_drives,
    [name]: next,
  }
}

const setSkillValue = (name: string, rawValue: string | number) => {
  const schema = skillSchemaByName.value.get(name)
  if (!schema) {
    return
  }

  const current = characterData.starting_skills[name] ?? schema.range_min
  const next = clamp(toNumber(rawValue, current), schema.range_min, schema.range_max)
  characterData.starting_skills = {
    ...characterData.starting_skills,
    [name]: next,
  }
}

const setGlobalEmotionalValue = (name: string, rawValue: string | number) => {
  const schema = emotionalGlobalSchemaByName.value.get(name)
  if (!schema) {
    return
  }

  const current = characterData.starting_emotional_state.global_state[name] ?? schema.default
  const next = clamp(toNumber(rawValue, current), schema.range_min, schema.range_max)

  characterData.starting_emotional_state = {
    ...characterData.starting_emotional_state,
    global_state: {
      ...characterData.starting_emotional_state.global_state,
      [name]: next,
    },
  }
}

const buildCanonicalRecordFromSchema = (
  source: Record<string, number>,
  schemaByName: Map<string, { name: string; range_min: number; range_max: number; default?: number }>,
  fallbackBySchema: (schema: { name: string; range_min: number; range_max: number; default?: number }) => number
): Record<string, number> => {
  const output: Record<string, number> = {}

  for (const schema of schemaByName.values()) {
    let value: number | undefined

    if (Number.isFinite(source[schema.name])) {
      value = source[schema.name]
    } else {
      const normalizedName = normalizeSchemaKey(schema.name)
      for (const [key, raw] of Object.entries(source)) {
        if (normalizeSchemaKey(key) === normalizedName && Number.isFinite(raw)) {
          value = raw
          break
        }
      }
    }

    const fallback = fallbackBySchema(schema)
    output[schema.name] = clamp(toNumber(value, fallback), schema.range_min, schema.range_max)
  }

  return output
}

const normalizeCurrentStartingState = () => {
  if (!selectedRuleset.value) {
    return
  }

  const normalizedDrives = buildCanonicalRecordFromSchema(
    toNumberRecord(characterData.starting_drives),
    driveSchemaByName.value,
    (schema) => schema.default ?? schema.range_min
  )

  const normalizedSkills = buildCanonicalRecordFromSchema(
    toNumberRecord(characterData.starting_skills),
    skillSchemaByName.value,
    (schema) => schema.range_min
  )

  const normalizedGlobalState = buildCanonicalRecordFromSchema(
    toNumberRecord(characterData.starting_emotional_state.global_state),
    emotionalGlobalSchemaByName.value,
    (schema) => schema.default ?? schema.range_min
  )

  characterData.starting_drives = normalizedDrives
  characterData.starting_skills = normalizedSkills
  characterData.starting_emotional_state = {
    ...characterData.starting_emotional_state,
    global_state: normalizedGlobalState,
  }
}

const applyAssistantStateAliases = (update: Partial<Character>) => {
  const rawUpdate = update as Record<string, unknown>
  const statBlock = isRecord(rawUpdate.stat_block)
    ? (rawUpdate.stat_block as Record<string, unknown>)
    : null

  if (isRecord(rawUpdate.drives) && !isRecord(rawUpdate.starting_drives)) {
    rawUpdate.starting_drives = rawUpdate.drives
  }
  if (statBlock && isRecord(statBlock.drives) && !isRecord(rawUpdate.starting_drives)) {
    rawUpdate.starting_drives = statBlock.drives
  }

  if (isRecord(rawUpdate.skills) && !isRecord(rawUpdate.starting_skills)) {
    rawUpdate.starting_skills = rawUpdate.skills
  }
  if (statBlock && isRecord(statBlock.skills) && !isRecord(rawUpdate.starting_skills)) {
    rawUpdate.starting_skills = statBlock.skills
  }

  if (!isRecord(rawUpdate.starting_emotional_state)) {
    const emotionalState =
      (isRecord(rawUpdate.emotional_state) && rawUpdate.emotional_state) ||
      (statBlock && isRecord(statBlock.emotional_state) ? statBlock.emotional_state : null)

    if (isRecord(emotionalState)) {
      if (isRecord(emotionalState.global_state) || isRecord(emotionalState.per_relationship)) {
        rawUpdate.starting_emotional_state = {
          global_state: isRecord(emotionalState.global_state) ? emotionalState.global_state : {},
          per_relationship: isRecord(emotionalState.per_relationship) ? emotionalState.per_relationship : {},
        }
      } else {
        rawUpdate.starting_emotional_state = {
          global_state: emotionalState,
          per_relationship: {},
        }
      }
    }
  }

  if (isRecord(rawUpdate.starting_emotional_state)) {
    rawUpdate.starting_emotional_state = {
      global_state: isRecord(rawUpdate.starting_emotional_state.global_state)
        ? rawUpdate.starting_emotional_state.global_state
        : {},
      per_relationship: isRecord(rawUpdate.starting_emotional_state.per_relationship)
        ? rawUpdate.starting_emotional_state.per_relationship
        : {},
    }
  }
}

const applyRulesetSchemaToStartingState = (ruleset: RulesetDetailV2) => {
  const nextDrives: Record<string, number> = {}
  for (const drive of ruleset.state_schemas.drives) {
    const existing = characterData.starting_drives[drive.name]
    const fallback = drive.default
    nextDrives[drive.name] = clamp(toNumber(existing, fallback), drive.range_min, drive.range_max)
  }

  const nextSkills: Record<string, number> = {}
  for (const skill of ruleset.state_schemas.skills) {
    const existing = characterData.starting_skills[skill.name]
    const fallback = skill.range_min
    nextSkills[skill.name] = clamp(toNumber(existing, fallback), skill.range_min, skill.range_max)
  }

  const nextGlobalState: Record<string, number> = {}
  for (const dim of ruleset.state_schemas.emotional_state.global_dims) {
    const existing = characterData.starting_emotional_state.global_state[dim.name]
    nextGlobalState[dim.name] = clamp(toNumber(existing, dim.default), dim.range_min, dim.range_max)
  }

  characterData.ruleset_id = ruleset.id
  characterData.starting_drives = nextDrives
  characterData.starting_skills = nextSkills
  characterData.starting_emotional_state = {
    global_state: nextGlobalState,
    per_relationship: characterData.starting_emotional_state.per_relationship,
  }
}

const getRulesetDetail = async (rulesetId: string): Promise<RulesetDetailV2> => {
  const cached = rulesetCache.value[rulesetId]
  if (cached) {
    return cached
  }

  const detail = await getRuleset(rulesetId)
  rulesetCache.value = {
    ...rulesetCache.value,
    [rulesetId]: detail,
  }
  return detail
}

const selectRuleset = async (rulesetId: string) => {
  if (!rulesetId || rulesetId === 'none') {
    selectedRuleset.value = null
    characterData.ruleset_id = ''
    return
  }

  rulesetError.value = null

  try {
    const detail = await getRulesetDetail(rulesetId)
    selectedRuleset.value = detail
    applyRulesetSchemaToStartingState(detail)
  } catch {
    selectedRuleset.value = null
    rulesetError.value = 'Failed to load selected ruleset.'
  }
}

const loadRulesetOptions = async () => {
  loadingRulesets.value = true
  rulesetError.value = null

  try {
    rulesets.value = await listRulesets()
  } catch {
    rulesets.value = []
    rulesetError.value = 'Failed to load rulesets.'
  } finally {
    loadingRulesets.value = false
  }
}

const extractAssistantUpdates = (
  rawAssistantContent: string
): { cleanMessage: string; updates: Partial<Character>[] } => {
  const updates: Partial<Character>[] = []

  const withoutCompleteBlocks = rawAssistantContent.replace(
    /<character_update>\s*([\s\S]*?)\s*<\/character_update>/g,
    (_, jsonPayload: string) => {
      try {
        updates.push(JSON.parse(jsonPayload) as Partial<Character>)
      } catch {
        // Ignore malformed update payloads.
      }

      return ` ${STRUCTURED_UPDATE_ANCHOR} `
    }
  )

  const pendingOpenTagIndex = withoutCompleteBlocks.indexOf('<character_update>')
  const cleanMessage = pendingOpenTagIndex >= 0
    ? `${withoutCompleteBlocks.slice(0, pendingOpenTagIndex).trimEnd()} ${STRUCTURED_UPDATE_ANCHOR}`.trim()
    : withoutCompleteBlocks.trim()

  return { cleanMessage, updates }
}

const renderAssistantContentWithUpdateState = (content: string, index: number): string => {
  const isActiveMessage = index === activeAssistantMessageIndex.value
  const statusText =
    !isActiveMessage || specialUpdateState.value === 'idle'
      ? ''
      : specialUpdateState.value === 'processing'
        ? '⟳ Applying structured update...'
        : '✓ Structured update applied'

  let nextContent = content

  if (statusText) {
    if (nextContent.includes(STRUCTURED_UPDATE_ANCHOR)) {
      nextContent = nextContent.split(STRUCTURED_UPDATE_ANCHOR).join(statusText)
    } else {
      nextContent = `${nextContent}${nextContent ? '\n' : ''}${statusText}`
    }
  } else if (nextContent.includes(STRUCTURED_UPDATE_ANCHOR)) {
    nextContent = nextContent.split(STRUCTURED_UPDATE_ANCHOR).join('')
  }

  return renderAssistantMessageHtml(nextContent.trim())
}

const applyCharacterState = (nextCharacter: Partial<Character>) => {
  Object.assign(characterData, createEmptyCharacterData(), nextCharacter)

  characterData.starting_drives = toNumberRecord(characterData.starting_drives)
  characterData.starting_skills = toNumberRecord(characterData.starting_skills)
  characterData.starting_emotional_state = normalizeEmotionalState(characterData.starting_emotional_state)
}

const toEditableCharacter = (detail: CharacterDetailV2): CharacterDraft => ({
  name: detail.name,
  tagline: detail.tagline,
  backstory: detail.backstory,
  personality: detail.personality,
  appearance: detail.appearance,
  ruleset_id: detail.ruleset_id || '',
  interests: [...detail.interests],
  dislikes: [...detail.dislikes],
  desires: [...detail.desires],
  kinks: [...detail.kinks],
  starting_drives: toNumberRecord(detail.starting_drives),
  starting_skills: toNumberRecord(detail.starting_skills),
  starting_emotional_state: normalizeEmotionalState(detail.starting_emotional_state),
})

const clearDraft = () => {
  if (isEditMode.value && originalSnapshot.value) {
    applyCharacterState(originalSnapshot.value)
    selectedRulesetId.value = originalSnapshot.value.ruleset_id || 'none'
  } else {
    applyCharacterState(createEmptyCharacterData())
    selectedRulesetId.value = rulesets.value[0]?.id || 'none'
  }

  messages.value = []
  userInput.value = ''
  error.value = null
  clearLocalStorage()
}

const loadExistingCharacter = async () => {
  if (!isEditMode.value) {
    return
  }

  loadingEntity.value = true
  error.value = null

  try {
    const detail = await getCharacterDetail(editingCharacterId.value)
    loadedPersonaMode.value = detail.is_persona

    const editable = toEditableCharacter(detail)
    originalSnapshot.value = editable
    applyCharacterState(editable)
    selectedRulesetId.value = editable.ruleset_id || 'none'
  } catch {
    error.value = 'Failed to load character for editing.'
  } finally {
    loadingEntity.value = false
  }
}

watch(
  selectedRulesetId,
  async (nextId, prevId) => {
    if (nextId === prevId) {
      return
    }
    await selectRuleset(nextId)
  }
)

watch(
  () => messages.value.length,
  () => {
    nextTick(() => {
      if (chatEndRef.value && 'scrollIntoView' in chatEndRef.value) {
        chatEndRef.value.scrollIntoView({ behavior: 'smooth' })
      }
    })
  }
)

onMounted(async () => {
  if (isEditMode.value) {
    await loadExistingCharacter()
    loadFromLocalStorage()
  } else {
    loadFromLocalStorage()
  }

  await loadRulesetOptions()

  const currentRulesetId = characterData.ruleset_id.trim()
  const canKeepCurrent = currentRulesetId && rulesets.value.some((ruleset) => ruleset.id === currentRulesetId)

  if (canKeepCurrent) {
    selectedRulesetId.value = currentRulesetId
    await selectRuleset(currentRulesetId)
    return
  }

  if (rulesets.value.length) {
    selectedRulesetId.value = rulesets.value[0].id
    await selectRuleset(rulesets.value[0].id)
    return
  }

  selectedRulesetId.value = 'none'
})

const submitAssistantPrompt = async () => {
  if (!userInput.value.trim() || isThinking.value) {
    return
  }

  const prompt = userInput.value.trim()

  messages.value.push({
    author: 'You',
    content: prompt,
    isUser: true,
    timestamp: new Date(),
  })

  userInput.value = ''
  error.value = null
  isThinking.value = true
  specialUpdateState.value = 'idle'
  activeAssistantMessageIndex.value = null

  const assistantMessageIndex = messages.value.length
  let rawAssistantContent = ''

  try {
    const payload: CharacterCreationRequest = {
      user_message: prompt,
      current_character: { ...characterData },
      ruleset_context: selectedRulesetContext.value,
      conversation_history: messages.value.map((message) => ({
        author: message.author,
        content: message.content,
        is_user: message.isUser,
      })),
      processor_type: settings.value.aiProcessor,
      backup_processor_type: settings.value.backupProcessor,
    }

    await streamCharacterCreation(
      payload,
      (messageChunk: string) => {
        rawAssistantContent += messageChunk

        const { cleanMessage, updates } = extractAssistantUpdates(rawAssistantContent)

        if (!messages.value[assistantMessageIndex]) {
          messages.value.push({
            author: 'Assistant',
            content: '',
            isUser: false,
            timestamp: new Date(),
          })
        }
        activeAssistantMessageIndex.value = assistantMessageIndex

        messages.value[assistantMessageIndex].content = cleanMessage

        for (const update of updates) {
          applyAssistantStateAliases(update)
          Object.assign(characterData, update)
        }

        const hasPendingTag = hasPendingSpecialXmlTag(rawAssistantContent, ['character_update'])
        if (hasPendingTag) {
          specialUpdateState.value = 'processing'
        } else if (updates.length > 0) {
          specialUpdateState.value = 'done'
        }

        if (characterData.starting_emotional_state) {
          characterData.starting_emotional_state = normalizeEmotionalState(characterData.starting_emotional_state)
        }
        normalizeCurrentStartingState()

        if (characterData.ruleset_id && characterData.ruleset_id !== selectedRulesetId.value) {
          selectedRulesetId.value = characterData.ruleset_id
        }

        isThinking.value = false
      },
      (updates: Partial<Character>) => {
        if (!messages.value[assistantMessageIndex]) {
          messages.value.push({
            author: 'Assistant',
            content: '',
            isUser: false,
            timestamp: new Date(),
          })
        }
        activeAssistantMessageIndex.value = assistantMessageIndex

        applyAssistantStateAliases(updates)
        Object.assign(characterData, updates)
        specialUpdateState.value = 'done'

        if (characterData.starting_emotional_state) {
          characterData.starting_emotional_state = normalizeEmotionalState(characterData.starting_emotional_state)
        }
        normalizeCurrentStartingState()

        if (characterData.ruleset_id && characterData.ruleset_id !== selectedRulesetId.value) {
          selectedRulesetId.value = characterData.ruleset_id
        }
      },
      () => {
        if (!messages.value[assistantMessageIndex]?.content && specialUpdateState.value === 'idle') {
          messages.value.splice(assistantMessageIndex, 1)
        }
        if (specialUpdateState.value === 'processing') {
          specialUpdateState.value = 'done'
        }
        isThinking.value = false
      },
      (errorMessage: string) => {
        specialUpdateState.value = 'idle'
        error.value = errorMessage
        isThinking.value = false
      }
    )
  } catch {
    specialUpdateState.value = 'idle'
    error.value = 'Failed to process assistant request.'
    isThinking.value = false
  }
}

const saveEntity = async (saveAsPersona = isPersonaMode.value) => {
  if (!characterData.name.trim()) {
    error.value = 'Name is required.'
    return
  }

  if (!selectedRulesetId.value || selectedRulesetId.value === 'none') {
    error.value = 'Ruleset selection is required.'
    return
  }

  saving.value = true
  error.value = null

  try {
    const payloadCharacter: Character = {
      ...characterData,
      ruleset_id: selectedRulesetId.value,
      starting_drives: { ...characterData.starting_drives },
      starting_skills: { ...characterData.starting_skills },
      starting_emotional_state: {
        global_state: { ...characterData.starting_emotional_state.global_state },
        per_relationship: { ...characterData.starting_emotional_state.per_relationship },
      },
    }

    const payload = {
      data: payloadCharacter,
      is_yaml_text: false,
      is_persona: saveAsPersona,
    }

    if (isEditMode.value) {
      await updateCharacter(editingCharacterId.value, payload)
    } else {
      await createCharacter(payload)
    }

    if (saveAsPersona) {
      await fetchPersonas()
    }

    clearLocalStorage()
    await router.push(saveAsPersona ? '/library/personas' : '/library/characters')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save entity.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-3 flex items-center gap-2">
        <Badge variant="outline">{{ isEditMode ? 'Edit' : 'Create' }}</Badge>
        <Badge :class="isPersonaMode ? 'choice-pill-dialogue' : 'choice-pill-action'">
          {{ isPersonaMode ? 'Persona' : 'Character' }}
        </Badge>
        <Badge variant="outline">{{ autoSaveStatus === 'saved' ? 'Draft Saved' : 'Draft' }}</Badge>
      </div>
      <h1 class="display-heading text-3xl leading-tight sm:text-4xl">{{ pageTitle }}</h1>
      <p class="mt-3 max-w-3xl text-sm text-muted-foreground sm:text-base">{{ pageSubtitle }}</p>
    </section>

    <section v-if="loadingEntity" class="grid gap-4 lg:grid-cols-[1.7fr_1fr]">
      <div class="surface-panel h-96 rounded-2xl" />
      <div class="surface-panel h-96 rounded-2xl" />
    </section>

    <section v-else class="grid gap-4 lg:min-h-[calc(100dvh-8rem)] lg:grid-cols-[1.7fr_1fr]">
      <article class="surface-panel rounded-2xl p-6">
        <div class="mb-4 flex items-center justify-between gap-2">
          <h2 class="text-xl font-semibold">{{ panelTitle }}</h2>
          <div class="flex items-center gap-2">
            <Button size="sm" variant="outline" @click="clearDraft">
              {{ isEditMode ? 'Reset Changes' : 'Reset Draft' }}
            </Button>
          </div>
        </div>

        <div class="grid gap-4 md:grid-cols-2">
          <div class="space-y-1.5">
            <label for="character-name" class="text-sm">Name</label>
            <Input id="character-name" v-model="characterData.name" placeholder="Mara Kade" />
          </div>

          <div class="space-y-1.5">
            <label for="character-tagline" class="text-sm">Tagline</label>
            <Input
              id="character-tagline"
              v-model="characterData.tagline"
              placeholder="Dockside investigator with ledger debt"
            />
          </div>

          <div class="space-y-1.5 md:col-span-2">
            <label for="character-ruleset" class="text-sm">Ruleset</label>

            <Select v-model="selectedRulesetId" :disabled="loadingRulesets || !rulesets.length">
              <SelectTrigger id="character-ruleset" data-testid="character-ruleset-select">
                <SelectValue placeholder="Select a ruleset" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="ruleset in rulesets" :key="ruleset.id" :value="ruleset.id">
                  {{ ruleset.name }}
                </SelectItem>
              </SelectContent>
            </Select>

            <p v-if="loadingRulesets" class="text-xs text-muted-foreground">Loading rulesets...</p>
            <p v-else-if="!rulesets.length" class="text-xs text-muted-foreground">
              No rulesets available. Create one before saving this character.
            </p>
            <p v-if="rulesetError" class="text-xs text-destructive">{{ rulesetError }}</p>
            <Button v-if="!rulesets.length" size="sm" variant="outline" as-child>
              <RouterLink to="/rulesets/new">Create Ruleset</RouterLink>
            </Button>
          </div>

          <div class="space-y-1.5 md:col-span-2">
            <label for="character-backstory" class="text-sm">Backstory</label>
            <Textarea
              id="character-backstory"
              v-model="characterData.backstory"
              rows="5"
              placeholder="Key history, turning points, and unresolved obligations..."
            />
          </div>

          <div class="space-y-1.5">
            <label for="character-personality" class="text-sm">Personality</label>
            <Textarea
              id="character-personality"
              v-model="characterData.personality"
              rows="4"
              placeholder="Measured, guarded, and persistent under pressure"
            />
          </div>

          <div class="space-y-1.5">
            <label for="character-appearance" class="text-sm">Appearance</label>
            <Textarea
              id="character-appearance"
              v-model="characterData.appearance"
              rows="4"
              placeholder="Practical coat, tired eyes, worn transit badge"
            />
          </div>
        </div>

        <section class="mt-6 rounded-xl border border-border/70 bg-background/70 p-4">
          <div class="mb-3 flex items-center justify-between gap-2">
            <h3 class="text-sm font-semibold">Starting Stat Block</h3>
            <Badge v-if="selectedRuleset" variant="outline">{{ selectedRuleset.name }}</Badge>
          </div>

          <p v-if="!selectedRuleset" class="text-xs text-muted-foreground">
            Select a ruleset to initialize drives, skills, and emotional state defaults.
          </p>

          <div v-else class="space-y-4">
            <div>
              <p class="mb-2 text-xs uppercase tracking-wide text-muted-foreground">Drives</p>
              <div class="grid gap-2 md:grid-cols-2">
                <div
                  v-for="drive in selectedRuleset.state_schemas.drives"
                  :key="`drive-${drive.name}`"
                  class="space-y-1"
                >
                  <label :for="`drive-${slugify(drive.name)}`" class="text-xs">{{ drive.name }}</label>
                  <Input
                    :id="`drive-${slugify(drive.name)}`"
                    type="number"
                    :min="drive.range_min"
                    :max="drive.range_max"
                    step="0.1"
                    :model-value="String(characterData.starting_drives[drive.name] ?? drive.default)"
                    @update:model-value="(value) => setDriveValue(drive.name, value)"
                  />
                </div>
              </div>
            </div>

            <div>
              <p class="mb-2 text-xs uppercase tracking-wide text-muted-foreground">Skills</p>
              <div class="grid gap-2 md:grid-cols-2">
                <div
                  v-for="skill in selectedRuleset.state_schemas.skills"
                  :key="`skill-${skill.name}`"
                  class="space-y-1"
                >
                  <label :for="`skill-${slugify(skill.name)}`" class="text-xs">{{ skill.name }}</label>
                  <Input
                    :id="`skill-${slugify(skill.name)}`"
                    type="number"
                    :min="skill.range_min"
                    :max="skill.range_max"
                    step="0.1"
                    :model-value="String(characterData.starting_skills[skill.name] ?? skill.range_min)"
                    @update:model-value="(value) => setSkillValue(skill.name, value)"
                  />
                </div>
              </div>
            </div>

            <div>
              <p class="mb-2 text-xs uppercase tracking-wide text-muted-foreground">Emotional Global State</p>
              <div class="grid gap-2 md:grid-cols-2">
                <div
                  v-for="dim in selectedRuleset.state_schemas.emotional_state.global_dims"
                  :key="`emotion-${dim.name}`"
                  class="space-y-1"
                >
                  <label :for="`emotion-${slugify(dim.name)}`" class="text-xs">{{ dim.name }}</label>
                  <Input
                    :id="`emotion-${slugify(dim.name)}`"
                    type="number"
                    :min="dim.range_min"
                    :max="dim.range_max"
                    step="0.1"
                    :model-value="String(characterData.starting_emotional_state.global_state[dim.name] ?? dim.default)"
                    @update:model-value="(value) => setGlobalEmotionalValue(dim.name, value)"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        <div class="mt-6 grid gap-4 xl:grid-cols-2">
          <section
            v-for="field in listFields"
            :key="field.key"
            class="rounded-xl border border-border/70 bg-background/70 p-3"
          >
            <div class="mb-2 flex items-center justify-between gap-2">
              <h3 class="text-sm font-semibold">{{ field.label }}</h3>
              <Button size="icon" variant="ghost" @click="addListItem(field.key)">
                <Plus class="size-4" />
              </Button>
            </div>

            <div class="space-y-2">
              <div
                v-for="(item, index) in characterData[field.key]"
                :key="`${field.key}-${index}`"
                class="flex gap-2"
              >
                <Input
                  :model-value="item"
                  :placeholder="field.placeholder"
                  @update:model-value="(value) => updateListItem(field.key, index, String(value))"
                />
                <Button size="icon" variant="ghost" @click="removeListItem(field.key, index)">
                  <Trash2 class="size-4" />
                </Button>
              </div>

              <p v-if="!characterData[field.key].length" class="text-xs text-muted-foreground">
                No entries yet.
              </p>
            </div>
          </section>
        </div>

        <p v-if="error" class="mt-4 text-sm text-destructive">{{ error }}</p>

        <div class="mt-5 flex items-center justify-between gap-2">
          <Button variant="ghost" as-child>
            <RouterLink to="/hub">Back to Hub</RouterLink>
          </Button>
          <div class="flex items-center gap-2">
            <Button
              v-if="showCreatePersonaAction"
              data-testid="create-persona-cta"
              variant="outline"
              @click="saveEntity(true)"
            >
              Create Persona
            </Button>
            <Button
              data-testid="save-entity-bottom"
              :disabled="saving || loadingEntity || selectedRulesetId === 'none'"
              @click="saveEntity()"
            >
              <component :is="isPersonaMode ? Users : UserRound" class="mr-2 size-4" />
              {{ saveButtonText }}
            </Button>
          </div>
        </div>
      </article>

      <aside class="surface-panel flex flex-col rounded-2xl p-6 lg:sticky lg:top-24 lg:h-[calc(100dvh-7.5rem)]">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h2 class="text-xl font-semibold">AI Assistant</h2>
          <div class="flex items-center gap-2">
            <Badge variant="outline">
              <Sparkles class="mr-1 size-3.5" />
              {{ settings.aiProcessor }}
            </Badge>
            <ModelSettingsDialog />
          </div>
        </div>

        <ScrollArea class="h-[360px] min-h-0 flex-1 rounded-xl border border-border/70 bg-background/70 px-3 py-2">
          <div v-if="!messages.length" class="space-y-2 text-sm text-muted-foreground">
            <p>Try prompts like:</p>
            <button
              type="button"
              class="w-full rounded-md border border-border/70 px-2 py-1.5 text-left text-xs hover:bg-accent/20"
              @click="userInput = 'Create a weary investigator with hidden debt and dry humor.'"
            >
              Create a weary investigator with hidden debt and dry humor.
            </button>
            <button
              type="button"
              class="w-full rounded-md border border-border/70 px-2 py-1.5 text-left text-xs hover:bg-accent/20"
              @click="userInput = 'Given this ruleset, suggest a balanced starting drive and skill spread.'"
            >
              Given this ruleset, suggest a balanced starting drive and skill spread.
            </button>
          </div>

          <div v-else class="space-y-2">
            <div
              v-for="(message, index) in messages"
              :key="`message-${index}`"
              :class="[
                'rounded-lg px-3 py-2 text-sm leading-relaxed',
                message.isUser
                  ? 'ml-6 bg-primary text-primary-foreground'
                  : 'mr-6 bg-secondary text-secondary-foreground',
              ]"
              v-html="message.isUser
                ? renderPlainTextHtml(message.content)
                : renderAssistantContentWithUpdateState(message.content, index)"
            />
          </div>
          <div ref="chatEndRef" />
        </ScrollArea>

        <form class="mt-3 space-y-2" @submit.prevent="submitAssistantPrompt">
          <Input
            id="assistant-input"
            v-model="userInput"
            :disabled="isThinking"
            placeholder="Ask the assistant to draft or refine details"
          />
          <div class="flex items-center justify-between gap-2">
            <p v-if="isThinking" class="text-xs text-muted-foreground">Assistant is thinking...</p>
            <span v-else class="text-xs text-muted-foreground">Draft sync: {{ autoSaveStatus }}</span>
            <Button type="submit" size="sm" :disabled="isThinking || !userInput.trim()">
              <SendHorizontal class="mr-1 size-3.5" />
              Send
            </Button>
          </div>
        </form>
      </aside>
    </section>
  </main>
</template>
