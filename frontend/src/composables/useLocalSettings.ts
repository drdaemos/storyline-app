import { ref, watch, type Ref } from 'vue'
import type { LocalSettings } from '@/types'

const STORAGE_PREFIX = 'storyline_'

const defaultSettings: LocalSettings = {
  aiProcessor: 'google',
  backupProcessor: 'deepseek',
  lastSelectedCharacter: undefined
}

export function useLocalSettings() {
  const settings: Ref<LocalSettings> = ref({ ...defaultSettings })

  const loadSettings = () => {
    try {
      const aiProcessor = localStorage.getItem(`${STORAGE_PREFIX}ai_processor`)
      const backupProcessor = localStorage.getItem(`${STORAGE_PREFIX}backup_processor`)
      const lastSelectedCharacter = localStorage.getItem(`${STORAGE_PREFIX}last_character`)

      settings.value = {
        aiProcessor: aiProcessor || defaultSettings.aiProcessor,
        backupProcessor: backupProcessor || defaultSettings.backupProcessor,
        lastSelectedCharacter: lastSelectedCharacter || undefined
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
        localStorage.setItem(`${STORAGE_PREFIX}last_character`, settings.value.lastSelectedCharacter)
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

  // Watch for changes and auto-save
  watch(settings, saveSettings, { deep: true })

  // Load settings on initialization
  loadSettings()

  return {
    settings,
    loadSettings,
    updateSetting,
    clearSettings
  }
}