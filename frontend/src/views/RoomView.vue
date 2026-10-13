<script setup lang="ts">
import { computed, ref, toRef, watchEffect } from 'vue'
import { RouterLink } from 'vue-router'
import BookPane from '@/components/BookPane.vue'
import ConversationPane from '@/components/ConversationPane.vue'
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
          @click="pane = item.id"
        >
          {{ item.label }}
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
    gap: 0.75rem;
    padding: 0.75rem 1rem 1rem;
  }

  .room__tabs {
    display: flex;
    gap: 0.5rem;
  }

  .room__tab {
    flex: 1 1 0;
    min-height: 44px;
    background: transparent;
    color: var(--ink-on-desk);
    border: 1px solid var(--desk-rule);
    border-radius: var(--radius-button);
  }

  .room__tab[aria-pressed='true'] {
    background: var(--paper);
    color: var(--ink);
    border-color: var(--paper);
    font-weight: 600;
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
