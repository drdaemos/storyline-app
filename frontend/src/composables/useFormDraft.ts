import { watch, type Ref } from 'vue'

/**
 * Persist a form ref to localStorage so the input survives navigation and reloads
 * (same draft pattern as the character/scenario creation screens).
 * Loads any existing draft immediately, then saves on every change.
 */
export function useFormDraft<T extends object>(storageKey: string, form: Ref<T>): { clearDraft: () => void } {
  try {
    const raw = localStorage.getItem(storageKey)
    if (raw) {
      form.value = { ...form.value, ...JSON.parse(raw) }
    }
  } catch (err) {
    console.error('Failed to load form draft:', err)
  }

  watch(
    form,
    (value) => {
      try {
        localStorage.setItem(storageKey, JSON.stringify(value))
      } catch (err) {
        console.error('Failed to save form draft:', err)
      }
    },
    { deep: true },
  )

  const clearDraft = () => {
    try {
      localStorage.removeItem(storageKey)
    } catch (err) {
      console.error('Failed to clear form draft:', err)
    }
  }

  return { clearDraft }
}
