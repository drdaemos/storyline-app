<template>
  <section class="space-y-6">
    <div class="story-panel p-6 md:p-8">
      <div class="flex flex-wrap gap-4 items-end justify-between">
        <div class="space-y-2">
          <span class="story-chip px-3 py-1 text-xs font-medium inline-flex">World Lore Library</span>
          <h1 class="story-headline text-3xl md:text-4xl">Tag Groups</h1>
          <p class="story-subtext">Browse lore by tags. Root view shows groups, then drill into entries.</p>
        </div>
        <div class="flex gap-2">
          <UButton color="primary" icon="i-lucide-book-plus" @click="createWorldLore">Create World Lore</UButton>
          <UButton v-if="selectedTag" color="neutral" variant="soft" icon="i-lucide-arrow-left" @click="clearGroup">
            Back To Groups
          </UButton>
        </div>
      </div>
    </div>

    <UAlert
      v-if="error"
      color="error"
      variant="soft"
      icon="i-lucide-alert-triangle"
      title="Failed to load world lore"
      :description="error.message"
    />

    <div v-if="loading" class="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
      <UCard v-for="i in 6" :key="i" class="story-panel-muted">
        <USkeleton class="h-6 w-32 mb-3" />
        <USkeleton class="h-4 w-20" />
      </UCard>
    </div>

    <div v-else-if="items.length === 0" class="story-panel-muted p-8 text-center">
      <h2 class="text-xl story-headline mb-2">No world lore assets yet</h2>
      <p class="story-subtext mb-4">Create your first lore entry and assign tags to organize groups.</p>
      <UButton color="primary" icon="i-lucide-book-plus" @click="createWorldLore">Create World Lore</UButton>
    </div>

    <div v-else-if="!selectedTag" class="space-y-4">
      <div class="story-panel p-4 md:p-5">
        <UFormField label="Find group">
          <UInput v-model="groupQuery" placeholder="Search tag groups..." icon="i-lucide-search" />
        </UFormField>
      </div>

      <div class="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        <UCard
          v-for="group in filteredGroups"
          :key="group.tag"
          class="story-panel-muted story-card-hover cursor-pointer"
          @click="openGroup(group.tag)"
        >
          <div class="space-y-3">
            <div class="flex items-start justify-between gap-3">
              <h3 class="story-headline text-lg">{{ group.label }}</h3>
              <UBadge color="neutral" variant="subtle">{{ group.count }}</UBadge>
            </div>
            <p class="text-sm story-subtext">{{ group.count }} lore {{ group.count === 1 ? 'entry' : 'entries' }}</p>
          </div>
        </UCard>
      </div>
    </div>

    <div v-else class="space-y-4">
      <div class="story-panel p-4 md:p-5 flex flex-wrap gap-3 items-center justify-between">
        <div class="flex items-center gap-3">
          <UBadge color="primary" variant="subtle">{{ selectedTagLabel }}</UBadge>
          <span class="story-subtext text-sm">{{ groupedItems.length }} entries</span>
        </div>
        <UFormField label="Filter entries" class="min-w-[260px]">
          <UInput v-model="entryQuery" placeholder="Search name or lore text" icon="i-lucide-search" />
        </UFormField>
      </div>

      <div v-if="filteredEntries.length === 0" class="story-panel-muted p-8 text-center">
        <p class="story-subtext">No entries found in this group.</p>
      </div>

      <div v-else class="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        <UCard v-for="item in filteredEntries" :key="item.id" class="story-panel-muted story-card-hover">
          <div class="space-y-3">
            <div class="flex items-start justify-between gap-3">
              <h3 class="story-headline text-lg line-clamp-2">{{ item.name }}</h3>
              <div class="flex gap-1">
                <UButton color="neutral" variant="ghost" icon="i-lucide-pencil" size="xs" @click="startEdit(item.id)" />
                <UButton
                  color="neutral"
                  variant="ghost"
                  icon="i-lucide-trash-2"
                  size="xs"
                  :disabled="item.id === 'default-world'"
                  @click="remove(item.id)"
                />
              </div>
            </div>
            <div class="flex flex-wrap gap-1">
              <UBadge v-for="tag in item.tags" :key="`${item.id}-${tag}`" color="neutral" variant="subtle" class="cursor-pointer" @click="openGroup(tag)">
                {{ tag }}
              </UBadge>
            </div>
            <p class="text-sm story-subtext line-clamp-4">{{ item.lore_text }}</p>
          </div>
        </UCard>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import type { WorldLoreAsset } from '@/types'

const router = useRouter()
const { listWorldLore, deleteWorldLore, loading, error } = useApi()

const items = ref<WorldLoreAsset[]>([])
const selectedTag = ref<string | null>(null)
const groupQuery = ref('')
const entryQuery = ref('')

const normalize = (value: string) => value.trim().toLowerCase()

const groupMap = computed(() => {
  const map = new Map<string, WorldLoreAsset[]>()
  for (const item of items.value) {
    const tags = item.tags?.length ? item.tags : ['untagged']
    for (const tag of tags) {
      const key = normalize(tag)
      const list = map.get(key) || []
      list.push(item)
      map.set(key, list)
    }
  }
  return map
})

const groups = computed(() => {
  return Array.from(groupMap.value.entries())
    .map(([key, list]) => ({
      tag: key,
      label: key === 'untagged' ? 'Untagged' : list[0]?.tags?.find(t => normalize(t) === key) || key,
      count: list.length,
    }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
})

const filteredGroups = computed(() => {
  const query = normalize(groupQuery.value)
  if (!query) return groups.value
  return groups.value.filter(group => normalize(group.label).includes(query))
})

const groupedItems = computed(() => {
  if (!selectedTag.value) return []
  return groupMap.value.get(selectedTag.value) || []
})

const filteredEntries = computed(() => {
  const query = normalize(entryQuery.value)
  if (!query) return groupedItems.value
  return groupedItems.value.filter(item => {
    const haystack = normalize(`${item.name} ${item.lore_text}`)
    return haystack.includes(query)
  })
})

const selectedTagLabel = computed(() => {
  if (!selectedTag.value) return ''
  const group = groups.value.find(g => g.tag === selectedTag.value)
  return group?.label || selectedTag.value
})

const load = async () => {
  items.value = await listWorldLore()
  if (selectedTag.value && !groupMap.value.has(selectedTag.value)) {
    selectedTag.value = null
  }
}

const openGroup = (tag: string) => {
  selectedTag.value = normalize(tag)
  entryQuery.value = ''
}

const clearGroup = () => {
  selectedTag.value = null
  entryQuery.value = ''
}

const createWorldLore = () => {
  router.push({ name: 'create-world-lore' })
}

const startEdit = (id: string) => {
  router.push({ name: 'create-world-lore', query: { id } })
}

const remove = async (id: string) => {
  if (id === 'default-world') return
  if (!confirm('Delete this world lore asset?')) return
  await deleteWorldLore(id)
  await load()
}

onMounted(() => {
  load()
})
</script>
