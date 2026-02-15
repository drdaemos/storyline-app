<script setup lang="ts">
import { ArrowLeft, Clock3, Play } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { usePipelineApi } from '@/composables/usePipelineApi'
import type {
  CharacterSummaryV2,
  RulesetSummaryV2,
  ScenarioDetailV2,
  WorldLoreSummaryV2,
} from '@/types/pipeline'

const route = useRoute()
const router = useRouter()
const scenarioId = computed(() => String(route.params.scenarioId || ''))

const { settings } = useLocalSettings()
const {
  getScenarioDetail,
  listCharacters,
  listPersonas,
  listRulesets,
  listWorldLore,
  startSession,
} = usePipelineApi()

const loading = ref(true)
const loadError = ref<string | null>(null)
const starting = ref(false)

const scenario = ref<ScenarioDetailV2 | null>(null)
const characters = ref<CharacterSummaryV2[]>([])
const personas = ref<CharacterSummaryV2[]>([])
const rulesets = ref<RulesetSummaryV2[]>([])
const lore = ref<WorldLoreSummaryV2[]>([])

const characterNameById = computed(() => {
  const map = new Map<string, string>()
  for (const character of [...characters.value, ...personas.value]) {
    map.set(character.id, character.name)
  }
  return map
})

const loreNameById = computed(() => {
  const map = new Map<string, string>()
  for (const entry of lore.value) {
    map.set(entry.id, entry.name)
  }
  return map
})

const rulesetNameById = computed(() => {
  const map = new Map<string, string>()
  for (const ruleset of rulesets.value) {
    map.set(ruleset.id, ruleset.name)
  }
  return map
})

const participantNames = computed(() => {
  if (!scenario.value) {
    return []
  }
  return scenario.value.character_ids.map((id) => characterNameById.value.get(id) || id)
})

const personaName = computed(() => {
  if (!scenario.value?.persona_id) {
    return ''
  }
  return characterNameById.value.get(scenario.value.persona_id) || scenario.value.persona_id
})

const selectedLoreNames = computed(() => {
  if (!scenario.value) {
    return []
  }
  return scenario.value.lore_ids.map((id) => loreNameById.value.get(id) || id)
})

const loadScenario = async () => {
  loading.value = true
  loadError.value = null

  const results = await Promise.allSettled([
    getScenarioDetail(scenarioId.value),
    listCharacters(),
    listPersonas(),
    listRulesets(),
    listWorldLore(),
  ])

  if (results[0].status === 'fulfilled') {
    scenario.value = results[0].value
  } else {
    loadError.value = 'Failed to load scenario.'
  }
  if (results[1].status === 'fulfilled') {
    characters.value = results[1].value
  }
  if (results[2].status === 'fulfilled') {
    personas.value = results[2].value
  }
  if (results[3].status === 'fulfilled') {
    rulesets.value = results[3].value
  }
  if (results[4].status === 'fulfilled') {
    lore.value = results[4].value
  }

  loading.value = false
}

const playScenario = async () => {
  starting.value = true
  loadError.value = null

  try {
    const response = await startSession({
      scenario_id: scenarioId.value,
      processor_type: settings.value.aiProcessor,
      mini_processor_type: settings.value.backupProcessor,
    })
    await router.push(`/play/${response.session_id}`)
  } catch {
    loadError.value = 'Failed to start session.'
  } finally {
    starting.value = false
  }
}

