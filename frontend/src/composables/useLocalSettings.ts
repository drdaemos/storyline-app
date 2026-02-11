import { ref, watch, type Ref } from 'vue'
import type { LocalSettings } from '@/types'

const STORAGE_PREFIX = 'storyline_'

const defaultSettings: LocalSettings = {
  largeModelKey: 'claude-sonnet',
  smallModelKey: 'deepseek-v32',
  selectedPersonaId: undefined,
  lastSelectedCharacter: undefined,
}

// Create a singleton ref that's shared across all component instances
const settings: Ref<LocalSettings> = ref({ ...defaultSettings })

export function useLocalSettings() {

  const loadSettings = () => {
    try {
      const aiProcessor = localStorage.getItem(`${STORAGE_PREFIX}ai_processor`)
      const backupProcessor = localStorage.getItem(`${STORAGE_PREFIX}backup_processor`)
      const selectedPersonaId = localStorage.getItem(`${STORAGE_PREFIX}selected_persona`)
      const lastSelectedCharacter = localStorage.getItem(`${STORAGE_PREFIX}last_character`)

      settings.value = {
        largeModelKey: aiProcessor || defaultSettings.largeModelKey,
        smallModelKey: backupProcessor || defaultSettings.smallModelKey,
        selectedPersonaId: selectedPersonaId || undefined,
        lastSelectedCharacter: lastSelectedCharacter || undefined,
      }
    } catch (error) {
      console.warn('Failed to load settings from localStorage, using defaults:', error)
      settings.value = { ...defaultSettings }
    }
  }

  const updateSetting = <K extends keyof LocalSettings>(key: K, value: LocalSettings[K]) => {
    settings.value[key] = value
  }

  const clearSettings = () => {
    try {
      settings.value = { ...defaultSettings }
    } catch (error) {
      console.error('Failed to clear settings from localStorage:', error)
    }
  }

  return {
    settings,
    loadSettings,
    updateSetting,
    clearSettings,
  }
}

// Initialize settings and set up watchers once at module level
let initialized = false
if (!initialized) {
  // Watch for changes and auto-save
  watch(settings, () => {
    try {
      localStorage.removeItem(`${STORAGE_PREFIX}last_character`)
      localStorage.setItem(`${STORAGE_PREFIX}ai_processor`, settings.value.largeModelKey)
      localStorage.setItem(`${STORAGE_PREFIX}backup_processor`, settings.value.smallModelKey)
      if (settings.value.selectedPersonaId) {
        localStorage.setItem(`${STORAGE_PREFIX}selected_persona`, settings.value.selectedPersonaId)
      } else {
        localStorage.removeItem(`${STORAGE_PREFIX}selected_persona`)
      }

      if (settings.value.lastSelectedCharacter) {
        localStorage.setItem(
          `${STORAGE_PREFIX}last_character`,
          settings.value.lastSelectedCharacter
        )
      }
    } catch (error) {
      console.error('Failed to save settings to localStorage:', error)
    }
  }, { deep: true })

  // Load settings on initialization
  try {
    const aiProcessor = localStorage.getItem(`${STORAGE_PREFIX}ai_processor`)
    const backupProcessor = localStorage.getItem(`${STORAGE_PREFIX}backup_processor`)
    const selectedPersonaId = localStorage.getItem(`${STORAGE_PREFIX}selected_persona`)
    const lastSelectedCharacter = localStorage.getItem(`${STORAGE_PREFIX}last_character`)

    settings.value = {
      largeModelKey: aiProcessor || defaultSettings.largeModelKey,
      smallModelKey: backupProcessor || defaultSettings.smallModelKey,
      selectedPersonaId: selectedPersonaId || undefined,
      lastSelectedCharacter: lastSelectedCharacter || undefined,
    }
  } catch (error) {
    console.warn('Failed to load settings from localStorage, using defaults:', error)
    settings.value = { ...defaultSettings }
  }

  initialized = true
}
