<template>
  <div v-if="show" class="modal-overlay" @click="handleOverlayClick">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h2>{{ headerTitle }}</h2>
        <button class="btn-close" @click="emit('close')" title="Close">×</button>
      </div>

      <div class="modal-body">
        <!-- Step 1: Choice -->
        <div v-if="currentStep === 'choice'" class="step-choice">
          <p>How would you like to start your conversation?</p>
          <div class="choice-buttons">
            <button class="btn btn-primary btn-large" @click="selectGenerateScenario">
              Generate Scenario
            </button>
            <button class="btn btn-secondary btn-large" @click="selectSkipToChat">
              Skip to Chat
            </button>
          </div>
        </div>

        <!-- Step 2: Mood Selection -->
        <div v-if="currentStep === 'mood'" class="step-mood">
          <p>Select the mood for your scenarios:</p>
          <div class="mood-grid">
            <button
              v-for="mood in moodOptions"
              :key="mood"
              class="mood-button"
              :class="{ selected: selectedMood === mood }"
              @click="selectMood(mood)"
            >
              {{ mood }}
            </button>
          </div>
        </div>

        <!-- Step 3: Loading -->
        <div v-if="currentStep === 'loading'" class="step-loading">
          <div class="loading-spinner"></div>
          <p>Generating scenarios...</p>
          <p v-if="error" class="error-text">{{ error }}</p>
        </div>

        <!-- Step 4: Scenario Selection -->
        <div v-if="currentStep === 'scenario'" class="step-scenario">
          <div class="scenario-grid">
            <div
              v-for="(scenario, index) in scenarios"
              :key="index"
              class="scenario-card"
              @click="selectScenario(scenario)"
            >
              <h3 class="scenario-title">{{ scenario.summary }}</h3>
              <p
                class="scenario-intro"
                :class="{ expanded: expandedScenario === index }"
              >
                {{ scenario.intro_message }}
              </p>
              <div class="scenario-footer">
                <span class="scenario-category">{{ scenario.narrative_category }}</span>
                <button
                  class="btn-expand"
                  @click.stop="toggleExpanded(index)"
                >
                  {{ expandedScenario === index ? 'Show less' : 'Show more' }}
                </button>
              </div>
            </div>
          </div>
          <div class="step-actions">
            <button class="btn btn-secondary" @click="goBackToMood">
              Back to Mood Selection
            </button>
          </div>
        </div>

        <!-- Step 5: User Info -->
        <div v-if="currentStep === 'userInfo'" class="step-user-info">
          <p>Tell us about yourself:</p>
          <form @submit.prevent="startSession">
            <div class="form-group">
              <label for="userName">Your Name *</label>
              <input
                id="userName"
                v-model="userName"
                type="text"
                class="form-input"
                placeholder="Enter your name"
                required
              />
            </div>
            <div class="form-group">
              <label for="userDescription">Your Description (optional)</label>
              <textarea
                id="userDescription"
                v-model="userDescription"
                class="form-textarea"
                placeholder="Describe yourself in the roleplay..."
                rows="4"
              />
            </div>
            <div class="form-actions">
              <button type="button" class="btn btn-secondary" @click="goBack">
                Back
              </button>
              <button type="submit" class="btn btn-primary" :disabled="!userName.trim()">
                Start Session
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import type { Scenario } from '@/types'

interface Props {
  show: boolean
  characterName: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
}>()

const router = useRouter()
const { generateScenarios, startSessionWithScenario } = useApi()
const { settings, loadSettings } = useLocalSettings()

type Step = 'choice' | 'mood' | 'loading' | 'scenario' | 'userInfo'

const currentStep = ref<Step>('choice')
const selectedMood = ref<string>('')
const scenarios = ref<Scenario[]>([])
const selectedScenario = ref<Scenario | null>(null)
const expandedScenario = ref<number | null>(null)
const userName = ref('')
const userDescription = ref('')
const error = ref<string | null>(null)

const moodOptions = [
  'Normal',
  'Romantic',
  'Spicy',
  'Dark',
  'Unhinged',
  'Mysterious',
  'Comedic',
  'Dramatic',
  'Gritty',
  'Philosophical',
  'Chaotic'
]

const headerTitle = computed(() => {
  switch (currentStep.value) {
    case 'choice':
      return 'Start New Session'
    case 'mood':
      return 'Select Mood'
    case 'loading':
      return 'Generating Scenarios'
    case 'scenario':
      return 'Choose Scenario'
    case 'userInfo':
      return 'Your Information'
    default:
      return 'New Session'
  }
})

const selectGenerateScenario = () => {
  currentStep.value = 'mood'
}

const selectSkipToChat = () => {
  emit('close')
  router.push({
    name: 'chat',
    params: {
      characterName: props.characterName,
      sessionId: 'new'
    }
  })
}

const selectMood = (mood: string) => {
  selectedMood.value = mood
  generateScenariosForMood()
}

const generateScenariosForMood = async () => {
  currentStep.value = 'loading'
  error.value = null

  try {
    const response = await generateScenarios({
      character_name: props.characterName,
      count: 3,
      mood: selectedMood.value.toLowerCase(),
      processor_type: settings.value.aiProcessor,
      backup_processor_type: settings.value.backupProcessor
    })

    scenarios.value = response.scenarios
    currentStep.value = 'scenario'
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to generate scenarios'
    // Stay on loading step to show error
  }
}

const selectScenario = (scenario: Scenario) => {
  selectedScenario.value = scenario
  currentStep.value = 'userInfo'
}

