<script setup lang="ts">
import { Plus, ScrollText, Search, Trash2 } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { usePipelineApi } from '@/composables/usePipelineApi'
import type { RulesetSummaryV2 } from '@/types/pipeline'

const { deleteRuleset, listRulesets } = usePipelineApi()

const loading = ref(true)
const deletingId = ref<string | null>(null)
const loadError = ref<string | null>(null)
const query = ref('')

const rulesets = ref<RulesetSummaryV2[]>([])

const filteredRulesets = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) {
    return rulesets.value
  }

  return rulesets.value.filter((ruleset) => ruleset.name.toLowerCase().includes(q))
})

const loadRulesets = async () => {
  loading.value = true
  loadError.value = null

  try {
    rulesets.value = await listRulesets()
  } catch {
    loadError.value = 'Failed to load rulesets.'
  } finally {
    loading.value = false
  }
}

const handleDelete = async (rulesetId: string) => {
  deletingId.value = rulesetId

  try {
    await deleteRuleset(rulesetId)
    rulesets.value = rulesets.value.filter((item) => item.id !== rulesetId)
  } catch {
    loadError.value = 'Failed to delete ruleset.'
  } finally {
    deletingId.value = null
  }
}

onMounted(loadRulesets)
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-3 flex items-center gap-2">
        <Badge variant="outline">Library</Badge>
        <Badge class="choice-pill-dialogue">Rulesets</Badge>
      </div>
      <h1 class="display-heading text-3xl leading-tight sm:text-4xl">Rulesets</h1>
      <p class="mt-3 max-w-3xl text-sm text-muted-foreground sm:text-base">
        Manage simulation mechanics for drives, skills, and emotional state behavior.
      </p>
    </section>

    <section class="surface-panel rounded-2xl p-6">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div class="relative w-full lg:max-w-md">
          <Search class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input v-model="query" class="pl-9" placeholder="Search rulesets by name" />
        </div>

        <Button as-child>
          <RouterLink to="/rulesets/new">
            <Plus class="mr-1 size-4" />
            New Ruleset
          </RouterLink>
        </Button>
      </div>

      <p v-if="loadError" class="mt-3 text-sm text-destructive">{{ loadError }}</p>

      <div v-if="loading" class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <div v-for="index in 6" :key="index" class="h-28 rounded-xl border border-border/60 bg-background/60" />
      </div>

      <div v-else-if="filteredRulesets.length" class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="ruleset in filteredRulesets"
          :key="ruleset.id"
          class="rounded-xl border border-border/70 bg-background/70 p-3"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="line-clamp-1 text-sm font-semibold">{{ ruleset.name }}</p>
            <Badge variant="outline">{{ ruleset.drive_count }} drives</Badge>
          </div>

          <p class="mt-2 text-xs text-muted-foreground">
            {{ ruleset.skill_count }} skills · created {{ ruleset.created_at || 'recently' }}
          </p>

          <Button
            size="sm"
            variant="ghost"
            class="mt-2"
            :disabled="deletingId === ruleset.id"
            @click="handleDelete(ruleset.id)"
          >
            <Trash2 class="mr-1 size-3.5" />
            Delete
          </Button>
        </article>
      </div>

      <div v-else class="mt-4 rounded-xl border border-dashed border-border/70 bg-background/60 p-5">
        <p class="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
          <ScrollText class="size-4" />
          No rulesets yet. Create one to define your simulation mechanics.
        </p>
      </div>
    </section>
  </main>
</template>
