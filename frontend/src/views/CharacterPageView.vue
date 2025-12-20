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
      <div class="flex items-center justify-center gap-3">
        <h2 class="text-2xl font-bold font-serif">{{ characterInfo?.name }}</h2>
        <UButton
          color="neutral"
          variant="ghost"
          icon="i-lucide-pencil"
          size="sm"
          @click="navigateToEdit"
        />
      </div>
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

    <!-- Saved Scenarios Section -->
    <div v-if="savedScenarios.length > 0" class="mt-8">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold font-serif">Saved Scenarios</h3>
        <UButton
          color="neutral"
          variant="ghost"
          icon="i-lucide-plus"
          size="sm"
          @click="navigateToCreateScenario"
        >
          Create New
        </UButton>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <UCard
          v-for="scenario in savedScenarios"
          :key="scenario.id"
          class="cursor-pointer hover:ring-2 hover:ring-primary transition-all"
          @click="startSessionWithSavedScenario(scenario.id)"
        >
          <div class="space-y-2">
            <div class="flex items-start justify-between gap-2">
              <h4 class="font-semibold line-clamp-1">{{ scenario.summary }}</h4>
              <UButton
                color="neutral"
                variant="ghost"
                icon="i-lucide-trash-2"
                size="xs"
                @click.stop="deleteScenarioById(scenario.id)"
              />
            </div>
            <UBadge v-if="scenario.narrative_category" color="primary" variant="subtle" size="sm">
              {{ scenario.narrative_category }}
            </UBadge>
            <p class="text-xs text-gray-500 dark:text-gray-400">
              Created {{ formatDate(scenario.created_at) }}
            </p>
          </div>
        </UCard>
      </div>
    </div>
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
import { useLocalSettings } from '@/composables/useLocalSettings'
import SessionList from '@/components/SessionList.vue'
import ScenarioSelectionModal from '@/components/ScenarioSelectionModal.vue'
import type { SessionInfo, ScenarioSummary } from '@/types'

const router = useRouter()
const route = useRoute()
const { getCharacterInfo, getSessions, listScenariosForCharacter, deleteScenario, startSessionWithScenario, loading, error } = useApi()
const { settings } = useLocalSettings()

const characterId = ref(route.params.characterId as string)
const characterInfo = ref<Record<string, string> | null>(null)
const sessions = ref<SessionInfo[]>([])
const savedScenarios = ref<ScenarioSummary[]>([])
const showScenarioModal = ref(false)

const loadCharacterData = async () => {
  try {
    const [info, sessionList, scenarioList] = await Promise.all([
      getCharacterInfo(characterId.value),
      getSessions(),
      listScenariosForCharacter(characterId.value).catch(() => ({ scenarios: [] })),
    ])

    characterInfo.value = info
    sessions.value = sessionList
    savedScenarios.value = scenarioList.scenarios || []
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

const navigateToCreateScenario = () => {
  router.push({
    name: 'create-scenario',
    params: {
      characterId: characterId.value,
    },
  })
}

const startSessionWithSavedScenario = async (scenarioId: string) => {
  try {
    const response = await startSessionWithScenario({
      character_name: characterId.value,
      scenario_id: scenarioId,
      persona_id: settings.value.selectedPersonaId || null,
      processor_type: settings.value.aiProcessor,
      backup_processor_type: settings.value.backupProcessor,
    })

    router.push({
      name: 'chat',
      params: {
        characterId: characterId.value,
        sessionId: response.session_id,
      },
    })
  } catch (err) {
    console.error('Failed to start session with scenario:', err)
  }
}

const deleteScenarioById = async (scenarioId: string) => {
  if (!confirm('Are you sure you want to delete this scenario?')) {
    return
  }

  try {
    await deleteScenario(scenarioId)
    savedScenarios.value = savedScenarios.value.filter((s) => s.id !== scenarioId)
  } catch (err) {
    console.error('Failed to delete scenario:', err)
  }
}

const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

onMounted(() => {
  loadCharacterData()
})
</script>
