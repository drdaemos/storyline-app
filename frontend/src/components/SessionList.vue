<template>
  <div class="session-list">
    <div class="session-header">
      <h3>Chat Sessions</h3>
      <button
        class="btn btn-primary"
        @click="emit('open-scenario-modal')"
      >
        Start New Session
      </button>
    </div>

    <div v-if="filteredSessions.length === 0" class="no-sessions">
      <p>No sessions found for this character.</p>
      <button class="btn btn-secondary" @click="emit('open-scenario-modal')">
        Start your first conversation
      </button>
    </div>

    <div v-else class="sessions-grid">
      <div
        v-for="session in filteredSessions"
        :key="session.session_id"
        class="session-card"
        @click="emit('select-session', session.session_id)"
      >
        <div class="session-info">
          <div class="session-header-row">
            <span class="session-id">{{ formatSessionId(session.session_id) }}</span>
            <time class="session-time">{{ formatRelativeTime(session.last_message_time) }}</time>
          </div>

          <div class="session-meta">
            <span class="message-count">{{ session.message_count }} messages</span>
          </div>

          <div v-if="session.last_character_response" class="session-preview">
            <p>{{ truncateText(session.last_character_response, 160) }}</p>
          </div>
        </div>

        <div class="session-actions">
          <button
            class="btn-icon delete-btn"
            @click.stop="showDeleteConfirmation(session.session_id)"
            :title="`Delete session ${formatSessionId(session.session_id)}`"
          >
            <Trash2 :size="16" />
          </button>
        </div>
      </div>
    </div>

    <ConfirmModal
      :show="showConfirmModal"
      title="Delete Session"
      message="Are you sure you want to delete this session? This action cannot be undone."
      confirm-text="Delete"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { SessionInfo } from '@/types'
import { formatRelativeTime, truncateText } from '@/utils/formatters'
import { useApi } from '@/composables/useApi'
import { Trash2 } from 'lucide-vue-next'
import ConfirmModal from './ConfirmModal.vue'

interface Props {
  sessions: SessionInfo[]
  characterName: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'select-session': [sessionId: string]
  'open-scenario-modal': []
  'session-deleted': [sessionId: string]
}>()

const { deleteSession: apiDeleteSession } = useApi()

const showConfirmModal = ref(false)
const sessionToDelete = ref<string | null>(null)

const filteredSessions = computed(() => {
  return props.sessions
    .filter(session => session.character_name === props.characterName)
    .sort((a, b) => new Date(b.last_message_time).getTime() - new Date(a.last_message_time).getTime())
})

const formatSessionId = (sessionId: string): string => {
  // Show first 8 characters of session ID
  return sessionId.substring(0, 8)
}

const showDeleteConfirmation = (sessionId: string) => {
  sessionToDelete.value = sessionId
  showConfirmModal.value = true
}

const confirmDelete = async () => {
  if (!sessionToDelete.value) return

  try {
    await apiDeleteSession(sessionToDelete.value)
    emit('session-deleted', sessionToDelete.value)
  } catch (err) {
    console.error('Failed to delete session:', err)
    // Error will be shown via the error state from useApi
  } finally {
    cancelDelete()
  }
}

const cancelDelete = () => {
  showConfirmModal.value = false
  sessionToDelete.value = null
}
</script>

<style scoped>
.session-list {
  max-width: 800px;
  margin: 0 auto;
}

.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-color);
}

.session-header h3 {
  margin: 0;
  color: var(--text-primary);
}

.no-sessions {
  text-align: center;
  padding: 3rem 2rem;
  color: var(--text-secondary);
}

.no-sessions p {
  margin: 0 0 1.5rem 0;
  font-size: 1.1rem;
}

.sessions-grid {
  display: grid;
  gap: 1rem;
}

.session-card {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.session-card:hover {
  border-color: var(--primary-color);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.session-id {
  font-weight: 600;
  color: var(--text-primary);
  font-family: monospace;
  font-size: 0.9rem;
}

.session-time {
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.session-meta {
  margin-bottom: 1rem;
}

.message-count {
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.session-preview {
  color: var(--text-secondary);
  font-size: 0.875rem;
  line-height: 1.4;
}

.session-preview p {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.session-actions {
  margin-left: 1rem;
  display: flex;
  gap: 0.5rem;
}

.btn-icon {
  background: none;
  border: none;
  padding: 0.5rem;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background-color 0.2s;
  font-size: 1rem;
}

.delete-btn:hover {
  background: #fee2e2;
}

.delete-btn:active {
  background: #fecaca;
}

@media (max-width: 768px) {
  .session-header {
    flex-direction: column;
    gap: 1rem;
    text-align: center;
  }

  .session-card {
    flex-direction: column;
    gap: 1rem;
  }

  .session-actions {
    margin-left: 0;
    align-self: flex-end;
  }

  .session-header-row {
    flex-direction: column;
    gap: 0.25rem;
    align-items: flex-start;
  }

  .no-sessions {
    padding: 2rem 1rem;
  }
}
</style>