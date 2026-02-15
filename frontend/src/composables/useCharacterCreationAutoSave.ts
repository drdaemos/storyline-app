import { ref, watch, type Ref } from 'vue'
import type { ChatMessage } from '@/types'

const STORAGE_KEY_CHARACTER = 'character-creation-draft'
const STORAGE_KEY_MESSAGES = 'character-creation-messages'

type AutoSaveStatus = 'saved' | 'saving' | 'idle'

export function useCharacterCreationAutoSave<T extends Record<string, unknown>>(
  formData: T,
  messages: Ref<ChatMessage[]>,
  storageKeyPrefix?: string
) {
  const dataKey = storageKeyPrefix ? `${storageKeyPrefix}-draft` : STORAGE_KEY_CHARACTER
  const messagesKey = storageKeyPrefix ? `${storageKeyPrefix}-messages` : STORAGE_KEY_MESSAGES

  const autoSaveStatus = ref<AutoSaveStatus>('idle')

  const saveToLocalStorage = () => {
    try {
      autoSaveStatus.value = 'saving'
      localStorage.setItem(dataKey, JSON.stringify(formData))
      localStorage.setItem(messagesKey, JSON.stringify(messages.value))
      autoSaveStatus.value = 'saved'
    } catch {
      autoSaveStatus.value = 'idle'
    }
  }

  const loadFromLocalStorage = () => {
    try {
      const savedData = localStorage.getItem(dataKey)
      const savedMessages = localStorage.getItem(messagesKey)

      if (savedData) {
        const parsed = JSON.parse(savedData) as Partial<T>
        Object.assign(formData, parsed)
      }

      if (savedMessages) {
        const parsed = JSON.parse(savedMessages) as Array<
          Omit<ChatMessage, 'timestamp'> & { timestamp: string }
        >
        messages.value = parsed.map((message) => ({
          ...message,
          timestamp: new Date(message.timestamp),
        }))
      }

      return !!(savedData || savedMessages)
    } catch {
      return false
    }
  }

  const clearLocalStorage = () => {
    try {
      localStorage.removeItem(dataKey)
      localStorage.removeItem(messagesKey)
    } catch {
      // Ignore localStorage clearing failures.
    }
  }

  watch(
    () => ({ ...formData }),
    () => {
      saveToLocalStorage()
    },
    { deep: true }
  )

  watch(
    messages,
    () => {
      saveToLocalStorage()
    },
    { deep: true }
  )

  return {
    autoSaveStatus,
    saveToLocalStorage,
    loadFromLocalStorage,
    clearLocalStorage,
  }
}
