<script setup lang="ts">
import {
  BookOpenText,
  Plus,
  Search,
  SendHorizontal,
  Sparkles,
  Trash2,
  WandSparkles,
  X,
} from 'lucide-vue-next'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
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
import type { ChatMessage, PartialScenario, Scenario, ScenarioCreationRequest } from '@/types'
import type { CharacterSummaryV2, RulesetSummaryV2, WorldLoreSummaryV2 } from '@/types/pipeline'

interface ScenarioFormState {
  summary: string
  intro_message: string
  narrative_category: string
  location: string
  time_context: string
  atmosphere: string
  stakes: string
  plot_hooks: string[]
  potential_directions: string[]
}

const route = useRoute()
const router = useRouter()

const { settings } = useLocalSettings()
const { streamScenarioCreation, saveScenario, startSessionWithScenario } = useApi()
const { listCharacters, listPersonas, listRulesets, listWorldLore } = usePipelineApi()

const loading = ref(true)
const loadError = ref<string | null>(null)
const error = ref<string | null>(null)
const saving = ref(false)
const isThinking = ref(false)

const userInput = ref('')
const messages = ref<ChatMessage[]>([])
const chatEndRef = ref<HTMLElement | null>(null)

const characters = ref<CharacterSummaryV2[]>([])
const personas = ref<CharacterSummaryV2[]>([])
const rulesets = ref<RulesetSummaryV2[]>([])
const worldLore = ref<WorldLoreSummaryV2[]>([])

const selectedCharacterIds = ref<string[]>([])
const characterSearch = ref('')
const selectedPersonaId = ref('none')
const selectedRulesetId = ref('none')
const selectedLoreIds = ref<string[]>([])

const form = reactive<ScenarioFormState>({
  summary: '',
  intro_message: '',
  narrative_category: '',
  location: '',
  time_context: '',
  atmosphere: '',
  stakes: '',
  plot_hooks: [],
  potential_directions: [],
})

const { autoSaveStatus, loadFromLocalStorage, clearLocalStorage } = useCharacterCreationAutoSave(
  form,
  messages,
  'scenario-modern-creation'
)

const availablePersonas = computed(() => {
  return personas.value.map((persona) => ({
    id: persona.id,
    name: persona.name,
    tagline: persona.tagline,
    personality: '',
  }))
})

const selectedPrimaryCharacterId = computed(() => selectedCharacterIds.value[0] || '')
const selectedCharacterNames = computed(() => {
  const map = new Map(characters.value.map((character) => [character.id, character.name]))
  return selectedCharacterIds.value.map((id) => map.get(id) || id)
})
const selectedCharacterEntries = computed(() => {
  const map = new Map(characters.value.map((character) => [character.id, character]))
  return selectedCharacterIds.value
    .map((id) => map.get(id))
    .filter((value): value is CharacterSummaryV2 => !!value)
})
const availableCharacters = computed(() => {
  const query = characterSearch.value.trim().toLowerCase()

  return characters.value.filter((character) => {
    if (selectedCharacterIds.value.includes(character.id)) {
      return false
    }

    if (!query) {
      return true
    }

    return (
      character.name.toLowerCase().includes(query) ||
      character.tagline.toLowerCase().includes(query)
    )
  })
})

const canSave = computed(() => {
  return (
    selectedCharacterIds.value.length > 0 &&
    selectedRulesetId.value !== 'none' &&
    !!form.summary.trim() &&
    !!form.intro_message.trim()
  )
})

const addListItem = (key: 'plot_hooks' | 'potential_directions') => {
  const list = form[key]
  const limit = key === 'plot_hooks' ? 6 : 4

  if (list.length < limit) {
    list.push('')
  }
}

const removeListItem = (key: 'plot_hooks' | 'potential_directions', index: number) => {
  form[key].splice(index, 1)
}

const toggleLoreSelection = (loreId: string) => {
  if (selectedLoreIds.value.includes(loreId)) {
    selectedLoreIds.value = selectedLoreIds.value.filter((item) => item !== loreId)
    return
  }

  selectedLoreIds.value = [...selectedLoreIds.value, loreId]
}

