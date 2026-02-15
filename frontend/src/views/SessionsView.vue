<script setup lang="ts">
import { Search, Trash2 } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
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
import { usePipelineApi } from '@/composables/usePipelineApi'
import type { SessionInfoV2 } from '@/types/pipeline'
import { formatRelativeTime } from '@/utils/formatters'

type SessionState = 'active' | 'paused' | 'complete' | 'archived'

const { listSessions, deleteSession } = usePipelineApi()

const loading = ref(true)
const loadError = ref<string | null>(null)
const deleting = ref(false)
const query = ref('')
const selectedState = ref<'all' | SessionState>('all')
const sessionToDelete = ref<SessionInfoV2 | null>(null)
const sessions = ref<SessionInfoV2[]>([])

const stateClass: Record<SessionState, string> = {
  active: 'choice-pill-relocation',
  paused: 'choice-pill-timeskip',
  complete: 'choice-pill-dialogue',
  archived: 'choice-pill-action',
}

const stateFilters: Array<{ label: string; value: 'all' | SessionState }> = [
  { label: 'All', value: 'all' },
  { label: 'Active', value: 'active' },
  { label: 'Paused', value: 'paused' },
  { label: 'Complete', value: 'complete' },
  { label: 'Archived', value: 'archived' },
]

const inferSessionState = (session: SessionInfoV2): SessionState => {
  const lastTimestamp = new Date(session.last_message_time).getTime()
  const dayDelta = (Date.now() - lastTimestamp) / (1000 * 60 * 60 * 24)
  const turns = session.turn_count ?? 0

  if (dayDelta > 21) {
    return 'archived'
  }
  if (dayDelta > 7 && turns > 10) {
    return 'complete'
  }
  if (turns > 0) {
    return 'active'
  }
  return 'paused'
}

const sortedSessions = computed(() => {
  return [...sessions.value].sort((a, b) => {
    return new Date(b.last_message_time).getTime() - new Date(a.last_message_time).getTime()
  })
})

const filteredSessions = computed(() => {
  return sortedSessions.value.filter((session) => {
    const state = inferSessionState(session)
    const matchesState = selectedState.value === 'all' || selectedState.value === state

    const q = query.value.trim().toLowerCase()
    const name = (session.scenario_name || session.character_name).toLowerCase()
    const responseText = (session.last_character_response || '').toLowerCase()
    const matchesQuery = !q || name.includes(q) || responseText.includes(q)

    return matchesState && matchesQuery
  })
})

const loadSessions = async () => {
  loading.value = true
  loadError.value = null

  try {
    sessions.value = await listSessions()
  } catch {
    loadError.value = 'Failed to load sessions.'
  } finally {
    loading.value = false
  }
}

const confirmDelete = (session: SessionInfoV2) => {
  sessionToDelete.value = session
}

const handleDelete = async () => {
  if (!sessionToDelete.value) {
    return
  }

  deleting.value = true
  try {
    await deleteSession(sessionToDelete.value.session_id)
    sessions.value = sessions.value.filter(
      (item) => item.session_id !== sessionToDelete.value?.session_id
    )
    sessionToDelete.value = null
  } catch {
    loadError.value = 'Failed to delete session.'
  } finally {
    deleting.value = false
  }
}

onMounted(loadSessions)
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-3 flex items-center gap-2">
        <Badge variant="outline">Sessions</Badge>
        <Badge class="choice-pill-timeskip">Play entrypoint</Badge>
      </div>
      <h1 class="display-heading text-3xl leading-tight sm:text-4xl">Session Library</h1>
      <p class="mt-3 max-w-3xl text-sm text-muted-foreground sm:text-base">
        Search, filter, and resume story sessions. Play is session-scoped rather than top navigation.
      </p>
    </section>

    <section class="surface-panel rounded-2xl p-6">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div class="relative w-full lg:max-w-md">
          <Search class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            v-model="query"
            class="pl-9"
            placeholder="Search by scenario name or recent narration"
          />
        </div>

        <div class="flex flex-wrap gap-2">
          <Button
            v-for="filter in stateFilters"
            :key="filter.value"
            size="sm"
            :variant="selectedState === filter.value ? 'default' : 'outline'"
            @click="selectedState = filter.value"
          >
            {{ filter.label }}
          </Button>
        </div>
      </div>

      <p v-if="loadError" class="mt-3 text-sm text-destructive">{{ loadError }}</p>

      <div v-if="loading" class="mt-4 grid gap-3 sm:grid-cols-2">
        <div v-for="index in 6" :key="index" class="h-32 rounded-xl border border-border/60 bg-background/60" />
      </div>

      <div v-else-if="filteredSessions.length" class="mt-4 grid gap-3 sm:grid-cols-2">
        <article
          v-for="session in filteredSessions"
          :key="session.session_id"
          class="rounded-xl border border-border/70 bg-background/70 p-4"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="line-clamp-1 text-sm font-semibold">
              {{ session.scenario_name || 'Untitled Scenario' }}
            </p>
            <Badge :class="stateClass[inferSessionState(session)]">{{ inferSessionState(session) }}</Badge>
          </div>

          <p class="mt-1 text-xs text-muted-foreground">
            {{ session.turn_count ?? 0 }} turns · {{ formatRelativeTime(session.last_message_time) }}
          </p>

          <p class="mt-2 line-clamp-2 text-xs text-muted-foreground">
            {{ session.last_character_response || 'No narration available.' }}
          </p>

          <div class="mt-3 flex gap-2">
            <Button size="sm" class="flex-1" as-child>
              <RouterLink :to="`/play/${session.session_id}`">Resume</RouterLink>
            </Button>
            <Button size="sm" variant="ghost" as-child>
              <RouterLink :to="`/sessions/${session.session_id}`">Details</RouterLink>
            </Button>

            <Dialog>
              <DialogTrigger as-child>
                <Button size="icon" variant="ghost" @click="confirmDelete(session)">
                  <Trash2 class="size-4" />
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Delete Session?</DialogTitle>
                  <DialogDescription>
                    This removes the selected session and cannot be undone.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button variant="outline">Cancel</Button>
                  <Button :disabled="deleting" @click="handleDelete">Delete</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </article>
      </div>

      <div v-else class="mt-4 rounded-xl border border-dashed border-border/70 bg-background/60 p-5">
        <p class="text-sm text-muted-foreground">No sessions match this filter yet.</p>
      </div>
    </section>
  </main>
</template>
