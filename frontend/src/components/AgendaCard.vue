<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import type { AgendaItem, AgendaStatus } from '@/protocol/types'
import StatusMark from './StatusMark.vue'
import { NARROW_SCREEN, useMediaQuery } from './useMediaQuery'

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

/** A narrow screen starts with the card folded to one line, so the conversation keeps the room. */
const open = ref(!useMediaQuery(NARROW_SCREEN).value)
const listId = useId()

/** The item a folded card names: what waits on the user, else what is being worked on, else what is next. */
const FOCUS_ORDER: readonly AgendaStatus[] = ['waiting', 'working', 'open']
const focus = computed(() => {
  for (const status of FOCUS_ORDER) {
    const item = props.items.find((candidate) => candidate.status === status)
    if (item) return item
  }
  return null
})
</script>

<template>
  <section v-if="visible" class="agenda on-paper" :class="{ 'agenda--folded': !open }" aria-labelledby="agenda-title">
    <span class="agenda__pin" aria-hidden="true"></span>
    <h2 id="agenda-title" class="agenda__head">
      <button
        type="button"
        class="agenda__toggle"
        :aria-expanded="open"
        :aria-controls="listId"
        @click="open = !open"
      >
        <span class="agenda__title">Agenda</span>
        <span v-if="counted.length > 0" class="agenda__count">
          {{ settled }} of {{ counted.length }} settled
        </span>
        <span class="agenda__chevron" aria-hidden="true">{{ open ? '–' : '+' }}</span>
      </button>
    </h2>
    <p v-if="error" class="agenda__error" role="alert">{{ error }}</p>
    <p v-if="!open && focus" class="agenda__focus">
      <StatusMark :status="focus.status" />
      <span class="item__body">
        <span class="sr-only">{{ STATUS_WORDS[focus.status] }}: </span>
        <span class="item__title">{{ focus.title }}</span>
        <span v-if="focus.status === 'waiting'" class="item__flag">waiting on you</span>
      </span>
    </p>
    <ul v-show="open" :id="listId" class="agenda__list">
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

.agenda--folded {
  padding-bottom: 0.45rem;
}

.agenda__head {
  flex: none;
  margin: 0;
  font-size: inherit;
  font-weight: inherit;
  border-bottom: 1.5px solid var(--accent-soft);
}

.agenda--folded .agenda__head {
  border-bottom-color: transparent;
}

/* The whole head folds and unfolds the card; it is tall enough for a thumb. */
.agenda__toggle {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  width: 100%;
  min-height: 36px;
  padding: 0 0 0.35rem;
  background: transparent;
  color: inherit;
  border: 0;
  text-align: left;
}

.agenda__toggle:hover .agenda__title {
  text-decoration: underline;
}

.agenda__title {
  margin-right: auto;
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

.agenda__chevron {
  min-width: 1ch;
  font-family: var(--font-typewriter);
  color: var(--ink-muted);
}

/* The one line a folded card shows. */
.agenda__focus {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  margin: 0;
  font-family: var(--font-list);
  font-size: var(--size-list);
  line-height: 1.4;
}

.agenda__focus .item__body {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.agenda__focus .mark {
  flex: none;
  margin-top: 0.2rem;
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
  font-family: var(--font-list);
  font-size: var(--size-list);
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

@media (max-width: 760px) {
  .agenda {
    max-height: 45%;
    padding: 0.7rem 0.9rem 0.4rem;
  }

  .agenda--folded {
    padding-bottom: 0.55rem;
  }

  .agenda__toggle {
    min-height: 32px;
    padding-bottom: 0.2rem;
  }

  .item {
    padding: 0.3rem 0;
  }
}
</style>