onMounted(loadScenario)
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-4 flex items-center justify-between gap-2">
        <Button variant="ghost" size="sm" as-child>
          <RouterLink to="/library/scenarios">
            <ArrowLeft class="mr-1 size-4" />
            Back to Scenarios
          </RouterLink>
        </Button>

        <Button size="sm" :disabled="starting || loading || !!loadError" @click="playScenario">
          <Play class="mr-1 size-4" />
          Start Session
        </Button>
      </div>

      <h1 class="display-heading text-2xl sm:text-3xl">
        {{ scenario?.summary || 'Scenario Detail' }}
      </h1>
      <p class="mt-2 font-mono text-xs text-muted-foreground">{{ scenarioId }}</p>
      <p v-if="scenario?.intro_message" class="mt-3 max-w-4xl font-serif text-base leading-relaxed">
        {{ scenario.intro_message }}
      </p>
    </section>

    <section v-if="loadError" class="surface-panel rounded-2xl p-5">
      <p class="text-sm text-destructive">{{ loadError }}</p>
      <Button class="mt-3" size="sm" @click="loadScenario">Try Again</Button>
    </section>

    <section v-else-if="loading" class="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
      <div class="surface-panel h-56 rounded-2xl" />
      <div class="surface-panel h-56 rounded-2xl" />
    </section>

    <section v-else-if="scenario" class="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
      <Card class="surface-panel rounded-2xl">
        <CardHeader>
          <CardTitle class="text-xl font-semibold">Story Setup</CardTitle>
          <CardDescription>
            Scenario composition with reusable entities and world context.
          </CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="grid gap-2 sm:grid-cols-3">
            <div class="rounded-lg border border-border/60 bg-background/70 px-3 py-2">
              <p class="text-[11px] uppercase tracking-wider text-muted-foreground">Ruleset</p>
              <p class="text-sm font-semibold">
                {{ rulesetNameById.get(scenario.ruleset_id) || 'Unknown Ruleset' }}
              </p>
            </div>
            <div class="rounded-lg border border-border/60 bg-background/70 px-3 py-2">
              <p class="text-[11px] uppercase tracking-wider text-muted-foreground">Participants</p>
              <p class="text-sm font-semibold">{{ participantNames.length }}</p>
            </div>
            <div class="rounded-lg border border-border/60 bg-background/70 px-3 py-2">
              <p class="text-[11px] uppercase tracking-wider text-muted-foreground">Lore Links</p>
              <p class="text-sm font-semibold">{{ scenario.lore_ids.length }}</p>
            </div>
          </div>

          <div class="rounded-xl border border-border/60 bg-background/70 p-3">
            <p class="text-xs uppercase tracking-wider text-muted-foreground">Setting</p>
            <p class="mt-1 text-sm">Location: {{ scenario.location || 'Unknown' }}</p>
            <p class="text-sm">Time: {{ scenario.time_context || 'Unspecified' }}</p>
            <p class="text-sm">Atmosphere: {{ scenario.atmosphere || 'Unspecified' }}</p>
          </div>

          <div v-if="scenario.stakes" class="rounded-xl border border-border/60 bg-background/70 p-3">
            <p class="text-xs uppercase tracking-wider text-muted-foreground">Stakes</p>
            <p class="mt-1 text-sm">{{ scenario.stakes }}</p>
          </div>

          <div v-if="scenario.plot_hooks.length">
            <p class="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Plot Hooks</p>
            <ul class="space-y-1">
              <li
                v-for="hook in scenario.plot_hooks"
                :key="hook"
                class="rounded-lg border border-border/60 bg-background/70 px-3 py-2 text-sm"
              >
                {{ hook }}
              </li>
            </ul>
          </div>

          <div v-if="scenario.potential_directions.length">
            <Separator />
            <p class="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Potential Directions</p>
            <ul class="space-y-1">
              <li
                v-for="direction in scenario.potential_directions"
                :key="direction"
                class="rounded-lg border border-border/60 bg-background/70 px-3 py-2 text-sm"
              >
                {{ direction }}
              </li>
            </ul>
          </div>
        </CardContent>
      </Card>

      <Card class="surface-panel rounded-2xl">
        <CardHeader>
          <CardTitle class="text-xl font-semibold">Participants</CardTitle>
          <CardDescription>Characters, persona, and selected lore references.</CardDescription>
        </CardHeader>
        <CardContent class="space-y-3">
          <div>
            <p class="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Characters</p>
            <div class="flex flex-wrap gap-1.5">
              <Badge v-for="name in participantNames" :key="name" class="choice-pill-action">{{ name }}</Badge>
              <p v-if="!participantNames.length" class="text-xs text-muted-foreground">No characters</p>
            </div>
          </div>

          <Separator />

          <div>
            <p class="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Persona</p>
            <Badge v-if="personaName" class="choice-pill-dialogue">{{ personaName }}</Badge>
            <p v-else class="text-xs text-muted-foreground">None selected</p>
          </div>

          <Separator />

          <div>
            <p class="mb-2 text-xs uppercase tracking-wider text-muted-foreground">World Lore</p>
            <div class="flex flex-wrap gap-1.5">
              <Badge v-for="entry in selectedLoreNames" :key="entry" variant="outline">{{ entry }}</Badge>
              <p v-if="!selectedLoreNames.length" class="text-xs text-muted-foreground">No lore linked</p>
            </div>
          </div>

          <Separator />

          <p class="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Clock3 class="size-3.5" />
            Start session to enter the turn feed.
          </p>
        </CardContent>
      </Card>
    </section>
  </main>
</template>
