<template>
  <section class="space-y-8">
    <div class="story-panel p-5 md:p-7">
      <div class="flex flex-wrap items-center gap-3 justify-between">
        <UButton
          color="neutral"
          variant="ghost"
          icon="i-lucide-arrow-left"
          @click="navigateBack"
        >
          Back
        </UButton>
        <UButton
          color="neutral"
          variant="soft"
          icon="i-lucide-pencil"
          @click="navigateToEdit"
        >
          Edit Character
        </UButton>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="flex items-center justify-center py-16">
      <div class="text-center space-y-4">
        <UIcon name="i-lucide-loader-2" class="w-12 h-12 animate-spin text-primary mx-auto" />
        <p class="story-subtext">Loading character information...</p>
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
      <div class="mb-8 text-center story-panel p-8">
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
        <div class="flex items-center justify-center gap-3">
          <h2 class="text-3xl story-headline">{{ characterInfo?.name }}</h2>
        </div>
        <p v-if="characterInfo?.tagline" class="story-subtext mt-2">
          {{ characterInfo.tagline }}
        </p>
      </div>

      <SessionList
        :sessions="sessions"
        :character-name="characterId"
        @select-session="navigateToChat"
        @open-scenario-modal="openScenarioModal"
        @session-deleted="handleSessionDeleted"
      />

      <div class="mt-8 story-panel p-6">
        <h3 class="text-2xl story-headline mb-2">Scenario Assets</h3>
        <p class="story-subtext mb-4">
          Scenario and world lore assets are now managed globally.
        </p>
        <div class="flex gap-2 flex-wrap">
          <UButton
            color="primary"
            icon="i-lucide-plus"
            size="sm"
            @click="navigateToCreateScenario"
          >
            Create Scenario
          </UButton>
          <UButton
            color="neutral"
            variant="soft"
            icon="i-lucide-library"
            size="sm"
            @click="navigateToScenarioLibrary"
          >
            Open Scenario Library
          </UButton>
        </div>
      </div>
    </div>

    <!-- Scenario Selection Modal -->
    <ScenarioSelectionModal
      :show="showScenarioModal"
      :character-name="characterId"
      @close="closeScenarioModal"
    />
  </section>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useApi } from '@/composables/useApi'
import SessionList from '@/components/SessionList.vue'
import ScenarioSelectionModal from '@/components/ScenarioSelectionModal.vue'
import type { Character, SessionInfo } from '@/types'

const router = useRouter()
const route = useRoute()
const { getCharacterInfo, getSessions, loading, error } = useApi()

const characterId = ref(route.params.characterId as string)
const characterInfo = ref<Character | null>(null)
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

const navigateToEdit = () => {
  router.push({ name: 'edit-character', params: { characterId: characterId.value } })
}

const navigateToChat = (sessionId: string) => {
  router.push({
    name: 'chat',
    params: {
      characterId: characterId.value,
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

const navigateToCreateScenario = () => {
  router.push({
    name: 'create-scenario-global',
    query: { characterIds: characterId.value },
  })
}

const navigateToScenarioLibrary = () => {
  router.push({ name: 'library-scenarios' })
}

onMounted(() => {
  loadCharacterData()
})
</script>
