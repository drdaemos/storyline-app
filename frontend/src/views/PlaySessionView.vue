<script setup lang="ts">
import {
  Clock3,
  Compass,
  Dice5,
  MessageSquareText,
  SendHorizontal,
  SlidersHorizontal,
  Sword,
  UserRound,
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAuth } from '@/composables/useAuth'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { usePipelineApi } from '@/composables/usePipelineApi'
import type {
  ContinuationOptionV2,
  SessionCharacterSummaryV2,
  SessionStateResponseV2,
  TurnStreamEventV2,
} from '@/types/pipeline'

interface TurnLogEntry {
  id: string
  input: string
  narration: string
}

const route = useRoute()
const sessionId = computed(() => String(route.params.sessionId || ''))

const { getAuthToken } = useAuth()
const { settings, updateSetting } = useLocalSettings()
const { getSessionCharacters, getSessionState } = usePipelineApi()

const loading = ref(true)
const submitting = ref(false)
const loadError = ref<string | null>(null)
const streamStep = ref<string>('')
const userInput = ref('')
const turns = ref<TurnLogEntry[]>([])
const options = ref<ContinuationOptionV2[]>([])
const state = ref<SessionStateResponseV2 | null>(null)
const characters = ref<SessionCharacterSummaryV2[]>([])

const modelOptions = ['google-flash', 'gpt-5.2', 'claude-sonnet', 'deepseek-v32']

const mapChoiceClass = (type: ContinuationOptionV2['type']) => {
  if (type === 'dialogue') {
    return 'choice-pill-dialogue'
  }
  if (type === 'relocation') {
    return 'choice-pill-relocation'
  }
  if (type === 'time_skip') {
    return 'choice-pill-timeskip'
  }
  return 'choice-pill-action'
}

const mapChoiceIcon = (type: ContinuationOptionV2['type']) => {
  if (type === 'dialogue') {
    return MessageSquareText
  }
  if (type === 'relocation') {
    return Compass
  }
  if (type === 'time_skip') {
    return Clock3
  }
  return Sword
}

const toTurnInputType = (
  type: ContinuationOptionV2['type']
): 'action' | 'relocation' | 'time_skip' | undefined => {
  if (type === 'relocation') {
    return 'relocation'
  }
  if (type === 'time_skip') {
    return 'time_skip'
  }
  if (type === 'action') {
    return 'action'
  }
  return undefined
}

const loadSession = async () => {
  loading.value = true
  loadError.value = null

  try {
    const [stateResult, characterResult] = await Promise.all([
      getSessionState(sessionId.value),
      getSessionCharacters(sessionId.value),
    ])

    state.value = stateResult
    characters.value = characterResult

    turns.value = stateResult.narration_history.map((narration, index) => ({
      id: `history-${index}`,
      input: index === 0 ? 'Session intro' : `Turn ${index}`,
      narration,
    }))
  } catch {
    loadError.value = 'Failed to load play session.'
  } finally {
    loading.value = false
  }
}

const refreshState = async () => {
  try {
    const [stateResult, characterResult] = await Promise.all([
      getSessionState(sessionId.value),
      getSessionCharacters(sessionId.value),
    ])
    state.value = stateResult
    characters.value = characterResult
  } catch {
    // Keep play flow running even if state refresh fails.
  }
}

const parseSseChunk = (rawEvent: string): TurnStreamEventV2 | null => {
  const lines = rawEvent
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('data:'))

  if (!lines.length) {
    return null
  }

  const payload = lines.map((line) => line.replace(/^data:\s*/, '')).join('')

  try {
    return JSON.parse(payload) as TurnStreamEventV2
  } catch {
    return null
  }
}

