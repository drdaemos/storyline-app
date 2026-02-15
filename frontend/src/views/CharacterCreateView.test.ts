import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CharacterCreateView from './CharacterCreateView.vue'

const push = vi.fn()
const streamCharacterCreation = vi.fn()
const createCharacter = vi.fn()
const updateCharacter = vi.fn()
const getCharacterDetail = vi.fn()
const fetchPersonas = vi.fn()
const routeState: { query: Record<string, string>; params: Record<string, string> } = {
  query: {},
  params: {},
}

vi.mock('vue-router', () => ({
  RouterLink: {
    template: '<a><slot /></a>',
  },
  useRoute: () => routeState,
  useRouter: () => ({ push }),
}))

vi.mock('@/composables/useApi', () => ({
  useApi: () => ({
    streamCharacterCreation,
    createCharacter,
    updateCharacter,
  }),
}))

vi.mock('@/composables/usePipelineApi', () => ({
  usePipelineApi: () => ({
    getCharacterDetail,
  }),
}))

vi.mock('@/composables/useLocalSettings', () => ({
  useLocalSettings: () => ({
    settings: ref({ aiProcessor: 'google-flash', backupProcessor: 'deepseek-v32' }),
  }),
}))

vi.mock('@/composables/usePersonas', () => ({
  usePersonas: () => ({
    fetchPersonas,
  }),
}))

vi.mock('@/composables/useCharacterCreationAutoSave', () => ({
  useCharacterCreationAutoSave: () => ({
    autoSaveStatus: ref<'saved' | 'idle'>('idle'),
    loadFromLocalStorage: vi.fn(),
    clearLocalStorage: vi.fn(),
  }),
}))

const uiStubs = {
  RouterLink: {
    template: '<a><slot /></a>',
  },
  Badge: {
    template: '<span><slot /></span>',
  },
  Button: {
    emits: ['click'],
    template: '<button @click="$emit(\'click\', $event)"><slot /></button>',
  },
  Input: {
    inheritAttrs: false,
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<input v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  Textarea: {
    inheritAttrs: false,
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<textarea v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ScrollArea: {
    template: '<div><slot /></div>',
  },
}

describe('CharacterCreateView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeState.query = {}
    routeState.params = {}
    getCharacterDetail.mockResolvedValue({
      name: 'Existing Character',
      tagline: 'Existing tagline',
      backstory: 'Existing backstory',
      personality: '',
      appearance: '',
      interests: [],
      dislikes: [],
      desires: [],
      kinks: [],
      is_persona: false,
      starting_drives: {},
      starting_skills: {},
      starting_emotional_state: {},
    })
  })

  it('applies assistant stream updates to the character form', async () => {
    streamCharacterCreation.mockImplementation(
      async (_payload, onMessage, onUpdate, onComplete) => {
        onMessage('Drafted a profile with grounded noir tone.')
        onUpdate({
          name: 'Mara Kade',
          tagline: 'Ledger-bound investigator',
        })
        onComplete()
      }
    )

    createCharacter.mockResolvedValue({ message: 'ok', character_filename: 'mara_kade' })

    const wrapper = mount(CharacterCreateView, {
      global: {
        stubs: uiStubs,
      },
    })

    await wrapper.get('#assistant-input').setValue('Build a noir investigator profile.')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(streamCharacterCreation).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Drafted a profile with grounded noir tone.')
    expect((wrapper.get('#character-name').element as HTMLInputElement).value).toBe('Mara Kade')
  })

  it('creates personas with persona flag and redirects to persona filter', async () => {
    streamCharacterCreation.mockResolvedValue(undefined)
    createCharacter.mockResolvedValue({ message: 'ok', character_filename: 'persona_main' })
    fetchPersonas.mockResolvedValue(undefined)

    const wrapper = mount(CharacterCreateView, {
      props: {
        personaMode: true,
      },
      global: {
        stubs: uiStubs,
      },
    })

    await wrapper.get('#character-name').setValue('Proxy Delta')
    await wrapper.get('[data-testid="save-entity-top"]').trigger('click')
    await flushPromises()

    expect(createCharacter).toHaveBeenCalledWith(
      expect.objectContaining({
        is_persona: true,
      })
    )
    expect(fetchPersonas).toHaveBeenCalledTimes(1)
    expect(push).toHaveBeenCalledWith('/library/personas')
  })

  it('loads existing entity and saves through update endpoint in edit mode', async () => {
    routeState.params = { characterId: 'char-7' }
    updateCharacter.mockResolvedValue({ message: 'ok', character_filename: 'char-7' })

    const wrapper = mount(CharacterCreateView, {
      global: {
        stubs: uiStubs,
      },
    })

    await flushPromises()

    expect(getCharacterDetail).toHaveBeenCalledWith('char-7')
    expect((wrapper.get('#character-name').element as HTMLInputElement).value).toBe(
      'Existing Character'
    )

    await wrapper.get('#character-name').setValue('Updated Character')
    await wrapper.get('[data-testid="save-entity-top"]').trigger('click')
    await flushPromises()

    expect(updateCharacter).toHaveBeenCalledWith(
      'char-7',
      expect.objectContaining({
        is_yaml_text: false,
      })
    )
    expect(createCharacter).not.toHaveBeenCalled()
    expect(push).toHaveBeenCalledWith('/library/characters')
  })
})
