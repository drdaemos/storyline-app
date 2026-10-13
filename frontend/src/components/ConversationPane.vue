<script setup lang="ts">
import { computed } from 'vue'
import { activityLabel, isWorking } from '@/room/roomState'
import type { Room } from '@/room/useRoom'
import AgendaCard from './AgendaCard.vue'
import Composer from './Composer.vue'
import ConversationLog from './ConversationLog.vue'
import RoomHeader from './RoomHeader.vue'

const props = defineProps<{ room: Room; story: string }>()

const state = computed(() => props.room.state.value)
const connection = computed(() => props.room.connection.value)
const working = computed(() => isWorking(state.value))
const activity = computed(() => activityLabel(state.value))
</script>

<template>
  <section class="conversation" aria-label="Conversation with the writer">
    <RoomHeader
      :story="story"
      :model-name="state.modelName"
      :working="working"
      @change-model="room.changeModel"
      @undo="room.undo"
      @clear="room.clear"
    />
    <p v-if="connection.status === 'reconnecting'" class="conversation__status" role="status">
      Connection lost. Reconnecting…
    </p>
    <AgendaCard :items="state.agenda" :error="state.agendaError" />
    <ConversationLog :entries="state.entries" :hidden-entries="state.hiddenEntries" :activity="activity" />
    <Composer
      :draft="state.draft"
      :working="working"
      :queue="state.queue"
      :disabled="connection.status === 'failed'"
      @update:draft="room.setDraft"
      @send="room.send"
      @stop="room.stop"
    />
  </section>
</template>

<style scoped>
.conversation {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  height: 100%;
  min-height: 0;
  min-width: 0;
  padding: 1.15rem 1.35rem 1.35rem;
  background: var(--surface-blotter);
  border-radius: var(--radius-blotter);
  box-shadow: var(--shadow-blotter);
}

/* A tooled line just inside the pad's edge. */
.conversation::before {
  content: '';
  position: absolute;
  inset: 7px;
  border: 1px solid var(--blotter-tooling);
  border-radius: calc(var(--radius-blotter) - 4px);
  pointer-events: none;
}

.conversation > * {
  position: relative;
}

@media (max-width: 760px) {
  .conversation {
    padding: 0.9rem 0.9rem 1rem;
    gap: 0.75rem;
  }
}

.conversation__status {
  flex: none;
  margin: 0;
  color: var(--ink-on-desk-muted);
  font-style: italic;
}
</style>
