<template>
  <div class="start-view">
    <div class="start-content">
      <header class="view-header">
        <div class="header-main">
          <button class="btn btn-secondary" @click="deselectCharacter">
            <ArrowLeft :size="20" />
          </button>
          <h2>Choose a Character</h2>
          <button
            class="btn btn-secondary btn-settings"
            @click="showSettings = !showSettings"
          >
            <Settings :size="20" />
          </button>
        </div>

        <div v-if="loading" class="loading-state">
          <div class="loading-spinner"></div>
          <span>Loading characters...</span>
        </div>

        <div v-if="error" class="error-state">
          <p>{{ error.message }}</p>
          <button class="btn btn-primary" @click="loadCharacters">
            Try Again
          </button>
        </div>
      </header>

      <!-- Character Grid -->
      <div v-if="!selectedCharacter" class="character-section">
        <div class="characters-grid">
          <CharacterCard
            v-for="character in characters"
            :key="character"
            :character="character"
            :selected="false"
            @select="selectCharacter"
          />

          <CharacterCard
            :is-create-new="true"
            @create="navigateToCreate"
          />
        </div>
      </div>

      <!-- Session List -->
      <div v-else class="session-section">
        <div class="selected-character-info">
          <h2>{{ selectedCharacter }}</h2>
          <p v-if="selectedCharacterInfo?.role">
            {{ selectedCharacterInfo.role }}
          </p>
        </div>

        <SessionList
          :sessions="sessions"
          :character-name="selectedCharacter"
          @select-session="navigateToChat"
          @open-scenario-modal="openScenarioModal"
          @session-deleted="handleSessionDeleted"
        />
      </div>
    </div>

    <!-- Settings Menu -->
    <SettingsMenu
      v-model:show="showSettings"
      @setting-changed="handleSettingChanged"
    />

    <!-- Scenario Selection Modal -->
    <ScenarioSelectionModal
      :show="showScenarioModal"
      :character-name="selectedCharacter || ''"
      @close="closeScenarioModal"
    />
  </div>
</template>

<script setup lang="ts">
// biome-ignore lint/style/useNamingConvention: Vue template functions need specific names
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import CharacterCard from '@/components/CharacterCard.vue'
import SessionList from '@/components/SessionList.vue'
import SettingsMenu from '@/components/SettingsMenu.vue'
import ScenarioSelectionModal from '@/components/ScenarioSelectionModal.vue'
import type { SessionInfo } from '@/types'
import { Settings, ArrowLeft } from 'lucide-vue-next'

const router = useRouter()
const { getCharacters, getCharacterInfo, getSessions, loading, error } = useApi()
const { settings, updateSetting } = useLocalSettings()

const characters = ref<string[]>([])
const sessions = ref<SessionInfo[]>([])
const selectedCharacter = ref<string | null>(null)
const selectedCharacterInfo = ref<Record<string, string> | null>(null)
const showSettings = ref(false)
const showScenarioModal = ref(false)

const loadCharacters = async () => {
  try {
    characters.value = await getCharacters()

    // Auto-select last selected character if available
    if (settings.value.lastSelectedCharacter &&
        characters.value.includes(settings.value.lastSelectedCharacter)) {
      await selectCharacter(settings.value.lastSelectedCharacter)
    }
  } catch (err) {
    console.error('Failed to load characters:', err)
  }
}

const loadSessions = async () => {
  try {
    sessions.value = await getSessions()
  } catch (err) {
    console.error('Failed to load sessions:', err)
  }
}

const selectCharacter = async (characterName: string) => {
  selectedCharacter.value = characterName
  updateSetting('lastSelectedCharacter', characterName)

  try {
    // Load character info and sessions in parallel
    const [characterInfo] = await Promise.all([
      getCharacterInfo(characterName),
      loadSessions()
    ])

    selectedCharacterInfo.value = characterInfo
  } catch (err) {
    console.error('Failed to select character or load character info:', err)
  }
}

const deselectCharacter = () => {
  selectedCharacter.value = null
  selectedCharacterInfo.value = null
}

const navigateToChat = (sessionId: string) => {
  if (selectedCharacter.value) {
    router.push({
      name: 'chat',
      params: {
        characterName: selectedCharacter.value,
        sessionId
      }
    })
  }
}

const openScenarioModal = () => {
  showScenarioModal.value = true
}

const closeScenarioModal = () => {
  showScenarioModal.value = false
}

const navigateToCreate = () => {
  router.push({ name: 'create' })
}

const handleSessionDeleted = (sessionId: string) => {
  sessions.value = sessions.value.filter(session => session.session_id !== sessionId)
}

const handleSettingChanged = (_payload: { key: string; value: any }) => {
  // Settings are automatically persisted via the composable
}

onMounted(() => {
  loadCharacters()
})
</script>

<style scoped>
.start-view {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.start-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
  width: 100%;
}

.view-header {
  margin-bottom: 2rem;
}

.btn-settings {
  margin-left: auto;
}

.loading-state,
.error-state {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  border-radius: var(--radius-md);
  background: var(--background-color);
  border: 1px solid var(--border-color);
}

.loading-state {
  color: var(--text-secondary);
}

.error-state {
  color: var(--error-color);
  background: #fef2f2;
  border-color: #fecaca;
}

.character-section {
  animation: fadeIn 0.3s ease-out;
}

.characters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
}

.session-section {
  animation: fadeIn 0.3s ease-out;
}

.selected-character-info {
  text-align: center;
  margin-bottom: 2rem;
  padding: 2rem;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.selected-character-info h2 {
  margin: 0 0 0.5rem 0;
  color: var(--text-primary);
  font-size: 2rem;
}

.selected-character-info p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 1.125rem;
  font-style: italic;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 768px) {
  .start-content {
    padding: 1.5rem 1rem;
  }

  .header-main {
    gap: 1rem;
  }

  .header-main h2 {
    font-size: 1.75rem;
  }

  .characters-grid {
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 1rem;
  }

  .selected-character-info {
    padding: 1.5rem;
  }

  .selected-character-info h2 {
    font-size: 1.75rem;
  }

  .loading-state,
  .error-state {
    flex-direction: column;
    text-align: center;
  }
}

@media (max-width: 480px) {
  .characters-grid {
    grid-template-columns: 1fr;
  }

  .header-main h2 {
    font-size: 1.5rem;
  }

  .selected-character-info h2 {
    font-size: 1.5rem;
  }
}

/* Icon utility classes */
.inline {
  display: inline-block;
  vertical-align: middle;
}

.mr-1 {
  margin-right: 0.25rem;
}
</style>