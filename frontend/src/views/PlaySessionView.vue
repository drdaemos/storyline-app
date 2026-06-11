<script setup lang="ts">
import {
  Clock3,
  Compass,
  Dice5,
  MessageSquareText,
  SendHorizontal,
  SlidersHorizontal,
  Sword,
} from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
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
import { usePromptProcessorOptions } from '@/composables/usePromptProcessorOptions'
import type {
  ContinuationOptionV2,
  SessionDetailsV2,
  SessionCharacterSummaryV2,
  SessionStateResponseV2,
  TurnStreamEventV2,
} from '@/types/pipeline'
import { renderAssistantMessageHtml, renderPlainTextHtml } from '@/utils/assistantMessageFormatting'

interface TurnLogEntry {
  id: string
  input: string
  narration: string
}

const route = useRoute()
const sessionId = computed(() => String(route.params.sessionId || ''))

const { getAuthToken } = useAuth()
const { settings, updateSetting } = useLocalSettings()
const { getSessionCharacters, getSessionDetails, getSessionState } = usePipelineApi()
const { refresh: refreshProcessorOptions, getOptionsWithCurrentValues } = usePromptProcessorOptions()

const loading = ref(true)
const submitting = ref(false)
const loadError = ref<string | null>(null)
const streamStep = ref<string>('')
const userInput = ref('')
const modelSettingsOpen = ref(false)
const turns = ref<TurnLogEntry[]>([])
const options = ref<ContinuationOptionV2[]>([])
const state = ref<SessionStateResponseV2 | null>(null)
const characters = ref<SessionCharacterSummaryV2[]>([])
const modelOptions = computed(() =>
  getOptionsWithCurrentValues([settings.value.aiProcessor, settings.value.backupProcessor])
)

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

const applyTurnHistory = (stateResult: SessionStateResponseV2, detailsResult: SessionDetailsV2) => {
  const narrationHistory = stateResult.narration_history
  const recentUserInputs = detailsResult.last_messages
    .filter((message) => message.role === 'user')
    .map((message) => message.content)
    .slice(-narrationHistory.length)

  const unmatchedCount = Math.max(0, narrationHistory.length - recentUserInputs.length)
  let userInputIndex = recentUserInputs.length - 1
  const mappedTurns: TurnLogEntry[] = []
  for (let index = narrationHistory.length - 1; index >= 0; index -= 1) {
    const mappedInput =
      userInputIndex >= 0
        ? recentUserInputs[userInputIndex--]
        : index === 0 && unmatchedCount > 0
          ? 'Session intro'
          : `Turn ${index}`
    mappedTurns.push({
      id: `history-${index}`,
      input: mappedInput,
      narration: narrationHistory[index],
    })
  }
  turns.value = mappedTurns.reverse()
}

const applySessionSnapshot = (
  stateResult: SessionStateResponseV2,
  characterResult: SessionCharacterSummaryV2[],
  detailsResult: SessionDetailsV2
) => {
  state.value = stateResult
  characters.value = characterResult
  applyTurnHistory(stateResult, detailsResult)
}



const loadSession = async () => {
  loading.value = true
  loadError.value = null

  try {
    const [stateResult, characterResult, detailsResult] = await Promise.all([
      getSessionState(sessionId.value),
      getSessionCharacters(sessionId.value),
      getSessionDetails(sessionId.value),
    ])
    applySessionSnapshot(stateResult, characterResult, detailsResult)
  } catch {
    loadError.value = 'Failed to load play session.'
  } finally {
    loading.value = false
  }
}

