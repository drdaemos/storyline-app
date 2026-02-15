import { ref, watch, type Ref } from 'vue'
import type { LocalSettings } from '@/types'

const STORAGE_PREFIX = 'storyline_'

const defaultSettings: LocalSettings = {
  aiProcessor: 'google-flash',
  backupProcessor: 'deepseek-v32',
  lastSelectedCharacter: undefined,
  selectedPersonaId: undefined,
}

const settings: Ref<LocalSettings> = ref({ ...defaultSettings })

const loadSettingsFromStorage = (): LocalSettings => {
  try {
    return {
      aiProcessor:
        localStorage.getItem(`${STORAGE_PREFIX}ai_processor`) || defaultSettings.aiProcessor,
      backupProcessor:
        localStorage.getItem(`${STORAGE_PREFIX}backup_processor`) ||
        defaultSettings.backupProcessor,
      lastSelectedCharacter:
        localStorage.getItem(`${STORAGE_PREFIX}last_character`) ||
        defaultSettings.lastSelectedCharacter,
      selectedPersonaId:
        localStorage.getItem(`${STORAGE_PREFIX}selected_persona`) ||
        defaultSettings.selectedPersonaId,
    }
  } catch {
    return { ...defaultSettings }
  }
}

const persistSettings = () => {
  try {
    localStorage.setItem(`${STORAGE_PREFIX}ai_processor`, settings.value.aiProcessor)
    localStorage.setItem(`${STORAGE_PREFIX}backup_processor`, settings.value.backupProcessor)

    if (settings.value.lastSelectedCharacter) {
      localStorage.setItem(`${STORAGE_PREFIX}last_character`, settings.value.lastSelectedCharacter)
    } else {
      localStorage.removeItem(`${STORAGE_PREFIX}last_character`)
    }

    if (settings.value.selectedPersonaId) {
      localStorage.setItem(`${STORAGE_PREFIX}selected_persona`, settings.value.selectedPersonaId)
    } else {
      localStorage.removeItem(`${STORAGE_PREFIX}selected_persona`)
    }
  } catch {
    // Ignore storage write failures and keep in-memory settings.
  }
}

export function useLocalSettings() {
  const loadSettings = () => {
    settings.value = loadSettingsFromStorage()
  }

  const updateSetting = <K extends keyof LocalSettings>(key: K, value: LocalSettings[K]) => {
    settings.value[key] = value
  }

  const clearSettings = () => {
    settings.value = { ...defaultSettings }

    try {
      localStorage.removeItem(`${STORAGE_PREFIX}ai_processor`)
      localStorage.removeItem(`${STORAGE_PREFIX}backup_processor`)
      localStorage.removeItem(`${STORAGE_PREFIX}last_character`)
      localStorage.removeItem(`${STORAGE_PREFIX}selected_persona`)
    } catch {
      // Ignore storage clear failures.
    }
  }

  return {
    settings,
    loadSettings,
    updateSetting,
    clearSettings,
  }
}

let initialized = false
if (!initialized) {
  settings.value = loadSettingsFromStorage()

  watch(
    settings,
    () => {
      persistSettings()
    },
    { deep: true }
  )

  initialized = true
}
