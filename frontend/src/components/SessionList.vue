<template>
  <div class="max-w-4xl mx-auto space-y-6">
    <div v-if="filteredSessions.length > 0" class="flex items-center justify-between">
      <div>
        <h3 class="text-xl font-semibold">Chat Sessions</h3>
        <p class="text-sm text-gray-500 mt-1">Continue your conversations with {{ characterName }}</p>
      </div>
      <UButton
        color="primary"
        icon="i-lucide-plus"
        @click="emit('open-scenario-modal')"
      >
        New Session
      </UButton>
    </div>

    <div v-if="filteredSessions.length === 0" class="text-center py-16">
      <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
        <span class="i-lucide-message-square w-8 h-8 text-gray-400" />
      </div>
      <h4 class="text-lg font-medium mb-2">No conversations yet</h4>
      <p class="text-gray-500 mb-6">Start your first conversation with {{ characterName }}</p>
      <UButton
        color="primary"
        icon="i-lucide-plus"
        @click="emit('open-scenario-modal')"
      >
        Start Conversation
      </UButton>
    </div>

    <div v-else class="space-y-3">
      <UCard
        v-for="session in filteredSessions"
        :key="session.session_id"
        class="hover:shadow-md transition-shadow cursor-pointer group"
        @click="emit('select-session', session.session_id)"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-3 mb-2">
              <UBadge color="primary" variant="subtle" size="sm">
                {{ formatSessionId(session.session_id) }}
              </UBadge>
              <span class="text-xs text-gray-500">
                {{ formatRelativeTime(session.last_message_time) }}
              </span>
              <UBadge color="neutral" variant="subtle" size="sm">
                {{ session.message_count }} messages
              </UBadge>
            </div>

            <p v-if="session.last_character_response" class="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
              {{ session.last_character_response }}
            </p>
          </div>

          <UButton
            color="neutral"
            variant="ghost"
            icon="i-lucide-trash-2"
            size="sm"
            class="opacity-0 group-hover:opacity-100 transition-opacity"
            @click.stop="showDeleteConfirmation(session.session_id)"
          />
        </div>
      </UCard>
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
import { formatRelativeTime } from '@/utils/formatters'
import { useApi } from '@/composables/useApi'
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
    .filter((session) => session.character_name === props.characterName)
    .sort(
      (a, b) => new Date(b.last_message_time).getTime() - new Date(a.last_message_time).getTime()
    )
})

const formatSessionId = (sessionId: string): string => {
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
  } finally {
    cancelDelete()
  }
}

const cancelDelete = () => {
  showConfirmModal.value = false
  sessionToDelete.value = null
}
</script>
