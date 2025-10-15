<template>
  <!-- Header with back button -->
  <div class="flex mb-8 gap-4">
    <UButton
      color="neutral"
      variant="ghost"
      icon="i-lucide-arrow-left"
      @click="navigateBack"
    >
      Back
    </UButton>
  </div>

  <!-- Loading state -->
  <div v-if="loading" class="flex items-center justify-center py-16">
    <div class="text-center space-y-4">
      <UIcon name="i-lucide-loader-2" class="w-12 h-12 animate-spin text-primary mx-auto" />
      <p class="text-gray-500">Loading character information...</p>
    </div>
  </div>

  <!-- Error state -->
  <UAlert
    v-else-if="error"
    color="error"
    variant="soft"
    icon="i-lucide-alert-triangle"
    title="Failed to load character information"
    :description="error.message"
  >
    <template #actions>
      <UButton color="error" variant="solid" @click="loadCharacterData">
        Try Again
      </UButton>
    </template>
  </UAlert>

  <!-- Character Info and Sessions -->
  <div v-else>
    <div class="mb-8 text-center">
      <UAvatar
        :alt="characterInfo?.name || 'Character Avatar'"
        size="xl"
        class="mx-auto mb-4"
      >
        <template #fallback>
          <span class="text-3xl font-semibold">
            {{ characterInfo?.name || 'Character' }}
          </span>
        </template>
      </UAvatar>
      <h2 class="text-2xl font-bold font-serif">{{ characterInfo?.name }}</h2>
      <p v-if="characterInfo?.role" class="text-gray-600 dark:text-gray-400 mt-1">
        {{ characterInfo.role }}
      </p>
    </div>

    <SessionList
      :sessions="sessions"
      :character-name="characterId"
      @select-session="navigateToChat"
      @open-scenario-modal="openScenarioModal"
      @session-deleted="handleSessionDeleted"
    />
  </div>

  <!-- Scenario Selection Modal -->
  <ScenarioSelectionModal
    :show="showScenarioModal"
    :character-name="characterId"
    @close="closeScenarioModal"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useApi } from '@/composables/useApi'
import SessionList from '@/components/SessionList.vue'
import ScenarioSelectionModal from '@/components/ScenarioSelectionModal.vue'
import type { SessionInfo } from '@/types'

const router = useRouter()
const route = useRoute()
const { getCharacterInfo, getSessions, loading, error } = useApi()

const characterId = ref(route.params.characterId as string)
const characterInfo = ref<Record<string, string> | null>(null)
const sessions = ref<SessionInfo[]>([])
const showScenarioModal = ref(false)

const loadCharacterData = async () => {
  try {
    const [info, sessionList] = await Promise.all([
      getCharacterInfo(characterId.value),
      getSessions(),
    ])

    characterInfo.value = info
    sessions.value = sessionList
  } catch (err) {
    console.error('Failed to load character data:', err)
  }
}

const navigateBack = () => {
  router.push({ name: 'start' })
}

const navigateToChat = (sessionId: string) => {
  router.push({
    name: 'chat',
    params: {
      characterName: characterId.value,
      sessionId,
    },
  })
}

const openScenarioModal = () => {
  showScenarioModal.value = true
}

const closeScenarioModal = () => {
  showScenarioModal.value = false
}

const handleSessionDeleted = (sessionId: string) => {
  sessions.value = sessions.value.filter((session) => session.session_id !== sessionId)
}

onMounted(() => {
  loadCharacterData()
})
</script>