const toggleCharacterSelection = (characterId: string) => {
  if (selectedCharacterIds.value.includes(characterId)) {
    selectedCharacterIds.value = selectedCharacterIds.value.filter((item) => item !== characterId)
    return
  }

  selectedCharacterIds.value = [...selectedCharacterIds.value, characterId]
}

const addCharacter = (characterId: string) => {
  if (selectedCharacterIds.value.includes(characterId)) {
    return
  }
  selectedCharacterIds.value = [...selectedCharacterIds.value, characterId]
  characterSearch.value = ''
}

const resetDraft = () => {
  Object.assign(form, {
    summary: '',
    intro_message: '',
    narrative_category: '',
    location: '',
    time_context: '',
    atmosphere: '',
    stakes: '',
    plot_hooks: [],
    potential_directions: [],
  })

  selectedRulesetId.value = rulesets.value.length ? rulesets.value[0].id : 'none'
  selectedLoreIds.value = []
  selectedCharacterIds.value = characters.value.length ? [characters.value[0].id] : []
  characterSearch.value = ''
  messages.value = []
  userInput.value = ''
  error.value = null
  clearLocalStorage()
}

const extractScenarioUpdates = (
  rawAssistantContent: string
): { cleanMessage: string; updates: PartialScenario[] } => {
  const updates: PartialScenario[] = []

  const withoutCompleteBlocks = rawAssistantContent.replace(
    /<scenario_update>\s*([\s\S]*?)\s*<\/scenario_update>/g,
    (_, jsonPayload: string) => {
      try {
        updates.push(JSON.parse(jsonPayload) as PartialScenario)
      } catch {
        // Ignore malformed scenario update payloads.
      }

      return ''
    }
  )

  const pendingOpenTagIndex = withoutCompleteBlocks.indexOf('<scenario_update>')
  const cleanMessage =
    pendingOpenTagIndex >= 0
      ? withoutCompleteBlocks.slice(0, pendingOpenTagIndex).trim()
      : withoutCompleteBlocks.trim()

  return { cleanMessage, updates }
}

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

const loadContext = async () => {
  loading.value = true
  loadError.value = null

  const results = await Promise.allSettled([
    listCharacters(),
    listPersonas(),
    listRulesets(),
    listWorldLore(),
  ])

  if (results[0].status === 'fulfilled') {
    characters.value = results[0].value
  }
  if (results[1].status === 'fulfilled') {
    personas.value = results[1].value
  }
  if (results[2].status === 'fulfilled') {
    rulesets.value = results[2].value
  }
  if (results[3].status === 'fulfilled') {
    worldLore.value = results[3].value
  }

  if (results.every((entry) => entry.status === 'rejected')) {
    loadError.value = 'Failed to load scenario creation context.'
  }

  if (!selectedCharacterIds.value.length && characters.value.length) {
    const fromQuery = String(route.query.character || '').trim()
    const inList = characters.value.find((item) => item.id === fromQuery)
    selectedCharacterIds.value = [inList?.id || characters.value[0].id]
  }

  if (selectedRulesetId.value === 'none' && rulesets.value.length) {
    selectedRulesetId.value = rulesets.value[0].id
  }

  loading.value = false
}

onMounted(async () => {
  loadFromLocalStorage()
  await loadContext()
})

