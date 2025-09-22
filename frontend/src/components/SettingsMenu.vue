<template>
  <div v-if="show" class="settings-overlay" @click="closeMenu">
    <div class="settings-menu" @click.stop>
      <header class="settings-header">
        <h3>Settings</h3>
        <button class="close-button" @click="closeMenu">✕</button>
      </header>

      <div class="settings-content">
        <div class="setting-group">
          <label class="setting-label" for="ai-processor">
            AI Processor
          </label>
          <select
            id="ai-processor"
            class="setting-select"
            :value="settings.aiProcessor"
            @change="updateAiProcessor"
          >
            <option value="google">Google (Gemini)</option>
            <option value="gpt">OpenAI (GPT)</option>
            <option value="cohere">Cohere</option>
            <option value="claude">Anthropic (Claude)</option>
            <option value="grok">xAI (Grok)</option>
            <option value="deepseek">DeepSeek</option>
            <option value="gpt-oss">GPT OSS</option>
          </select>
          <p class="setting-description">
            Choose which AI model to use for new conversations. Changes apply to new sessions only.
          </p>
        </div>

        <div class="setting-group">
          <label class="setting-label" for="theme">
            Theme
          </label>
          <select
            id="theme"
            class="setting-select"
            :value="settings.theme"
            @change="updateTheme"
          >
            <option value="light">Light</option>
            <option value="dark">Dark</option>
            <option value="auto">Auto</option>
          </select>
          <p class="setting-description">
            Choose your preferred color theme. Auto follows your system preference.
          </p>
        </div>

        <div class="setting-group">
          <h4>Storage Info</h4>
          <div class="storage-info">
            <div class="info-item">
              <span class="info-label">Last Selected Character:</span>
              <span class="info-value">
                {{ settings.lastSelectedCharacter || 'None' }}
              </span>
            </div>
          </div>
        </div>

        <div class="setting-group">
          <button class="btn btn-secondary" @click="clearSettings">
            Clear All Settings
          </button>
          <p class="setting-description">
            Reset all settings to default values. This will not affect your conversations.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useLocalSettings } from '@/composables/useLocalSettings'

interface Props {
  show: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  'update:show': [show: boolean]
  'setting-changed': [payload: { key: string; value: any }]
}>()

const { settings, updateSetting } = useLocalSettings()

const closeMenu = () => {
  emit('update:show', false)
}

const updateAiProcessor = (event: Event) => {
  const target = event.target as HTMLSelectElement
  const value = target.value
  updateSetting('aiProcessor', value)
  emit('setting-changed', { key: 'aiProcessor', value })
}

const updateTheme = (event: Event) => {
  const target = event.target as HTMLSelectElement
  const value = target.value
  updateSetting('theme', value)
  emit('setting-changed', { key: 'theme', value })
}

const clearSettings = () => {
  if (confirm('Are you sure you want to reset all settings to default values?')) {
    localStorage.removeItem('storyline_ai_processor')
    localStorage.removeItem('storyline_theme')
    localStorage.removeItem('storyline_last_character')

    updateSetting('aiProcessor', 'google')
    updateSetting('theme', 'light')
    updateSetting('lastSelectedCharacter', undefined)

    emit('setting-changed', { key: 'all', value: null })
  }
}
</script>

<style scoped>
.settings-overlay {
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

.settings-menu {
  background: var(--surface-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  width: 100%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.settings-header h3 {
  margin: 0;
  color: var(--text-primary);
}

.close-button {
  background: none;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  transition: all 0.2s;
}

.close-button:hover {
  background: var(--background-color);
  color: var(--text-primary);
}

.settings-content {
  padding: 1.5rem;
}

.setting-group {
  margin-bottom: 2rem;
}

.setting-group:last-child {
  margin-bottom: 0;
}

.setting-label {
  display: block;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.setting-select {
  width: 100%;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--surface-color);
  color: var(--text-primary);
  font-size: 0.875rem;
  cursor: pointer;
  transition: border-color 0.2s;
}

.setting-select:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgb(37 99 235 / 0.1);
}

.setting-description {
  margin: 0.75rem 0 0 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

.setting-group h4 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  color: var(--text-primary);
}

.storage-info {
  background: var(--background-color);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1rem;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.info-label {
  font-weight: 500;
  color: var(--text-primary);
  font-size: 0.875rem;
}

.info-value {
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-family: monospace;
  text-align: right;
}

@media (max-width: 768px) {
  .settings-overlay {
    padding: 0;
    align-items: flex-end;
  }

  .settings-menu {
    width: 100%;
    max-width: none;
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    max-height: 80vh;
  }

  .settings-header {
    padding: 1.25rem;
  }

  .settings-content {
    padding: 1.25rem;
  }

  .info-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.25rem;
  }

  .info-value {
    text-align: left;
  }
}
</style>