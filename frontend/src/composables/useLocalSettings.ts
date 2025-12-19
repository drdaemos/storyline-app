import { ref, watch, type Ref } from 'vue'
import type { LocalSettings } from '@/types'

const STORAGE_PREFIX = 'storyline_'

const defaultSettings: LocalSettings = {
  aiProcessor: 'google-flash',
  backupProcessor: 'deepseek-v32',
  lastSelectedCharacter: undefined,
  selectedPersonaId: undefined,
}

// Create a singleton ref that's shared across all component instances
const settings: Ref<LocalSettings> = ref({ ...defaultSettings })

export function useLocalSettings() {

  const loadSettings = () => {
    try {
      const aiProcessor = localStorage.getItem(`${STORAGE_PREFIX}ai_processor`)
      const backupProcessor = localStorage.getItem(`${STORAGE_PREFIX}backup_processor`)
      const lastSelectedCharacter = localStorage.getItem(`${STORAGE_PREFIX}last_character`)
      const selectedPersonaId = localStorage.getItem(`${STORAGE_PREFIX}selected_persona`)

      settings.value = {
        aiProcessor: aiProcessor || defaultSettings.aiProcessor,
        backupProcessor: backupProcessor || defaultSettings.backupProcessor,
        lastSelectedCharacter: lastSelectedCharacter || undefined,
        selectedPersonaId: selectedPersonaId || undefined,
      }
    } catch (error) {
      console.warn('Failed to load settings from localStorage, using defaults:', error)
      settings.value = { ...defaultSettings }
    }
  }

  const saveSettings = () => {
    try {
      localStorage.removeItem(`{STORAGE_PREFIX}last_character`)
      localStorage.setItem(`${STORAGE_PREFIX}ai_processor`, settings.value.aiProcessor)
      localStorage.setItem(`${STORAGE_PREFIX}backup_processor`, settings.value.backupProcessor)

      if (settings.value.lastSelectedCharacter) {
        localStorage.setItem(
          `${STORAGE_PREFIX}last_character`,
          settings.value.lastSelectedCharacter
        )
      }

      if (settings.value.selectedPersonaId && settings.value.selectedPersonaId !== 'none') {
        localStorage.setItem(
          `${STORAGE_PREFIX}selected_persona`,
          settings.value.selectedPersonaId
        )
      } else {
        localStorage.removeItem(`${STORAGE_PREFIX}selected_persona`)
      }
    } catch (error) {
      console.error('Failed to save settings to localStorage:', error)
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
      localStorage.removeItem(`{STORAGE_PREFIX}last_character`)
      localStorage.setItem(`${STORAGE_PREFIX}ai_processor`, settings.value.aiProcessor)
      localStorage.setItem(`${STORAGE_PREFIX}backup_processor`, settings.value.backupProcessor)

      if (settings.value.lastSelectedCharacter) {
        localStorage.setItem(
          `${STORAGE_PREFIX}last_character`,
          settings.value.lastSelectedCharacter
        )
      }

      if (settings.value.selectedPersonaId && settings.value.selectedPersonaId !== 'none') {
        localStorage.setItem(
          `${STORAGE_PREFIX}selected_persona`,
          settings.value.selectedPersonaId
        )
      } else {
        localStorage.removeItem(`${STORAGE_PREFIX}selected_persona`)
      }
    } catch (error) {
      console.error('Failed to save settings to localStorage:', error)
    }
  }, { deep: true })

  // Load settings on initialization
  try {
    const aiProcessor = localStorage.getItem(`${STORAGE_PREFIX}ai_processor`)
    const backupProcessor = localStorage.getItem(`${STORAGE_PREFIX}backup_processor`)
    const lastSelectedCharacter = localStorage.getItem(`${STORAGE_PREFIX}last_character`)
    const selectedPersonaId = localStorage.getItem(`${STORAGE_PREFIX}selected_persona`)

    settings.value = {
      aiProcessor: aiProcessor || defaultSettings.aiProcessor,
      backupProcessor: backupProcessor || defaultSettings.backupProcessor,
      lastSelectedCharacter: lastSelectedCharacter || undefined,
      selectedPersonaId: selectedPersonaId || undefined,
    }
  } catch (error) {
    console.warn('Failed to load settings from localStorage, using defaults:', error)
    settings.value = { ...defaultSettings }
  }

  initialized = true
}
