<script setup lang="ts">
import { Plus, Search, UserRound, Users } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { usePipelineApi } from '@/composables/usePipelineApi'
import type { CharacterSummaryV2 } from '@/types/pipeline'

type FilterMode = 'all' | 'characters' | 'personas'

interface Props {
  initialFilter?: FilterMode
}

const route = useRoute()
const { listCharacters, listPersonas } = usePipelineApi()
const props = withDefaults(defineProps<Props>(), {
  initialFilter: 'all',
})

const loading = ref(true)
const loadError = ref<string | null>(null)
const query = ref('')
const filter = ref<FilterMode>(props.initialFilter)

const characters = ref<CharacterSummaryV2[]>([])
const personas = ref<CharacterSummaryV2[]>([])

const combinedEntries = computed(() => {
  const base = [
    ...characters.value.map((item) => ({ ...item, kind: 'character' as const })),
    ...personas.value.map((item) => ({ ...item, kind: 'persona' as const })),
  ]

  const filteredByKind = base.filter((entry) => {
    if (filter.value === 'characters') {
      return entry.kind === 'character'
    }
    if (filter.value === 'personas') {
      return entry.kind === 'persona'
    }
    return true
  })

  const q = query.value.trim().toLowerCase()
  if (!q) {
    return filteredByKind
  }

  return filteredByKind.filter((entry) => {
    return entry.name.toLowerCase().includes(q) || entry.tagline.toLowerCase().includes(q)
  })
})

const isPersonaLibrary = computed(() => props.initialFilter === 'personas')
const pageTitle = computed(() => (isPersonaLibrary.value ? 'Persona Library' : 'Character Library'))
const pageLabel = computed(() => (isPersonaLibrary.value ? 'Personas' : 'Characters and Personas'))
const pageDescription = computed(() => {
  if (isPersonaLibrary.value) {
    return 'Browse player personas and switch to full library mode when needed.'
  }
  return 'Browse reusable NPCs and personas, then compose scenarios from Hub.'
})

const loadLibrary = async () => {
  loading.value = true
  loadError.value = null

  try {
    const [characterResult, personaResult] = await Promise.all([listCharacters(), listPersonas()])

    characters.value = characterResult
    personas.value = personaResult
  } catch {
    loadError.value = 'Failed to load character library.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (isPersonaLibrary.value) {
    filter.value = 'personas'
  }

  const personaQuery = String(route.query.persona || '').toLowerCase()
  if (personaQuery === 'true' || personaQuery === '1') {
    filter.value = 'personas'
  }

  loadLibrary()
})
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-3 flex items-center gap-2">
        <Badge variant="outline">Library</Badge>
        <Badge class="choice-pill-action">{{ pageLabel }}</Badge>
      </div>
      <h1 class="display-heading text-3xl leading-tight sm:text-4xl">{{ pageTitle }}</h1>
      <p class="mt-3 max-w-3xl text-sm text-muted-foreground sm:text-base">
        {{ pageDescription }}
      </p>
    </section>

    <section class="surface-panel rounded-2xl p-6">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div class="relative w-full lg:max-w-md">
          <Search class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input v-model="query" class="pl-9" placeholder="Search names or taglines" />
        </div>

        <div class="flex flex-wrap gap-2">
          <Button size="sm" :variant="filter === 'all' ? 'default' : 'outline'" @click="filter = 'all'">All</Button>
          <Button
            size="sm"
            :variant="filter === 'characters' ? 'default' : 'outline'"
            @click="filter = 'characters'"
          >
            Characters
          </Button>
          <Button
            size="sm"
            :variant="filter === 'personas' ? 'default' : 'outline'"
            @click="filter = 'personas'"
          >
            Personas
          </Button>
        </div>

        <div class="flex gap-2">
          <Button variant="outline" as-child>
            <RouterLink to="/characters/new">
              <UserRound class="mr-1 size-4" />
              Character
            </RouterLink>
          </Button>
          <Button as-child>
            <RouterLink to="/personas/new">
              <Users class="mr-1 size-4" />
              Persona
            </RouterLink>
          </Button>
        </div>
      </div>

      <p v-if="loadError" class="mt-3 text-sm text-destructive">{{ loadError }}</p>

      <div v-if="loading" class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <div v-for="index in 6" :key="index" class="h-28 rounded-xl border border-border/60 bg-background/60" />
      </div>

      <div v-else-if="combinedEntries.length" class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="entry in combinedEntries"
          :key="`${entry.kind}-${entry.id}`"
          class="rounded-xl border border-border/70 bg-background/70 p-3"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm font-semibold">{{ entry.name }}</p>
            <Badge :class="entry.kind === 'persona' ? 'choice-pill-dialogue' : 'choice-pill-action'">
              {{ entry.kind }}
            </Badge>
          </div>

          <p class="mt-2 line-clamp-2 text-xs text-muted-foreground">{{ entry.tagline }}</p>

          <Button variant="ghost" size="sm" class="mt-2" as-child>
            <RouterLink :to="`/characters/${entry.id}`">Open</RouterLink>
          </Button>
        </article>
      </div>

      <div v-else class="mt-4 rounded-xl border border-dashed border-border/70 bg-background/60 p-5">
        <p class="text-sm text-muted-foreground">No entries match this filter yet.</p>
        <Button class="mt-3" size="sm" as-child>
          <RouterLink to="/characters/new">
            <Plus class="mr-1 size-4" />
            Create Character
          </RouterLink>
        </Button>
      </div>
    </section>
  </main>
</template>
