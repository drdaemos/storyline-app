<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { freshInkStart, renderMarkdown } from '@/markdown/markdown'
import type { Loaded } from '@/room/useStoryFiles'
import { useFollowScroll } from './useFollowScroll'

const props = defineProps<{
  script: Loaded
  /** The script as it was when the last turn began; text added after it is fresh ink. */
  baseline: string | null
  /** The writer is writing: follow the end of the page. */
  writing: boolean
}>()

const scroller = ref<HTMLElement | null>(null)
const placed = ref(false)
const active = computed(() => props.writing || !placed.value)
const { jumpToEnd } = useFollowScroll(scroller, () => props.script.text, { active })

const freshFrom = computed(() => freshInkStart(props.baseline, props.script.text))
const html = computed(() => renderMarkdown(props.script.text, { freshFrom: freshFrom.value }))
const isEmpty = computed(() => props.script.status === 'ready' && props.script.text.trim() === '')

// A script opened for the first time shows where the writing stands.
watch(
  () => props.script.status,
  async (status) => {
    if (status !== 'ready' || placed.value) return
    await nextTick()
    jumpToEnd()
    placed.value = true
  },
  { immediate: true }
)

watch(
  () => props.writing,
  (isWriting) => {
    if (isWriting) jumpToEnd()
  }
)
</script>

<template>
  <div ref="scroller" class="script" role="region" tabindex="0" aria-label="Script">
    <div class="script__inner">
      <p v-if="script.status === 'loading'" class="quiet">Opening the script…</p>
      <p v-else-if="script.status === 'error'" class="quiet quiet--error" role="alert">
        {{ script.error }}
      </p>
      <p v-else-if="script.status === 'missing' || isEmpty" class="quiet">Nothing is written yet.</p>
      <template v-if="script.text">
        <p v-if="freshFrom !== null" class="fresh-note">Fresh ink: what the writer added in its latest turn.</p>
        <div class="prose prose--page prose--manuscript" v-html="html"></div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.script {
  height: 100%;
  overflow-y: auto;
  scrollbar-width: thin;
  padding: 0 1.25rem 0 1rem;
  mask-image: linear-gradient(180deg, transparent 0, black 2.75rem, black calc(100% - 2.25rem), transparent 100%);
}

.script__inner {
  max-width: var(--measure-manuscript);
  margin-inline: auto;
  padding: 3.25rem 0 3rem;
}

.quiet {
  margin: 0;
  color: var(--ink-muted);
  font-style: italic;
  text-align: center;
}

.quiet--error {
  color: var(--error);
}

.fresh-note {
  margin: 0 0 0.75rem;
  font-size: var(--size-small);
  font-style: italic;
  color: var(--ink-fresh);
  text-align: right;
}
</style>
