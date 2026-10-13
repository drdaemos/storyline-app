<script setup lang="ts">
import { computed, watch } from 'vue'
import { renderMarkdown, stripLoreHeader } from '@/markdown/markdown'
import type { Loaded } from '@/room/useStoryFiles'

const props = defineProps<{
  title: string
  filename: string
  /** Shown when the story has no such file yet. */
  emptyText: string
  file: Loaded | undefined
  /** True while this page is the one open in the book. */
  shown: boolean
}>()

const emit = defineEmits<{ want: [filename: string] }>()

watch(
  () => props.shown,
  (isShown) => {
    if (isShown) emit('want', props.filename)
  },
  { immediate: true }
)

const html = computed(() => (props.file?.text ? renderMarkdown(stripLoreHeader(props.file.text)) : ''))
</script>

<template>
  <div class="role" role="region" tabindex="0" :aria-label="title">
    <h2 class="role__title">{{ title }}</h2>
    <p v-if="!file || file.status === 'loading'" class="quiet">Opening {{ filename }}…</p>
    <p v-else-if="file.status === 'missing'" class="quiet">{{ emptyText }}</p>
    <p v-else-if="file.status === 'error'" class="quiet quiet--error" role="alert">{{ file.error }}</p>
    <p v-else-if="!html" class="quiet">{{ emptyText }}</p>
    <div v-if="html" class="prose prose--page" v-html="html"></div>
  </div>
</template>

<style scoped>
.role {
  height: 100%;
  overflow-y: auto;
  scrollbar-width: thin;
  padding: 3.25rem 1.25rem 3rem 1rem;
  mask-image: linear-gradient(180deg, transparent 0, black 2.75rem, black calc(100% - 2.25rem), transparent 100%);
}

/* A running head: the file's own headings do the titling. */
.role__title {
  max-width: var(--measure-manuscript);
  margin: 0 auto 1.4rem;
  padding-bottom: 0.45rem;
  border-bottom: 1px solid var(--paper-rule-warm);
  font-size: var(--size-small);
  font-weight: 500;
  font-variant: small-caps;
  letter-spacing: 0.22em;
  color: var(--tab-color, var(--ink-muted));
}

.quiet {
  max-width: var(--measure-manuscript);
  margin: 0 auto;
  color: var(--ink-muted);
  font-style: italic;
}

.quiet--error {
  color: var(--error);
}
</style>
