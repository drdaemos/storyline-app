<script setup lang="ts">
import { ref, watch } from 'vue'
import type { LoreFileSummary } from '@/protocol/types'
import type { Loaded, LoadStatus } from '@/room/useStoryFiles'
import LorePage from './LorePage.vue'

const props = defineProps<{
  index: { status: LoadStatus; files: readonly LoreFileSummary[]; error: string | null }
  files: Readonly<Record<string, Loaded>>
  /** Whether this page is the one open in the book. Leaving it closes the seal again. */
  shown: boolean
}>()

defineEmits<{ want: [filename: string] }>()

/** Kept in memory for this visit only: nothing is stored, and nothing is read until it is true. */
const peeking = ref(false)
watch(
  () => props.shown,
  (shown) => {
    if (!shown) peeking.value = false
  }
)
</script>

<template>
  <LorePage
    v-if="peeking"
    :index="index"
    :files="files"
    empty-text="Nothing is sealed."
    @want="$emit('want', $event)"
  />
  <div v-else class="seal">
    <div class="seal__card" role="group" aria-labelledby="seal-title">
      <h2 id="seal-title" class="seal__title">Sealed</h2>
      <p class="seal__text">
        {{ index.files.length === 1 ? 'One file is' : `${index.files.length} files are` }} sealed here: what the
        writer knows and you do not, such as secrets, twists and hidden causes.
      </p>
      <p class="seal__text seal__text--warning">
        Reading them will spoil the story. Once you have seen them, you cannot unsee them.
      </p>
      <button type="button" class="seal__peek" @click="peeking = true">Break the seal and peek</button>
    </div>
  </div>
</template>

<style scoped>
.seal {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3.25rem 1.25rem 2.5rem;
  overflow-y: auto;
}

.seal__card {
  max-width: 28rem;
  padding: 1.25rem 1.5rem 1.5rem;
  border: 1px dashed var(--bookmark-sealed);
  border-left: 4px solid var(--bookmark-sealed);
  border-radius: var(--radius-paper);
  color: var(--ink);
}

.seal__title {
  margin: 0 0 0.5rem;
  font-size: var(--size-heading);
  font-style: italic;
  font-weight: 400;
  color: var(--bookmark-sealed);
}

.seal__text {
  margin: 0 0 0.75rem;
}

.seal__text--warning {
  font-style: italic;
  color: var(--ink-muted);
}

.seal__peek {
  min-height: 44px;
  padding: 0 1.2rem;
  background: var(--button-ground);
  color: var(--button-ink);
  border: 1.5px solid var(--button-edge);
  border-radius: var(--radius-button);
}
</style>
