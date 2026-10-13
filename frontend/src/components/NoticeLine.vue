<script setup lang="ts">
import type { NoticeEntry } from '@/room/roomState'

defineProps<{ notice: NoticeEntry }>()
</script>

<template>
  <p
    class="notice"
    :class="[`notice--${notice.level}`, { 'on-paper': notice.level === 'error' }]"
    :role="notice.level === 'error' ? 'alert' : 'status'"
  >
    {{ notice.text }}
  </p>
</template>

<style scoped>
.notice {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.notice--info {
  color: var(--ink-on-desk-muted);
  font-style: italic;
}

.notice--error {
  padding: 0.6rem 0.9rem;
  background: var(--note-error);
  color: var(--error);
  border-radius: var(--radius-paper);
  box-shadow: var(--shadow-note);
  font-size: var(--size-note);
}
</style>
