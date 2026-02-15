<script setup lang="ts">
import {
  ArrowLeft,
  BookOpenText,
  Pencil,
  Play,
  Plus,
  Sparkles,
  Trash2,
  UserRound,
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { usePipelineApi } from '@/composables/usePipelineApi'
import type { CharacterDetailV2, ScenarioSummaryV2, SessionInfoV2 } from '@/types/pipeline'
import { formatRelativeTime } from '@/utils/formatters'

const route = useRoute()
const router = useRouter()
const characterId = computed(() => String(route.params.characterId || ''))

const { settings } = useLocalSettings()
const { deleteScenario, getCharacterDetail, listCharacterSessions, listScenarios, startSession } =
  usePipelineApi()

const loading = ref(true)
const loadError = ref<string | null>(null)
const actionError = ref<string | null>(null)
const startingScenarioId = ref<string | null>(null)
const deletingScenarioId = ref<string | null>(null)

const character = ref<CharacterDetailV2 | null>(null)
const scenarios = ref<ScenarioSummaryV2[]>([])
const characterSessions = ref<SessionInfoV2[]>([])

const characterScenarios = computed(() => {
  return scenarios.value
    .filter((scenario) => scenario.character_ids.includes(characterId.value))
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
})

const recentCharacterSessions = computed(() => {
  return characterSessions.value
    .sort(
      (a, b) => new Date(b.last_message_time).getTime() - new Date(a.last_message_time).getTime()
    )
    .slice(0, 6)
})

const characterTraits = computed(() => {
  const source = character.value
  if (!source) {
    return []
  }

  return [
    ...source.interests.map((value) => ({ label: 'Interest', value })),
    ...source.dislikes.map((value) => ({ label: 'Dislike', value })),
    ...source.desires.map((value) => ({ label: 'Desire', value })),
    ...source.kinks.map((value) => ({ label: 'Preference', value })),
  ]
})

const startingDrives = computed(() => Object.entries(character.value?.starting_drives || {}))
const startingSkills = computed(() => Object.entries(character.value?.starting_skills || {}))
const emotionalStateEntries = computed(() =>
  Object.entries(character.value?.starting_emotional_state || {})
)

const loadCharacter = async () => {
  loading.value = true
  loadError.value = null

  const results = await Promise.allSettled([
    getCharacterDetail(characterId.value),
    listScenarios(),
    listCharacterSessions(characterId.value, { limit: 20 }),
  ])

  if (results[0].status === 'fulfilled') {
    character.value = results[0].value
  } else {
    loadError.value = 'Failed to load character information.'
  }
  if (results[1].status === 'fulfilled') {
    scenarios.value = results[1].value.scenarios
  }
  if (results[2].status === 'fulfilled') {
    characterSessions.value = results[2].value
  }

  loading.value = false
}

const startFromScenario = async (scenarioId: string) => {
  actionError.value = null
  startingScenarioId.value = scenarioId

  try {
    const response = await startSession({
      scenario_id: scenarioId,
      processor_type: settings.value.aiProcessor,
      mini_processor_type: settings.value.backupProcessor,
    })
    await router.push(`/play/${response.session_id}`)
  } catch {
    actionError.value = 'Failed to start session from this scenario.'
  } finally {
    startingScenarioId.value = null
  }
}

const removeScenario = async (scenarioId: string) => {
  const confirmed = window.confirm('Delete this scenario from the library?')
  if (!confirmed) {
    return
  }

  actionError.value = null
  deletingScenarioId.value = scenarioId

  try {
    await deleteScenario(scenarioId)
    scenarios.value = scenarios.value.filter((scenario) => scenario.id !== scenarioId)
  } catch {
    actionError.value = 'Failed to delete scenario.'
  } finally {
    deletingScenarioId.value = null
  }
}

onMounted(loadCharacter)
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-4 flex items-center justify-between gap-2">
        <Button variant="ghost" size="sm" as-child>
          <RouterLink to="/library/characters">
            <ArrowLeft class="mr-1 size-4" />
            Back to Library
          </RouterLink>
        </Button>

        <div class="flex gap-2">
          <Button variant="outline" size="sm" as-child>
            <RouterLink :to="`/scenarios/new?character=${encodeURIComponent(characterId)}`">
              <Plus class="mr-1 size-4" />
              New Scenario
            </RouterLink>
          </Button>
          <Button variant="outline" size="sm" as-child>
            <RouterLink :to="`/characters/${characterId}/edit`">
              <Pencil class="mr-1 size-4" />
              Edit
            </RouterLink>
          </Button>
        </div>
      </div>

      <div class="mb-3 flex items-center gap-2">
        <Badge variant="outline">Character</Badge>
        <Badge :class="character?.is_persona ? 'choice-pill-dialogue' : 'choice-pill-action'">
          {{ character?.is_persona ? 'Persona' : 'Character' }}
        </Badge>
      </div>
      <h1 class="display-heading text-3xl leading-tight sm:text-4xl">
        {{ character?.name || characterId }}
      </h1>
      <p class="mt-2 text-sm text-muted-foreground">{{ character?.tagline || 'No tagline available.' }}</p>
    </section>

    <section v-if="loadError" class="surface-panel rounded-2xl p-5">
      <p class="text-sm text-destructive">{{ loadError }}</p>
      <Button class="mt-3" size="sm" @click="loadCharacter">Try Again</Button>
    </section>

    <section v-else-if="loading" class="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <div class="surface-panel h-80 rounded-2xl" />
      <div class="surface-panel h-80 rounded-2xl" />
    </section>

    <section v-else class="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <Card class="surface-panel rounded-2xl">
        <CardHeader>
          <CardTitle class="text-xl font-semibold">Character Information</CardTitle>
          <CardDescription>Core profile and narrative identity.</CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <div>
            <p class="mb-1 text-xs uppercase tracking-wider text-muted-foreground">Backstory</p>
            <p class="text-sm leading-relaxed">{{ character?.backstory || 'No backstory provided.' }}</p>
          </div>

          <Separator />

          <div class="grid gap-4 sm:grid-cols-2">
            <div>
              <p class="mb-1 text-xs uppercase tracking-wider text-muted-foreground">Personality</p>
              <p class="text-sm leading-relaxed">{{ character?.personality || 'Not specified.' }}</p>
            </div>
            <div>
              <p class="mb-1 text-xs uppercase tracking-wider text-muted-foreground">Appearance</p>
              <p class="text-sm leading-relaxed">{{ character?.appearance || 'Not specified.' }}</p>
            </div>
          </div>

          <div v-if="characterTraits.length">
            <p class="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Traits</p>
            <div class="flex flex-wrap gap-1.5">
              <Badge
                v-for="trait in characterTraits"
                :key="`${trait.label}-${trait.value}`"
                variant="outline"
              >
                {{ trait.label }}: {{ trait.value }}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card class="surface-panel rounded-2xl">
        <CardHeader>
          <CardTitle class="text-xl font-semibold">Starting State</CardTitle>
          <CardDescription>Default simulation stats used as baseline.</CardDescription>
        </CardHeader>
        <CardContent class="space-y-3 text-sm">
          <div>
            <p class="mb-1 text-xs uppercase tracking-wider text-muted-foreground">Drives</p>
            <p v-if="!startingDrives.length" class="text-muted-foreground">No default drives</p>
            <div v-else class="space-y-1">
              <p v-for="[key, value] in startingDrives" :key="key">{{ key }}: {{ value }}</p>
            </div>
          </div>

          <Separator />

          <div>
            <p class="mb-1 text-xs uppercase tracking-wider text-muted-foreground">Skills</p>
            <p v-if="!startingSkills.length" class="text-muted-foreground">No default skills</p>
            <div v-else class="space-y-1">
              <p v-for="[key, value] in startingSkills" :key="key">{{ key }}: {{ value }}</p>
            </div>
          </div>

          <Separator />

          <div>
            <p class="mb-1 text-xs uppercase tracking-wider text-muted-foreground">Emotional State</p>
            <p v-if="!emotionalStateEntries.length" class="text-muted-foreground">
              No emotional defaults
            </p>
            <div v-else class="space-y-1">
              <p v-for="[key, value] in emotionalStateEntries" :key="key">{{ key }}: {{ value }}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </section>

    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-4 flex items-center justify-between gap-2">
        <h2 class="text-xl font-semibold">Scenarios Featuring This Character</h2>
        <Button variant="ghost" size="sm" as-child>
          <RouterLink to="/library/scenarios">
            <BookOpenText class="mr-1 size-4" />
            All Scenarios
          </RouterLink>
        </Button>
      </div>

      <p v-if="actionError" class="mb-3 text-sm text-destructive">{{ actionError }}</p>

      <div v-if="characterScenarios.length" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="scenario in characterScenarios"
          :key="scenario.id"
          class="rounded-xl border border-border/70 bg-background/70 p-4"
        >
          <p class="line-clamp-1 text-sm font-semibold">{{ scenario.summary }}</p>
          <p class="mt-2 inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Sparkles class="size-3.5" />
            {{ scenario.character_ids.length }} participants
          </p>
          <p class="mt-1 text-xs text-muted-foreground">Updated {{ formatRelativeTime(scenario.updated_at) }}</p>

          <div class="mt-3 flex gap-2">
            <Button size="sm" variant="ghost" class="flex-1" as-child>
              <RouterLink :to="`/scenarios/${scenario.id}`">Details</RouterLink>
            </Button>
            <Button
              size="sm"
              class="flex-1"
              :disabled="startingScenarioId === scenario.id"
              @click="startFromScenario(scenario.id)"
            >
              <Play class="mr-1 size-4" />
              Play
            </Button>
            <Button
              size="icon"
              variant="ghost"
              :disabled="deletingScenarioId === scenario.id"
              @click="removeScenario(scenario.id)"
            >
              <Trash2 class="size-4" />
            </Button>
          </div>
        </article>
      </div>

      <div v-else class="rounded-xl border border-dashed border-border/70 bg-background/60 p-5">
        <p class="text-sm text-muted-foreground">No scenarios include this character yet.</p>
      </div>
    </section>

    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-4 flex items-center justify-between gap-2">
        <h2 class="text-xl font-semibold">Recent Sessions</h2>
        <Badge variant="outline">Character scoped</Badge>
      </div>

      <div v-if="recentCharacterSessions.length" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="session in recentCharacterSessions"
          :key="session.session_id"
          class="rounded-xl border border-border/70 bg-background/70 p-4"
        >
          <p class="line-clamp-1 text-sm font-semibold">{{ session.scenario_name || 'Untitled Scenario' }}</p>
          <p class="mt-1 text-xs text-muted-foreground">{{ session.turn_count ?? 0 }} turns</p>
          <p class="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {{ session.last_character_response || 'No narration available.' }}
          </p>
          <Button class="mt-3 w-full" size="sm" as-child>
            <RouterLink :to="`/play/${session.session_id}`">
              <UserRound class="mr-1 size-4" />
              Resume
            </RouterLink>
          </Button>
        </article>
      </div>

      <div v-else class="rounded-xl border border-dashed border-border/70 bg-background/60 p-5">
        <p class="text-sm text-muted-foreground">No sessions yet for this character.</p>
      </div>
    </section>
  </main>
</template>
