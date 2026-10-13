<script setup lang="ts">
import { computed } from 'vue'
import type { AgendaItem, AgendaStatus } from '@/protocol/types'
import StatusMark from './StatusMark.vue'

const props = defineProps<{ items: readonly AgendaItem[]; error: string | null }>()

const STATUS_WORDS: Record<AgendaStatus, string> = {
  open: 'Open',
  working: 'Being worked on',
  waiting: 'Waiting on you',
  settled: 'Settled',
  dropped: 'Dropped',
}

const counted = computed(() => props.items.filter((item) => item.status !== 'dropped'))
const settled = computed(() => counted.value.filter((item) => item.status === 'settled').length)
const visible = computed(() => props.items.length > 0 || props.error !== null)
</script>

<template>
  <section v-if="visible" class="agenda on-paper" aria-labelledby="agenda-title">
    <span class="agenda__pin" aria-hidden="true"></span>
    <header class="agenda__head">
      <h2 id="agenda-title" class="agenda__title">Agenda</h2>
      <span v-if="counted.length > 0" class="agenda__count">
        {{ settled }} of {{ counted.length }} settled
      </span>
    </header>
    <p v-if="error" class="agenda__error" role="alert">{{ error }}</p>
    <ul class="agenda__list">
      <li
        v-for="item in items"
        :key="item.id"
        class="item"
        :class="`item--${item.status}`"
        :data-status="item.status"
      >
        <StatusMark :status="item.status" />
        <span class="item__body">
          <span class="sr-only">{{ STATUS_WORDS[item.status] }}: </span>
          <span class="item__title">{{ item.title }}</span>
          <span v-if="item.status === 'waiting'" class="item__flag">waiting on you</span>
          <span v-if="item.status === 'settled' && item.outcome" class="item__outcome">
            {{ item.outcome }}
          </span>
        </span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.agenda {
  position: relative;
  flex: none;
  display: flex;
  flex-direction: column;
  max-height: 34%;
  min-height: 0;
  padding: 1.05rem 1.2rem 0.55rem;
  background: var(--surface-card);
  color: var(--ink);
  box-shadow: var(--shadow-card);
  border-radius: var(--radius-paper);
}

.agenda__pin {
  position: absolute;
  top: -8px;
  left: calc(50% - 8px);
  width: 16px;
  height: 16px;
  border-radius: var(--radius-round);
  background: radial-gradient(circle at 35% 30%, var(--pin-top), var(--pin-bottom) 70%);
  box-shadow: var(--shadow-pin);
}

.agenda__head {
  flex: none;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  padding-bottom: 0.35rem;
  border-bottom: 1.5px solid var(--accent-soft);
}

.agenda__title {
  margin: 0;
  font-size: 1.0625rem;
  font-weight: 500;
  font-variant: small-caps;
  letter-spacing: 0.16em;
  color: var(--accent);
}

.agenda__count {
  font-family: var(--font-typewriter);
  font-size: var(--size-small);
  color: var(--ink-muted);
}

.agenda__error {
  margin: 0.4rem 0 0;
  color: var(--error);
  font-size: var(--size-small);
}

.agenda__list {
  flex: 1 1 auto;
  min-height: 0;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  list-style: none;
  font-family: var(--font-typewriter);
  font-size: var(--size-small);
}

.item {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  padding: 0.38rem 0 0.34rem;
  line-height: 1.4;
  border-bottom: 1px solid var(--paper-rule);
}

.item:last-child {
  border-bottom: 0;
}

.item .mark {
  margin-top: 0.2rem;
}

.item__body {
  min-width: 0;
}

.item__flag {
  margin-left: 0.5rem;
  color: var(--accent);
  font-style: italic;
}

.item__outcome {
  color: var(--ink-muted);
  font-style: italic;
}

.item__outcome::before {
  content: ' — ';
  font-style: normal;
}

.item--working .item__title {
  background: linear-gradient(180deg, transparent 18%, var(--highlight) 18%, var(--highlight) 88%, transparent 88%);
}

.item--settled .item__title {
  color: var(--ink-muted);
}

.item--dropped {
  color: var(--ink-faint);
}

.item--dropped .item__title {
  text-decoration: line-through;
}
</style>
