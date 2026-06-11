import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ScenarioCreateView from './ScenarioCreateView.vue'

const push = vi.fn()
const streamScenarioCreation = vi.fn()
const saveScenario = vi.fn()
const startSession = vi.fn()

const listCharacters = vi.fn()
const listPersonas = vi.fn()
const listRulesets = vi.fn()
const listWorldLore = vi.fn()

vi.mock('vue-router', () => ({
  RouterLink: {
    template: '<a><slot /></a>',
  },
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push }),
}))

vi.mock('@/composables/useApi', () => ({
  useApi: () => ({
    streamScenarioCreation,
    saveScenario,
  }),
}))

vi.mock('@/composables/usePipelineApi', () => ({
  usePipelineApi: () => ({
    listCharacters,
    listPersonas,
    listRulesets,
    listWorldLore,
    startSession,
  }),
}))

vi.mock('@/composables/useLocalSettings', () => ({
  useLocalSettings: () => ({
    settings: ref({ aiProcessor: 'google-flash', backupProcessor: 'deepseek-v32' }),
  }),
}))

vi.mock('@/composables/useCharacterCreationAutoSave', () => ({
  useCharacterCreationAutoSave: () => ({
    autoSaveStatus: ref<'saved' | 'saving' | 'idle'>('idle'),
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

describe('ScenarioCreateView', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    listCharacters.mockResolvedValue([
      { id: 'char-1', name: 'Mara', tagline: 'Detective' },
      { id: 'char-2', name: 'Ren', tagline: 'Broker' },
    ])
    listPersonas.mockResolvedValue([{ id: 'persona-1', name: 'You', tagline: 'Observer' }])
    listRulesets.mockResolvedValue([
      { id: 'rules-1', name: 'Noir', drive_count: 0, skill_count: 0, created_at: '' },
    ])
    listWorldLore.mockResolvedValue([
      { id: 'lore-1', name: 'Dock District', tags: ['district'], content_preview: '...' },
    ])
  })

  it('shows model settings trigger in assistant panel', async () => {
    const wrapper = mount(ScenarioCreateView, {
      global: {
        stubs: uiStubs,
      },
    })

    await flushPromises()
    expect(wrapper.find('[data-testid="model-settings-trigger"]').exists()).toBe(true)
  })

  it('applies assistant stream updates to scenario form fields', async () => {
    streamScenarioCreation.mockImplementation(async (_payload, onMessage, onUpdate, onComplete) => {
      onMessage('Assistant reply')
      onUpdate({
        summary: 'Nightfall Ledger',
        intro_message: 'Rain needles the station canopy.',
      })
      onComplete()
    })

    saveScenario.mockResolvedValue({ scenario_id: 'sc-1' })
    startSession.mockResolvedValue({ session_id: 'sess-1' })

    const wrapper = mount(ScenarioCreateView, {
      global: {
        stubs: uiStubs,
      },
    })

    await flushPromises()

    await wrapper.get('#scenario-assistant-input').setValue('Draft a noir intro.')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(streamScenarioCreation).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Assistant reply')
    expect((wrapper.get('#scenario-summary').element as HTMLInputElement).value).toBe(
      'Nightfall Ledger'
    )
    expect(wrapper.text()).toContain('Structured update applied')
  })

  it('saves and starts session then navigates to play', async () => {
    streamScenarioCreation.mockResolvedValue(undefined)
    saveScenario.mockResolvedValue({ scenario_id: 'sc-9' })
    startSession.mockResolvedValue({ session_id: 'sess-9' })

    const wrapper = mount(ScenarioCreateView, {
      global: {
        stubs: uiStubs,
      },
    })

    await flushPromises()

    await wrapper.get('#scenario-summary').setValue('Midnight Audit')
    await wrapper.get('#scenario-intro').setValue('A file goes missing during curfew.')
    await wrapper.get('[data-testid="save-start"]').trigger('click')
    await flushPromises()

    expect(saveScenario).toHaveBeenCalledTimes(1)
    expect(saveScenario).toHaveBeenCalledWith(
      expect.objectContaining({
        scenario: expect.objectContaining({
          character_ids: ['char-1'],
          ruleset_id: 'rules-1',
        }),
      })
    )
    expect(startSession).toHaveBeenCalledWith(
      expect.objectContaining({
        scenario_id: 'sc-9',
      })
    )
    expect(push).toHaveBeenCalledWith('/play/sess-9')
  })

  it('supports multi-character selection in scenario payload', async () => {
    streamScenarioCreation.mockResolvedValue(undefined)
    saveScenario.mockResolvedValue({ scenario_id: 'sc-10' })
    startSession.mockResolvedValue({ session_id: 'sess-10' })

    const wrapper = mount(ScenarioCreateView, {
      global: {
        stubs: uiStubs,
      },
    })

    await flushPromises()

    await wrapper.get('[data-testid="character-option-char-2"]').trigger('click')
    await wrapper.get('#scenario-summary').setValue('Two-Handers In The Rain')
    await wrapper
      .get('#scenario-intro')
      .setValue('Two investigators cross paths under curfew sirens.')
    await wrapper.get('[data-testid="save-start"]').trigger('click')
    await flushPromises()

    expect(saveScenario).toHaveBeenCalledWith(
      expect.objectContaining({
        scenario: expect.objectContaining({
          character_ids: ['char-1', 'char-2'],
        }),
      })
    )
  })
})
