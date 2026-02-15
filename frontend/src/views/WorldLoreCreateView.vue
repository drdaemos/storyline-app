<script setup lang="ts">
import { BookOpenText, Plus, Tags } from 'lucide-vue-next'
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { usePipelineApi } from '@/composables/usePipelineApi'

const router = useRouter()
const { createWorldLore, listWorldLoreTags } = usePipelineApi()

const loadingTags = ref(true)
const saving = ref(false)
const error = ref<string | null>(null)

const availableTags = ref<string[]>([])
const manualTagInput = ref('')

const form = reactive({
  name: '',
  content: '',
  tags: [] as string[],
})

const normalizedTags = computed(() => {
  return [...new Set(form.tags.map((tag) => tag.trim()).filter((tag) => tag.length > 0))]
})

const contentPreview = computed(() => {
  return form.content.trim().slice(0, 280)
})

const addManualTag = () => {
  const tag = manualTagInput.value.trim()
  if (!tag) {
    return
  }

  if (!form.tags.includes(tag)) {
    form.tags.push(tag)
  }

  manualTagInput.value = ''
}

const removeTag = (tag: string) => {
  form.tags = form.tags.filter((item) => item !== tag)
}

const toggleTag = (tag: string) => {
  if (form.tags.includes(tag)) {
    removeTag(tag)
    return
  }

  form.tags.push(tag)
}

const saveLore = async () => {
  if (!form.name.trim()) {
    error.value = 'Lore name is required.'
    return
  }

  saving.value = true
  error.value = null

  try {
    await createWorldLore({
      name: form.name.trim(),
      content: form.content.trim(),
      tags: normalizedTags.value,
    })

    await router.push('/library/world-lore')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to create world lore entry.'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  loadingTags.value = true

  try {
    availableTags.value = await listWorldLoreTags()
  } catch {
    availableTags.value = []
  } finally {
    loadingTags.value = false
  }
})
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-3 flex items-center gap-2">
        <Badge variant="outline">Create</Badge>
        <Badge class="choice-pill-relocation">World Lore</Badge>
      </div>
      <h1 class="display-heading text-3xl leading-tight sm:text-4xl">Create World Lore</h1>
      <p class="mt-3 max-w-3xl text-sm text-muted-foreground sm:text-base">
        Add reusable world context entries with tags for fast scenario composition and filtering.
      </p>
    </section>

    <section class="grid gap-4 lg:grid-cols-[1.65fr_1fr]">
      <article class="surface-panel rounded-2xl p-6">
        <div class="mb-4 flex items-center justify-between gap-2">
          <h2 class="text-xl font-semibold">Lore Surface</h2>
          <Button data-testid="save-lore" :disabled="saving" @click="saveLore">Save Lore</Button>
        </div>

        <div class="space-y-4">
          <div class="space-y-1.5">
            <label for="lore-name" class="text-sm">Name</label>
            <Input id="lore-name" v-model="form.name" placeholder="Dock District Union Archive" />
          </div>

          <div class="space-y-1.5">
            <label for="lore-content" class="text-sm">Content</label>
            <Textarea
              id="lore-content"
              v-model="form.content"
              rows="14"
              placeholder="Key details, factions, tensions, and historical notes..."
            />
          </div>

          <div class="space-y-2">
            <label for="lore-tag-input" class="text-sm">Tags</label>
            <div class="flex gap-2">
              <Input
                id="lore-tag-input"
                v-model="manualTagInput"
                placeholder="district, faction, history"
                @keydown.enter.prevent="addManualTag"
              />
              <Button type="button" size="icon" variant="outline" @click="addManualTag">
                <Plus class="size-4" />
              </Button>
            </div>

            <div class="flex flex-wrap gap-2">
              <button
                v-for="tag in normalizedTags"
                :key="`selected-${tag}`"
                type="button"
                class="choice-option choice-pill-relocation"
                @click="removeTag(tag)"
              >
                {{ tag }}
              </button>
            </div>
          </div>
        </div>

        <p v-if="error" class="mt-4 text-sm text-destructive">{{ error }}</p>

        <div class="mt-5 flex items-center justify-between gap-2">
          <Button variant="ghost" as-child>
            <RouterLink to="/library/world-lore">Back to World Lore</RouterLink>
          </Button>
          <Button :disabled="saving" @click="saveLore">Save Lore</Button>
        </div>
      </article>

      <aside class="surface-panel rounded-2xl p-6 lg:sticky lg:top-24 lg:h-fit">
        <div class="mb-3 flex items-center gap-2">
          <Tags class="size-4" />
          <h2 class="text-xl font-semibold">Tag Palette</h2>
        </div>

        <div v-if="loadingTags" class="rounded-xl border border-border/70 bg-background/70 p-3 text-sm text-muted-foreground">
          Loading tags...
        </div>

        <div v-else class="flex flex-wrap gap-2 rounded-xl border border-border/70 bg-background/70 p-3">
          <button
            v-for="tag in availableTags"
            :key="`available-${tag}`"
            type="button"
            :class="[
              'rounded-full border px-2.5 py-1 text-xs transition-colors',
              form.tags.includes(tag)
                ? 'choice-pill-relocation'
                : 'border-border/70 bg-background/70 text-muted-foreground hover:bg-accent/20',
            ]"
            @click="toggleTag(tag)"
          >
            {{ tag }}
          </button>

          <p v-if="!availableTags.length" class="text-xs text-muted-foreground">No existing tags yet.</p>
        </div>

        <div class="mt-4 rounded-xl border border-border/70 bg-background/70 p-3">
          <p class="mb-2 text-xs uppercase tracking-wide text-muted-foreground">Preview</p>
          <p class="text-sm font-semibold">{{ form.name || 'Untitled Lore Entry' }}</p>
          <p class="mt-2 text-xs text-muted-foreground">{{ contentPreview || 'No content yet.' }}</p>
        </div>

        <p class="mt-4 inline-flex items-center gap-1.5 rounded-md border border-border/60 bg-background/70 px-2.5 py-1 text-xs text-muted-foreground">
          <BookOpenText class="size-3.5" />
          Tags are used for grouping, search, and scenario composition.
        </p>
      </aside>
    </section>
  </main>
</template>
