<script setup lang="ts">
import { ArrowLeft, Play } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { usePipelineApi } from '@/composables/usePipelineApi'
import type {
  SessionCharacterSummaryV2,
  SessionDetailsV2,
  SessionStateResponseV2,
} from '@/types/pipeline'
import { formatRelativeTime } from '@/utils/formatters'

const route = useRoute()
const sessionId = computed(() => String(route.params.sessionId || ''))

const { getSessionCharacters, getSessionDetails, getSessionState } = usePipelineApi()

const loading = ref(true)
const loadError = ref<string | null>(null)
const details = ref<SessionDetailsV2 | null>(null)
const state = ref<SessionStateResponseV2 | null>(null)
const characters = ref<SessionCharacterSummaryV2[]>([])

const loadSession = async () => {
  loading.value = true
  loadError.value = null

  try {
    const [detailResult, stateResult, charactersResult] = await Promise.all([
      getSessionDetails(sessionId.value),
      getSessionState(sessionId.value),
      getSessionCharacters(sessionId.value),
    ])

    details.value = detailResult
    state.value = stateResult
    characters.value = charactersResult
  } catch {
    loadError.value = 'Failed to load session details.'
  } finally {
    loading.value = false
  }
}

onMounted(loadSession)
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-4 flex items-center justify-between gap-2">
        <Button variant="ghost" size="sm" as-child>
          <RouterLink to="/sessions">
            <ArrowLeft class="mr-1 size-4" />
            Back to Sessions
          </RouterLink>
        </Button>

        <Button size="sm" as-child>
          <RouterLink :to="`/play/${sessionId}`">
            <Play class="mr-1 size-4" />
            Resume Play
          </RouterLink>
        </Button>
      </div>

      <h1 class="display-heading text-2xl sm:text-3xl">Session Detail</h1>
      <p class="mt-2 font-mono text-xs text-muted-foreground">{{ sessionId }}</p>
    </section>

    <section v-if="loadError" class="surface-panel rounded-2xl p-5">
      <p class="text-sm text-destructive">{{ loadError }}</p>
      <Button class="mt-3" size="sm" @click="loadSession">Try Again</Button>
    </section>

    <section v-else-if="loading" class="grid gap-4 lg:grid-cols-2">
      <div class="surface-panel h-48 rounded-2xl" />
      <div class="surface-panel h-48 rounded-2xl" />
    </section>

    <section v-else class="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
      <Card class="surface-panel rounded-2xl">
        <CardHeader>
          <CardTitle class="text-xl font-semibold">Timeline Summary</CardTitle>
          <CardDescription>
            Last update {{ details ? formatRelativeTime(details.last_message_time) : 'unknown' }}
          </CardDescription>
        </CardHeader>
        <CardContent class="space-y-3">
          <div class="grid gap-2 sm:grid-cols-3">
            <div class="rounded-lg border border-border/60 bg-background/70 px-3 py-2">
              <p class="text-[11px] uppercase tracking-wider text-muted-foreground">Messages</p>
              <p class="text-lg font-semibold">{{ details?.message_count ?? 0 }}</p>
            </div>
            <div class="rounded-lg border border-border/60 bg-background/70 px-3 py-2">
              <p class="text-[11px] uppercase tracking-wider text-muted-foreground">Turns</p>
              <p class="text-lg font-semibold">{{ state?.turn_counter ?? 0 }}</p>
            </div>
            <div class="rounded-lg border border-border/60 bg-background/70 px-3 py-2">
              <p class="text-[11px] uppercase tracking-wider text-muted-foreground">Status</p>
              <p class="text-lg font-semibold">{{ state?.status || 'active' }}</p>
            </div>
          </div>

          <div class="rounded-xl border border-border/60 bg-background/70 p-3">
            <p class="text-xs uppercase tracking-wider text-muted-foreground">World State</p>
            <p class="mt-1 text-sm">Location: {{ state?.world_state.location || 'Unknown' }}</p>
            <p class="text-sm">Time: {{ state?.world_state.time || 'Unknown' }}</p>
          </div>

          <Separator />

          <div>
            <p class="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Recent Messages</p>
            <ul class="space-y-2">
              <li
                v-for="message in details?.last_messages.slice(-6)"
                :key="message.created_at + message.content"
                class="rounded-lg border border-border/60 bg-background/70 px-3 py-2"
              >
                <p class="text-[11px] uppercase tracking-wide text-muted-foreground">{{ message.role }}</p>
                <p class="line-clamp-2 text-sm">{{ message.content }}</p>
              </li>
            </ul>
          </div>
        </CardContent>
      </Card>

      <Card class="surface-panel rounded-2xl">
        <CardHeader>
          <CardTitle class="text-xl font-semibold">Characters</CardTitle>
          <CardDescription>Present participants and active goals.</CardDescription>
        </CardHeader>
        <CardContent class="space-y-2">
          <article
            v-for="character in characters"
            :key="character.character_id"
            class="rounded-lg border border-border/60 bg-background/70 px-3 py-2"
          >
            <div class="flex items-center justify-between gap-2">
              <p class="text-sm font-medium">{{ character.character_name }}</p>
              <Badge :class="character.is_present ? 'choice-pill-relocation' : 'choice-pill-action'">
                {{ character.is_present ? 'Present' : 'Offscreen' }}
              </Badge>
            </div>
            <p class="mt-1 line-clamp-2 text-xs text-muted-foreground">
              {{ character.active_intent_goal || 'No active intent' }}
            </p>
          </article>
        </CardContent>
      </Card>
    </section>
  </main>
</template>
