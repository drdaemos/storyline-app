<script setup lang="ts">
import { computed, reactive, ref, toRef, watch, watchEffect } from 'vue'
import { RouterLink } from 'vue-router'
import BookPane from '@/components/BookPane.vue'
import ConversationPane from '@/components/ConversationPane.vue'
import { isWorking } from '@/room/roomState'
import { useRoom } from '@/room/useRoom'
import { useStoryFiles } from '@/room/useStoryFiles'

const props = defineProps<{ name: string }>()

const story = toRef(props, 'name')
const room = useRoom(story)
const state = computed(() => room.state.value)
const files = useStoryFiles({
  story,
  activity: computed(() => state.value.activity),
  scriptRevision: computed(() => state.value.scriptRevision),
  loreRevision: computed(() => state.value.loreRevision),
})

/** Which pane a narrow screen shows. */
const pane = ref<'conversation' | 'book'>('conversation')
const PANES = [
  { id: 'conversation', label: 'Conversation' },
  { id: 'book', label: 'Book' },
] as const

type PaneId = (typeof PANES)[number]['id']

/** A pane that changed while the other one was shown gets a mark on its tab until it is shown. */
const changed = reactive<Record<PaneId, boolean>>({ conversation: false, book: false })
const working = computed(() => isWorking(state.value))

// Files change during a turn; a reconnect's snapshot also bumps the revisions, and that is no news.
watch([() => state.value.scriptRevision, () => state.value.loreRevision], () => {
  if (working.value && pane.value !== 'book') changed.book = true
})

watch(working, (now, before) => {
  if (before && !now && pane.value !== 'conversation') changed.conversation = true
})

function show(id: PaneId): void {
  pane.value = id
  changed[id] = false
}

watchEffect(() => {
  document.title = `${props.name} · Storyline`
})
</script>

<template>
  <main class="room" :data-pane="pane">
    <div v-if="room.connection.value.status === 'failed'" class="room__failed on-paper" role="alert">
      <h1 class="room__failed-title">Could not open this story</h1>
      <p>{{ room.connection.value.detail }}</p>
      <RouterLink to="/">Back to the shelf</RouterLink>
    </div>

    <template v-else>
      <nav class="room__tabs" aria-label="Show">
        <button
          v-for="item in PANES"
          :key="item.id"
          type="button"
          class="room__tab"
          :aria-pressed="pane === item.id"
          :data-pane="item.id"
          @click="show(item.id)"
        >
          {{ item.label }}
          <template v-if="changed[item.id]">
            <span class="room__tab-mark" aria-hidden="true"></span>
            <span class="sr-only">, updated</span>
          </template>
        </button>
      </nav>

      <div class="room__pane room__pane--conversation">
        <ConversationPane :room="room" :story="name" />
      </div>
      <div class="room__pane room__pane--book">
        <BookPane :files="files" :activity="state.activity" />
      </div>
    </template>
  </main>
</template>

<style scoped>
.room {
  display: grid;
  grid-template-columns: minmax(22rem, 33%) minmax(0, 1fr);
  gap: 2.5rem;
  height: 100%;
  padding: 1.75rem 3.25rem 2.25rem 2rem;
}

.room__pane {
  min-width: 0;
  min-height: 0;
}

.room__pane--book {
  padding-top: 0;
}

.room__tabs {
  display: none;
}

.room__failed {
  grid-column: 1 / -1;
  align-self: start;
  justify-self: center;
  max-width: 28rem;
  padding: 1.5rem 1.75rem;
  background: var(--card);
  color: var(--ink);
  border-radius: var(--radius-paper);
  box-shadow: var(--shadow-card);
}

.room__failed a {
  color: var(--accent);
}

.room__failed-title {
  margin: 0 0 0.5rem;
  font-size: var(--size-heading);
  font-style: italic;
  font-weight: 400;
}

/* A narrow screen shows one pane at a time, both kept in layout so their scroll positions survive. */
@media (max-width: 760px) {
  .room {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto minmax(0, 1fr);
    gap: 0.5rem;
    padding: 0.5rem 0.5rem max(0.5rem, env(safe-area-inset-bottom));
  }

  /* One segmented control: the shown pane is the lit half. */
  .room__tabs {
    display: flex;
    padding: 3px;
    border: 1px solid var(--desk-rule);
    border-radius: var(--radius-button);
  }

  .room__tab {
    position: relative;
    flex: 1 1 0;
    min-height: 40px;
    background: transparent;
    color: var(--ink-on-desk);
    border: 0;
    border-radius: var(--radius-paper);
  }

  .room__tab[aria-pressed='true'] {
    background: var(--paper);
    color: var(--ink);
    font-weight: 600;
  }

  .room__tab-mark {
    display: inline-block;
    width: 0.5rem;
    height: 0.5rem;
    margin-left: 0.4rem;
    vertical-align: 0.15em;
    background: var(--accent-soft);
    border-radius: var(--radius-round);
  }

  .room__pane {
    grid-row: 2;
    grid-column: 1;
  }

  .room[data-pane='conversation'] .room__pane--book,
  .room[data-pane='book'] .room__pane--conversation {
    visibility: hidden;
    pointer-events: none;
  }

  .room__pane--book {
    padding-top: 0;
  }
}
</style>