const submitAssistantPrompt = async () => {
  if (!userInput.value.trim() || isThinking.value) {
    return
  }

  if (!selectedCharacterIds.value.length) {
    error.value = 'Select at least one character first.'
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

  const assistantMessageIndex = messages.value.length
  let rawAssistantContent = ''

  try {
    const payload: ScenarioCreationRequest = {
      user_message: prompt,
      current_scenario: {
        ...form,
        character_id: selectedPrimaryCharacterId.value,
        character_ids: [...selectedCharacterIds.value],
        persona_id: selectedPersonaId.value !== 'none' ? selectedPersonaId.value : '',
        ruleset_id: selectedRulesetId.value !== 'none' ? selectedRulesetId.value : '',
        lore_ids: [...selectedLoreIds.value],
      },
      character_name: selectedPrimaryCharacterId.value,
      persona_id: selectedPersonaId.value !== 'none' ? selectedPersonaId.value : null,
      available_personas: availablePersonas.value,
      conversation_history: messages.value.map((message) => ({
        author: message.author,
        content: message.content,
        is_user: message.isUser,
      })),
      processor_type: settings.value.aiProcessor,
      backup_processor_type: settings.value.backupProcessor,
    }

    await streamScenarioCreation(
      payload,
      (messageChunk: string) => {
        rawAssistantContent += messageChunk
        const { cleanMessage, updates } = extractScenarioUpdates(rawAssistantContent)

        if (!messages.value[assistantMessageIndex]) {
          messages.value.push({
            author: 'Assistant',
            content: '',
            isUser: false,
            timestamp: new Date(),
          })
        }

        messages.value[assistantMessageIndex].content = cleanMessage

        for (const update of updates) {
          Object.assign(form, {
            ...update,
            plot_hooks: Array.isArray(update.plot_hooks) ? update.plot_hooks : form.plot_hooks,
            potential_directions: Array.isArray(update.potential_directions)
              ? update.potential_directions
              : form.potential_directions,
          })
        }

        isThinking.value = false
      },
      (updates: PartialScenario) => {
        Object.assign(form, {
          ...updates,
          plot_hooks: Array.isArray(updates.plot_hooks) ? updates.plot_hooks : form.plot_hooks,
          potential_directions: Array.isArray(updates.potential_directions)
            ? updates.potential_directions
            : form.potential_directions,
        })
      },
      () => {
        if (!messages.value[assistantMessageIndex]?.content) {
          messages.value.splice(assistantMessageIndex, 1)
        }
        isThinking.value = false
      },
      (errorMessage: string) => {
        error.value = errorMessage
        isThinking.value = false
      }
    )
  } catch {
    error.value = 'Failed to process assistant request.'
    isThinking.value = false
  }
}

const buildScenarioPayload = (): Scenario => {
  return {
    summary: form.summary.trim(),
    intro_message: form.intro_message.trim(),
    narrative_category: form.narrative_category.trim(),
    character_id: selectedPrimaryCharacterId.value,
    character_ids: [...selectedCharacterIds.value],
    persona_id: selectedPersonaId.value !== 'none' ? selectedPersonaId.value : undefined,
    ruleset_id: selectedRulesetId.value !== 'none' ? selectedRulesetId.value : '',
    lore_ids: [...selectedLoreIds.value],
    location: form.location.trim(),
    time_context: form.time_context.trim(),
    atmosphere: form.atmosphere.trim(),
    plot_hooks: form.plot_hooks.filter((item) => item.trim().length > 0),
    stakes: form.stakes.trim(),
    character_goals: {},
    potential_directions: form.potential_directions.filter((item) => item.trim().length > 0),
  }
}

const saveScenarioDraft = async () => {
  if (!canSave.value) {
    error.value = 'At least one character, a ruleset, summary, and intro are required.'
    return null
  }

  saving.value = true
  error.value = null

  try {
    const response = await saveScenario({ scenario: buildScenarioPayload() })
    return response.scenario_id
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save scenario.'
    return null
  } finally {
    saving.value = false
  }
}

const saveDraftOnly = async () => {
  const scenarioId = await saveScenarioDraft()
  if (scenarioId) {
    await router.push('/hub')
  }
}

const saveAndStart = async () => {
  const scenarioId = await saveScenarioDraft()
  if (!scenarioId) {
    return
  }

  saving.value = true
  try {
    const response = await startSessionWithScenario({
      character_name: selectedPrimaryCharacterId.value,
      scenario_id: scenarioId,
      persona_id: selectedPersonaId.value !== 'none' ? selectedPersonaId.value : null,
      processor_type: settings.value.aiProcessor,
      backup_processor_type: settings.value.backupProcessor,
    })

    clearLocalStorage()
    await router.push(`/play/${response.session_id}`)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to start session.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-3 flex items-center gap-2">
        <Badge variant="outline">Create</Badge>
        <Badge class="choice-pill-relocation">Scenario</Badge>
        <Badge variant="outline">{{ autoSaveStatus === 'saved' ? 'Draft Saved' : 'Draft' }}</Badge>
      </div>
      <h1 class="display-heading text-3xl leading-tight sm:text-4xl">Create Scenario</h1>
      <p class="mt-3 max-w-3xl text-sm text-muted-foreground sm:text-base">
        Two-panel scenario composer with AI-assisted drafting, entity selection, and immediate session launch.
      </p>
    </section>

    <section v-if="loadError" class="surface-panel rounded-2xl p-5">
      <p class="text-sm text-destructive">{{ loadError }}</p>
      <Button class="mt-3" size="sm" @click="loadContext">Retry</Button>
    </section>

    <section v-else class="grid gap-4 lg:grid-cols-[1.7fr_1fr]">
      <article class="surface-panel rounded-2xl p-6">
        <div class="mb-4 flex items-center justify-between gap-2">
          <h2 class="text-xl font-semibold">Scenario Surface</h2>
          <div class="flex items-center gap-2">
            <Button size="sm" variant="outline" :disabled="saving" @click="resetDraft">Reset Draft</Button>
            <Button data-testid="save-draft" size="sm" :disabled="saving || loading" @click="saveDraftOnly">
              Save Draft
            </Button>
            <Button data-testid="save-start" size="sm" :disabled="saving || loading" @click="saveAndStart">
              <WandSparkles class="mr-1 size-4" />
              Save & Start
            </Button>
          </div>
        </div>

        <div v-if="loading" class="grid gap-3 md:grid-cols-3">
          <div v-for="index in 6" :key="index" class="h-16 rounded-lg border border-border/60 bg-background/60" />
        </div>

        <div v-else class="grid gap-4 md:grid-cols-3">
          <div class="space-y-1.5 md:col-span-3">
            <div class="flex items-center justify-between gap-2">
              <label class="text-sm">Characters</label>
              <Badge variant="outline">{{ selectedCharacterIds.length }} selected</Badge>
            </div>

            <div class="rounded-xl border border-border/70 bg-background/70 p-3">
              <div class="mb-2 flex flex-wrap gap-1.5">
                <Badge
                  v-for="character in selectedCharacterEntries"
                  :key="character.id"
                  class="choice-pill-action inline-flex items-center gap-1"
                  :data-testid="`selected-character-${character.id}`"
                >
                  <span>{{ character.name }}</span>
                  <button
                    type="button"
                    class="rounded-full p-0.5 hover:bg-black/10"
                    aria-label="Remove character"
                    @click="toggleCharacterSelection(character.id)"
                  >
                    <X class="size-3" />
                  </button>
                </Badge>
              </div>

              <div class="relative">
                <Search
                  class="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
                />
                <Input
                  id="scenario-character-search"
                  v-model="characterSearch"
                  class="pl-8"
                  placeholder="Search and add characters"
                  data-testid="character-search-input"
                />
              </div>

              <div class="mt-2 max-h-36 space-y-1 overflow-y-auto">
                <button
                  v-for="character in availableCharacters"
                  :key="character.id"
                  type="button"
                  class="flex w-full items-center justify-between rounded-md border border-border/60 px-2.5 py-1.5 text-left text-xs hover:bg-accent/20"
                  :data-testid="`character-option-${character.id}`"
                  @click="addCharacter(character.id)"
                >
                  <span class="font-medium">{{ character.name }}</span>
                  <span class="text-muted-foreground">{{ character.tagline }}</span>
                </button>

                <p v-if="!availableCharacters.length" class="text-xs text-muted-foreground">
                  No matching characters.
                </p>
              </div>
            </div>

            <p class="text-xs text-muted-foreground">
              Selected: {{ selectedCharacterNames.join(', ') || 'None' }}. Click a tag to remove.
            </p>
          </div>

          <div class="space-y-1.5">
            <label for="scenario-persona" class="text-sm">Persona</label>
            <Select v-model="selectedPersonaId">
              <SelectTrigger id="scenario-persona">
                <SelectValue placeholder="Optional persona" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">None</SelectItem>
                <SelectItem v-for="persona in personas" :key="persona.id" :value="persona.id">
                  {{ persona.name }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div class="space-y-1.5">
            <label for="scenario-ruleset" class="text-sm">Ruleset</label>
            <Select v-model="selectedRulesetId">
              <SelectTrigger id="scenario-ruleset">
                <SelectValue placeholder="Optional ruleset" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">None</SelectItem>
                <SelectItem v-for="ruleset in rulesets" :key="ruleset.id" :value="ruleset.id">
                  {{ ruleset.name }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div class="space-y-1.5 md:col-span-2">
            <label for="scenario-summary" class="text-sm">Summary</label>
            <Input
              id="scenario-summary"
              v-model="form.summary"
              placeholder="Nightfall Ledger: union archive under pressure"
            />
          </div>

          <div class="space-y-1.5">
            <label for="scenario-category" class="text-sm">Category</label>
            <Input
              id="scenario-category"
              v-model="form.narrative_category"
              placeholder="Noir Investigation"
            />
          </div>

          <div class="space-y-1.5 md:col-span-3">
            <label for="scenario-intro" class="text-sm">Opening Scene</label>
            <Textarea
              id="scenario-intro"
              v-model="form.intro_message"
              rows="5"
              placeholder="Write the opening beat and immediate tension..."
            />
          </div>

          <div class="space-y-1.5">
            <label for="scenario-location" class="text-sm">Location</label>
            <Input id="scenario-location" v-model="form.location" placeholder="Dock District Archive" />
          </div>

          <div class="space-y-1.5">
            <label for="scenario-time" class="text-sm">Time Context</label>
            <Input id="scenario-time" v-model="form.time_context" placeholder="03:00, heavy rain" />
          </div>

          <div class="space-y-1.5">
            <label for="scenario-stakes" class="text-sm">Stakes</label>
            <Input
              id="scenario-stakes"
              v-model="form.stakes"
              placeholder="Expose ledger corruption before dawn"
            />
          </div>

          <div class="space-y-1.5 md:col-span-3">
            <label for="scenario-atmosphere" class="text-sm">Atmosphere</label>
            <Textarea
              id="scenario-atmosphere"
              v-model="form.atmosphere"
              rows="3"
              placeholder="Muted neon, wet concrete, exhausted voices"
            />
          </div>

          <section class="rounded-xl border border-border/70 bg-background/70 p-3 md:col-span-3">
            <div class="mb-2 flex items-center justify-between gap-2">
              <h3 class="text-sm font-semibold">World Lore Attachments</h3>
              <Badge variant="outline">{{ selectedLoreIds.length }} selected</Badge>
            </div>

            <div class="flex flex-wrap gap-2">
              <button
                v-for="entry in worldLore"
                :key="entry.id"
                type="button"
                :class="[
                  'rounded-full border px-2.5 py-1 text-xs transition-colors',
                  selectedLoreIds.includes(entry.id)
                    ? 'choice-pill-relocation'
                    : 'border-border/70 bg-background/70 text-muted-foreground hover:bg-accent/20',
                ]"
                @click="toggleLoreSelection(entry.id)"
              >
                <BookOpenText class="mr-1 inline size-3.5" />
                {{ entry.name }}
              </button>
            </div>
          </section>

          <section class="rounded-xl border border-border/70 bg-background/70 p-3">
            <div class="mb-2 flex items-center justify-between gap-2">
              <h3 class="text-sm font-semibold">Plot Hooks</h3>
              <Button size="icon" variant="ghost" @click="addListItem('plot_hooks')">
                <Plus class="size-4" />
              </Button>
            </div>

            <div class="space-y-2">
              <div v-for="(_, index) in form.plot_hooks" :key="`hook-${index}`" class="flex gap-2">
                <Input
                  v-model="form.plot_hooks[index]"
                  :placeholder="`Hook ${index + 1}`"
                />
                <Button size="icon" variant="ghost" @click="removeListItem('plot_hooks', index)">
                  <Trash2 class="size-4" />
                </Button>
              </div>
              <p v-if="!form.plot_hooks.length" class="text-xs text-muted-foreground">No hooks yet.</p>
            </div>
          </section>

          <section class="rounded-xl border border-border/70 bg-background/70 p-3">
            <div class="mb-2 flex items-center justify-between gap-2">
              <h3 class="text-sm font-semibold">Potential Directions</h3>
              <Button size="icon" variant="ghost" @click="addListItem('potential_directions')">
                <Plus class="size-4" />
              </Button>
            </div>

            <div class="space-y-2">
              <div v-for="(_, index) in form.potential_directions" :key="`direction-${index}`" class="flex gap-2">
                <Input
                  v-model="form.potential_directions[index]"
                  :placeholder="`Direction ${index + 1}`"
                />
                <Button size="icon" variant="ghost" @click="removeListItem('potential_directions', index)">
                  <Trash2 class="size-4" />
                </Button>
              </div>
              <p v-if="!form.potential_directions.length" class="text-xs text-muted-foreground">No directions yet.</p>
            </div>
          </section>
        </div>

        <p v-if="error" class="mt-4 text-sm text-destructive">{{ error }}</p>

        <div class="mt-5 flex items-center justify-between gap-2">
          <Button variant="ghost" as-child>
            <RouterLink to="/hub">Back to Hub</RouterLink>
          </Button>
          <Button :disabled="saving || !canSave" @click="saveAndStart">
            <WandSparkles class="mr-1 size-4" />
            Save & Start Session
          </Button>
        </div>
      </article>

      <aside class="surface-panel rounded-2xl p-6 lg:sticky lg:top-24 lg:h-fit">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h2 class="text-xl font-semibold">AI Assistant</h2>
          <Badge variant="outline">
            <Sparkles class="mr-1 size-3.5" />
            {{ settings.aiProcessor }}
          </Badge>
        </div>

        <p class="mb-3 text-sm text-muted-foreground">
          Ask for hooks, stronger stakes, or alternate openings. Updates flow directly into this form.
        </p>

        <ScrollArea class="h-[360px] rounded-xl border border-border/70 bg-background/70 px-3 py-2">
          <div v-if="!messages.length" class="space-y-2 text-sm text-muted-foreground">
            <p>Try prompts like:</p>
            <button
              type="button"
              class="w-full rounded-md border border-border/70 px-2 py-1.5 text-left text-xs hover:bg-accent/20"
              @click="userInput = 'Draft a tense rail-district opening with political pressure and rain-soaked atmosphere.'"
            >
              Draft a tense rail-district opening with political pressure and rain-soaked atmosphere.
            </button>
            <button
              type="button"
              class="w-full rounded-md border border-border/70 px-2 py-1.5 text-left text-xs hover:bg-accent/20"
              @click="userInput = 'Give me three branching directions with one time skip path.'"
            >
              Give me three branching directions with one time skip path.
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
            >
              {{ message.content }}
            </div>
          </div>

          <div ref="chatEndRef" />
        </ScrollArea>

        <form class="mt-3 space-y-2" @submit.prevent="submitAssistantPrompt">
          <Input
            id="scenario-assistant-input"
            v-model="userInput"
            :disabled="isThinking"
            placeholder="Ask assistant to refine tone, hooks, and branches"
          />
          <div class="flex items-center justify-between gap-2">
            <p v-if="isThinking" class="text-xs text-muted-foreground">Assistant is thinking…</p>
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
