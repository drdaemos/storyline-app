<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '@/markdown/markdown'
import type { MessageEntry } from '@/protocol/types'

const props = defineProps<{ entry: MessageEntry }>()

const streaming = computed(() => props.entry.reply_id !== null)
const html = computed(() => (props.entry.role === 'writer' ? renderMarkdown(props.entry.text) : ''))
const empty = computed(() => props.entry.text.trim() === '')
</script>

<template>
  <div
    v-if="!empty"
    class="note on-paper"
    :class="`note--${entry.role}`"
    :data-role="entry.role"
    :aria-busy="streaming"
  >
    <p v-if="entry.role === 'user'" class="note__user">{{ entry.text }}</p>
    <!-- eslint-disable-next-line vue/no-v-html -- markdown-it renders with raw HTML disabled -->
    <div v-else class="prose prose--note" v-html="html"></div>
  </div>
</template>

<style scoped>
.note {
  padding: 0.8rem 1.05rem;
  border-radius: var(--radius-paper);
  box-shadow: var(--shadow-note);
  color: var(--ink);
}

.note--user {
  align-self: flex-end;
  max-width: 88%;
  background: var(--surface-note-user);
}

.note--writer {
  align-self: stretch;
  background: var(--surface-note-writer);
  font-family: var(--font-typewriter);
}

.note__user {
  margin: 0;
  font-size: 1.125rem;
  line-height: 1.45;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

@media (max-width: 760px) {
  .note {
    padding: 0.6rem 0.75rem;
  }

  .note--user {
    max-width: 92%;
  }

  .note__user {
    font-size: 1.0625rem;
  }
}
</style>
