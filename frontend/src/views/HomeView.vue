<script setup lang="ts">
import { ArrowRight, Clock3, Compass, FolderKanban, Play, Sparkles } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { usePipelineApi } from '@/composables/usePipelineApi'
import type {
  CharacterSummaryV2,
  RulesetSummaryV2,
  SessionInfoV2,
  WorldLoreSummaryV2,
} from '@/types/pipeline'
import { formatRelativeTime } from '@/utils/formatters'

interface AssetBlock {
  title: string
  count: number
  route: string
  highlights: string[]
}

interface StartOption {
  title: string
  description: string
  route: string
}

const { listCharacters, listPersonas, listRulesets, listScenarios, listSessions, listWorldLore } =
  usePipelineApi()

const loading = ref(true)
const loadError = ref<string | null>(null)

const sessions = ref<SessionInfoV2[]>([])
const characters = ref<CharacterSummaryV2[]>([])
const personas = ref<CharacterSummaryV2[]>([])
const rulesets = ref<RulesetSummaryV2[]>([])
const worldLore = ref<WorldLoreSummaryV2[]>([])
const scenarioCount = ref(0)

const startOptions: StartOption[] = [
  {
    title: 'From Scenarios',
    description: 'Pick a saved scenario and launch a new session.',
    route: '/library/scenarios',
  },
  {
    title: 'Resume Session',
    description: 'Jump back into one of your recent story sessions.',
    route: '/sessions',
  },
  {
    title: 'Browse World Lore',
    description: 'Review tags and world context before starting.',
    route: '/library/world-lore',
  },
]

const sortedSessions = computed(() => {
  return [...sessions.value].sort((a, b) => {
    return new Date(b.last_message_time).getTime() - new Date(a.last_message_time).getTime()
  })
})

const recentSessions = computed(() => sortedSessions.value.slice(0, 4))

const assetBlocks = computed<AssetBlock[]>(() => {
  const scenarioHighlights = ['Scenarios assembled from rulesets, lore, and personas.']
  return [
    {
      title: 'Characters',
      count: characters.value.length,
      route: '/library/characters',
      highlights: characters.value.slice(0, 3).map((item) => item.name),
    },
    {
      title: 'Personas',
      count: personas.value.length,
      route: '/library/personas',
      highlights: personas.value.slice(0, 3).map((item) => item.name),
    },
    {
      title: 'Rulesets',
      count: rulesets.value.length,
      route: '/library/rulesets',
      highlights: rulesets.value.slice(0, 3).map((item) => item.name),
    },
    {
      title: 'World Lore',
      count: worldLore.value.length,
      route: '/library/world-lore',
      highlights: worldLore.value.slice(0, 3).map((item) => item.name),
    },
    {
      title: 'Scenarios',
      count: scenarioCount.value,
      route: '/library/scenarios',
      highlights: scenarioHighlights,
    },
  ]
})

const loadDashboard = async () => {
  loading.value = true
  loadError.value = null

  const results = await Promise.allSettled([
    listSessions(),
    listCharacters(),
    listPersonas(),
    listRulesets(),
    listWorldLore(),
    listScenarios(),
  ])

  if (results[0].status === 'fulfilled') {
    sessions.value = results[0].value
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
    worldLore.value = results[4].value
  }
  if (results[5].status === 'fulfilled') {
    scenarioCount.value = results[5].value.scenarios.length
  }

  if (results[0].status === 'rejected') {
    loadError.value = 'Failed to load sessions. Please refresh.'
  }

  loading.value = false
}

