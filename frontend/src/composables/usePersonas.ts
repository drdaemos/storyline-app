import { ref, onMounted } from 'vue'
import type { SelectItem } from '@nuxt/ui'
import type { CharacterSummary } from '@/types'

export function usePersonas() {
  const personaOptions = ref<SelectItem[]>([])
  const personasLoading = ref(false)

  const fetchPersonas = async () => {
    personasLoading.value = true
    try {
      const response = await fetch('/api/personas')
      if (response.ok) {
        const personas: CharacterSummary[] = await response.json()
        personaOptions.value = [
          { label: 'None', id: 'none' },
          ...personas.map(p => ({ label: `${p.name} - ${p.tagline}`, id: p.id }))
        ]
      } else {
        console.error('Failed to fetch personas')
        personaOptions.value = [{ label: 'None', id: 'none' }]
      }
    } catch (error) {
      console.error('Error fetching personas:', error)
      personaOptions.value = [{ label: 'None', id: 'none' }]
    } finally {
      personasLoading.value = false
    }
  }

  return {
    personaOptions,
    personasLoading,
    fetchPersonas
  }
}
