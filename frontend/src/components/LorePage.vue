<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { renderMarkdown, stripLoreHeader } from '@/markdown/markdown'
import type { LoreFileSummary } from '@/protocol/types'
import { keywordList, loreTitle } from '@/room/format'
import { ROLE_FILES } from '@/room/useStoryFiles'
import type { Loaded, LoadStatus } from '@/room/useStoryFiles'

const props = defineProps<{
  index: { status: LoadStatus; files: readonly LoreFileSummary[]; error: string | null }
  files: Readonly<Record<string, Loaded>>
  /** What to say when the index is empty. */
  emptyText?: string
}>()

const emit = defineEmits<{ want: [filename: string] }>()

/** Plan, style and the working agreement have their own bookmarks. */
const ROLE_FILENAMES: ReadonlySet<string> = new Set(Object.values(ROLE_FILES))
const entries = computed(() => props.index.files.filter((file) => !ROLE_FILENAMES.has(file.filename)))

const selected = ref<string | null>(null)
watch(selected, (filename) => {
  if (filename) emit('want', filename)
})
// A file that disappears from the index is no longer chosen.
watch(entries, (list) => {
  if (selected.value && !list.some((file) => file.filename === selected.value)) selected.value = null
})

const current = computed(() => (selected.value ? props.files[selected.value] : undefined))
const currentSummary = computed(() => entries.value.find((file) => file.filename === selected.value))
const html = computed(() => (current.value?.text ? renderMarkdown(stripLoreHeader(current.value.text)) : ''))
const keywords = computed(() => keywordList(currentSummary.value?.keywords))
</script>

<template>
  <div class="lore-frame">
  <div class="lore" :data-has-file="selected !== null">
    <nav class="lore__index" aria-label="Lore files">
      <p v-if="index.status === 'loading'" class="quiet">Opening the lore…</p>
      <p v-else-if="index.status === 'error'" class="quiet quiet--error" role="alert">{{ index.error }}</p>
      <p v-else-if="entries.length === 0" class="quiet">{{ emptyText ?? 'No lore yet.' }}</p>
      <ul v-else class="lore__list">
        <li v-for="file in entries" :key="file.filename">
          <button
            type="button"
            class="entry"
            :class="{ 'entry--chosen': file.filename === selected }"
            :aria-current="file.filename === selected ? 'true' : undefined"
            @click="selected = file.filename"
          >
            <span class="entry__name">{{ loreTitle(file.filename) }}</span>
            <span v-if="file.summary" class="entry__summary">{{ file.summary }}</span>
          </button>
        </li>
      </ul>
    </nav>

    <article class="lore__file">
      <button type="button" class="lore__back" @click="selected = null">‹ All lore</button>
      <template v-if="selected">
        <p class="lore__filename">{{ selected }}</p>
        <p v-if="keywords.length > 0" class="lore__keywords">{{ keywords.join(' · ') }}</p>
        <p v-if="!current || current.status === 'loading'" class="quiet">Opening the file…</p>
        <p v-else-if="current.status === 'missing'" class="quiet">This file no longer exists.</p>
        <p v-else-if="current.status === 'error'" class="quiet quiet--error" role="alert">
          {{ current.error }}
        </p>
        <div v-if="html" class="prose prose--page" v-html="html"></div>
      </template>
      <p v-else class="quiet lore__choose">Choose a file to read it.</p>
    </article>
  </div>
  </div>
</template>

<style scoped>
.lore-frame {
  height: 100%;
  container-type: inline-size;
}

.lore {
  height: 100%;
  display: grid;
  grid-template-columns: minmax(11rem, 15rem) minmax(0, 1fr);
  gap: 2.25rem;
  padding: 0 1.25rem 0 1rem;
}

.lore__index,
.lore__file {
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  padding: 3.25rem 0 2.5rem;
}

.lore__file {
  mask-image: linear-gradient(180deg, transparent 0, black 2.75rem, black calc(100% - 2.25rem), transparent 100%);
}

/* The index reads like a contents page: ruled entries, the open one marked in the margin. */
.lore__index {
  margin: 2.75rem 0 2.25rem;
  padding: 0.5rem 1.5rem 0.5rem 0;
  border-right: 1px solid var(--paper-rule-warm);
}

.lore__list {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
  list-style: none;
}

.entry {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  width: 100%;
  min-height: 40px;
  padding: 0.6rem 0.25rem 0.65rem 0.75rem;
  text-align: left;
  background: transparent;
  color: var(--ink);
  border: 0;
  border-bottom: 1px dotted var(--paper-rule-dotted);
  border-left: 3px solid transparent;
}

.entry:hover .entry__name {
  color: var(--tab-color);
}

.entry--chosen {
  border-left-color: var(--tab-color);
}

.entry--chosen .entry__name {
  color: var(--tab-color);
  font-weight: 600;
}

.entry__name {
  font-size: 1.1875rem;
  font-variant: small-caps;
  letter-spacing: 0.06em;
  overflow-wrap: anywhere;
}

.entry__summary {
  font-size: var(--size-small);
  font-style: italic;
  color: var(--ink-muted);
}

.lore__back {
  display: none;
  min-height: 40px;
  margin-bottom: 0.5rem;
  padding: 0 0.75rem;
  background: transparent;
  color: var(--accent);
  border: 1px solid var(--paper-rule-warm);
  border-radius: var(--radius-paper);
}

.lore__filename {
  margin: 0;
  font-size: var(--size-small);
  font-variant: small-caps;
  letter-spacing: 0.2em;
  color: var(--tab-color);
}

.lore__keywords {
  margin: 0.15rem 0 0.75rem;
  font-size: var(--size-small);
  font-style: italic;
  color: var(--ink-muted);
}

.lore__choose {
  text-align: left;
}

.quiet {
  margin: 0;
  color: var(--ink-muted);
  font-style: italic;
}

.quiet--error {
  color: var(--error);
}

@container (max-width: 40rem) {
  .lore {
    grid-template-columns: minmax(0, 1fr);
  }

  .lore__index {
    margin: 0;
    padding: 3.25rem 0 2.5rem;
    border-right: 0;
  }

  .lore[data-has-file='true'] .lore__index {
    display: none;
  }

  .lore[data-has-file='false'] .lore__file {
    display: none;
  }

  .lore__back {
    display: inline-flex;
    align-items: center;
  }
}
</style>
