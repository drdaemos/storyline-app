import { ref, watch, type Ref } from 'vue'
import type { ChatMessage } from '@/types'

const STORAGE_KEY_CHARACTER = 'character-creation-draft'
const STORAGE_KEY_MESSAGES = 'character-creation-messages'

export function useCharacterCreationAutoSave(
  characterData: Record<string, unknown>,
  messages: Ref<ChatMessage[]>,
  storageKeyPrefix?: string
) {
  // Allow custom storage keys for different use cases (e.g., scenario creation)
  const dataKey = storageKeyPrefix ? `${storageKeyPrefix}-draft` : STORAGE_KEY_CHARACTER
  const messagesKey = storageKeyPrefix ? `${storageKeyPrefix}-messages` : STORAGE_KEY_MESSAGES

  const autoSaveStatus = ref<'saving' | 'saved' | 'idle'>('idle')

  const saveToLocalStorage = () => {
    try {
      autoSaveStatus.value = 'saving'
      localStorage.setItem(dataKey, JSON.stringify(characterData))
      localStorage.setItem(messagesKey, JSON.stringify(messages.value))
      autoSaveStatus.value = 'saved'
    } catch (err) {
      console.error('Failed to save to localStorage:', err)
    }
  }

  const loadFromLocalStorage = () => {
    try {
      const savedCharacter = localStorage.getItem(dataKey)
      const savedMessages = localStorage.getItem(messagesKey)

      if (savedCharacter) {
        const parsed = JSON.parse(savedCharacter)
        Object.assign(characterData, parsed)
      }

      if (savedMessages) {
        const parsed = JSON.parse(savedMessages) as Array<Omit<ChatMessage, 'timestamp'> & { timestamp: string }>
        messages.value = parsed.map((msg) => ({
          ...msg,
          timestamp: new Date(msg.timestamp)
        }))
      }

      return !!(savedCharacter || savedMessages)
    } catch (err) {
      console.error('Failed to load from localStorage:', err)
      return false
    }
  }

  const clearLocalStorage = () => {
    try {
      localStorage.removeItem(dataKey)
      localStorage.removeItem(messagesKey)
    } catch (err) {
      console.error('Failed to clear localStorage:', err)
    }
  }

  // Auto-save watchers - save on every change
  watch(() => ({ ...characterData }), () => {
    saveToLocalStorage()
  }, { deep: true })

  watch(messages, () => {
    saveToLocalStorage()
  }, { deep: true })

  return {
    autoSaveStatus,
    saveToLocalStorage,
    loadFromLocalStorage,
    clearLocalStorage
  }
}