onMounted(loadDashboard)
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-3 flex items-center gap-2">
        <Badge variant="outline">Home</Badge>
        <Badge class="choice-pill-dialogue">Session-driven</Badge>
      </div>
      <h1 class="display-heading text-3xl leading-tight sm:text-4xl">Story Dashboard</h1>
      <p class="mt-3 max-w-3xl text-sm text-muted-foreground sm:text-base">
        Continue active sessions, start new runs from Hub, and monitor your core narrative entities.
      </p>
    </section>

    <section v-if="loadError" class="surface-panel rounded-2xl p-5">
      <p class="text-sm text-destructive">{{ loadError }}</p>
      <Button class="mt-3" size="sm" @click="loadDashboard">Try Again</Button>
    </section>

    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-4 flex items-center justify-between gap-2">
        <h2 class="text-xl font-semibold">Continue Playing</h2>
        <Button variant="ghost" size="sm" as-child>
          <RouterLink to="/sessions">
            All Sessions
            <ArrowRight class="ml-1 size-4" />
          </RouterLink>
        </Button>
      </div>

      <div v-if="loading" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div v-for="index in 4" :key="index" class="h-32 rounded-xl border border-border/60 bg-background/60" />
      </div>

      <div v-else-if="recentSessions.length" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article
          v-for="session in recentSessions"
          :key="session.session_id"
          class="rounded-xl border border-border/70 bg-background/70 p-3"
        >
          <p class="line-clamp-1 text-sm font-semibold">{{ session.scenario_name || 'Untitled Scenario' }}</p>
          <p class="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {{ session.last_character_response || 'No narration yet.' }}
          </p>
          <div class="mt-3 flex items-center justify-between text-[11px] text-muted-foreground">
            <span class="inline-flex items-center gap-1">
              <Clock3 class="size-3" />
              {{ formatRelativeTime(session.last_message_time) }}
            </span>
            <span>{{ session.turn_count ?? 0 }} turns</span>
          </div>
          <div class="mt-3 flex gap-2">
            <Button size="sm" class="flex-1" as-child>
              <RouterLink :to="`/play/${session.session_id}`">
                <Play class="mr-1 size-3.5" />
                Resume
              </RouterLink>
            </Button>
            <Button size="sm" variant="ghost" as-child>
              <RouterLink :to="`/sessions/${session.session_id}`">Details</RouterLink>
            </Button>
          </div>
        </article>
      </div>

      <div v-else class="rounded-xl border border-dashed border-border/70 bg-background/60 p-5">
        <p class="text-sm text-muted-foreground">No sessions yet. Start from Hub and launch your first scenario.</p>
        <Button class="mt-3" size="sm" as-child>
          <RouterLink to="/hub">
            <Compass class="mr-1 size-4" />
            Open Hub
          </RouterLink>
        </Button>
      </div>
    </section>

    <section class="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
      <Card class="surface-panel rounded-2xl">
        <CardHeader>
          <CardTitle class="text-xl font-semibold">Start New</CardTitle>
          <CardDescription>Paths into the new pipeline without top-level Play navigation.</CardDescription>
        </CardHeader>
        <CardContent class="grid gap-2 sm:grid-cols-3">
          <article
            v-for="option in startOptions"
            :key="option.title"
            class="rounded-xl border border-border/65 bg-background/70 px-3 py-3"
          >
            <p class="text-sm font-medium">{{ option.title }}</p>
            <p class="mt-1 text-xs text-muted-foreground">{{ option.description }}</p>
            <Button variant="ghost" size="sm" class="mt-2" as-child>
              <RouterLink :to="option.route">Open</RouterLink>
            </Button>
          </article>
        </CardContent>
      </Card>

      <Card class="surface-panel rounded-2xl">
        <CardHeader>
          <CardTitle class="text-xl font-semibold">Creation Hub</CardTitle>
          <CardDescription>Compose worlds from independent entities and launch sessions.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button class="w-full" as-child>
            <RouterLink to="/hub">
              <FolderKanban class="mr-2 size-4" />
              Open Hub
            </RouterLink>
          </Button>
          <Button variant="ghost" class="mt-2 w-full" as-child>
            <RouterLink to="/library/scenarios">
              <Sparkles class="mr-2 size-4" />
              Browse Scenarios
            </RouterLink>
          </Button>
        </CardContent>
      </Card>
    </section>

    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-4 flex items-center justify-between gap-2">
        <h2 class="text-xl font-semibold">Recent Assets</h2>
      </div>

      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <article
          v-for="block in assetBlocks"
          :key="block.title"
          class="rounded-xl border border-border/70 bg-background/70 p-3"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm font-semibold">{{ block.title }}</p>
            <Badge variant="outline">{{ block.count }}</Badge>
          </div>
          <ul class="mt-2 space-y-1">
            <li
              v-for="line in block.highlights"
              :key="line"
              class="line-clamp-1 text-xs text-muted-foreground"
            >
              {{ line }}
            </li>
          </ul>
          <Button variant="ghost" size="sm" class="mt-2" as-child>
            <RouterLink :to="block.route">Open</RouterLink>
          </Button>
        </article>
      </div>
    </section>
  </main>
</template>
