<script setup lang="ts">
import type { AgendaStatus } from '@/protocol/types'

defineProps<{ status: AgendaStatus }>()
</script>

<template>
  <svg
    class="mark"
    :class="`mark--${status}`"
    width="14"
    height="14"
    viewBox="0 0 14 14"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <!-- open: an empty ring -->
    <circle v-if="status === 'open'" cx="7" cy="7" r="4.6" />
    <!-- working: a filled dot -->
    <circle v-else-if="status === 'working'" cx="7" cy="7" r="4.6" fill="currentColor" />
    <!-- waiting: a half-filled ring -->
    <template v-else-if="status === 'waiting'">
      <circle cx="7" cy="7" r="4.6" />
      <path d="M7 2.4a4.6 4.6 0 0 0 0 9.2z" fill="currentColor" stroke="none" />
    </template>
    <!-- settled: a tick -->
    <path v-else-if="status === 'settled'" d="M2.2 7.6l3.2 3.2 6.4-7.2" />
    <!-- dropped: a dash -->
    <path v-else d="M3 7h8" />
  </svg>
</template>

<style scoped>
.mark {
  flex: none;
}

.mark--settled {
  color: var(--success);
}

.mark--waiting {
  color: var(--accent);
}

.mark--dropped {
  color: var(--ink-faint);
}

@media (prefers-reduced-motion: no-preference) {
  .mark--working {
    animation: pulse 1.8s ease-in-out infinite;
  }
}

@keyframes pulse {
  50% {
    opacity: 0.45;
  }
}
</style>
