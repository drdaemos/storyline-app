<script setup lang="ts">
import {
  BookOpenText,
  PlusCircle,
  ScrollText,
  UserRound,
  Users,
  WandSparkles,
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { usePipelineApi } from '@/composables/usePipelineApi'
import type { CharacterSummaryV2, RulesetSummaryV2, WorldLoreSummaryV2 } from '@/types/pipeline'

interface HubCollection {
  title: string
  count: number
  detail: string
  route: string
}

const { listCharacters, listPersonas, listRulesets, listScenarios, listWorldLore } =
  usePipelineApi()

const loading = ref(true)
const loadError = ref<string | null>(null)

const characters = ref<CharacterSummaryV2[]>([])
const personas = ref<CharacterSummaryV2[]>([])
const rulesets = ref<RulesetSummaryV2[]>([])
const worldLore = ref<WorldLoreSummaryV2[]>([])
const scenarioCount = ref(0)

const collections = computed<HubCollection[]>(() => {
  return [
    {
      title: 'Characters',
      count: characters.value.length,
      detail: 'Reusable NPC identities and traits',
      route: '/library/characters',
    },
    {
      title: 'Personas',
      count: personas.value.length,
      detail: 'Player-facing protagonist profiles',
      route: '/library/personas',
    },
    {
      title: 'Rulesets',
      count: rulesets.value.length,
      detail: 'Mechanics schema for drives, skills, and state',
      route: '/library/rulesets',
    },
    {
      title: 'World Lore',
      count: worldLore.value.length,
      detail: 'Taggable world entries for locations, factions, and history',
      route: '/library/world-lore',
    },
    {
      title: 'Scenarios',
      count: scenarioCount.value,
      detail: 'Composed playable setups',
      route: '/library/scenarios',
    },
  ]
})

const loadHub = async () => {
  loading.value = true
  loadError.value = null

  const results = await Promise.allSettled([
    listCharacters(),
    listPersonas(),
    listRulesets(),
    listWorldLore(),
    listScenarios(),
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
  if (results[4].status === 'fulfilled') {
    scenarioCount.value = results[4].value.scenarios.length
  }

  if (results.every((item) => item.status === 'rejected')) {
    loadError.value = 'Failed to load hub data.'
  }

  loading.value = false
}

onMounted(loadHub)
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-3 flex items-center gap-2">
        <Badge variant="outline">Hub</Badge>
        <Badge class="choice-pill-relocation">Entity-first creation</Badge>
      </div>
      <h1 class="display-heading text-3xl leading-tight sm:text-4xl">Creation Hub</h1>
      <p class="mt-3 max-w-3xl text-sm text-muted-foreground sm:text-base">
        Build independent entities, manage libraries, then compose scenarios and launch sessions.
      </p>
    </section>

    <section class="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
      <Card class="surface-panel rounded-2xl">
        <CardHeader>
          <CardTitle class="text-xl font-semibold">Create New</CardTitle>
          <CardDescription>Jump straight into entity creation flows.</CardDescription>
        </CardHeader>
        <CardContent class="grid gap-2 sm:grid-cols-2">
          <Button as-child>
            <RouterLink to="/characters/new">
              <UserRound class="mr-2 size-4" />
              Character
            </RouterLink>
          </Button>
          <Button variant="secondary" as-child>
            <RouterLink to="/personas/new">
              <Users class="mr-2 size-4" />
              Persona
            </RouterLink>
          </Button>
          <Button variant="outline" as-child>
            <RouterLink to="/rulesets/new">
              <ScrollText class="mr-2 size-4" />
              Ruleset
            </RouterLink>
          </Button>
          <Button variant="outline" as-child>
            <RouterLink to="/world-lore/new">
              <BookOpenText class="mr-2 size-4" />
              World Lore
            </RouterLink>
          </Button>
        </CardContent>
      </Card>

      <Card class="surface-panel rounded-2xl">
        <CardHeader>
          <CardTitle class="text-xl font-semibold">Compose Scenarios</CardTitle>
          <CardDescription>Assemble characters, personas, rulesets, and lore.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button class="w-full" as-child>
            <RouterLink to="/scenarios/new">
              <WandSparkles class="mr-2 size-4" />
              Open Scenario Composer
            </RouterLink>
          </Button>
          <Button variant="ghost" class="mt-2 w-full" as-child>
            <RouterLink to="/library/scenarios">
              <PlusCircle class="mr-2 size-4" />
              Manage Scenario Library
            </RouterLink>
          </Button>
        </CardContent>
      </Card>
    </section>

    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-4 flex items-center justify-between gap-2">
        <h2 class="text-xl font-semibold">Entity Libraries</h2>
        <Button variant="ghost" size="sm" @click="loadHub">Refresh</Button>
      </div>

      <p v-if="loadError" class="mb-3 text-sm text-destructive">{{ loadError }}</p>

      <div v-if="loading" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <div v-for="index in 5" :key="index" class="h-28 rounded-xl border border-border/60 bg-background/60" />
      </div>

      <div v-else class="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <article
          v-for="item in collections"
          :key="item.title"
          class="rounded-xl border border-border/70 bg-background/70 p-3"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm font-semibold">{{ item.title }}</p>
            <Badge variant="outline">{{ item.count }}</Badge>
          </div>
          <p class="mt-2 text-xs text-muted-foreground">{{ item.detail }}</p>
          <Button variant="ghost" size="sm" class="mt-2" as-child>
            <RouterLink :to="item.route">Open</RouterLink>
          </Button>
        </article>
      </div>
    </section>
  </main>
</template>
