<script setup lang="ts">
import { Clock3, Play, Plus, Search } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { usePipelineApi } from '@/composables/usePipelineApi'
import type { CharacterSummaryV2, RulesetSummaryV2, ScenarioSummaryV2 } from '@/types/pipeline'
import { formatRelativeTime } from '@/utils/formatters'

const router = useRouter()

const { settings } = useLocalSettings()
const { listCharacters, listPersonas, listRulesets, listScenarios, startSession } = usePipelineApi()

const loading = ref(true)
const loadError = ref<string | null>(null)
const startingScenarioId = ref<string | null>(null)
const query = ref('')

const scenarios = ref<ScenarioSummaryV2[]>([])
const characters = ref<CharacterSummaryV2[]>([])
const personas = ref<CharacterSummaryV2[]>([])
const rulesets = ref<RulesetSummaryV2[]>([])

const characterNameById = computed(() => {
  const map = new Map<string, string>()
  for (const character of [...characters.value, ...personas.value]) {
    map.set(character.id, character.name)
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

const filteredScenarios = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) {
    return scenarios.value
  }

  return scenarios.value.filter((scenario) => {
    const rulesetName = rulesetNameById.value.get(scenario.ruleset_id) || ''
    const participantNames = scenario.character_ids
      .map((id) => characterNameById.value.get(id) || id)
      .join(' ')
      .toLowerCase()

    return (
      scenario.summary.toLowerCase().includes(q) ||
      rulesetName.toLowerCase().includes(q) ||
      participantNames.includes(q)
    )
  })
})

const loadScenarios = async () => {
  loading.value = true
  loadError.value = null

  const results = await Promise.allSettled([
    listScenarios(),
    listCharacters(),
    listPersonas(),
    listRulesets(),
  ])

  if (results[0].status === 'fulfilled') {
    scenarios.value = [...results[0].value.scenarios].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    )
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

  if (results[0].status === 'rejected') {
    loadError.value = 'Failed to load scenarios.'
  }

  loading.value = false
}

const startFromScenario = async (scenarioId: string) => {
  startingScenarioId.value = scenarioId
  loadError.value = null

  try {
    const response = await startSession({
      scenario_id: scenarioId,
      processor_type: settings.value.aiProcessor,
      mini_processor_type: settings.value.backupProcessor,
    })
    await router.push(`/play/${response.session_id}`)
  } catch {
    loadError.value = 'Failed to start a session from this scenario.'
  } finally {
    startingScenarioId.value = null
  }
}

const participantNames = (scenario: ScenarioSummaryV2) => {
  return scenario.character_ids.map((id) => characterNameById.value.get(id) || id)
}

onMounted(loadScenarios)
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-3 flex items-center gap-2">
        <Badge variant="outline">Library</Badge>
        <Badge class="choice-pill-timeskip">Scenarios</Badge>
      </div>
      <h1 class="display-heading text-3xl leading-tight sm:text-4xl">Scenario Library</h1>
      <p class="mt-3 max-w-3xl text-sm text-muted-foreground sm:text-base">
        Browse saved scenarios, inspect composition, and start a new session directly from any entry.
      </p>
    </section>

    <section class="surface-panel rounded-2xl p-6">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div class="relative w-full lg:max-w-md">
          <Search class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input v-model="query" class="pl-9" placeholder="Search by scenario, ruleset, or participant" />
        </div>

        <div class="flex gap-2">
          <Button variant="outline" @click="loadScenarios">Refresh</Button>
          <Button as-child>
            <RouterLink to="/scenarios/new">
              <Plus class="mr-1 size-4" />
              New Scenario
            </RouterLink>
          </Button>
        </div>
      </div>

      <p v-if="loadError" class="mt-3 text-sm text-destructive">{{ loadError }}</p>

      <div v-if="loading" class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <div v-for="index in 6" :key="index" class="h-32 rounded-xl border border-border/60 bg-background/60" />
      </div>

      <div v-else-if="filteredScenarios.length" class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="scenario in filteredScenarios"
          :key="scenario.id"
          class="rounded-xl border border-border/70 bg-background/70 p-4"
        >
          <h3 class="m-0">
            <RouterLink
              :to="`/scenarios/${scenario.id}`"
              class="line-clamp-1 text-sm font-semibold underline-offset-4 transition hover:underline focus-visible:underline"
            >
              {{ scenario.summary }}
            </RouterLink>
          </h3>
          <div class="mt-2 flex flex-wrap gap-1">
            <Badge variant="outline">
              {{ rulesetNameById.get(scenario.ruleset_id) || 'Unknown Ruleset' }}
            </Badge>
            <Badge class="choice-pill-dialogue">{{ scenario.character_ids.length }} participants</Badge>
          </div>

          <p class="mt-2 text-xs text-muted-foreground">
            {{ participantNames(scenario).slice(0, 3).join(', ') || 'No participants assigned' }}
          </p>

          <p class="mt-2 inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Clock3 class="size-3.5" />
            Updated {{ formatRelativeTime(scenario.updated_at) }}
          </p>

          <div class="mt-3 flex gap-2">
            <Button
              size="sm"
              class="flex-1"
              :disabled="startingScenarioId === scenario.id"
              @click="startFromScenario(scenario.id)"
            >
              <Play class="mr-1 size-4" />
              Play
            </Button>
          </div>
        </article>
      </div>

      <div v-else class="mt-4 rounded-xl border border-dashed border-border/70 bg-background/60 p-5">
        <p class="text-sm text-muted-foreground">No scenarios found. Create one from Hub or composer.</p>
        <Button class="mt-3" size="sm" as-child>
          <RouterLink to="/scenarios/new">Create Scenario</RouterLink>
        </Button>
      </div>
    </section>
  </main>
</template>
