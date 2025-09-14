import { ref, watch, type Ref } from 'vue'
import type { LocalSettings } from '@/types'

const STORAGE_PREFIX = 'storyline_'

const defaultSettings: LocalSettings = {
  aiProcessor: 'google',
  theme: 'light'
}

export function useLocalSettings() {
  const settings: Ref<LocalSettings> = ref({ ...defaultSettings })

  const loadSettings = () => {
    try {
      const aiProcessor = localStorage.getItem(`${STORAGE_PREFIX}ai_processor`)
      const theme = localStorage.getItem(`${STORAGE_PREFIX}theme`)
      const lastSelectedCharacter = localStorage.getItem(`${STORAGE_PREFIX}last_character`)

      settings.value = {
        aiProcessor: aiProcessor || defaultSettings.aiProcessor,
        theme: theme || defaultSettings.theme,
        lastSelectedCharacter: lastSelectedCharacter || undefined
      }
    } catch (error) {
      console.warn('Failed to load settings from localStorage:', error)
      settings.value = { ...defaultSettings }
    }
  }

  const saveSettings = () => {
    try {
      localStorage.setItem(`${STORAGE_PREFIX}ai_processor`, settings.value.aiProcessor)
      localStorage.setItem(`${STORAGE_PREFIX}theme`, settings.value.theme)

      if (settings.value.lastSelectedCharacter) {
        localStorage.setItem(`${STORAGE_PREFIX}last_character`, settings.value.lastSelectedCharacter)
      }
    } catch (error) {
      console.warn('Failed to save settings to localStorage:', error)
    }
  }

  const updateSetting = <K extends keyof LocalSettings>(key: K, value: LocalSettings[K]) => {
    settings.value[key] = value
    saveSettings()
  }

  // Watch for changes and auto-save
  watch(settings, saveSettings, { deep: true })

  // Load settings on initialization
  loadSettings()

  return {
    settings,
    loadSettings,
    updateSetting
  }
}