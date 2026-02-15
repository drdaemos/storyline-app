<script setup lang="ts">
import { Sparkles, SendHorizontal, Plus, Trash2, UserRound, Users } from 'lucide-vue-next'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import { useApi } from '@/composables/useApi'
import { useCharacterCreationAutoSave } from '@/composables/useCharacterCreationAutoSave'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { usePipelineApi } from '@/composables/usePipelineApi'
import { usePersonas } from '@/composables/usePersonas'
import type { Character, CharacterCreationRequest, ChatMessage } from '@/types'
import type { CharacterDetailV2 } from '@/types/pipeline'

interface Props {
  personaMode?: boolean
}

interface RelationshipItem {
  name: string
  description: string
}

type ListFieldKey = 'interests' | 'dislikes' | 'desires' | 'kinks' | 'key_locations'

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
const { getCharacterDetail } = usePipelineApi()
const { settings } = useLocalSettings()
const { fetchPersonas } = usePersonas()

const userInput = ref('')
const isThinking = ref(false)
const loadingEntity = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const messages = ref<ChatMessage[]>([])
const chatEndRef = ref<HTMLElement | null>(null)
const relationshipsList = ref<RelationshipItem[]>([])
const originalSnapshot = ref<Partial<Character> | null>(null)

const createEmptyCharacterData = (): Partial<Character> => ({
  name: '',
  tagline: '',
  backstory: '',
  personality: '',
  appearance: '',
  setting_description: '',
  relationships: {},
  key_locations: [],
  interests: [],
  dislikes: [],
  desires: [],
  kinks: [],
})

const characterData = reactive<Partial<Character>>(createEmptyCharacterData())

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
  { key: 'key_locations', label: 'Key Locations', placeholder: 'Rail District Office' },
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

const ensureList = (key: ListFieldKey): string[] => {
  const existing = characterData[key]
  if (!Array.isArray(existing)) {
    characterData[key] = []
    return characterData[key] as string[]
  }
  return existing
}

const updateListItem = (key: ListFieldKey, index: number, value: string) => {
  const list = ensureList(key)
  list[index] = value
}

const addListItem = (key: ListFieldKey) => {
  const list = ensureList(key)
  if (list.length < 10) {
    list.push('')
  }
}

const removeListItem = (key: ListFieldKey, index: number) => {
  const list = ensureList(key)
  list.splice(index, 1)
}

const addRelationship = () => {
  if (relationshipsList.value.length < 10) {
    relationshipsList.value.push({ name: '', description: '' })
  }
}

const removeRelationship = (index: number) => {
  relationshipsList.value.splice(index, 1)
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

      return ''
    }
  )

  const pendingOpenTagIndex = withoutCompleteBlocks.indexOf('<character_update>')
  const cleanMessage =
    pendingOpenTagIndex >= 0
      ? withoutCompleteBlocks.slice(0, pendingOpenTagIndex).trim()
      : withoutCompleteBlocks.trim()

  return { cleanMessage, updates }
}

const applyCharacterState = (nextCharacter: Partial<Character>) => {
  Object.assign(characterData, createEmptyCharacterData(), nextCharacter)
}

const toEditableCharacter = (detail: CharacterDetailV2): Partial<Character> => ({
  name: detail.name,
  tagline: detail.tagline,
  backstory: detail.backstory,
  personality: detail.personality,
  appearance: detail.appearance,
  setting_description: '',
  relationships: {},
  key_locations: [],
  interests: [...detail.interests],
  dislikes: [...detail.dislikes],
  desires: [...detail.desires],
  kinks: [...detail.kinks],
})

const clearDraft = () => {
  if (isEditMode.value && originalSnapshot.value) {
    applyCharacterState(originalSnapshot.value)
  } else {
    applyCharacterState(createEmptyCharacterData())
  }

  messages.value = []
  relationshipsList.value = []
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
  } catch {
    error.value = 'Failed to load character for editing.'
  } finally {
    loadingEntity.value = false
  }
}

const syncRelationshipsToCharacter = () => {
  const nextRelationships: Record<string, string> = {}

  for (const relationship of relationshipsList.value) {
    const key = relationship.name.trim()
    const value = relationship.description.trim()
    if (key && value) {
      nextRelationships[key] = value
    }
  }

  characterData.relationships = nextRelationships
}

watch(relationshipsList, syncRelationshipsToCharacter, { deep: true })