const toggleExpanded = (index: number) => {
  expandedScenario.value = expandedScenario.value === index ? null : index
}

const goBack = () => {
  currentStep.value = 'scenario'
}

const goBackToMood = () => {
  currentStep.value = 'mood'
  scenarios.value = []
  selectedScenario.value = null
  expandedScenario.value = null
  error.value = null
}

const startSession = async () => {
  if (!selectedScenario.value || !userName.value.trim()) return

  try {
    const response = await startSessionWithScenario({
      character_name: props.characterName,
      intro_message: selectedScenario.value.intro_message,
      user_name: userName.value.trim(),
      user_description: userDescription.value.trim(),
      processor_type: settings.value.aiProcessor,
      backup_processor_type: settings.value.backupProcessor
    })

    // Navigate to chat with the new session
    emit('close')
    router.push({
      name: 'chat',
      params: {
        characterName: props.characterName,
        sessionId: response.session_id
      }
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to start session'
  }
}

const handleOverlayClick = () => {
  emit('close')
}

const resetModal = () => {
  currentStep.value = 'choice'
  selectedMood.value = ''
  scenarios.value = []
  selectedScenario.value = null
  expandedScenario.value = null
  userName.value = ''
  userDescription.value = ''
  error.value = null
}

// Reset modal state when it's closed, reload settings when it's opened
watch(() => props.show, (newShow) => {
  if (newShow) {
    // Reload settings to pick up any changes made in SettingsMenu
    loadSettings()
  } else {
    resetModal()
  }
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-content {
  background: var(--surface-color);
  border-radius: var(--radius-lg);
  max-width: 800px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h2 {
  margin: 0;
  color: var(--text-primary);
}

.btn-close {
  background: none;
  border: none;
  font-size: 2rem;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  transition: background-color 0.2s;
}

.btn-close:hover {
  background: var(--background-color);
}

.modal-body {
  padding: 2rem 1.5rem;
}

/* Step: Choice */
.step-choice {
  text-align: center;
}

.step-choice p {
  margin-bottom: 2rem;
  font-size: 1.125rem;
  color: var(--text-secondary);
}

.choice-buttons {
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
}

.btn-large {
  padding: 1.25rem 2.5rem;
  font-size: 1.125rem;
  min-width: 200px;
}

/* Step: Mood */
.step-mood p {
  margin-bottom: 1.5rem;
  color: var(--text-secondary);
  text-align: center;
}

.mood-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 0.75rem;
}

.mood-button {
  padding: 0.875rem 1rem;
  background: var(--background-color);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--text-primary);
  transition: all 0.2s;
  text-align: center;
}

.mood-button:hover {
  border-color: var(--primary-color);
  background: var(--surface-color);
}

.mood-button.selected {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: white;
}

/* Step: Loading */
.step-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  gap: 1.5rem;
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.step-loading p {
  color: var(--text-secondary);
  font-size: 1.125rem;
  margin: 0;
}

.error-text {
  color: var(--error-color);
  margin-top: 1rem;
}

/* Step: Scenario */
.step-scenario p {
  margin-bottom: 1.5rem;
  color: var(--text-secondary);
}

.scenario-grid {
  display: grid;
  gap: 1rem;
  margin-bottom: 2rem;
}

.step-actions {
  display: flex;
  justify-content: center;
}

.scenario-card {
  background: var(--background-color);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1.25rem;
  cursor: pointer;
  transition: all 0.2s;
}

.scenario-card:hover {
  border-color: var(--primary-color);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.scenario-title {
  margin: 0 0 1rem 0;
  font-size: 1.125rem;
  color: var(--text-primary);
}

.scenario-category {
  background: var(--primary-color);
  color: white;
  padding: 0.25rem 0.75rem;
  border-radius: var(--radius-sm);
  font-size: 0.8125rem;
  font-weight: 500;
  white-space: nowrap;
}

.scenario-intro {
  color: var(--text-secondary);
  line-height: 1.5;
  margin-bottom: 0.75rem;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.scenario-intro.expanded {
  display: block;
  -webkit-line-clamp: unset;
}

.scenario-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.btn-expand {
  background: none;
  border: none;
  color: var(--primary-color);
  cursor: pointer;
  font-size: 0.875rem;
  padding: 0;
  text-decoration: underline;
}

.btn-expand:hover {
  text-decoration: none;
}

/* Step: User Info */
.step-user-info p {
  margin-bottom: 1.5rem;
  color: var(--text-secondary);
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: var(--text-primary);
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 1rem;
  font-family: inherit;
  background: var(--background-color);
  color: var(--text-primary);
  transition: border-color 0.2s;
}

.form-input:focus,
.form-textarea:focus {
  outline: none;
  border-color: var(--primary-color);
}

.form-textarea {
  resize: vertical;
}

.form-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  margin-top: 2rem;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .modal-content {
    max-height: 95vh;
  }

  .modal-body {
    padding: 1.5rem 1rem;
  }

  .choice-buttons {
    flex-direction: column;
  }

  .btn-large {
    width: 100%;
  }

  .mood-grid {
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 0.5rem;
  }

  .mood-button {
    padding: 0.75rem 0.5rem;
    font-size: 0.875rem;
  }

  .scenario-footer {
    flex-wrap: wrap;
  }

  .form-actions {
    flex-direction: column-reverse;
  }

  .form-actions button {
    width: 100%;
  }
}

@media (max-width: 480px) {
  .modal-header {
    padding: 1rem;
  }

  .modal-header h2 {
    font-size: 1.25rem;
  }

  .mood-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
