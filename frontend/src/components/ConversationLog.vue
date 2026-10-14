<script setup lang="ts">
import { ref } from 'vue'
import type { LogEntry } from '@/room/roomState'
import MessageNote from './MessageNote.vue'
import NoticeLine from './NoticeLine.vue'
import ToolStamp from './ToolStamp.vue'
import { useFollowScroll } from './useFollowScroll'

const props = defineProps<{
  entries: readonly LogEntry[]
  hiddenEntries: number
  /** What the writer is doing, e.g. "Thinking…"; empty when it is the user's move. */
  activity: string
}>()

const scroller = ref<HTMLElement | null>(null)
const { unseen, jumpToEnd } = useFollowScroll(scroller, () => [props.entries, props.activity])
</script>

<template>
  <div class="log-frame">
    <div ref="scroller" class="log" tabindex="0" role="region" aria-label="Conversation">
      <div class="log__inner">
        <p v-if="hiddenEntries > 0" class="log__hidden">
          … {{ hiddenEntries }} earlier {{ hiddenEntries === 1 ? 'entry' : 'entries' }} not shown
        </p>
        <template v-for="(entry, index) in entries" :key="index">
          <MessageNote v-if="entry.kind === 'message'" :entry="entry" />
          <ToolStamp v-else-if="entry.kind === 'tool_call'" :entry="entry" />
          <NoticeLine v-else :notice="entry" />
        </template>
        <p class="log__activity" role="status" aria-live="polite">{{ activity }}</p>
      </div>
    </div>
    <button v-if="unseen" type="button" class="log__jump" @click="jumpToEnd">
      Newer messages below
    </button>
  </div>
</template>

<style scoped>
.log-frame {
  position: relative;
  flex: 1 1 0;
  min-height: 0;
  display: flex;
}

.log {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  padding: 1rem 0.5rem 0.25rem 0.1rem;
  mask-image: linear-gradient(180deg, transparent 0, black 2.25rem);
}

.log__inner {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  min-height: 100%;
  justify-content: flex-end;
}

.log__hidden {
  margin: 0;
  color: var(--ink-on-desk-muted);
  font-style: italic;
  text-align: center;
}

.log__activity {
  min-height: 1.6rem;
  margin: 0;
  color: var(--ink-on-desk);
  font-style: italic;
}

.log__jump {
  position: absolute;
  right: 1.25rem;
  bottom: 0.5rem;
  min-height: 40px;
  padding: 0 1rem;
  background: var(--button-ground);
  color: var(--button-ink);
  border: 1.5px solid var(--button-edge);
  border-radius: var(--radius-button);
  box-shadow: var(--shadow-button);
}

.log__jump:hover {
  background: var(--button-ground-hover);
}

@media (max-width: 760px) {
  .log {
    padding: 0.6rem 0.25rem 0.25rem 0;
    mask-image: linear-gradient(180deg, transparent 0, black 1rem);
  }

  .log__inner {
    gap: 0.6rem;
  }

  /* A small pill in the middle, so it covers little of the text under it. */
  .log__jump {
    right: auto;
    left: 50%;
    min-height: 36px;
    padding: 0 0.85rem;
    transform: translateX(-50%);
    font-size: var(--size-small);
    border-radius: var(--radius-button);
  }
}
</style>