watch(
  () => characterData.relationships,
  (relationships) => {
    if (!relationships || typeof relationships !== 'object') {
      relationshipsList.value = []
      return
    }

    const nextList = Object.entries(relationships).map(([name, description]) => ({
      name,
      description: String(description),
    }))

    if (JSON.stringify(nextList) !== JSON.stringify(relationshipsList.value)) {
      relationshipsList.value = nextList
    }
  },
  { deep: true }
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
    return
  }

  loadFromLocalStorage()
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

  const assistantMessageIndex = messages.value.length
  let rawAssistantContent = ''

  try {
    const payload: CharacterCreationRequest = {
      user_message: prompt,
      current_character: characterData,
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

        messages.value[assistantMessageIndex].content = cleanMessage

        for (const update of updates) {
          Object.assign(characterData, update)
        }

        isThinking.value = false
      },
      (updates: Partial<Character>) => {
        Object.assign(characterData, updates)
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

const saveEntity = async () => {
  if (!characterData.name?.trim()) {
    error.value = 'Name is required.'
    return
  }

  saving.value = true
  error.value = null

  try {
    const payload = {
      data: characterData as Character,
      is_yaml_text: false,
      is_persona: isPersonaMode.value,
    }

    if (isEditMode.value) {
      await updateCharacter(editingCharacterId.value, payload)
    } else {
      await createCharacter(payload)
    }

    if (isPersonaMode.value) {
      await fetchPersonas()
    }

    clearLocalStorage()
    await router.push(isPersonaMode.value ? '/library/personas' : '/library/characters')
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

    <section v-else class="grid gap-4 lg:grid-cols-[1.7fr_1fr]">
      <article class="surface-panel rounded-2xl p-6">
        <div class="mb-4 flex items-center justify-between gap-2">
          <h2 class="text-xl font-semibold">{{ panelTitle }}</h2>
          <div class="flex items-center gap-2">
            <Button size="sm" variant="outline" @click="clearDraft">
              {{ isEditMode ? 'Reset Changes' : 'Reset Draft' }}
            </Button>
            <Button
              data-testid="save-entity-top"
              size="sm"
              :disabled="saving || loadingEntity"
              @click="saveEntity"
            >
              {{ saveButtonText }}
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

          <div class="space-y-1.5 md:col-span-2">
            <label for="character-setting" class="text-sm">Setting Context</label>
            <Textarea
              id="character-setting"
              v-model="characterData.setting_description"
              rows="3"
              placeholder="City, district, and baseline social pressure around this character"
            />
          </div>
        </div>

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
                v-for="(item, index) in (characterData[field.key] as string[] || [])"
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

              <p
                v-if="!(characterData[field.key] as string[] || []).length"
                class="text-xs text-muted-foreground"
              >
                No entries yet.
              </p>
            </div>
          </section>
        </div>

        <section class="mt-4 rounded-xl border border-border/70 bg-background/70 p-3">
          <div class="mb-2 flex items-center justify-between gap-2">
            <h3 class="text-sm font-semibold">Relationships</h3>
            <Button size="sm" variant="ghost" @click="addRelationship">
              <Plus class="mr-1 size-4" />
              Add
            </Button>
          </div>

          <div class="space-y-2">
            <div
              v-for="(relationship, index) in relationshipsList"
              :key="`relationship-${index}`"
              class="grid gap-2 md:grid-cols-[1fr_1.4fr_auto]"
            >
              <Input v-model="relationship.name" placeholder="Faction leader" />
              <Input v-model="relationship.description" placeholder="Owes her a favor" />
              <Button size="icon" variant="ghost" @click="removeRelationship(index)">
                <Trash2 class="size-4" />
              </Button>
            </div>

            <p v-if="!relationshipsList.length" class="text-xs text-muted-foreground">
              Define named relationships to anchor social context.
            </p>
          </div>
        </section>

        <p v-if="error" class="mt-4 text-sm text-destructive">{{ error }}</p>

        <div class="mt-5 flex items-center justify-between gap-2">
          <Button variant="ghost" as-child>
            <RouterLink to="/hub">Back to Hub</RouterLink>
          </Button>
          <Button data-testid="save-entity-bottom" :disabled="saving || loadingEntity" @click="saveEntity">
            <component :is="isPersonaMode ? Users : UserRound" class="mr-2 size-4" />
            {{ saveButtonText }}
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
          Describe traits and motivations naturally. The assistant updates the sheet in place.
        </p>

        <ScrollArea class="h-[360px] rounded-xl border border-border/70 bg-background/70 px-3 py-2">
          <div v-if="!messages.length" class="space-y-2 text-sm text-muted-foreground">
            <p>Try prompts like:</p>
            <button
              type="button"
              class="w-full rounded-md border border-border/70 px-2 py-1.5 text-left text-xs hover:bg-accent/20"
              @click="userInput = 'Create a weary investigator with a hidden family debt and dry humor.'"
            >
              Create a weary investigator with a hidden family debt and dry humor.
            </button>
            <button
              type="button"
              class="w-full rounded-md border border-border/70 px-2 py-1.5 text-left text-xs hover:bg-accent/20"
              @click="userInput = 'Give this character three concrete desires and two conflicting loyalties.'"
            >
              Give this character three concrete desires and two conflicting loyalties.
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
            id="assistant-input"
            v-model="userInput"
            :disabled="isThinking"
            placeholder="Ask the assistant to draft or refine details"
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
