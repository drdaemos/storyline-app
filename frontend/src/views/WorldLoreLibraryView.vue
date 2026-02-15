<script setup lang="ts">
import { BookOpenText, Plus, Search, Tag, Trash2 } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { usePipelineApi } from '@/composables/usePipelineApi'
import type { WorldLoreSummaryV2 } from '@/types/pipeline'

const { deleteWorldLore, listWorldLore, listWorldLoreTags } = usePipelineApi()

const loading = ref(true)
const deletingId = ref<string | null>(null)
const loadError = ref<string | null>(null)

const search = ref('')
const selectedTag = ref('all')

const loreEntries = ref<WorldLoreSummaryV2[]>([])
const tags = ref<string[]>([])

const filteredEntries = computed(() => {
  const q = search.value.trim().toLowerCase()

  return loreEntries.value.filter((entry) => {
    const tagMatch = selectedTag.value === 'all' || entry.tags.includes(selectedTag.value)
    const matchesQuery =
      !q ||
      entry.name.toLowerCase().includes(q) ||
      entry.content_preview.toLowerCase().includes(q) ||
      entry.tags.some((tag) => tag.toLowerCase().includes(q))

    return tagMatch && matchesQuery
  })
})

const groupedEntries = computed(() => {
  if (selectedTag.value !== 'all') {
    return [
      {
        group: selectedTag.value,
        entries: filteredEntries.value,
      },
    ]
  }

  const groups = new Map<string, WorldLoreSummaryV2[]>()

  for (const entry of filteredEntries.value) {
    const primaryTag = entry.tags[0] || 'untagged'
    const existing = groups.get(primaryTag) || []
    existing.push(entry)
    groups.set(primaryTag, existing)
  }

  return [...groups.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([group, entries]) => ({
      group,
      entries,
    }))
})

const loadLore = async () => {
  loading.value = true
  loadError.value = null

  try {
    const [entriesResult, tagsResult] = await Promise.all([listWorldLore(), listWorldLoreTags()])

    loreEntries.value = entriesResult
    tags.value = tagsResult
  } catch {
    loadError.value = 'Failed to load world lore.'
  } finally {
    loading.value = false
  }
}

const handleDelete = async (loreId: string) => {
  deletingId.value = loreId

  try {
    await deleteWorldLore(loreId)
    loreEntries.value = loreEntries.value.filter((entry) => entry.id !== loreId)
  } catch {
    loadError.value = 'Failed to delete world lore entry.'
  } finally {
    deletingId.value = null
  }
}

onMounted(loadLore)
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-3 flex items-center gap-2">
        <Badge variant="outline">Library</Badge>
        <Badge class="choice-pill-relocation">World Lore</Badge>
      </div>
      <h1 class="display-heading text-3xl leading-tight sm:text-4xl">World Lore</h1>
      <p class="mt-3 max-w-3xl text-sm text-muted-foreground sm:text-base">
        Search and group lore entries by tags. Use these entries when composing scenarios.
      </p>
    </section>

    <section class="surface-panel rounded-2xl p-6">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div class="relative w-full lg:max-w-md">
          <Search class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input v-model="search" class="pl-9" placeholder="Search lore name, preview, or tags" />
        </div>

        <div class="flex flex-wrap gap-2">
          <Button
            size="sm"
            :variant="selectedTag === 'all' ? 'default' : 'outline'"
            @click="selectedTag = 'all'"
          >
            All
          </Button>
          <Button
            v-for="tag in tags"
            :key="tag"
            size="sm"
            :variant="selectedTag === tag ? 'default' : 'outline'"
            @click="selectedTag = tag"
          >
            {{ tag }}
          </Button>
        </div>

        <Button as-child>
          <RouterLink to="/world-lore/new">
            <Plus class="mr-1 size-4" />
            New Lore
          </RouterLink>
        </Button>
      </div>

      <p v-if="loadError" class="mt-3 text-sm text-destructive">{{ loadError }}</p>

      <div v-if="loading" class="mt-4 grid gap-3 sm:grid-cols-2">
        <div v-for="index in 6" :key="index" class="h-28 rounded-xl border border-border/60 bg-background/60" />
      </div>

      <div v-else class="mt-4 space-y-4">
        <section
          v-for="group in groupedEntries"
          :key="group.group"
          class="rounded-xl border border-border/65 bg-background/70 p-4"
        >
          <div class="mb-3 flex items-center gap-2">
            <Tag class="size-4 text-muted-foreground" />
            <h2 class="text-sm font-semibold uppercase tracking-wide">{{ group.group }}</h2>
            <Badge variant="outline">{{ group.entries.length }}</Badge>
          </div>

          <div v-if="group.entries.length" class="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            <article
              v-for="entry in group.entries"
              :key="entry.id"
              class="rounded-lg border border-border/60 bg-background/75 px-3 py-3"
            >
              <p class="text-sm font-medium">{{ entry.name }}</p>
              <p class="mt-1 line-clamp-2 text-xs text-muted-foreground">{{ entry.content_preview }}</p>

              <div class="mt-2 flex flex-wrap gap-1">
                <Badge v-for="tag in entry.tags" :key="`${entry.id}-${tag}`" variant="outline">
                  {{ tag }}
                </Badge>
              </div>

              <Button
                size="sm"
                variant="ghost"
                class="mt-2"
                :disabled="deletingId === entry.id"
                @click="handleDelete(entry.id)"
              >
                <Trash2 class="mr-1 size-3.5" />
                Delete
              </Button>
            </article>
          </div>

          <p v-else class="text-sm text-muted-foreground">No entries in this group.</p>
        </section>
      </div>

      <div v-if="!loading && !groupedEntries.length" class="mt-4 rounded-xl border border-dashed border-border/70 bg-background/60 p-5">
        <p class="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
          <BookOpenText class="size-4" />
          No lore entries yet. Create your first one to start tagging your world.
        </p>
      </div>
    </section>
  </main>
</template>