const refreshState = async () => {
  try {
    const [stateResult, characterResult, detailsResult] = await Promise.all([
      getSessionState(sessionId.value),
      getSessionCharacters(sessionId.value),
      getSessionDetails(sessionId.value),
    ])
    applySessionSnapshot(stateResult, characterResult, detailsResult)
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

const applyStreamEvent = (event: TurnStreamEventV2, turnIndex: number) => {
  const turnEntry = turns.value[turnIndex]
  if (!turnEntry) {
    return
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

const handleSseLine = (line: string, turnIndex: number) => {
  const trimmedLine = line.trim()
  if (!trimmedLine.startsWith('data:')) {
    return
  }
  const event = parseSseChunk(trimmedLine)
  if (!event) {
    return
  }
  applyStreamEvent(event, turnIndex)
}

const runTurn = async (content: string, inputType?: 'action' | 'relocation' | 'time_skip') => {
  if (!content.trim() || submitting.value) {
    return
  }

  submitting.value = true
  loadError.value = null
  streamStep.value = ''
  options.value = []

  const turnIndex = turns.value.push({
    id: `turn-${Date.now()}`,
    input: content.trim(),
    narration: '',
  }) - 1

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

    const bodyPayload = {
      session_id: sessionId.value,
      user_input: content.trim(),
      processor_type: settings.value.aiProcessor,
      mini_processor_type: settings.value.backupProcessor,
      ...(inputType ? { input_type: inputType } : {}),
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
      if (value) {
        buffer += decoder.decode(value, { stream: true })
      }

      if (done) {
        buffer += decoder.decode()
      }

      const lines = buffer.split(/\r?\n/)
      buffer = lines.pop() || ''

      for (const line of lines) {
        handleSseLine(line, turnIndex)
      }

      if (done) {
        break
      }
    }
    if (buffer.trim()) {
      handleSseLine(buffer, turnIndex)
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

onMounted(async () => {
  await loadSession()
})

watch(modelSettingsOpen, async (isOpen) => {
  if (!isOpen) {
    return
  }
  await refreshProcessorOptions()
})
</script>

<template>
  <main class="mx-auto flex min-h-[calc(100vh-4.5rem)] w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-3 flex items-center gap-2">
        <Badge variant="outline">Play</Badge>
        <Badge class="choice-pill-dialogue">Session {{ sessionId }}</Badge>
      </div>
      <h1 class="display-heading text-3xl leading-tight sm:text-4xl">Turn Feed</h1>
    </section>

    <section v-if="loadError" class="surface-panel rounded-2xl p-5">
      <p class="text-sm text-destructive">{{ loadError }}</p>
      <Button class="mt-3" size="sm" @click="loadSession">Reload Session</Button>
    </section>

    <section v-else-if="loading" class="surface-panel h-80 rounded-2xl" />

    <section v-else class="surface-panel rounded-2xl p-6 lg:flex-1 lg:min-h-0">
      <div class="grid gap-6 lg:h-full lg:min-h-0 lg:grid-cols-[2.1fr_1fr]">
        <div class="lg:flex lg:min-h-0 lg:flex-col">
          <div class="mb-3 flex items-center justify-between gap-2">
            <p class="text-lg font-semibold">Session Turns</p>
            <p class="text-xs text-muted-foreground">{{ state?.turn_counter ?? 0 }} turns</p>
          </div>

          <ScrollArea class="h-[430px] rounded-xl border border-border/70 bg-background/65 px-4 py-3 lg:h-auto lg:min-h-0 lg:flex-1">
            <article
              v-for="(turn, index) in turns"
              :key="turn.id"
              class="mb-5 border-b border-border/50 pb-5 last:mb-0 last:border-b-0 last:pb-0"
            >
              <div class="mb-2 text-[13px] font-semibold uppercase tracking-[0.18em] text-foreground/80">
                Turn {{ index + 1 }}
              </div>

              <p class="text-sm font-medium">
                <span class="mr-1 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">Action:</span>
                <span v-html="renderPlainTextHtml(turn.input)" />
              </p>

              <div class="mt-3">
                <p class="mb-1 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">Narration</p>
                <p
                  class="font-serif text-[1.03rem] leading-relaxed text-foreground/90"
                  v-html="turn.narration ? renderAssistantMessageHtml(turn.narration) : renderPlainTextHtml('...')"
                />
              </div>
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

              <Dialog v-model:open="modelSettingsOpen">
                <DialogTrigger as-child>
                  <Button variant="outline" size="icon" aria-label="Model settings">
                    <SlidersHorizontal class="size-4" />
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Model Settings</DialogTitle>
                    <DialogDescription>
                      Choose Large and Mini processors for upcoming turns.
                    </DialogDescription>
                  </DialogHeader>

                  <div class="space-y-3">
                    <div class="space-y-1.5">
                      <label for="large-model" class="text-sm">Large model</label>
                      <Select
                        :model-value="settings.aiProcessor"
                        @update:model-value="(value) => updateSetting('aiProcessor', String(value))"
                      >
                        <SelectTrigger id="large-model">
                          <SelectValue placeholder="Select model" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem v-for="model in modelOptions" :key="model.id" :value="model.id">
                            {{ model.displayName }}
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div class="space-y-1.5">
                      <label for="mini-model" class="text-sm">Mini model</label>
                      <Select
                        :model-value="settings.backupProcessor"
                        @update:model-value="(value) => updateSetting('backupProcessor', String(value))"
                      >
                        <SelectTrigger id="mini-model">
                          <SelectValue placeholder="Select model" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem v-for="model in modelOptions" :key="`${model.id}-mini`" :value="model.id">
                            {{ model.displayName }}
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <DialogFooter>
                    <DialogClose as-child>
                      <Button variant="outline" type="button">Close</Button>
                    </DialogClose>
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

        <aside class="rounded-xl border border-border/70 bg-background/60 p-4 lg:min-h-0 lg:overflow-auto">
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
