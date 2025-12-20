import { ref } from 'vue'
import type { SelectItem } from '@nuxt/ui'
import type { CharacterSummary } from '@/types'

export function usePersonas() {
  const personaOptions = ref<SelectItem[]>([])
  const personas = ref<CharacterSummary[]>([])
  const personasLoading = ref(false)

  const fetchPersonas = async () => {
    personasLoading.value = true
    try {
      const response = await fetch('/api/personas')
      if (response.ok) {
        const personaList: CharacterSummary[] = await response.json()
        personas.value = personaList
        personaOptions.value = [
          { label: 'None', id: 'none' },
          ...personaList.map(p => ({ label: `${p.name} - ${p.tagline}`, id: p.id }))
        ]
      } else {
        console.error('Failed to fetch personas')
        personas.value = []
        personaOptions.value = [{ label: 'None', id: 'none' }]
      }
    } catch (error) {
      console.error('Error fetching personas:', error)
      personas.value = []
      personaOptions.value = [{ label: 'None', id: 'none' }]
    } finally {
      personasLoading.value = false
    }
  }

  return {
    personaOptions,
    personas,
    personasLoading,
    fetchPersonas
  }
}
