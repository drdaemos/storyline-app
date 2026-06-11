import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CharacterCreateView from './CharacterCreateView.vue'

const push = vi.fn()
const streamCharacterCreation = vi.fn()
const createCharacter = vi.fn()
const updateCharacter = vi.fn()
const getCharacterDetail = vi.fn()
const listRulesets = vi.fn()
const getRuleset = vi.fn()
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
    listRulesets,
    getRuleset,
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
  Select: {
    template: '<div><slot /></div>',
  },
  SelectContent: {
    template: '<div><slot /></div>',
  },
  SelectItem: {
    template: '<div><slot /></div>',
  },
  SelectTrigger: {
    template: '<div><slot /></div>',
  },
  SelectValue: {
    template: '<div><slot /></div>',
  },
  ModelSettingsDialog: {
    template: '<button data-testid="model-settings-trigger"></button>',
  },
}

describe('CharacterCreateView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeState.query = {}
    routeState.params = {}
    listRulesets.mockResolvedValue([{ id: 'rules-1', name: 'Noir', drive_count: 1, skill_count: 1, created_at: '' }])
    getRuleset.mockResolvedValue({
      id: 'rules-1',
      name: 'Noir',
      rules_text: 'Tension-driven',
      state_schemas: {
        drives: [{ name: 'resolve', range_min: 0, range_max: 10, default: 5, decay_rate: 0.5 }],
        skills: [{ name: 'persuasion', range_min: 0, range_max: 20 }],
        emotional_state: {
          global_dims: [{ name: 'composure', range_min: 0, range_max: 10, default: 5 }],
          per_relationship: [],
        },
      },
      config: {},
    })
    getCharacterDetail.mockResolvedValue({
      name: 'Existing Character',
      tagline: 'Existing tagline',
      backstory: 'Existing backstory',
      personality: '',
      appearance: '',
      ruleset_id: 'rules-1',
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

  it('shows model settings trigger in assistant panel', async () => {
    const wrapper = mount(CharacterCreateView, {
      global: {
        stubs: uiStubs,
      },
    })

    await flushPromises()
    expect(wrapper.find('[data-testid="model-settings-trigger"]').exists()).toBe(true)
  })

  it('saves character draft as persona from the same screen', async () => {
    createCharacter.mockResolvedValue({ message: 'ok', character_filename: 'persona_draft' })
    fetchPersonas.mockResolvedValue(undefined)

    const wrapper = mount(CharacterCreateView, {
      global: {
        stubs: uiStubs,
      },
    })

    await flushPromises()
    expect(wrapper.find('[data-testid="create-persona-cta"]').exists()).toBe(true)

    await wrapper.get('#character-name').setValue('Persona Draft')
    await wrapper.get('[data-testid="create-persona-cta"]').trigger('click')
    await flushPromises()

    expect(createCharacter).toHaveBeenCalledWith(
      expect.objectContaining({
        is_persona: true,
      })
    )
    expect(fetchPersonas).toHaveBeenCalledTimes(1)
    expect(push).toHaveBeenCalledWith('/library/personas')
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

    await flushPromises()
    await wrapper.get('#assistant-input').setValue('Build a noir investigator profile.')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(streamCharacterCreation).toHaveBeenCalledTimes(1)
    expect(streamCharacterCreation).toHaveBeenCalledWith(
      expect.objectContaining({
        ruleset_context: expect.objectContaining({
          id: 'rules-1',
        }),
      }),
      expect.any(Function),
      expect.any(Function),
      expect.any(Function),
      expect.any(Function)
    )
    expect(wrapper.text()).toContain('Drafted a profile with grounded noir tone.')
    expect((wrapper.get('#character-name').element as HTMLInputElement).value).toBe('Mara Kade')
  })

  it('normalizes assistant stat aliases into ruleset fields', async () => {
    streamCharacterCreation.mockImplementation(
      async (_payload, _onMessage, onUpdate, onComplete) => {
        onUpdate({
          skills: { Persuasion: 4 },
          drives: { Resolve: 8 },
          emotional_state: { Composure: 6 },
        })
        onComplete()
      }
    )

    const wrapper = mount(CharacterCreateView, {
      global: {
        stubs: uiStubs,
      },
    })

    await flushPromises()
    await wrapper.get('#assistant-input').setValue('Set a stat baseline.')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect((wrapper.get('#skill-persuasion').element as HTMLInputElement).value).toBe('4')
    expect((wrapper.get('#drive-resolve').element as HTMLInputElement).value).toBe('8')
    expect((wrapper.get('#emotion-composure').element as HTMLInputElement).value).toBe('6')
    expect(wrapper.text()).toContain('Structured update applied')
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

    await flushPromises()
    await wrapper.get('#character-name').setValue('Proxy Delta')
    await wrapper.get('[data-testid="save-entity-bottom"]').trigger('click')
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
    await wrapper.get('[data-testid="save-entity-bottom"]').trigger('click')
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