const runTurn = async (content: string, inputType?: 'action' | 'relocation' | 'time_skip') => {
  if (!content.trim() || submitting.value) {
    return
  }

  submitting.value = true
  loadError.value = null
  streamStep.value = ''
  options.value = []

  const turnEntry: TurnLogEntry = {
    id: `turn-${Date.now()}`,
    input: content.trim(),
    narration: '',
  }
  turns.value.push(turnEntry)

  try {
    const token = await getAuthToken()
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      'Cache-Control': 'no-cache',
    }

    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    const bodyPayload: {
      session_id: string
      user_input: string
      processor_type: string
      mini_processor_type: string
      input_type?: 'action' | 'relocation' | 'time_skip'
    } = {
      session_id: sessionId.value,
      user_input: content.trim(),
      processor_type: settings.value.aiProcessor,
      mini_processor_type: settings.value.backupProcessor,
    }

    if (inputType) {
      bodyPayload.input_type = inputType
    }

    const response = await fetch('/api/turn', {
      method: 'POST',
      headers,
      body: JSON.stringify(bodyPayload),
    })

    if (!response.ok || !response.body) {
      throw new Error(`Failed to execute turn: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() || ''

      for (const chunk of chunks) {
        const event = parseSseChunk(chunk)
        if (!event) {
          continue
        }

        if (event.type === 'status' && event.step) {
          streamStep.value = event.step
        }

        if (event.type === 'narration_chunk' && typeof event.text === 'string') {
          turnEntry.narration += event.text
        }

        if (event.type === 'narration_complete' && typeof event.text === 'string') {
          turnEntry.narration = event.text
        }

        if ((event.type === 'continuation_options' || event.type === 'options') && event.options) {
          options.value = event.options
        }

        if (event.type === 'error') {
          loadError.value = event.message || 'Turn execution failed.'
        }
      }
    }

    await refreshState()
    userInput.value = ''
  } catch {
    loadError.value = 'Failed to execute turn.'
  } finally {
    submitting.value = false
    streamStep.value = ''
  }
}

const submitInput = async () => {
  await runTurn(userInput.value, 'action')
}

const useOption = async (option: ContinuationOptionV2) => {
  await runTurn(option.description, toTurnInputType(option.type))
}

onMounted(loadSession)
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-3 flex items-center gap-2">
        <Badge variant="outline">Play</Badge>
        <Badge class="choice-pill-dialogue">Session {{ sessionId }}</Badge>
      </div>
      <h1 class="display-heading text-3xl leading-tight sm:text-4xl">Turn Feed</h1>
      <p class="mt-3 max-w-3xl text-sm text-muted-foreground sm:text-base">
        Visual-novel + MUD style play flow with typed continuation options and command input.
      </p>
    </section>

    <section v-if="loadError" class="surface-panel rounded-2xl p-5">
      <p class="text-sm text-destructive">{{ loadError }}</p>
      <Button class="mt-3" size="sm" @click="loadSession">Reload Session</Button>
    </section>

    <section v-else-if="loading" class="surface-panel h-80 rounded-2xl" />

    <section v-else class="surface-panel rounded-2xl p-6">
      <div class="grid gap-6 lg:grid-cols-[2.1fr_1fr]">
        <div>
          <div class="mb-3 flex items-center justify-between gap-2">
            <p class="text-lg font-semibold">Session Turns</p>
            <p class="text-xs text-muted-foreground">{{ state?.turn_counter ?? 0 }} turns</p>
          </div>

          <ScrollArea class="h-[430px] rounded-xl border border-border/70 bg-background/65 px-4 py-3">
            <article
              v-for="turn in turns"
              :key="turn.id"
              class="mb-5 border-b border-border/50 pb-5 last:mb-0 last:border-b-0 last:pb-0"
            >
              <div class="mb-2 flex items-center justify-between text-xs uppercase tracking-wider text-muted-foreground">
                <span class="inline-flex items-center gap-1.5">
                  <UserRound class="size-3.5" />
                  You
                </span>
              </div>

              <p class="mb-2 text-sm font-medium">{{ turn.input }}</p>
              <p class="mb-2 font-serif text-[1.03rem] leading-relaxed text-foreground/90">
                {{ turn.narration || '...' }}
              </p>
            </article>
          </ScrollArea>

          <div class="mt-4 rounded-xl border border-border/70 bg-background/60 p-3">
            <p class="text-xs uppercase tracking-wider text-muted-foreground">Command Dock</p>
            <div class="mt-2 flex gap-2">
              <Input
                id="play-input"
                v-model="userInput"
                name="playInput"
                placeholder="Type your action"
                :disabled="submitting"
                @keydown.enter.prevent="submitInput"
              />
              <Button :disabled="submitting || !userInput.trim()" @click="submitInput">
                <SendHorizontal class="mr-1 size-4" />
                Act
              </Button>

              <Dialog>
                <DialogTrigger as-child>
                  <Button variant="outline" size="icon" aria-label="Model settings">
                    <SlidersHorizontal class="size-4" />
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Model Settings</DialogTitle>
                    <DialogDescription>Choose primary and fallback model for turns.</DialogDescription>
                  </DialogHeader>

                  <div class="space-y-3">
                    <div class="space-y-1.5">
                      <label for="primary-model" class="text-sm">Primary model</label>
                      <Select
                        :model-value="settings.aiProcessor"
                        @update:model-value="(value) => updateSetting('aiProcessor', String(value))"
                      >
                        <SelectTrigger id="primary-model">
                          <SelectValue placeholder="Select model" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem v-for="model in modelOptions" :key="model" :value="model">
                            {{ model }}
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div class="space-y-1.5">
                      <label for="fallback-model" class="text-sm">Fallback model</label>
                      <Select
                        :model-value="settings.backupProcessor"
                        @update:model-value="(value) => updateSetting('backupProcessor', String(value))"
                      >
                        <SelectTrigger id="fallback-model">
                          <SelectValue placeholder="Select model" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem v-for="model in modelOptions" :key="`${model}-fallback`" :value="model">
                            {{ model }}
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <DialogFooter>
                    <Button variant="outline">Close</Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>

            <p v-if="streamStep" class="mt-2 text-xs text-muted-foreground">Processing: {{ streamStep }}</p>

            <div v-if="options.length" class="mt-3 flex flex-wrap gap-2">
              <button
                v-for="option in options"
                :key="`${option.type}-${option.description}`"
                type="button"
                :class="['choice-option', mapChoiceClass(option.type)]"
                :disabled="submitting"
                @click="useOption(option)"
              >
                <component :is="mapChoiceIcon(option.type)" class="size-3.5" />
                <span>{{ option.description }}</span>
              </button>
            </div>
          </div>
        </div>

        <aside class="rounded-xl border border-border/70 bg-background/60 p-4">
          <h2 class="mb-3 text-base font-semibold">State Rail</h2>
          <div class="space-y-3 text-sm">
            <div>
              <p class="text-xs uppercase tracking-wider text-muted-foreground">Location</p>
              <p>{{ state?.world_state.location || 'Unknown' }}</p>
            </div>
            <Separator />
            <div>
              <p class="text-xs uppercase tracking-wider text-muted-foreground">Time</p>
              <p>{{ state?.world_state.time || 'Unknown' }}</p>
            </div>
            <Separator />
            <div>
              <p class="text-xs uppercase tracking-wider text-muted-foreground">Participants</p>
              <div class="mt-1 space-y-1.5">
                <div
                  v-for="character in characters"
                  :key="character.character_id"
                  class="rounded-md border border-border/60 bg-background/70 px-2 py-1.5"
                >
                  <div class="flex items-center justify-between gap-2">
                    <p class="text-xs font-medium">{{ character.character_name }}</p>
                    <Badge :class="character.is_present ? 'choice-pill-relocation' : 'choice-pill-action'">
                      {{ character.is_present ? 'Present' : 'Offscreen' }}
                    </Badge>
                  </div>
                </div>
              </div>
            </div>
            <Separator />
            <p class="inline-flex items-center gap-1.5 rounded-md border border-border/60 bg-background/80 px-2.5 py-1 text-xs text-muted-foreground">
              <Dice5 class="size-3.5" />
              Dice and checks resolve in the turn pipeline.
            </p>
          </div>
        </aside>
      </div>
    </section>
  </main>
</template>
